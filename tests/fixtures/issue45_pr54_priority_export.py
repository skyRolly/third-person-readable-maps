"""Regression control: priority_register verbatim from merged PR #54.

Source commit 2832e799d8d6b80d82fe2f9cb24f7901f02bc0f2; this fixture intentionally
retains the defective applicability check to demonstrate the regression.
"""
from reconcile_issue45_live_audits import ROOT, LIVE, historic, verify_live, decode, digest
from release import require


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
