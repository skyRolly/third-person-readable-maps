#!/usr/bin/env python3
"""Fail-closed OSV audit for source-pinned, unreviewed legacy candidates.

This is a separate monitoring path: it never changes the reviewed ledger or
provides release authorization. Every advisory match is unreviewed and failing.
"""
import argparse
from datetime import date
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


def audit_candidate(snapshot, metadata, evidence, group, branch, source_sha, observed_sha):
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
            matches.append({'key': audit.identity(group, purl, identifier), 'purl': purl,
                            'advisory': identifier, 'scopes': scopes, 'state': 'new',
                            'review_status': 'awaiting investigation', 'disposition': 'Further investigation',
                            'failing': True, 'severity': (advisory.get('database_specific') or {}).get('severity', 'UNKNOWN'),
                            'fingerprint': audit.advisory_fingerprint(advisory)})
    return {'schema': 1, 'status': 'complete-unreviewed-candidate-scan', 'group': group,
            'branch': branch, 'source_sha': source_sha, 'snapshot_ref': snapshot['ref'],
            'scanned_on': date.today().isoformat(), 'database': 'https://api.osv.dev',
            'risk_acceptance': False, 'inventories': inventories, 'runtime_manifests': manifests,
            'findings': findings, 'advisories': advisories, 'matches': matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    matrix = commands.add_parser('matrix')
    matrix.add_argument('--evidence', default=str(EVIDENCE))
    run = commands.add_parser('audit')
    for argument in ('snapshot', 'source', 'group', 'branch', 'source-sha', 'output'):
        run.add_argument('--' + argument, required=True)
    run.add_argument('--evidence', default=str(EVIDENCE))
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
        report = audit_candidate(read_json(args.snapshot), metadata, read_json(args.evidence),
                                 args.group, args.branch, args.source_sha, observed)
        print(f"{args.group} at {args.source_sha}: {len(report['matches'])} unreviewed, failing matches")
        result = 1 if report['matches'] else 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        report = {'schema': 1, 'status': 'incomplete', 'group': args.group,
                  'branch': args.branch, 'source_sha': args.source_sha, 'error': str(exc)}
        print('Candidate dependency audit incomplete: ' + str(exc), file=sys.stderr)
        result = 2
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    sys.exit(main())
