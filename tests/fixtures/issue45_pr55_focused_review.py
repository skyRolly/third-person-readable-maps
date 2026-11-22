"""Regression control: validate_focused_review from merged PR #55.

Source commit 990820103ffb97eee51d2b40ed304dfeaf9d3017; this fixture intentionally retains the missing
runtime-manifest comparison.
"""
from reconcile_issue45_live_audits import occurrence
from release import require


def validate_focused_review(identifier, finding, observed, current_rows, historical_rows, historical_reports, reports):
    """Fail closed if an investigation no longer describes the audited evidence.

    The archived review cites a historical report, while a live scan is a new
    report with its own independently checked archive digest. Compare their
    source-bound findings and advisory content, not their necessarily different
    report bytes. A changed `modified` timestamp alone is administrative; every
    other advisory field must match until separately reviewed.
    """
    require(finding.get('advisory_id') == identifier and finding.get('risk_accepted') is False and
            finding.get('release_blocking') is True, 'invalid focused review: ' + identifier)
    expected = {}
    for row in finding['occurrences']:
        key = occurrence(row['source_kind'], row['group'], {'purl': row['purl'], 'advisory': identifier})
        require(key not in expected, 'duplicate focused review occurrence: ' + identifier)
        expected[key] = row
    actual = {}
    for row in observed:
        key = occurrence(row['source_kind'], row['group'], {'purl': row['purl'], 'advisory': identifier})
        require(key not in actual, 'duplicate focused live occurrence: ' + identifier)
        actual[key] = row
    require(len(expected) == finding['occurrence_count'] and set(actual) == set(expected),
            'focused occurrence identities differ: ' + identifier)
    for key, reviewed in expected.items():
        current = actual[key]
        match = current_rows[key]
        old = historical_rows.get(key)
        group_key = key[0] + '|' + key[1]
        require(old is not None and group_key in reports and group_key in historical_reports,
                'focused historical source missing: ' + identifier)
        require(reviewed['source_sha'] == current['source_sha'] == old['source_sha'] and
                reviewed['purl'] == current['purl'] and
                reviewed['package_version'] == current['purl'].rsplit('@', 1)[-1],
                'focused review stale: source or package identity: ' + identifier)
        scopes = reviewed['dependency_scopes']
        require(scopes == current['scopes'] == old['scopes'] and
                sorted(reviewed['minecraft_versions']) ==
                sorted(s.split('/', 1)[1] for s in scopes if s.startswith('runtime/')),
                'focused review stale: dependency scopes or environments: ' + identifier)
        require(reviewed['fingerprint'] == current['fingerprint'] == old['fingerprint'],
                'focused review stale: advisory fingerprint: ' + identifier)
        require(reviewed['severity'] == match['severity'] == old['severity'] == finding['severity'] and
                reviewed['disposition'] == current['disposition'] == old['disposition'] and
                reviewed['failing'] == current['release_blocking'] == old['failing'] and
                reviewed['release_blocking'] == current['release_blocking'] and
                reviewed['risk_accepted'] is False and current['risk_accepted'] is False,
                'focused review stale: severity, disposition or blocking state: ' + identifier)
        source = reviewed['source_report']
        require(source.get('path') == old['report'] and
                source.get('sha256_uncompressed') == old['report_sha256_uncompressed'],
                'focused review stale: historical report provenance: ' + identifier)
        previous_advisory = historical_reports[group_key]['advisories'][identifier]
        current_advisory = reports[group_key][0]['advisories'][identifier]
        require(sorted(finding['aliases']) == sorted(previous_advisory.get('aliases', [])) and
                {k: v for k, v in previous_advisory.items() if k != 'modified'} ==
                {k: v for k, v in current_advisory.items() if k != 'modified'},
                'focused review stale: advisory metadata: ' + identifier)
