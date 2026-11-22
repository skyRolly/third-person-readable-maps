"""Regression control: priority_register from merged PR #58 (ded9fdb).

Intentionally omits lower-severity observations from cross-source comparison.
"""
from collections import defaultdict
from reconcile_issue45_live_audits import ROOT, LIVE, historic, verify_live, decode, digest, validate_focused_review
from release import require


def priority_register(live=LIVE, root=ROOT):
    old_index, old_reports, old_rows = historic(root)
    index, reports, rows = verify_live(live, old_index)
    evidence_path = 'docs/dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json'
    evidence_raw = (root / evidence_path).read_bytes()
    evidence = decode(evidence_raw)
    ledger = decode((root / 'docs/security-advisories.json').read_bytes())
    reference = ledger.get('critical_reachability_evidence', {})
    require(reference.get('path') == evidence_path and reference.get('sha256') == digest(evidence_raw),
            'focused evidence ledger provenance mismatch')
    source_index = evidence.get('source_provenance', {}).get('finding_index', {})
    index_path = 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
    require(source_index.get('path') == index_path and
            source_index.get('sha256') == digest((root / index_path).read_bytes()),
            'focused evidence finding-index provenance mismatch')
    focused = {row['advisory_id']: row for row in evidence['findings']}
    require(len(focused) == len(evidence['findings']), 'duplicate focused advisory')
    for severity, label in (('CRITICAL', 'critical'), ('HIGH', 'high')):
        count = sum(row['occurrence_count'] for row in focused.values() if row['severity'] == severity)
        field = 'targeted_' + label + '_occurrences'
        require(count == evidence.get(field) == reference.get(field),
                'incomplete focused advisory coverage: ' + severity)
    grouped = {}
    modified_by_source = defaultdict(dict)
    advisory_content = {}
    for ident, row in sorted(rows.items()):
        if row['severity'] not in ('CRITICAL', 'HIGH'):
            continue
        kind, group, purl, identifier = ident
        report, _, item = reports[kind + '|' + group]
        advisory = report['advisories'][identifier]
        content = {key: value for key, value in advisory.items() if key != 'modified'}
        require(identifier not in advisory_content or advisory_content[identifier] == content,
                'inconsistent advisory content across sources: ' + identifier)
        advisory_content[identifier] = content
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
                entry['severity'] == row['severity'] and isinstance(advisory.get('modified'), str) and
                advisory['modified'],
                'inconsistent advisory metadata')
        modified_by_source[identifier][kind + '|' + group] = advisory['modified']
        entry['affected_ranges'][package] = ranges
        entry['occurrences'].append({'source_kind': kind, 'group': group, 'source_sha': report['source_sha'],
            'purl': purl, 'scopes': row['scopes'], 'fingerprint': row['fingerprint'],
            'source_report_artifact_id': item['id'], 'source_report_archive_sha256': item['digest'].removeprefix('sha256:'),
            'source_report_member': 'candidate-dependency-audit.json' if kind == 'candidate' else 'dependency-audit.json',
            'dependency_owner': owner,
            'disposition': row['disposition'], 'release_blocking': row['failing'], 'risk_accepted': False})
    mixed_timestamps = False
    for identifier, observations in modified_by_source.items():
        if len(set(observations.values())) > 1:
            # Independent runs may observe administrative timestamp updates at
            # different times. Preserve each value without choosing one as current.
            grouped[identifier]['modified'] = None
            grouped[identifier]['modified_by_source'] = dict(sorted(observations.items()))
            mixed_timestamps = True
    for identifier, finding in focused.items():
        observed = grouped.get(identifier, {}).get('occurrences', [])
        validate_focused_review(identifier, finding, observed, rows, old_rows, old_reports, reports)
    result = {'schema': 2 if mixed_timestamps else 1, 'coordinator_sha': index['coordinator_sha'],
            'candidate_run': index['candidate_run'], 'maintenance_run': index['maintenance_run'],
            'focused_evidence_sha256': digest(evidence_raw), 'advisory_ids': len(grouped),
            'occurrences': sum(len(value['occurrences']) for value in grouped.values()),
            'review_status': 'No new security disposition or risk acceptance is implied by this index.',
            'security_clearance': False, 'advisories': [grouped[key] for key in sorted(grouped)]}
    if mixed_timestamps:
        result['schema_note'] = ('Schema 2 records differing advisory modified timestamps by source; '
                                 'a null modified value means there is no single observed timestamp.')
    return result
