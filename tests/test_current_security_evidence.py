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
    def test_moderate_low_investigation_is_source_bound_and_not_a_disposition(self):
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
        evidence = json.loads((ROOT / 'docs/dependency-evidence/moderate-low-advisory-review-2026-11-13.json').read_text())
        index = json.loads((ROOT / worklist['last_osv_rescan']['index_path']).read_text())['groups']
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
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
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
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
        inventory = json.loads((directory / 'mod-class-reference-inventory.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
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
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
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
                self.assertEqual(source['source_sha'], candidates[group]['candidate_head'])
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
                indexed.add((occurrence['group'], record['purl'], record['advisory'], occurrence['fingerprint']))
        self.assertEqual(indexed, expected)

    def test_unmerged_maintenance_proposals_remain_distinct_and_unreviewed(self):
        directory = ROOT / 'docs/dependency-evidence/1.0.0-maintenance-proposals-2026-11-12'
        index = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
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
