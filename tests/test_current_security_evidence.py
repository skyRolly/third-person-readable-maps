"""Keep current security evidence source-bound and traceable, without accepting risk."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_dependencies as audit


class CurrentSecurityEvidenceTests(unittest.TestCase):
    def test_each_finding_has_source_bound_runtime_ownership_evidence(self):
        directory = ROOT / 'docs/dependency-evidence/advisory-ownership-2026-11-14'
        index = json.loads((directory / 'index.json').read_text())
        scan = json.loads((ROOT / 'docs/dependency-evidence/osv-rescan-2026-11-14/index.json').read_text())
        worklist = json.loads((ROOT / scan['disposition_worklist']).read_text())
        expected = {}
        for group, source in scan['current_sources'].items():
            report = json.loads((ROOT / source['report_path']).read_text())
            for match in report['matches']:
                expected[group + '|' + match['purl'] + '|' + match['advisory']] = (source, report, match)
        self.assertEqual(set(index['occurrences']), set(expected))
        counts = {'gradle_and_runtime': 0, 'runtime_only': 0}
        for key, row in index['occurrences'].items():
            source, report, match = expected[key]
            self.assertEqual(row['source_sha'], source['source_sha'])
            self.assertEqual(row['source_kind'], source['source_kind'])
            self.assertEqual(row['report_sha256'], source['report_sha256'])
            self.assertEqual(row['fingerprint'], match['fingerprint'])
            self.assertEqual(row['disposition'], 'Further investigation')
            self.assertTrue(row['failing'])
            self.assertFalse(row['risk_accepted'])
            self.assertFalse(row['proposed_jar_bundles_third_party_classes_or_nested_jars'])
            self.assertEqual(row['proposed_jar_sha256'], worklist['packaging'][row['group']]['artifact_sha256'])
            self.assertEqual(row['gradle_scope'], 'gradle' in match['scopes'])
            counts['gradle_and_runtime' if row['gradle_scope'] else 'runtime_only'] += 1
            versions = {s.split('/', 1)[1] for s in match['scopes'] if s.startswith('runtime/')}
            self.assertTrue(versions)
            self.assertEqual(set(row['minecraft_runtime_metadata']), versions)
            for version, metadata in row['minecraft_runtime_metadata'].items():
                self.assertEqual(metadata['metadata_sha1'], report['runtime_manifests'][version]['sha1'])
                self.assertEqual(metadata['metadata_url'], report['runtime_manifests'][version]['url'])
                self.assertIn(match['purl'], report['inventories']['runtime/' + version])
        self.assertEqual(index['scope_counts'], counts)

    def test_november_14_osv_requery_preserves_source_bound_findings(self):
        directory = ROOT / 'docs/dependency-evidence/osv-rescan-2026-11-14'
        index = json.loads((directory / 'index.json').read_text())
        current = json.loads((ROOT / index['disposition_worklist']).read_text())['sources']
        proposals = json.loads((ROOT / 'docs/dependency-evidence/class-linkage-proposals-2026-11-13/index.json').read_text())['groups']
        self.assertEqual(index['scanned_on'], '2026-11-14')
        self.assertFalse(index['risk_acceptance'])
        self.assertEqual(set(index['current_sources']), set(current))
        self.assertEqual(set(index['unmerged_proposals']), set(proposals))
        signature = lambda m: (m['purl'], m['advisory'], m['fingerprint'],
                               tuple(sorted(m['scopes'])), m['state'], m['failing'])
        for category, sources in (('current_sources', current), ('unmerged_proposals', proposals)):
            for group, row in index[category].items():
                with self.subTest(category=category, group=group):
                    source = sources[group]
                    self.assertTrue(row['complete'] and row['same_as_prior'])
                    self.assertEqual(row['exit_code'], 1)
                    self.assertEqual(row['source_sha'], source['source_sha'])
                    self.assertEqual(row['snapshot_sha256'], source['snapshot_sha256'])
                    self.assertEqual(row['snapshot_path'], source['snapshot_path'])
                    self.assertEqual(hashlib.sha256((ROOT / row['snapshot_path']).read_bytes()).hexdigest(), row['snapshot_sha256'])
                    for kind in ('report', 'log'):
                        raw = (ROOT / row[kind + '_path']).read_bytes()
                        self.assertEqual(hashlib.sha256(raw).hexdigest(), row[kind + '_sha256'])
                        if kind == 'report':
                            report = json.loads(raw)
                    self.assertEqual(report['scanned_on'], '2026-11-14')
                    self.assertEqual(report['source_sha'], row['source_sha'])
                    previous = json.loads((ROOT / source['report_path']).read_text())
                    self.assertEqual({signature(m) for m in report['matches']},
                                     {signature(m) for m in previous['matches']})
                    self.assertEqual(row['matches'], row['failing'])
                    self.assertEqual(row['matches'], len(report['matches']))
                    self.assertFalse(row['resolved_needing_review'])
                    for match in report['matches']:
                        self.assertTrue(match['failing'])
                        self.assertEqual(match['fingerprint'], audit.advisory_fingerprint(report['advisories'][match['advisory']]))
        for name in ('run-current.py', 'run-current.log', 'run-proposals.py', 'run-proposals.log'):
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), index[name + '_sha256'])

    def test_moderate_low_investigation_is_source_bound_and_not_a_disposition(self):
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        evidence = json.loads((ROOT / 'docs/dependency-evidence/moderate-low-advisory-review-2026-11-13.json').read_text())
        index = json.loads((ROOT / worklist['historical_osv_rescan']['index_path']).read_text())['groups']
        eligible = {key: row for key, row in worklist['records'].items() if row['severity'] in ('MODERATE', 'LOW')}
        self.assertEqual(set(evidence['records']), {row['advisory'] for row in eligible.values()})
        self.assertEqual(len(evidence['records']), 52)
        summary = (ROOT / 'docs/security-moderate-low-2026-11-13.md').read_text()
        for advisory, note in evidence['records'].items():
            with self.subTest(advisory=advisory):
                group = index[note['report_group']]
                self.assertEqual(note['report_path'], group['report_path'])
                self.assertEqual(note['report_sha256'], group['report_sha256'])
                raw = (ROOT / note['report_path']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), note['report_sha256'])
                report = json.loads(raw)
                fingerprint = audit.advisory_fingerprint(report['advisories'][advisory])
                self.assertEqual(note['advisory_fingerprint'], fingerprint)
                self.assertIn(advisory, summary)
                self.assertTrue(note['trigger'] and note['remaining_investigation'])
                self.assertEqual(note['disposition'], 'Further investigation')
                self.assertFalse(note['risk_accepted'])
                expected = {key for key, row in eligible.items() if row['advisory'] == advisory}
                self.assertEqual(set(note['records']), expected)
                for key in expected:
                    record = eligible[key]
                    self.assertEqual(record['review_evidence'], 'docs/security-moderate-low-2026-11-13.md')
                    self.assertEqual(record['disposition'], 'Further investigation')
                    self.assertFalse(record['risk_accepted'])
                    self.assertTrue(all(o['fingerprint'] == fingerprint and o['failing'] for o in record['occurrences']))

    def test_november_13_proposal_rescans_remain_unreviewed(self):
        directory = ROOT / 'docs/dependency-evidence/1.0.0-proposal-osv-rescan-2026-11-13'
        index = json.loads((directory / 'index.json').read_text())
        previous_dir = ROOT / 'docs/dependency-evidence/1.0.0-maintenance-proposals-2026-11-12'
        previous = json.loads((previous_dir / 'index.json').read_text())['groups']
        self.assertEqual(set(index['groups']), set(previous))
        for group, result in index['groups'].items():
            with self.subTest(group=group):
                source = previous[group]
                self.assertTrue(result['complete'] and result['same_as_previous'])
                self.assertEqual(result['exit_code'], 1)
                self.assertEqual(result['source_sha'], source['source_sha'])
                self.assertEqual(result['branch'], source['branch'])
                self.assertEqual(result['snapshot_sha256'], source['snapshot_sha256'])
                self.assertEqual(hashlib.sha256((ROOT / result['snapshot_path']).read_bytes()).hexdigest(), source['snapshot_sha256'])
                for kind in ('report', 'log'):
                    raw = (ROOT / result[kind + '_path']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result[kind + '_sha256'])
                    if kind == 'report':
                        report = json.loads(raw)
                self.assertEqual(report['scanned_on'], '2026-11-13')
                self.assertEqual(report['status'], 'complete-unreviewed-maintenance-proposal')
                self.assertFalse(report['risk_acceptance'])
                self.assertEqual(report['source_sha'], source['source_sha'])
                old = json.loads((previous_dir / (group + '-osv.json')).read_text())
                key = lambda m: (m['purl'], m['advisory'], m['fingerprint'], m['state'], m['failing'])
                self.assertEqual({key(m) for m in report['matches']}, {key(m) for m in old['matches']})
                self.assertEqual(result['matches'], len(report['matches']))
                self.assertEqual(result['failing'], len(report['matches']))
                self.assertTrue(all(m['review_status'] == 'awaiting investigation' for m in report['matches']))

    def test_november_13_osv_rescan_reuses_exact_snapshots_and_keeps_findings_failing(self):
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
        pointer = worklist['last_osv_rescan']
        self.assertEqual(pointer['scanned_on'], '2026-11-13')
        index = json.loads((ROOT / pointer['index_path']).read_text())
        self.assertEqual(set(index['groups']), set(worklist['sources']))
        for group, result in index['groups'].items():
            with self.subTest(group=group):
                source = worklist['sources'][group]
                self.assertTrue(result['complete'])
                self.assertEqual(result['exit_code'], 1)
                self.assertEqual(result['source_sha'], source['source_sha'])
                self.assertEqual(result['source_kind'], source['source_kind'])
                self.assertEqual(result['snapshot_sha256'], source['snapshot_sha256'])
                self.assertEqual(result['snapshot_path'], source['snapshot_path'])
                for kind in ('report', 'log'):
                    raw = (ROOT / result[kind + '_path']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result[kind + '_sha256'])
                    if kind == 'report':
                        report = json.loads(raw)
                self.assertEqual(report['scanned_on'], '2026-11-13')
                self.assertEqual(report['source_sha'], source['source_sha'])
                previous = json.loads((ROOT / source['report_path']).read_text())
                key = lambda m: (m['purl'], m['advisory'], m['fingerprint'], m['state'], m['failing'])
                self.assertEqual({key(m) for m in report['matches']}, {key(m) for m in previous['matches']})
                self.assertEqual(result['matches'], len(report['matches']))
                self.assertEqual(result['failing'], len(report['matches']))
                self.assertFalse(report.get('resolved_needing_review', []))

    def test_followup_high_advisory_responses_match_the_scanned_findings(self):
        directory = ROOT / 'docs/dependency-evidence/high-advisories-2026-11-13'
        index = json.loads((directory / 'index.json').read_text())['records']
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        self.assertEqual(len(index), 12)
        for advisory, source in index.items():
            raw = (directory / (advisory + '.json')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
            response = json.loads(raw)
            self.assertEqual(response['id'], advisory)
            fingerprint = audit.advisory_fingerprint(response)
            records = [r for r in worklist['records'].values() if r['advisory'] == advisory]
            self.assertTrue(records)
            for record in records:
                self.assertEqual(record['severity'], 'HIGH')
                self.assertEqual(record['review_evidence'], 'docs/security-high-priority-2026-11-13.md')
                self.assertEqual(record['disposition'], 'Further investigation')
                self.assertFalse(record['risk_accepted'])
                self.assertTrue(all(o['fingerprint'] == fingerprint and o['failing'] for o in record['occurrences']))
        for record in worklist['records'].values():
            if record['severity'] in ('HIGH', 'CRITICAL'):
                self.assertTrue(record.get('review_evidence'))
        previous = json.loads((ROOT / 'docs/dependency-evidence/high-advisories-2026-11-12/index.json').read_text())['records']
        high_ids = {r['advisory'] for r in worklist['records'].values() if r['severity'] == 'HIGH'}
        self.assertEqual(high_ids, set(index) | set(previous))

    def test_prioritized_advisory_evidence_is_retained_and_source_bound(self):
        directory = ROOT / 'docs/dependency-evidence/high-advisories-2026-11-12'
        index = json.loads((directory / 'index.json').read_text())['records']
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        inventory = json.loads((directory / 'mod-class-reference-inventory.json').read_text())
        manifest = json.loads((ROOT / 'docs/historical-verifier-followup-2026-11-13/release-manifest.json').read_text())
        groups = {group['id']: group for group in manifest['groups']}
        self.assertEqual(len(index), 21)
        self.assertEqual(set(index), set(inventory['targets']))
        self.assertEqual(set(groups), set(inventory['groups']))
        self.assertEqual(inventory['parser']['source_commit'], groups['26.3']['source_commit'])
        self.assertRegex(inventory['parser']['sha256'], r'^[0-9a-f]{64}$')
        for advisory, source in index.items():
            raw = (directory / (advisory + '.json')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256'])
            self.assertEqual(json.loads(raw)['id'], advisory)
            records = [r for r in worklist['records'].values() if r['advisory'] == advisory]
            self.assertTrue(records)
            self.assertTrue(all(r['review_evidence'] == 'docs/security-high-priority-2026-11-12.md'
                                and r['disposition'] == 'Further investigation' and not r['risk_accepted']
                                for r in records))
        for group, result in inventory['groups'].items():
            self.assertEqual(result['source_commit'], groups[group]['source_commit'])
            self.assertEqual(result['artifact_sha256'], groups[group]['sha256'])
            self.assertGreater(result['class_files'], 0)
            self.assertEqual(result['external_field_writes'], [])
            self.assertEqual(set(result['direct_class_references']), set(index))
            self.assertTrue(all(not references for references in result['direct_class_references'].values()))

    def test_complete_current_scans_match_sources_and_individual_worklist(self):
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
        registry = json.loads((ROOT / 'release/maintenance-targets.json').read_text())['groups']
        self.assertFalse(worklist['risk_acceptance'])
        self.assertEqual(worklist['missing_or_stale_groups'], [])
        self.assertEqual(set(worklist['sources']), set(candidates) | set(registry))
        expected, indexed = set(), set()
        for group, source in worklist['sources'].items():
            for key in ('snapshot', 'report'):
                path = ROOT / source[key + '_path']
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), source[key + '_sha256'])
                if key == 'snapshot':
                    snapshot = json.loads(raw)
                else:
                    report = json.loads(raw)
            self.assertEqual(snapshot['sha'], source['source_sha'])
            self.assertEqual(snapshot['ref'], source['snapshot_ref'])
            self.assertEqual(report['source_sha'], source['source_sha'])
            self.assertEqual(len(report['matches']), source['matches'])
            if group in candidates:
                self.assertEqual(source['source_kind'], 'candidate')
                self.assertEqual(source['source_sha'], candidates[group]['source_commit'])
                self.assertEqual(report['status'], 'complete-unreviewed-candidate-scan')
            else:
                self.assertEqual(source['source_kind'], 'integrated-maintenance')
                self.assertEqual(source['source_sha'], registry[group]['integrated_commit'])
                self.assertEqual(report['status'], 'complete')
            for match in report['matches']:
                advisory = report['advisories'][match['advisory']]
                self.assertEqual(match['fingerprint'], audit.advisory_fingerprint(advisory))
                self.assertTrue(match['failing'])
                expected.add((group, match['purl'], match['advisory'], match['fingerprint']))
        for record in worklist['records'].values():
            self.assertFalse(record['risk_accepted'])
            self.assertEqual(record['disposition'], 'Further investigation')
            for occurrence in record['occurrences']:
                source = worklist['sources'][occurrence['group']]
                self.assertEqual(occurrence['source_sha'], source['source_sha'])
                self.assertEqual(occurrence['report'], source['report_path'])
                indexed.add((occurrence['group'], record['purl'], record['advisory'], occurrence['fingerprint']))
        self.assertEqual(indexed, expected)

    def test_advanced_candidate_scans_preserve_findings_and_provenance(self):
        directory = ROOT / 'docs/dependency-evidence/class-linkage-2026-11-13'
        index = json.loads((directory / 'index.json').read_text())
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        previous = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
        candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
        self.assertEqual(set(index['groups']), set(candidates))
        self.assertFalse(index['risk_acceptance'])
        for filename in ('run-resumed.py', 'orchestration.log'):
            self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
                             index[filename + '_sha256'])
        signature = lambda m: (m['purl'], m['advisory'], m['fingerprint'],
                               tuple(sorted(m['scopes'])), m['state'], m['failing'])
        for group, result in index['groups'].items():
            with self.subTest(group=group):
                self.assertTrue(result['complete'])
                self.assertEqual(result['exit_code'], 1)
                self.assertEqual(result['source_sha'], candidates[group]['source_commit'])
                self.assertEqual(result['source_sha'], worklist['sources'][group]['source_sha'])
                for kind in ('snapshot', 'report', 'snapshot_log', 'audit_log'):
                    raw = (ROOT / result[kind + '_path']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result[kind + '_sha256'])
                    if kind == 'report':
                        report = json.loads(raw)
                    elif kind == 'snapshot':
                        self.assertEqual(json.loads(raw)['sha'], result['source_sha'])
                old = json.loads((ROOT / previous['sources'][group]['report_path']).read_text())
                self.assertEqual({signature(m) for m in report['matches']},
                                 {signature(m) for m in old['matches']})
                self.assertEqual(result['matches'], result['failing'])
                self.assertEqual(result['matches'], len(report['matches']))
                self.assertFalse(report['resolved_needing_review'])

    def test_advanced_maintenance_proposals_remain_separate(self):
        directory = ROOT / 'docs/dependency-evidence/class-linkage-proposals-2026-11-13'
        index = json.loads((directory / 'index.json').read_text())
        transition = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        current = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
        previous = ROOT / 'docs/dependency-evidence/1.0.0-maintenance-proposals-2026-11-12'
        self.assertEqual(set(index['groups']), {'1.21.11', '26.1-26.2', '26.3'})
        self.assertFalse(index['risk_acceptance'])
        for filename in ('run.py', 'orchestration.log'):
            self.assertEqual(hashlib.sha256((directory / filename).read_bytes()).hexdigest(),
                             index[filename + '_sha256'])
        signature = lambda m: (m['purl'], m['advisory'], m['fingerprint'],
                               tuple(sorted(m['scopes'])), m['state'], m['failing'])
        for group, result in index['groups'].items():
            with self.subTest(group=group):
                self.assertTrue(result['complete'])
                self.assertEqual(result['exit_code'], 1)
                self.assertEqual(result['source_sha'], transition[group]['new_head'])
                self.assertNotEqual(result['source_sha'], current['sources'][group]['source_sha'])
                for kind in ('snapshot', 'report', 'snapshot_log', 'audit_log'):
                    raw = (ROOT / result[kind + '_path']).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result[kind + '_sha256'])
                    if kind == 'snapshot':
                        self.assertEqual(json.loads(raw)['sha'], result['source_sha'])
                    if kind == 'report':
                        report = json.loads(raw)
                old = json.loads((previous / (group + '-osv.json')).read_text())
                self.assertEqual({signature(m) for m in report['matches']},
                                 {signature(m) for m in old['matches']})
                self.assertEqual(report['status'], 'complete-unreviewed-maintenance-proposal')
                self.assertFalse(report['risk_acceptance'])
                self.assertEqual(result['matches'], result['failing'])
                self.assertEqual(result['matches'], len(report['matches']))

    def test_unmerged_maintenance_proposals_remain_distinct_and_unreviewed(self):
        directory = ROOT / 'docs/dependency-evidence/1.0.0-maintenance-proposals-2026-11-12'
        index = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/historical-verifier-followup-2026-11-13/release-manifest.json').read_text())
        proposals = {entry['id']: entry for entry in manifest['groups'] if entry['branch'].startswith('maintenance/')}
        self.assertFalse(index['risk_acceptance'])
        self.assertEqual(set(index['groups']), set(proposals))
        for group, source in index['groups'].items():
            self.assertEqual(source['source_sha'], proposals[group]['source_commit'])
            self.assertEqual(source['branch'], proposals[group]['branch'])
            for kind in ('snapshot', 'osv'):
                raw = (directory / (group + '-' + kind + '.json')).read_bytes()
                expected = source['snapshot_sha256' if kind == 'snapshot' else 'report_sha256']
                self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
                data = json.loads(raw)
                if kind == 'snapshot':
                    self.assertEqual(data['sha'], source['source_sha'])
                    self.assertEqual(data['ref'], 'refs/heads/' + source['branch'])
                else:
                    self.assertEqual(data['status'], 'complete-unreviewed-maintenance-proposal')
                    self.assertFalse(data['risk_acceptance'])
                    self.assertEqual(data['source_sha'], source['source_sha'])
                    self.assertEqual(len(data['matches']), source['matches'])
                    self.assertTrue(all(match['failing'] and match['review_status'] == 'awaiting investigation'
                                        for match in data['matches']))


if __name__ == '__main__':
    unittest.main()
