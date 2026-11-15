#!/usr/bin/env python3
"""Validate selected candidate evidence without turning it into release approval.

Historical records retain their own source identities. This validator checks
that the mutable selection describes the selected current sources and reports
missing evidence as pending. Strict production authorization is separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import release

ROOT = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_id(value, pattern, message):
    require(isinstance(value, str) and pattern.fullmatch(value), message)


def validate(heads, versions, selection, load, read_blob=None):
    """Return outstanding requirements; reject contradictory current claims."""
    require(selection.get('schema') == 1 and selection.get('scope') == 'candidate', 'invalid evidence scope')
    require(selection.get('authorizes_release') is False, 'candidate evidence cannot authorize release')
    rows = selection.get('groups')
    require(isinstance(rows, dict) and set(rows) == set(heads) == set(versions), 'current group mismatch')
    pending = []
    for group, row in sorted(rows.items()):
        source = row.get('source_commit')
        checked_id(source, COMMIT, group + ': invalid source commit')
        require(source == heads[group]['new_head'], group + ': obsolete current source')
        build = row['build']; state = build['state']
        require(state in ('pending', 'observed'), group + ': invalid build state')
        if state == 'pending':
            pending.append(group + ': build')
            require(row['static']['state'] == 'pending' and row['runtime']['state'] == 'pending',
                    group + ': evidence claims require an observed artifact')
        else:
            recorded = load(build['record'])[group]
            logs = load(selection['validation_logs'])
            digest = build['artifact_sha256']
            checked_id(digest, DIGEST, group + ': invalid artifact hash')
            require(recorded['source_commit'] == source and recorded['sha256'] == digest,
                    group + ': build record does not match source and artifact')
            metadata = load(build['metadata_record'])[group]
            require(metadata['source_commit'] == source and metadata['artifact_sha256'] == digest and
                    metadata['mod_id'] == 'thirdpersonreadablemaps' and
                    metadata['mod_version'] == selection['mod_version'] and
                    metadata['minecraft'] == versions[group] and
                    metadata['namespace'] == heads[group]['namespace'] and
                    metadata['artifact'] == recorded['artifact'] and metadata['bytecode_majors'] and
                    max(metadata['bytecode_majors']) <= metadata['java'] + 44,
                    group + ': packaged metadata does not match current claim')
            require(hashlib.sha256(logs['builds'][group].encode()).hexdigest() == recorded['log_sha256'],
                    group + ': build log hash mismatch')
            continuity = build['continuity']
            require(continuity in ('same', 'different', 'not-compared'), group + ': invalid continuity state')
            if continuity != 'not-compared':
                previous = build['previous_sha256']; checked_id(previous, DIGEST, group + ': invalid previous hash')
                prior = load(build['previous_record'])[group]
                require(prior['sha256'] == previous and prior['source_commit'] == build['previous_source'],
                        group + ': continuity reference does not match historical build')
                require((digest == previous) == (continuity == 'same'), group + ': incorrect continuity claim')
            static = row['static']
            require(static['state'] in ('pending', 'observed'), group + ': invalid static state')
            if static['state'] == 'pending':
                pending.append(group + ': static verification')
            else:
                entries = [x for x in load(static['record'])['results'] if x['group'] == group]
                require(len(entries) == len(versions[group]) and
                        {x['version'] for x in entries} == set(versions[group]), group + ': incomplete static coverage')
                require(all(x['source_commit'] == source and x['artifact_sha256'] == digest and x['exit_code'] == 0
                            for x in entries), group + ': static record does not match current artifact and verifier')
                require(all(hashlib.sha256(logs['static'][x['version']].encode()).hexdigest() == x['log_sha256']
                            for x in entries), group + ': static log hash mismatch')
            runtime = row['runtime']
            require(runtime['state'] in ('pending', 'historical-same-artifact', 'fresh'), group + ': invalid runtime state')
            if runtime['state'] == 'pending':
                pending.append(group + ': runtime observations')
            else:
                observations = load(runtime['record'])['versions']
                for version in versions[group]:
                    obs = observations.get(version, {})
                    require(obs.get('group') == group and obs.get('artifact_sha256') == digest,
                            group + ': runtime observation does not match artifact for ' + version)
                    checked_id(obs.get('source_commit'), COMMIT, group + ': invalid runtime source')
                    if runtime['state'] == 'fresh':
                        require(obs['source_commit'] == source and obs.get('execution_kind') == 'fresh',
                                group + ': historical observation cannot be relabeled fresh')
        security = row['security']
        require(security['state'] in ('pending', 'retained', 'fresh-resolution'), group + ': invalid security state')
        if security['state'] == 'pending':
            pending.append(group + ': security inventory')
        else:
            scanned = security['source_commit']; checked_id(scanned, COMMIT, group + ': invalid scanned source')
            report = load(security['report'])
            require(report['source_sha'] == scanned, group + ': security report source mismatch')
            require(security.get('risk_accepted') is False, group + ': risk acceptance requires separate owner approval')
            if security['state'] == 'fresh-resolution':
                require(scanned == source and security.get('resolution_kind') == 'fresh-gradle-resolution',
                        group + ': OSV re-query is not a fresh dependency resolution')
                snapshot = load(security['snapshot'])
                require(snapshot['sha'] == source, group + ': dependency snapshot source mismatch')
                resolution = load(security['resolution_record'])
                require(resolution.get('source_commit') == source and
                        resolution.get('kind') == 'fresh-gradle-resolution', group + ': missing resolution evidence')
                checked_id(resolution.get('log_sha256'), DIGEST, group + ': invalid resolution log hash')
                checked_id(resolution.get('snapshot_sha256'), DIGEST, group + ': invalid snapshot hash')
                require(read_blob is not None and
                        hashlib.sha256(read_blob(resolution['log'])).hexdigest() == resolution['log_sha256'] and
                        hashlib.sha256(read_blob(security['snapshot'])).hexdigest() == resolution['snapshot_sha256'],
                        group + ': dependency resolution evidence hash mismatch')
            else:
                require(security.get('resolution_kind') != 'fresh-gradle-resolution',
                        group + ': retained inventory cannot be relabeled fresh')
                pending.append(group + ': current-source security resolution')
    controls = selection.get('negative_controls', {'state': 'pending'})
    require(controls['state'] in ('observed', 'pending'), 'invalid negative-control state')
    if controls['state'] == 'pending':
        pending.append('adjacent-version negative controls')
    else:
        records = load(controls['record']); logs = load(selection['validation_logs'])['negative']
        require(bool(records), 'no negative controls recorded')
        for name, result in records.items():
            group = result['group']; checked_id(result.get('artifact_sha256'), DIGEST, 'invalid control artifact hash')
            require(group in rows and rows[group]['build']['state'] == 'observed' and
                    result['source_commit'] == rows[group]['source_commit'] and
                    result['artifact_sha256'] == rows[group]['build']['artifact_sha256'] and
                    result['exit_code'] != 0 and result['discriminating_rejection'],
                    'negative control does not match current source and artifact: ' + name)
            require(hashlib.sha256(logs[name].encode()).hexdigest() == result['log_sha256'],
                    'negative control log hash mismatch: ' + name)
    fixtures = selection.get('entrypoint_fixtures', {'state': 'pending'})
    require(fixtures['state'] in ('observed', 'pending'), 'invalid entrypoint fixture state')
    if fixtures['state'] == 'pending':
        pending.append('packaged verifier entrypoint fixtures')
    else:
        require(read_blob is not None, 'entrypoint fixtures require file-integrity checks')
        entries = load(fixtures['record'])['entrypoints']
        require(set(entries) == {'intermediary', 'official'}, 'both namespace fixtures are required')
        for namespace, entry in entries.items():
            group = entry['group']
            require(group in heads and heads[group]['namespace'] == namespace and
                    heads[group]['new_head'] == entry['source_commit'], namespace + ': stale fixture source')
            path = str(Path(fixtures['record']).parent/entry['log'])
            log = read_blob(path)
            require(hashlib.sha256(log).hexdigest() == entry['log_sha256'] and b'\nOK\n' in log,
                    namespace + ': fixture result or log hash mismatch')
    hosted = selection.get('hosted_checks', {'state': 'pending'})
    require(hosted['state'] in ('observed', 'pending'), 'invalid hosted check state')
    if hosted['state'] == 'pending':
        pending.append('hosted proposal CI')
    else:
        results = load(hosted['record'])['groups']
        require(set(results) == set(rows), 'hosted check group mismatch')
        for group, result in results.items():
            for key in ('base_sha', 'merge_sha', 'head_tree', 'merge_tree'):
                checked_id(result.get(key), COMMIT, group + ': invalid hosted ' + key)
            require(result['head_sha'] == rows[group]['source_commit'] and
                    result['head_tree'] == result['merge_tree'] and
                    set(result['checks']) == {'ubuntu-latest', 'windows-latest'},
                    group + ': hosted check source or tree mismatch')
            for check in result['checks'].values():
                checked_id(check['archive_sha256'], DIGEST, group + ': invalid archive hash')
                require(rows[group]['build']['state'] == 'observed' and check['conclusion'] == 'SUCCESS' and
                        check['checkout_merge_sha'] == result['merge_sha'] and
                        isinstance(check['run_attempt'], int) and check['run_attempt'] > 0 and
                        check['artifact_sha256'] == rows[group]['build']['artifact_sha256'] and
                        check['archive_and_jar_verified'], group + ': hosted artifact or checkout mismatch')
    rehearsal = selection.get('candidate_rehearsal', {'state': 'pending'})
    require(rehearsal['state'] in ('observed', 'pending'), 'invalid candidate rehearsal state')
    if rehearsal['state'] == 'pending':
        pending.append('candidate rehearsal')
    else:
        require(read_blob is not None, 'candidate rehearsal requires file-integrity checks')
        index, manifest, plan = (load(rehearsal[name]) for name in ('index', 'manifest', 'plan'))
        require(index['candidate'] and index['authorizes_release'] is False and manifest['candidate'] and
                manifest['version'] == selection['mod_version'] and
                plan['version'] == selection['mod_version'] and
                manifest['coordinator_sha'] == index['coordinator_code_commit'],
                'candidate rehearsal cannot establish production authorization')
        items = {item['id']: item for item in manifest['groups']}
        require(len(items) == len(manifest['groups']) and set(items) == set(rows) == set(plan['groups']),
                'candidate rehearsal group mismatch')
        config_path = index['candidate_compatibility_record']
        require(hashlib.sha256(read_blob(config_path)).hexdigest() == index['candidate_compatibility_sha256'],
                'candidate rehearsal compatibility configuration changed')
        config = load(config_path)
        require(set(config['groups']) == set(rows), 'candidate rehearsal compatibility group mismatch')
        matrix = (json.dumps(release.matrix(config, plan), indent=2) + '\n').encode()
        require(hashlib.sha256(matrix).hexdigest() == index['candidate_matrix_sha256'],
                'candidate rehearsal matrix mismatch')
        checksum_lines = read_blob(rehearsal['checksums']).decode().splitlines()
        checksums = {}
        for line in checksum_lines:
            parts = line.split('  ', 1)
            require(len(parts) == 2 and parts[1] not in checksums, 'invalid or duplicate rehearsal checksum')
            checked_id(parts[0], DIGEST, 'invalid rehearsal checksum digest')
            checksums[parts[1]] = parts[0]
        require(set(checksums) == {item['artifact'] for item in items.values()} | {'release-manifest.json'} and
                checksums['release-manifest.json'] == hashlib.sha256(read_blob(rehearsal['manifest'])).hexdigest(),
                'candidate rehearsal checksum inventory mismatch')
        for group, item in items.items():
            build = rows[group]['build']
            require(build['state'] == 'observed', group + ': candidate rehearsal lacks a current build')
            metadata = load(build['metadata_record'])[group]
            require(item['source_commit'] == rows[group]['source_commit'] and
                    plan['groups'][group]['commit'] == rows[group]['source_commit'] and
                    item['branch'] == heads[group]['branch'] and
                    plan['groups'][group]['source_branch'] == heads[group]['branch'] and
                    item['sha256'] == build['artifact_sha256'] and item['minecraft'] == versions[group] and
                    item['namespace'] == heads[group]['namespace'] and
                    item['artifact'] == metadata['artifact'] and item['java'] == metadata['java'] and
                    config['groups'][group]['minecraft'] == versions[group] and
                    config['groups'][group]['namespace'] == item['namespace'] and
                    config['groups'][group]['java'] == item['java'] and
                    checksums[item['artifact']] == item['sha256'],
                    group + ': candidate rehearsal source or artifact mismatch')
        for path, digest in index['coordinator_code_sha256'].items():
            require(hashlib.sha256(read_blob(path)).hexdigest() == digest,
                    'candidate rehearsal coordinator code changed: ' + path)
        base = read_blob(index['runner_base'])
        require(hashlib.sha256(base).hexdigest() == index['runner_base_sha256'], 'rehearsal runner base changed')
        runner = base
        substitutions = index['runner_substitutions']
        require(isinstance(substitutions, dict) and bool(substitutions), 'missing rehearsal runner substitutions')
        for old, new in substitutions.items():
            require(isinstance(old, str) and isinstance(new, str) and old and new and old.encode() in runner,
                    'invalid rehearsal runner substitution')
            runner = runner.replace(old.encode(), new.encode())
        require(hashlib.sha256(runner).hexdigest() == index['runner_sha256'], 'rehearsal runner mismatch')
        log_path = str(Path(rehearsal['index']).parent/'rehearsal.log')
        require(hashlib.sha256(read_blob(log_path)).hexdigest() == index['log_sha256'], 'rehearsal log hash mismatch')
        controls = load(rehearsal['controls'])
        harness = set(index['harness_controls'])
        require(harness == {'missing-static-evidence', 'failed-static-evidence', 'missing-wrapper-preflight-evidence'}
                and harness <= set(controls) and len(set(controls)-harness) == index['other_controls'],
                'rehearsal controls do not distinguish harness checks')
    return pending


def read(path):
    return json.loads(read_blob(path))


def read_blob(path):
    file = (ROOT/path).resolve()
    require(file.is_relative_to(ROOT), 'evidence path is outside the repository')
    return file.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    try:
        heads = read('docs/version-consistency-1.0.0/current-heads.json')['groups']
        candidates = read('docs/legacy-candidate-evidence.json')['groups']
        maintenance = read('release/maintenance-targets.json')['groups']
        versions = {k: v['versions'] for k, v in candidates.items()}
        for group, row in maintenance.items():
            if group in versions:
                require(versions[group] == row['minecraft'], group + ': conflicting current version coverage')
            versions[group] = row['minecraft']
        selection = read('docs/version-consistency-1.0.0/current-evidence.json')
        require(selection['mod_version'] == read('release/current-version.json')['version'],
                'current evidence version differs from coordinated version')
        pending = validate(heads, versions, selection, read, read_blob)
        print('Current candidate evidence: ' + ('PENDING: ' + '; '.join(pending) if pending else 'consistent'))
        return 1 if args.require_complete and pending else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Current evidence is inconsistent: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
