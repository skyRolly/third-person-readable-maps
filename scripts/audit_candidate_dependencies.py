#!/usr/bin/env python3
"""Fail-closed OSV audit for source-pinned, unreviewed legacy candidates.

This is a separate monitoring path: it never changes the reviewed ledger or
provides release authorization. Every advisory match is unreviewed and failing.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

import audit_dependencies as audit
from release import Invalid, read_json, require
import scan_dependency_snapshot as scanner

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/legacy-candidate-evidence.json'
BASELINE = ROOT / 'docs/candidate-advisory-baseline.json'
GROUP = re.compile(r'[0-9]+(?:\.[0-9]+)*(?:-[0-9]+(?:\.[0-9]+)*)?')
SHA = re.compile(r'[a-f0-9]{40}')
VERSION = re.compile(r'1\.[0-9]+(?:\.[0-9]+)?')
PR = re.compile(r'https://github\.com/skyRolly/third-person-readable-maps/pull/([1-9][0-9]*)')


def candidate_matrix(evidence):
    require(isinstance(evidence, dict) and evidence.get('schema') == 1 and
            isinstance(evidence.get('groups'), dict) and evidence['groups'], 'invalid candidate evidence')
    rows, covered = [], set()
    for group, entry in sorted(evidence['groups'].items()):
        require(isinstance(group, str) and GROUP.fullmatch(group) and isinstance(entry, dict), 'invalid candidate group')
        sha, versions, url = entry.get('candidate_head'), entry.get('versions'), entry.get('pull_request')
        require(isinstance(sha, str) and SHA.fullmatch(sha), group + ': invalid candidate head')
        require(isinstance(url, str) and PR.fullmatch(url), group + ': invalid candidate PR')
        require(isinstance(versions, list) and versions and len(versions) == len(set(versions)) and
                all(isinstance(v, str) and VERSION.fullmatch(v) for v in versions), group + ': invalid versions')
        require(not covered.intersection(versions), group + ': overlapping candidate versions')
        covered.update(versions)
        rows.append({'group': group, 'branch': 'candidate/mc-' + group, 'sha': sha})
    return {'include': rows}


def load_baseline(manifest, evidence, root=ROOT, today=None):
    """Validate the retained, explicitly unreviewed comparison baseline."""
    candidate_matrix(evidence)
    today = today or date.today()
    require(isinstance(manifest, dict) and manifest.get('schema') == 1 and
            manifest.get('risk_acceptance') is False and isinstance(manifest.get('reports'), list) and
            manifest['reports'], 'invalid candidate advisory baseline')
    captured = date.fromisoformat(manifest['captured_on'])
    require(0 <= (today - captured).days <= 90, 'stale candidate advisory baseline')
    groups, paths = {}, set()
    for spec in manifest['reports']:
        require(isinstance(spec, dict), 'invalid candidate baseline report')
        path, digest = spec.get('path'), spec.get('sha256')
        require(isinstance(path, str) and re.fullmatch(r'docs/dependency-evidence/legacy-candidate[a-z0-9-]*\.json', path)
                and path not in paths and isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest),
                'invalid candidate baseline report reference')
        paths.add(path)
        raw = (root / path).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'candidate baseline report hash mismatch')
        report = json.loads(raw)
        require(isinstance(report, dict) and report.get('schema') == 1 and
                report.get('status') == 'complete-unreviewed-candidate-scan' and
                report.get('risk_acceptance') is False and report.get('scanned_on_client_date') == captured.isoformat()
                and isinstance(report.get('groups'), dict) and report['groups'] and
                isinstance(report.get('findings'), dict) and isinstance(report.get('advisories'), dict),
                'invalid retained candidate scan')
        for name, old in report['groups'].items():
            require(name in evidence['groups'] and name not in groups and isinstance(old, dict),
                    'unknown or duplicated candidate baseline group')
            entry = evidence['groups'][name]
            pr = PR.fullmatch(entry['pull_request']).group(1)
            require(isinstance(old.get('source_sha'), str) and SHA.fullmatch(old['source_sha']) and
                    old.get('ref') == 'refs/pull/' + pr + '/merge', 'invalid candidate baseline provenance')
            scopes = {'gradle'} | {'runtime/' + version for version in entry['versions']}
            inventories = old.get('inventories')
            require(isinstance(inventories, dict) and set(inventories) == scopes and
                    isinstance(old.get('runtime_manifests'), dict) and
                    set(old['runtime_manifests']) == set(entry['versions']), 'incomplete candidate baseline scopes')
            for packages in inventories.values():
                require(isinstance(packages, list) and packages and len(packages) == len(set(packages)) and
                        all(isinstance(p, str) and audit.canonical(p) == p for p in packages),
                        'invalid candidate baseline inventory')
            for version, source in old['runtime_manifests'].items():
                require(isinstance(source, dict) and isinstance(source.get('sha1'), str) and
                        SHA.fullmatch(source['sha1']), version + ': invalid baseline runtime manifest')
            queried = set().union(*map(set, inventories.values()))
            expected = set()
            for purl, ids in report['findings'].items():
                require(isinstance(purl, str) and audit.canonical(purl) == purl and isinstance(ids, list) and ids and
                        len(ids) == len(set(ids)) and all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9._-]+', i)
                                                         for i in ids), 'invalid candidate baseline findings')
                if purl in queried:
                    expected.update((purl, identifier) for identifier in ids)
            records = {}
            require(isinstance(old.get('matches'), list), 'invalid candidate baseline matches')
            for record in old['matches']:
                require(isinstance(record, dict), 'invalid candidate baseline record')
                purl, identifier = record.get('purl'), record.get('advisory')
                require((purl, identifier) in expected, 'candidate baseline contains an unqueried match')
                key = audit.identity(name, purl, identifier)
                advisory = report['advisories'].get(identifier)
                require(record.get('key') == key and key not in records and isinstance(advisory, dict) and
                        advisory.get('id') == identifier and record.get('fingerprint') == audit.advisory_fingerprint(advisory)
                        and record.get('scopes') == sorted(scope for scope, packages in inventories.items() if purl in packages)
                        and record.get('review_status') == 'awaiting investigation' and
                        record.get('disposition') == 'Further investigation' and record.get('failing') is True,
                        'invalid or accepted candidate baseline record')
                records[key] = record
            require({(r['purl'], r['advisory']) for r in records.values()} == expected,
                    'candidate baseline omits an advisory match')
            groups[name] = {'source_sha': old['source_sha'], 'inventories': inventories, 'records': records}
    require(set(groups) == set(evidence['groups']), 'candidate baseline groups differ from candidate evidence')
    return groups


def audit_candidate(snapshot, metadata, evidence, group, branch, source_sha, observed_sha, baseline):
    matrix = candidate_matrix(evidence)
    rows = [r for r in matrix['include'] if r['group'] == group]
    require(len(rows) == 1, 'unknown candidate group')
    row, entry = rows[0], evidence['groups'][group]
    require(branch == row['branch'] and source_sha == row['sha'] and observed_sha == source_sha,
            'candidate branch or checked-out commit does not match evidence')
    pr_number = PR.fullmatch(entry['pull_request']).group(1)
    allowed_refs = {'refs/heads/' + branch, 'refs/pull/' + pr_number + '/merge'}
    require(isinstance(snapshot, dict) and snapshot.get('sha') == source_sha and
            snapshot.get('ref') in allowed_refs, 'snapshot does not identify the candidate source and ref')
    require(isinstance(metadata, dict) and metadata.get('id') == 'thirdpersonreadablemaps' and
            isinstance(metadata.get('depends'), dict), 'missing or invalid Fabric metadata')
    declared = metadata['depends'].get('minecraft')
    if isinstance(declared, str):
        declared = [declared]
    require(declared == entry['versions'], 'candidate Fabric version list differs from audited versions')
    purls, skipped = scanner.packages(snapshot)
    require(not skipped, 'unscanned snapshot entries: ' + ', '.join(skipped))
    inventories, manifests = audit.runtime_inventories(entry['versions'])
    inventories['gradle'] = sorted({audit.canonical(p) for p in purls})
    require(isinstance(baseline, dict) and group in baseline and
            set(inventories) == set(baseline[group]['inventories']), 'missing candidate baseline scopes')
    for scope, packages in inventories.items():
        missing = {audit.package_name(p) for p in baseline[group]['inventories'][scope]} - \
                  {audit.package_name(p) for p in packages}
        require(not missing, scope + ': incomplete candidate inventory; review removals: ' + ', '.join(sorted(missing)))
    all_packages = sorted(set().union(*map(set, inventories.values())))
    findings = scanner.query(all_packages)
    require(isinstance(findings, dict) and set(findings) <= set(all_packages), 'invalid or unqueried OSV package')
    ids = set()
    for identifiers in findings.values():
        require(isinstance(identifiers, list) and identifiers and len(identifiers) == len(set(identifiers)) and
                all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9._-]+', i) for i in identifiers),
                'invalid OSV advisory identifiers')
        ids.update(identifiers)
    advisories = {}
    for identifier in sorted(ids):
        advisory = audit.get_json('https://api.osv.dev/v1/vulns/' + quote(identifier, safe=''))
        require(advisory.get('id') == identifier, 'advisory identity mismatch')
        database_specific = advisory.get('database_specific')
        require(database_specific is None or isinstance(database_specific, dict), 'invalid advisory severity data')
        audit.advisory_fingerprint(advisory)
        advisories[identifier] = advisory
    matches = []
    for purl, identifiers in sorted(findings.items()):
        scopes = sorted(scope for scope, packages in inventories.items() if purl in packages)
        require(scopes, 'OSV result has no inventory scope')
        for identifier in identifiers:
            advisory = advisories[identifier]
            key = audit.identity(group, purl, identifier)
            fingerprint = audit.advisory_fingerprint(advisory)
            old = baseline[group]['records'].get(key)
            state = 'new' if old is None else ('changed' if old['fingerprint'] != fingerprint or
                                                old['scopes'] != scopes else 'known')
            matches.append({'key': key, 'purl': purl,
                            'advisory': identifier, 'scopes': scopes, 'state': state,
                            'review_status': 'awaiting investigation', 'disposition': 'Further investigation',
                            'failing': True, 'severity': (advisory.get('database_specific') or {}).get('severity', 'UNKNOWN'),
                            'fingerprint': fingerprint})
    resolved = sorted(set(baseline[group]['records']) - {m['key'] for m in matches})
    return {'schema': 1, 'status': 'complete-unreviewed-candidate-scan', 'group': group,
            'branch': branch, 'source_sha': source_sha, 'snapshot_ref': snapshot['ref'],
            'scanned_on': date.today().isoformat(), 'database': 'https://api.osv.dev',
            'risk_acceptance': False, 'inventories': inventories, 'runtime_manifests': manifests,
            'baseline_source_sha': baseline[group]['source_sha'], 'findings': findings,
            'advisories': advisories, 'matches': matches, 'resolved_needing_review': resolved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    matrix = commands.add_parser('matrix')
    matrix.add_argument('--evidence', default=str(EVIDENCE))
    run = commands.add_parser('audit')
    for argument in ('snapshot', 'source', 'group', 'branch', 'source-sha', 'output'):
        run.add_argument('--' + argument, required=True)
    run.add_argument('--evidence', default=str(EVIDENCE))
    run.add_argument('--baseline', default=str(BASELINE))
    args = parser.parse_args()
    if args.command == 'matrix':
        try:
            print(json.dumps(candidate_matrix(read_json(args.evidence)), separators=(',', ':')))
            return 0
        except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
            print('Candidate matrix incomplete: ' + str(exc), file=sys.stderr)
            return 2
    try:
        observed = subprocess.check_output(['git', '-C', args.source, 'rev-parse', 'HEAD'], text=True).strip()
        metadata = read_json(Path(args.source) / 'src/main/resources/fabric.mod.json')
        evidence = read_json(args.evidence)
        baseline = load_baseline(read_json(args.baseline), evidence)
        require(args.group in baseline and SHA.fullmatch(args.source_sha), 'invalid candidate baseline source')
        # A retained scan may predate evidence-only commits. It must still belong
        # to the actual checked-out candidate history, including after a force-push.
        subprocess.check_call(['git', '-C', args.source, 'merge-base', '--is-ancestor',
                               baseline[args.group]['source_sha'], args.source_sha],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        report = audit_candidate(read_json(args.snapshot), metadata, evidence,
                                 args.group, args.branch, args.source_sha, observed, baseline)
        print(f"{args.group} at {args.source_sha}: {len(report['matches'])} unreviewed, failing matches; "
              f"{len(report['resolved_needing_review'])} disappeared matches need review")
        result = 1 if report['matches'] or report['resolved_needing_review'] else 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        report = {'schema': 1, 'status': 'incomplete', 'group': args.group,
                  'branch': args.branch, 'source_sha': args.source_sha, 'error': str(exc)}
        print('Candidate dependency audit incomplete: ' + str(exc), file=sys.stderr)
        result = 2
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    sys.exit(main())
