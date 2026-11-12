#!/usr/bin/env python3
"""Validate active dependency-update targets independently of release admission.

An entry names an already integrated commit. The remote check verifies that the
commit is an ancestor of the current maintenance branch and that the current
source metadata still describes the intended game versions. Candidate evidence
and placeholder branch names are deliberately not sufficient for activation.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GROUP = re.compile(r'[0-9]+(?:\.[0-9]+)*(?:-[0-9]+(?:\.[0-9]+)*)?')
SHA = re.compile(r'[0-9a-f]{40}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def registry_entries(registry):
    require(isinstance(registry, dict) and registry.get('schema') == 1 and
            isinstance(registry.get('groups'), dict) and registry['groups'], 'invalid maintenance target registry')
    branches, versions = set(), set()
    for group, spec in registry['groups'].items():
        require(isinstance(group, str) and GROUP.fullmatch(group) and isinstance(spec, dict), 'invalid maintenance group')
        require(set(spec) == {'branch', 'target', 'minecraft', 'integrated_commit'}, group + ': invalid fields')
        require(spec['branch'] == 'mc/' + group and spec['branch'] not in branches, group + ': invalid or duplicate branch')
        require(isinstance(spec['minecraft'], list) and spec['minecraft'] and
                all(isinstance(v, str) and re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', v) for v in spec['minecraft']) and
                len(set(spec['minecraft'])) == len(spec['minecraft']) and spec['target'] in spec['minecraft'],
                group + ': invalid game versions')
        require(not versions.intersection(spec['minecraft']), group + ': overlapping game versions')
        require(isinstance(spec['integrated_commit'], str) and SHA.fullmatch(spec['integrated_commit']),
                group + ': invalid integrated commit')
        branches.add(spec['branch']); versions.update(spec['minecraft'])
    return {('github-actions', 'main')} | {(eco, branch) for branch in branches for eco in ('gradle', 'github-actions')}


def dependabot_entries(text):
    blocks = re.split(r'(?m)^  - package-ecosystem: ', text)[1:]
    require(blocks, 'no Dependabot entries')
    entries = []
    for block in blocks:
        ecosystem = block.splitlines()[0].strip()
        branch = re.findall(r'(?m)^    target-branch: (.+)$', block)
        require(ecosystem in ('gradle', 'github-actions') and len(branch) <= 1 and
                re.search(r'(?m)^    directory: /$', block) and
                re.search(r'(?m)^      interval: weekly$', block), 'invalid Dependabot entry')
        entries.append((ecosystem, branch[0] if branch else 'main'))
    require(len(entries) == len(set(entries)), 'duplicate Dependabot entry')
    return set(entries)


def validate_configuration(registry, dependabot):
    expected = registry_entries(registry)
    actual = dependabot_entries(dependabot)
    require(actual == expected, 'Dependabot targets differ from integrated maintenance registry: '
            f'missing={sorted(expected-actual)}, unexpected={sorted(actual-expected)}')


def validate_source(group, spec, properties, metadata, integrated_is_ancestor):
    require(integrated_is_ancestor, group + ': recorded integrated commit is not an ancestor of branch HEAD')
    require(properties.get('minecraft_version') == spec['target'], group + ': wrong compilation target')
    require(metadata.get('id') == 'thirdpersonreadablemaps' and isinstance(metadata.get('depends'), dict),
            group + ': invalid Fabric metadata')
    declared = metadata['depends'].get('minecraft')
    if declared == '${minecraft_version}':
        declared = properties['minecraft_version']
    if isinstance(declared, str):
        declared = [declared]
    require(declared == spec['minecraft'], group + ': source declares different Minecraft versions')
    if 'minecraft_group' in properties:
        require(properties['minecraft_group'] == group, group + ': wrong artifact group')


def git(*args, check=True):
    return subprocess.run(['git', '-C', str(ROOT), *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def validate_release_verifier_files(group, files):
    required = {'scripts/verify_supported_apis.py', 'scripts/jvm_linkage.py', 'scripts/game_linkage.py'}
    require(required.issubset(files), group + ': integrated source lacks the required release API verifier')


def validate_release_source_head(group, spec, observed):
    require(observed == spec['integrated_commit'],
            group + ': current maintenance head differs from the reviewed registry pin')


def validate_coordinated_version(group, properties, metadata, current):
    require(isinstance(current, dict) and set(current) == {'schema', 'version'} and current['schema'] == 1 and
            isinstance(current['version'], str) and re.fullmatch(r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)', current['version']),
            'invalid coordinated version')
    require(properties.get('mod_version') == current['version'] and
            metadata.get('version') in ('${version}', current['version']),
            group + ': integrated mod version differs from the coordinated version')


def check_remote(registry, require_release_verifiers=False):
    current = json.loads((ROOT / 'release/current-version.json').read_text()) if require_release_verifiers else None
    for group, spec in registry['groups'].items():
        ref = 'refs/tprm-maintenance-check/' + group
        git('fetch', '--no-tags', 'origin', '+' + 'refs/heads/' + spec['branch'] + ':' + ref)
        ancestor = git('merge-base', '--is-ancestor', spec['integrated_commit'], ref, check=False).returncode == 0
        props_text = git('show', ref + ':gradle.properties').stdout
        properties = {}
        for line in props_text.splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                require(key not in properties, group + ': duplicate Gradle property')
                properties[key.strip()] = value.strip()
        metadata = json.loads(git('show', ref + ':src/main/resources/fabric.mod.json').stdout)
        validate_source(group, spec, properties, metadata, ancestor)
        if require_release_verifiers:
            validate_release_source_head(group, spec, git('rev-parse', ref).stdout.strip())
            files = set(git('ls-tree', '-r', '--name-only', ref, '--', 'scripts').stdout.splitlines())
            validate_release_verifier_files(group, files)
            validate_coordinated_version(group, properties, metadata, current)
        print(group + ': integrated source is an ancestor and current metadata matches')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-remote', action='store_true')
    parser.add_argument('--require-release-verifiers', action='store_true')
    args = parser.parse_args()
    try:
        registry = json.loads((ROOT / 'release/maintenance-targets.json').read_text())
        validate_configuration(registry, (ROOT / '.github/dependabot.yml').read_text())
        require(not args.require_release_verifiers or args.verify_remote,
                '--require-release-verifiers requires --verify-remote')
        if args.verify_remote:
            check_remote(registry, args.require_release_verifiers)
        print('Active Dependabot targets match the integrated maintenance registry')
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print('Maintenance target validation failed: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
