#!/usr/bin/env python3
"""Create/retry a reviewed draft or publish the exact reviewed draft on GitHub."""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from release import Invalid, evidence_record, inspect_jar, load_plan, read_json, require
from authorize_release import api, authorize, check_deployment_approval


WRITE_GUARD = None


def mutate(path, method, data, content_type='application/json'):
    require(callable(WRITE_GUARD), 'write authorization guard is missing')
    WRITE_GUARD()
    token = os.environ.get('GH_TOKEN')
    require(bool(token), 'GH_TOKEN is required')
    payload = json.dumps(data).encode() if content_type == 'application/json' else data
    req = Request(path if path.startswith('https://') else 'https://api.github.com/' + path,
                  data=payload, method=method, headers={
                      'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                      'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'readable-maps-release',
                      'Content-Type': content_type})
    try:
        with urlopen(req, timeout=120) as response:
            return json.load(response)
    except HTTPError as exc:
        raise Invalid(f'GitHub write failed with HTTP {exc.code}') from exc


def verified_files(cfg, plan, directory, coordinator_sha):
    directory = Path(directory)
    manifest = read_json(directory / 'release-manifest.json')
    require(set(manifest) == {'schema', 'version', 'tag', 'coordinator_sha', 'candidate', 'release_date',
                              'changes', 'known_limitations', 'groups'} and manifest.get('schema') == 1,
            'release manifest schema or fields are invalid')
    require(manifest.get('version') == manifest.get('tag') == plan['version'] and manifest.get('candidate') is False and
            manifest.get('coordinator_sha') == coordinator_sha,
            'release manifest version or candidate flag is invalid')
    require(manifest.get('changes') == plan['changes'] and manifest.get('release_date') == plan['release_date'] and
            manifest.get('known_limitations') == plan['known_limitations'], 'release notes differ from plan')
    groups = manifest.get('groups', [])
    require(len(groups) == len(cfg['groups']) and {x.get('id') for x in groups} == set(cfg['groups']),
            'release manifest groups differ from plan')
    names = []
    sums = []
    for group in sorted(groups, key=lambda x: x['id']):
        require(set(group) == {'id', 'branch', 'source_commit', 'minecraft', 'compile_target', 'java',
                               'loader', 'namespace', 'artifact', 'sha256', 'runtime_evidence'},
                'release manifest group fields are invalid')
        name = group['id']
        spec = cfg['groups'][name]
        source = plan['groups'][name]
        require(group.get('branch') == spec['branch'] == source['source_branch'] and group.get('source_commit') == source['commit'] and
                group.get('minecraft') == spec['minecraft'] and group.get('java') == spec['java'] and
                group.get('compile_target') == spec['target'] and
                group.get('loader') == spec['loader'] and group.get('namespace') == spec['namespace'] and
                group.get('runtime_evidence') == {mc: evidence_record(source, name, mc) for mc in spec['minecraft']},
                f'{name}: source or runtime evidence differs from plan')
        filename = group.get('artifact', '')
        require(Path(filename).name == filename, 'unsafe artifact filename')
        digest = inspect_jar(directory / filename, plan['version'], name, spec)
        require(group.get('sha256') == digest and all(r['artifact_sha256'] == digest for r in group['runtime_evidence'].values()),
                f'{name}: artifact hash differs from manifest or runtime report')
        names.append(filename)
        sums.append(f'{digest}  {filename}')
    sums.append(f"{hashlib.sha256((directory / 'release-manifest.json').read_bytes()).hexdigest()}  release-manifest.json")
    require((directory / 'SHA256SUMS').read_text(encoding='utf-8') == '\n'.join(sums) + '\n', 'checksum file differs')
    names += ['release-manifest.json', 'SHA256SUMS']
    require({p.name for p in directory.iterdir() if p.is_file()} == set(names), 'unexpected release bundle files')
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in names}


def tag_target(repo, version):
    ref = api(f'repos/{repo}/git/ref/tags/{version}', allow_missing=True)
    if ref is None:
        return None
    obj = ref.get('object', {})
    require(obj.get('type') == 'tag', 'existing release tag is not annotated')
    tag = api(f"repos/{repo}/git/tags/{obj['sha']}")
    require(tag.get('tag') == version and tag.get('object', {}).get('type') == 'commit', 'invalid tag object')
    return tag['object']['sha']


def ensure_tag(repo, version, commit, allow_create):
    target = tag_target(repo, version)
    if target is None:
        require(allow_create, 'release tag does not exist')
        tag = mutate(f'repos/{repo}/git/tags', 'POST', {'tag': version, 'message': f'Release {version}',
                                                        'object': commit, 'type': 'commit'})
        try:
            mutate(f'repos/{repo}/git/refs', 'POST', {'ref': f'refs/tags/{version}', 'sha': tag['sha']})
        except Invalid:
            # A concurrent retry is safe only if it created the identical annotated tag.
            require(tag_target(repo, version) == commit, 'tag creation raced with a conflicting tag')
        target = tag_target(repo, version)
    require(target == commit, 'existing release tag points to another commit')


def check_assets(release, expected, complete):
    assets = release.get('assets', [])
    require(len({a['name'] for a in assets}) == len(assets), 'duplicate release assets')
    for asset in assets:
        name = asset['name']
        require(name in expected and asset.get('digest') == 'sha256:' + expected[name],
                f'conflicting, unexpected or unverifiable release asset: {name}')
    if complete:
        require({a['name'] for a in assets} == set(expected), 'draft release assets are incomplete')
    return {a['name'] for a in assets}


def release_body(cfg, plan):
    notes = '\n'.join(f'- {change}' for change in plan['changes'])
    downloads = '\n'.join(f"- Minecraft {', '.join(spec['minecraft'])}: Java {spec['java']}+, Fabric Loader {spec['loader']}+"
                          for _, spec in sorted(cfg['groups'].items()))
    limitations = '\n'.join(f'- {item}' for item in plan['known_limitations']) or '- None recorded.'
    return (f"Release date: {plan['release_date']}\n\n## Changes\n\n{notes}\n\n"
            f'## Downloads and requirements\n\n{downloads}\n\n## Known limitations\n\n{limitations}\n\n'
            'See release-manifest.json and SHA256SUMS for source and integrity details.')


def check_draft(release, version, body):
    require(release.get('draft') is True and release.get('tag_name') == version and
            release.get('name') == version and release.get('body') == body and
            release.get('prerelease') is False, 'draft metadata differs from reviewed plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare-draft', 'publish'])
    parser.add_argument('--plan', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--coordinator-sha', required=True)
    args = parser.parse_args()
    try:
        cfg, plan = load_plan(args.plan)
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        require(repo and repo.count('/') == 1, 'GITHUB_REPOSITORY is missing')
        files = verified_files(cfg, plan, args.bundle, args.coordinator_sha)
        environment = 'release-publication' if args.mode == 'publish' else 'release-draft'
        auditor = os.environ.get('RELEASE_AUDITOR_TOKEN')
        require(bool(auditor), 'RELEASE_AUDITOR_TOKEN is required for every write')
        def guard():
            write_token = os.environ.get('GH_TOKEN')
            try:
                os.environ['GH_TOKEN'] = auditor
                authorize(repo, cfg, plan, args.coordinator_sha, environment)
                check_deployment_approval(repo, environment, args.coordinator_sha)
            finally:
                if write_token is None:
                    os.environ.pop('GH_TOKEN', None)
                else:
                    os.environ['GH_TOKEN'] = write_token
        global WRITE_GUARD
        WRITE_GUARD = guard
        version = plan['version']
        body = release_body(cfg, plan)
        path = f'repos/{repo}/releases/tags/{version}'
        release = api(path, allow_missing=True)
        if release is not None:
            require(release.get('draft') is True and release.get('tag_name') == version,
                    'an existing public or mismatched release cannot be modified')
            require(tag_target(repo, version) is not None,
                    'an existing draft has no tag; repair it manually before retrying')
        ensure_tag(repo, version, args.coordinator_sha, args.mode == 'prepare-draft' and release is None)
        if release is None:
            require(args.mode == 'prepare-draft', 'draft release does not exist')
            release = mutate(f'repos/{repo}/releases', 'POST', {'tag_name': version, 'name': version,
                                                                 'body': body, 'draft': True, 'prerelease': False})
        check_draft(release, version, body)
        existing = check_assets(release, files, args.mode == 'publish')
        if args.mode == 'prepare-draft':
            for filename in sorted(set(files) - existing):
                upload = f"https://uploads.github.com/repos/{repo}/releases/{release['id']}/assets?name={quote(filename, safe='')}"
                mutate(upload, 'POST', (Path(args.bundle) / filename).read_bytes(), 'application/octet-stream')
            # GitHub computes asset digests asynchronously on some installations.
            for attempt in range(5):
                release = api(path)
                try:
                    check_assets(release, files, True)
                    break
                except Invalid:
                    if attempt == 4:
                        raise
                    time.sleep(2)
            print(f'Prepared draft release {version}; human review is still required.')
        else:
            # Re-read the draft and tag just before publishing; the write guard then
            # repeats authorization immediately before the PATCH.
            release = api(path)
            check_draft(release, version, body)
            check_assets(release, files, True)
            require(tag_target(repo, version) == args.coordinator_sha, 'release tag changed')
            mutate(f"repos/{repo}/releases/{release['id']}", 'PATCH', {'draft': False})
            print(f'Published previously reviewed release {version}.')
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'GitHub release failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
