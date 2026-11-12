import copy
from datetime import date
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_dependencies as audit
import audit_candidate_dependencies as candidate_audit
from release import Invalid

TODAY = date(2026, 11, 4)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.group = '26.1-26.2'
        self.groups = {self.group: {'branch': 'mc/' + self.group, 'minecraft': ['26.1', '26.2']}}
        self.purl = 'pkg:maven/example/library@1.0'
        self.advisory = {'id': 'GHSA-example', 'modified': '2026-11-04T00:00:00Z',
                         'details': 'Untrusted input must reach the decoder.',
                         'affected': [{'package': {'name': 'example:library', 'ecosystem': 'Maven'},
                                       'ranges': [{'type': 'ECOSYSTEM', 'events': [{'introduced': '0'}, {'fixed': '2.0'}]}]}],
                         'database_specific': {'severity': 'MODERATE'}}
        self.inventories = {'gradle': [self.purl], 'runtime/26.1': [self.purl], 'runtime/26.2': [self.purl]}
        record = {'key': audit.identity(self.group, self.purl, self.advisory['id']),
                  'group': self.group, 'purl': self.purl, 'advisory': self.advisory['id'],
                  'fingerprint': audit.advisory_fingerprint(self.advisory), 'scopes': sorted(self.inventories),
                  'disposition': 'Upstream-dependent', 'review_status': 'reviewed',
                  'reviewed_on': TODAY.isoformat(), 'review_due': '2027-02-02',
                  'rationale': 'Requires upstream game update; mod does not package the decoder.',
                  'follow_up': 'Verify upstream runtime limits.', 'owner': 'maintainer', 'recheck_when': 'before release'}
        self.ledger = {'schema': 1, 'reviewed_on': TODAY.isoformat(),
                       'inventories': {self.group: {s: ['pkg:maven/example/library'] for s in self.inventories}},
                       'records': [record]}
        self.findings = {self.purl: ['GHSA-example']}
        self.advisories = {'GHSA-example': self.advisory}

    def compare(self):
        return audit.compare(self.group, self.inventories, self.findings, self.advisories,
                             self.ledger, self.groups, TODAY)

    def test_existing_reviewed_deferred_match_stays_visible(self):
        result = self.compare()
        self.assertEqual(result['matches'][0]['state'], 'known')
        self.assertEqual(result['matches'][0]['disposition'], 'Upstream-dependent')
        self.assertFalse(result['failing'])
        self.assertEqual(len(result['matches']), 1)

    def test_known_unresolved_or_high_severity_still_fails(self):
        self.ledger['records'][0]['disposition'] = 'Further investigation'
        self.assertTrue(self.compare()['failing'])
        self.ledger['records'][0]['disposition'] = 'Upstream-dependent'
        self.advisory['database_specific']['severity'] = 'HIGH'
        self.ledger['records'][0]['fingerprint'] = audit.advisory_fingerprint(self.advisory)
        self.assertTrue(self.compare()['failing'])

    def test_new_advisory_on_previously_reviewed_package_fails(self):
        self.advisories['GHSA-new'] = {**self.advisory, 'id': 'GHSA-new'}
        self.findings[self.purl].append('GHSA-new')
        result = self.compare()
        self.assertTrue(result['failing'])
        self.assertEqual([m['state'] for m in result['matches']], ['known', 'new'])

    def test_newly_affected_version_is_not_covered_by_old_review(self):
        new = self.purl.replace('@1.0', '@1.1')
        self.inventories = {s: [new] for s in self.inventories}
        self.findings = {new: ['GHSA-example']}
        result = self.compare()
        self.assertEqual(result['matches'][0]['state'], 'new')
        self.assertTrue(result['failing'])
        self.assertEqual(result['resolved'], [])
        self.assertEqual(result['resolved_needing_review'], [self.ledger['records'][0]['key']])

    def test_new_affected_compatibility_group_has_no_implicit_review(self):
        new_group = '26.3'
        self.groups[new_group] = {'branch': 'mc/26.3', 'minecraft': ['26.3']}
        self.ledger['inventories'][new_group] = {'gradle': ['pkg:maven/example/library'],
                                                     'runtime/26.3': ['pkg:maven/example/library']}
        result = audit.compare(new_group, {'gradle': [self.purl], 'runtime/26.3': [self.purl]},
                               self.findings, self.advisories, self.ledger, self.groups, TODAY)
        self.assertTrue(result['failing'])
        self.assertEqual(result['matches'][0]['state'], 'new')

    def test_changed_runtime_scope_requires_new_review(self):
        self.ledger['records'][0]['scopes'].remove('runtime/26.2')
        self.assertEqual(self.compare()['matches'][0]['state'], 'changed')
        self.assertTrue(self.compare()['failing'])

    def test_affected_range_or_severity_increase_requires_review(self):
        for key, value in [('affected', [{'package': {'name': 'example:library'}, 'versions': ['1.0', '1.1']}]),
                           ('severity', [{'type': 'CVSS_V3', 'score': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'}])]:
            with self.subTest(key=key):
                original = copy.deepcopy(self.advisory)
                self.advisory[key] = value
                self.assertEqual(self.compare()['matches'][0]['state'], 'changed')
                self.assertTrue(self.compare()['failing'])
                self.advisory.clear(); self.advisory.update(original)

    def test_disappeared_finding_requires_review_and_is_not_deleted(self):
        self.findings = {}
        result = self.compare()
        self.assertTrue(result['failing'])
        self.assertEqual(result['resolved'], [])
        self.assertEqual(result['resolved_needing_review'], [self.ledger['records'][0]['key']])
        self.assertEqual(len(self.ledger['records']), 1)

    def test_resolution_review_binds_source_and_complete_inventory(self):
        self.findings = {}
        record = self.ledger['records'][0]
        record['disposition'] = 'Fixed'
        record['resolution_review'] = {'source_sha': 'a' * 40,
            'inventory_sha256': audit.inventory_fingerprint(self.inventories),
            'reviewed_by': 'independent-reviewer', 'evidence_reference': 'reviewed report'}
        def compare(sha):
            return audit.compare(self.group, self.inventories, self.findings, self.advisories,
                                 self.ledger, self.groups, TODAY, source_sha=sha)
        reviewed = compare('a' * 40)
        self.assertFalse(reviewed['failing'])
        self.assertEqual(reviewed['resolved'], [record['key']])
        self.assertEqual(reviewed['resolved_needing_review'], [])
        self.assertTrue(compare('b' * 40)['failing'])
        self.inventories['gradle'].append('pkg:maven/example/another@1.0')
        self.assertTrue(compare('a' * 40)['failing'])
        record['resolution_review']['reviewed_by'] = ''
        with self.assertRaises(Invalid): compare('a' * 40)

    def test_missing_or_incomplete_advisory_data_fails(self):
        for value in [None, {}, {'id': 'GHSA-example', 'modified': '2026-11-04'}]:
            with self.subTest(value=value), self.assertRaises((Invalid, KeyError)):
                self.advisories['GHSA-example'] = value
                self.compare()

    def test_incomplete_inventory_cannot_report_findings_resolved(self):
        self.findings = {}
        for inventory in [{}, {'gradle': []}, {'gradle': ['pkg:maven/another/library@1']}]:
            with self.subTest(inventory=inventory), self.assertRaises(Invalid):
                audit.compare(self.group, inventory, {}, {}, self.ledger, self.groups, TODAY)
        self.ledger['inventories'][self.group]['gradle'].append('pkg:maven/missing/package')
        with self.assertRaises(Invalid): self.compare()

    def test_malformed_stale_and_duplicate_baselines_fail(self):
        for edit in [lambda v: v.update(schema=999),
                     lambda v: v['records'][0].update(review_due='2026-11-03'),
                     lambda v: v['records'][0].update(review_due='2028-01-01'),
                     lambda v: v['records'][0].update(fingerprint=''),
                     lambda v: v['records'][0].update(disposition='ignored'),
                     lambda v: v['records'][0].update(disposition='Risk accepted'),
                     lambda v: v['records'].append(copy.deepcopy(v['records'][0]))]:
            value = copy.deepcopy(self.ledger); edit(value)
            with self.assertRaises(Invalid): audit.load_ledger(value, self.groups, TODAY)

    def test_api_failure_and_missing_data_write_incomplete_report(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'report.json'
            argv = ['audit_dependencies.py', '--snapshot', 'x', '--branch', 'mc/26.1-26.2',
                    '--source-sha', 'a' * 40, '--output', str(output)]
            with patch.object(sys, 'argv', argv), patch.object(audit, 'read_json', return_value={'groups': self.groups}), \
                 patch.object(audit, 'audit', side_effect=HTTPError('https://api.osv.dev', 503, 'unavailable', {}, None)), \
                 patch('sys.stderr', new_callable=io.StringIO):
                self.assertEqual(audit.main(), 2)
            self.assertEqual(json.loads(output.read_text())['status'], 'incomplete')

    def test_runtime_metadata_hash_and_identity_checks(self):
        with patch.object(audit, 'urlopen', return_value=io.BytesIO(b'{"id":"26.1"}')):
            with self.assertRaises(Invalid): audit.get_json('https://example.test', '0' * 40)
        with patch.object(audit, 'get_json', return_value={'versions': []}):
            with self.assertRaises(Invalid): audit.runtime_inventories(['26.1'])

    def test_osv_error_object_does_not_mean_clean_scan(self):
        with patch.object(audit.snapshot_scan, 'urlopen', return_value=io.BytesIO(
                b'{"results":[{"error":{"code":503,"message":"unavailable"}}]}')):
            with self.assertRaises(Invalid): audit.snapshot_scan.query([self.purl])

    def test_stale_inventory_baseline_is_rejected_without_findings(self):
        self.ledger['records'] = []
        self.ledger['reviewed_on'] = '2026-01-01'
        with self.assertRaises(Invalid): audit.load_ledger(self.ledger, self.groups, TODAY)

    def test_candidate_scans_keep_every_match_unreviewed_and_source_bound(self):
        root = Path(__file__).resolve().parents[1]
        reports = sorted((root / 'docs/dependency-evidence').glob('legacy-candidate*osv-2026-11-05.json'))
        self.assertTrue(reports)
        evidence = audit.read_json(root / 'docs/legacy-candidate-evidence.json')
        candidates = evidence['groups']
        baseline = candidate_audit.load_baseline(audit.read_json(candidate_audit.BASELINE), evidence,
                                                 today=date(2026, 11, 5))
        seen = set()
        for path in reports:
            report = audit.read_json(path)
            self.assertEqual(report['status'], 'complete-unreviewed-candidate-scan')
            self.assertFalse(report['risk_acceptance'])
            for group, entry in report['groups'].items():
                self.assertNotIn(group, seen)
                seen.add(group)
                self.assertEqual(entry['ref'], 'refs/pull/' + candidates[group]['pull_request'].rsplit('/', 1)[-1] + '/merge')
                self.assertRegex(entry['source_sha'], r'^[a-f0-9]{40}$')
                self.assertEqual(entry['source_sha'], baseline[group]['source_sha'])
                self.assertIn('gradle', entry['inventories'])
                self.assertEqual(set(entry['runtime_manifests']),
                                 {s.removeprefix('runtime/') for s in entry['inventories'] if s.startswith('runtime/')})
                queried = set().union(*map(set, entry['inventories'].values()))
                expected = {(purl, identifier) for purl, ids in report['findings'].items()
                            if purl in queried for identifier in ids}
                self.assertEqual(expected, {(m['purl'], m['advisory']) for m in entry['matches']})
                for match in entry['matches']:
                    self.assertEqual(match['key'], audit.identity(group, match['purl'], match['advisory']))
                    self.assertEqual(match['fingerprint'], audit.advisory_fingerprint(report['advisories'][match['advisory']]))
                    self.assertEqual(match['scopes'], sorted(k for k, v in entry['inventories'].items() if match['purl'] in v))
                    self.assertTrue(match['failing'])
                    self.assertEqual(match['review_status'], 'awaiting investigation')
                    self.assertEqual(match['disposition'], 'Further investigation')
        self.assertEqual(seen, set(candidates))

    def test_checked_in_ledger_covers_configured_inventories(self):
        root = Path(__file__).resolve().parents[1]
        groups = audit.read_json(root / 'release/compatibility.json')['groups']
        ledger = audit.read_json(root / 'docs/security-advisories.json')
        audit.load_ledger(ledger, groups)
        for group in groups:
            report = audit.read_json(root / 'docs/dependency-evidence' / (group + '.json'))
            result = audit.compare(group, report['inventories'], report['findings'], ledger['advisories'], ledger, groups)
            self.assertTrue(result['failing'])  # Unresolved risk was not accepted to make CI green.
            self.assertTrue(all(m['state'] == 'known' for m in result['matches']))


if __name__ == '__main__':
    unittest.main()
