#!/usr/bin/env python3
"""Verify the retained live Issue #45 scans and compare exact-source findings.

This is an evidence comparison, not a security clearance. The audit workflows
remain the authoritative, fail-closed security gates.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

import audit_dependencies as audit
from release import require, unique_object
import scan_dependency_snapshot as scanner

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
LIVE = ROOT / 'docs/dependency-evidence/issue45-live-source-2026-11-22'


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def occurrence(kind, group, row):
    return kind, group, row['purl'], row['advisory']


def historic(root=ROOT):
    index = decode((root / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json').read_bytes())
    require(index.get('schema') == 1 and isinstance(index.get('reports'), dict), 'invalid historical index')
    reports = {}
    for identity, spec in index['reports'].items():
        path = (root / spec['report']).resolve()
        require(path.is_relative_to(root.resolve()), 'historical report path escapes repository')
        raw = gzip.decompress(path.read_bytes())
        require(digest(raw) == spec['sha256_uncompressed'], 'historical report checksum mismatch: ' + identity)
        report = decode(raw)
        require(report['source_sha'] == spec['source_sha'], 'historical source mismatch: ' + identity)
        reports[identity] = report
    rows = {}
    for row in index['records']:
        key = occurrence(row['source_kind'], row['group'], row)
        group_key = row['source_kind'] + '|' + row['group']
        require(key not in rows and group_key in reports, 'duplicate or unknown historical occurrence')
        spec = index['reports'][group_key]
        require(row['source_sha'] == spec['source_sha'] and row['report'] == spec['report'] and
                row['report_sha256_uncompressed'] == spec['sha256_uncompressed'],
                'historical occurrence report provenance mismatch')
        matches = [m for m in reports[group_key]['matches'] if m['purl'] == row['purl'] and
                   m['advisory'] == row['advisory']]
        require(len(matches) == 1 and all(matches[0].get(k) == row.get(k) for k in
                ('scopes', 'fingerprint', 'severity', 'failing')), 'historical occurrence differs from report')
        rows[key] = row
    require(sum(len(r['matches']) for r in reports.values()) == len(rows),
            'historical index does not cover its reports exactly')
    return index, reports, rows


def verify_live(live=LIVE, historical=None):
    index = decode((live / 'artifact-index.json').read_bytes())
    require(index.get('schema') == 1 and re.fullmatch(r'[0-9a-f]{40}', index.get('coordinator_sha', '')),
            'invalid live artifact index')
    items = index.get('artifacts')
    require(isinstance(items, list) and len(items) == 26, 'expected 13 report and 13 snapshot archives')
    reports, graphs, identifiers, names = {}, {}, set(), set()
    for item in items:
        number, name = item['id'], item['name']
        require(isinstance(number, int) and number > 0 and number not in identifiers and
                isinstance(name, str) and name not in names, 'duplicate or invalid artifact identity')
        identifiers.add(number)
        names.add(name)
        require(item['run'] in (index['candidate_run'], index['maintenance_run']), 'unexpected workflow run')
        raw = (live / 'raw' / (str(number) + '.zip')).read_bytes()
        require(len(raw) == item['size'] and item['digest'] == 'sha256:' + digest(raw),
                'live archive size or checksum mismatch: ' + name)
        with ZipFile(BytesIO(raw)) as archive:
            members = archive.namelist()
            require(len(members) == len(set(members)), 'duplicate ZIP member: ' + name)
            if name.startswith('dependency-graph_'):
                require(len(members) == 1 and members[0].startswith('dependency-graph-reports/') and
                        members[0].endswith('.json'), 'invalid dependency snapshot archive')
                graph = decode(archive.read(members[0]))
                sha = graph['sha']
                require(sha not in graphs, 'duplicate dependency snapshot source')
                graphs[sha] = (graph, item)
                continue
            candidate = name.startswith('candidate-dependency-audit-')
            require(candidate or name.startswith('dependency-audit-'), 'unknown audit artifact')
            require(item['run'] == index['candidate_run' if candidate else 'maintenance_run'],
                    'audit artifact belongs to wrong workflow')
            report_name = 'candidate-dependency-audit.json' if candidate else 'dependency-audit.json'
            require(set(members) == {report_name, 'gradle-tool-audit.json'}, 'missing or unexpected audit report')
            report, tool = decode(archive.read(report_name)), decode(archive.read('gradle-tool-audit.json'))
            kind = 'candidate' if candidate else 'integrated'
            group = report['group'] if candidate else report['branch'].removeprefix('mc/')
            key = kind + '|' + group
            require(key not in reports, 'duplicate live source group')
            require(report['status'] == ('complete-unreviewed-candidate-scan' if candidate else 'complete'),
                    'incomplete live audit: ' + key)
            require(tool.get('status') == 'complete' and tool.get('source_sha') == report['source_sha'] and
                    isinstance(tool.get('advisories'), list) and tool.get('risk_accepted') is False,
                    'incomplete or mismatched Gradle tool audit: ' + key)
            require(tool.get('failing') == bool(tool['advisories']), 'invalid Gradle tool audit result')
            if candidate:
                require(report.get('risk_acceptance') is False, 'candidate risk acceptance is not permitted')
            reports[key] = (report, tool, item)
    require(len(reports) == len(graphs) == 13, 'incomplete report or snapshot set')
    require(set(reports) == set(historical['reports']), 'historical and live source groups differ')
    rows = {}
    for key, (report, tool, item) in reports.items():
        kind, group = key.split('|', 1)
        sha = report['source_sha']
        require(sha == historical['reports'][key]['source_sha'], 'source changed; comparison requires review: ' + key)
        require(sha in graphs, 'missing source-bound dependency snapshot: ' + key)
        graph, graph_item = graphs[sha]
        require(graph_item['run'] == item['run'] and graph['ref'] == 'refs/heads/' + report['branch'],
                'snapshot run or branch mismatch: ' + key)
        if kind == 'candidate':
            require(report['snapshot_ref'] == graph['ref'], 'candidate snapshot reference mismatch')
        purls, skipped = scanner.packages(graph)
        require(not skipped and sorted({audit.canonical(p) for p in purls}) == report['inventories']['gradle'],
                'snapshot and reported Gradle inventory differ: ' + key)
        inventories, findings, advisories = report['inventories'], report['findings'], report['advisories']
        require(isinstance(inventories, dict) and inventories and isinstance(findings, dict) and
                isinstance(advisories, dict), 'invalid reported inventory or advisories')
        for packages in inventories.values():
            require(isinstance(packages, list) and packages and len(packages) == len(set(packages)),
                    'empty or duplicate inventory entries')
        expected = set()
        for purl, ids in findings.items():
            require(isinstance(ids, list) and ids and len(ids) == len(set(ids)), 'invalid reported findings')
            for identifier in ids:
                expected.add((purl, identifier))
        require({identifier for _, identifier in expected} == set(advisories),
                'missing or unexpected advisory metadata: ' + key)
        observed = set()
        for row in report['matches']:
            purl, identifier = row['purl'], row['advisory']
            ident = occurrence(kind, group, row)
            require(ident not in rows, 'duplicate live occurrence: ' + '|'.join(ident))
            advisory = advisories.get(identifier)
            scopes = sorted(scope for scope, packages in inventories.items() if purl in packages)
            require((purl, identifier) in expected and scopes and row['scopes'] == scopes and
                    row['key'] == audit.identity(group, purl, identifier) and
                    isinstance(advisory, dict) and advisory.get('id') == identifier and
                    row['fingerprint'] == audit.advisory_fingerprint(advisory) and
                    row['severity'] == (advisory.get('database_specific') or {}).get('severity', 'UNKNOWN'),
                    'live occurrence, scope or advisory fingerprint mismatch: ' + '|'.join(ident))
            require(isinstance(row['failing'], bool), 'invalid failing state')
            require(kind != 'candidate' or row['failing'], 'candidate finding cannot be silently cleared')
            rows[ident] = row
            observed.add((purl, identifier))
        require(observed == expected, 'live report does not cover its findings exactly: ' + key)
        pending = report.get('resolved_needing_review')
        require(isinstance(pending, list), 'missing pending-resolution status: ' + key)
        if kind == 'integrated':
            require(report.get('failing') == (bool(pending) or any(row['failing'] for row in report['matches'])),
                    'maintenance failure status does not match findings: ' + key)
    return index, reports, rows


def reconcile(live=LIVE, root=ROOT):
    old_index, old_reports, old = historic(root)
    index, reports, current = verify_live(live, old_index)
    common = old.keys() & current.keys()
    differences = {field: sorted('|'.join(k) for k in common if old[k].get(field) != current[k].get(field))
                   for field in ('fingerprint', 'scopes', 'severity', 'failing', 'disposition')}
    metadata_changes, withdrawals = [], []
    alias_ids = defaultdict(set)
    for key, (report, _, _) in reports.items():
        previous = old_reports[key]['advisories']
        for identifier, advisory in report['advisories'].items():
            for alias in set(advisory.get('aliases', [])) | {identifier}:
                alias_ids[alias].add(identifier)
            if identifier in previous and any(advisory.get(field) != previous[identifier].get(field)
                                              for field in ('modified', 'aliases', 'withdrawn')):
                metadata_changes.append(key + '|' + identifier)
            if advisory.get('withdrawn'):
                withdrawals.append(key + '|' + identifier)
    severities = Counter(row['severity'] for row in current.values() if row['failing'])
    scopes = Counter(key[0] for key, row in current.items() if row['failing'])
    return {
        'schema': 1, 'coordinator_sha': index['coordinator_sha'],
        'candidate_run': index['candidate_run'], 'maintenance_run': index['maintenance_run'],
        'historical_occurrences': len(old), 'current_occurrences': len(current),
        'failing_occurrences': sum(scopes.values()), 'failing_by_source_kind': dict(sorted(scopes.items())),
        'failing_by_severity': dict(sorted(severities.items())),
        'distinct_advisory_ids': len({key[3] for key in current}),
        'distinct_package_version_advisory_pairs': len({(key[2], key[3]) for key in current}),
        'new_occurrences': sorted('|'.join(key) for key in current.keys() - old.keys()),
        'missing_occurrences_requiring_review': sorted('|'.join(key) for key in old.keys() - current.keys()),
        'changed_occurrences': differences, 'metadata_changed': sorted(metadata_changes),
        'aliases_shared_by_distinct_returned_ids': {key: sorted(ids) for key, ids in sorted(alias_ids.items())
                                                   if len(ids) > 1},
        'returned_withdrawn_advisories': sorted(withdrawals),
        'reported_resolutions_needing_review': {
            key: report['resolved_needing_review'] for key, (report, _, _) in reports.items()
            if report['resolved_needing_review']},
        'gradle_tool_advisories': sum(len(tool['advisories']) for _, tool, _ in reports.values()),
        'security_clearance': False,
    }


def priority_register(live=LIVE, root=ROOT):
    old_index, _, _ = historic(root)
    index, reports, rows = verify_live(live, old_index)
    evidence_path = 'docs/dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json'
    evidence_raw = (root / evidence_path).read_bytes()
    evidence = decode(evidence_raw)
    focused = {row['advisory_id']: row for row in evidence['findings']}
    require(len(focused) == len(evidence['findings']), 'duplicate focused advisory')
    grouped = {}
    for ident, row in sorted(rows.items()):
        if row['severity'] not in ('CRITICAL', 'HIGH'):
            continue
        kind, group, purl, identifier = ident
        report, _, item = reports[kind + '|' + group]
        advisory = report['advisories'][identifier]
        focus = focused.get(identifier)
        require(row['disposition'] != 'Risk accepted', 'risk acceptance requires separate review: ' + identifier)
        owner = ('Minecraft runtime manifest; Gradle resolution also contains this coordinate when scoped gradle'
                 if any(scope.startswith('runtime/') for scope in row['scopes']) else
                 'Gradle-resolved dependency; owner and actual use require investigation')
        package = purl.split('@', 1)[0]
        ranges = [entry.get('ranges', []) for entry in advisory.get('affected', [])
                  if (entry.get('package') or {}).get('purl') == package]
        require(ranges, 'missing affected package ranges: ' + identifier + ' ' + package)
        entry = grouped.setdefault(identifier, {'advisory_id': identifier,
            'aliases': sorted(advisory.get('aliases', [])), 'severity': row['severity'],
            'modified': advisory.get('modified'), 'affected_ranges': {}, 'occurrences': [],
            'focused_evidence': evidence_path if focus else None,
            'responsible_owner': focus.get('responsible_owner') if focus else
                'Project maintainer for assessment; upstream game/library owners for game-managed updates',
            'reviewer': focus.get('reviewer') if focus else None,
            'review_date': focus.get('review_date') if focus else None,
            'follow_up': focus.get('follow_up_requirements') if focus else
                ['Investigate the affected API, input trust boundary, supported runtime and compatible upstream fix.']})
        require(entry['aliases'] == sorted(advisory.get('aliases', [])) and
                entry['severity'] == row['severity'] and entry['modified'] == advisory.get('modified'),
                'inconsistent advisory metadata')
        entry['affected_ranges'][package] = ranges
        entry['occurrences'].append({'source_kind': kind, 'group': group, 'source_sha': report['source_sha'],
            'purl': purl, 'scopes': row['scopes'], 'fingerprint': row['fingerprint'],
            'source_report_artifact_id': item['id'], 'source_report_archive_sha256': item['digest'].removeprefix('sha256:'),
            'source_report_member': 'candidate-dependency-audit.json' if kind == 'candidate' else 'dependency-audit.json',
            'dependency_owner': owner,
            'disposition': row['disposition'], 'release_blocking': row['failing'], 'risk_accepted': False})
    for identifier, finding in focused.items():
        observed = grouped.get(identifier, {}).get('occurrences', [])
        require(len(observed) == finding['occurrence_count'], 'focused occurrence count differs: ' + identifier)
        actual = {(row['source_kind'], row['group'], row['purl'], row['source_sha']) for row in observed}
        expected = {(row['source_kind'], row['group'], row['purl'], row['source_sha'])
                    for row in finding['occurrences']}
        require(actual == expected and len(expected) == len(finding['occurrences']),
                'focused occurrence identities differ: ' + identifier)
    return {'schema': 1, 'coordinator_sha': index['coordinator_sha'],
            'candidate_run': index['candidate_run'], 'maintenance_run': index['maintenance_run'],
            'focused_evidence_sha256': digest(evidence_raw), 'advisory_ids': len(grouped),
            'occurrences': sum(len(value['occurrences']) for value in grouped.values()),
            'review_status': 'No new security disposition or risk acceptance is implied by this index.',
            'security_clearance': False, 'advisories': [grouped[key] for key in sorted(grouped)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', type=Path, default=LIVE)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--priority-register', type=Path)
    args = parser.parse_args()
    try:
        report = reconcile(args.live)
        text = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.output:
            args.output.write_text(text, encoding='utf-8')
        if args.priority_register:
            args.priority_register.write_text(json.dumps(priority_register(args.live), indent=2, sort_keys=True) + '\n',
                                              encoding='utf-8')
        print(text, end='')
        return 1 if (report['failing_occurrences'] or report['new_occurrences'] or
                     report['missing_occurrences_requiring_review'] or
                     any(report['changed_occurrences'].values()) or report['metadata_changed'] or
                     report['aliases_shared_by_distinct_returned_ids'] or
                     report['returned_withdrawn_advisories'] or report['reported_resolutions_needing_review'] or
                     report['gradle_tool_advisories']) else 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, EOFError) as exc:
        print('Live audit reconciliation incomplete: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
