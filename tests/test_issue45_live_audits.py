"""Mutation controls for source-bound live audit reconciliation."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_dependencies as audit
import reconcile_issue45_live_audits as live


class LiveAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'evidence'
        shutil.copytree(live.LIVE, self.path)
        self.index_path = self.path / 'artifact-index.json'
        # Every mutation starts from a fixture that actually passes integrity validation.
        baseline = live.reconcile(self.path)
        self.assertEqual(baseline['failing_occurrences'], 490)
        self.assertFalse(baseline['new_occurrences'])
        self.assertFalse(baseline['missing_occurrences_requiring_review'])

    def mutate(self, label, member, operation):
        index = json.loads(self.index_path.read_text())
        item = next(row for row in index['artifacts'] if row['name'] == label)
        path = self.path / 'raw' / (str(item['id']) + '.zip')
        with ZipFile(path) as zipped:
            data = {name: zipped.read(name) for name in zipped.namelist()}
        content = json.loads(data[member])
        operation(content)
        data[member] = (json.dumps(content, indent=2) + '\n').encode()
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as zipped:
            for name, value in data.items():
                zipped.writestr(name, value)
        raw = output.getvalue()
        path.write_bytes(raw)
        item['size'] = len(raw)
        item['digest'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
        self.index_path.write_text(json.dumps(index, indent=2) + '\n')

    def candidate(self, operation):
        self.mutate('candidate-dependency-audit-0', 'candidate-dependency-audit.json', operation)

    def test_baseline_counts_and_blocking_exit(self):
        report = live.reconcile(self.path)
        stored = json.loads((live.LIVE / 'comparison.json').read_text())
        self.assertEqual(report, stored)
        self.assertEqual(report['failing_by_source_kind'], {'candidate': 385, 'integrated': 105})
        self.assertEqual(report['failing_by_severity'], {'CRITICAL': 22, 'HIGH': 177, 'LOW': 17, 'MODERATE': 274})
        self.assertEqual(report['distinct_advisory_ids'], 89)
        self.assertEqual(report['distinct_package_version_advisory_pairs'], 243)
        self.assertFalse(report['security_clearance'])
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/reconcile_issue45_live_audits.py'),
                                 '--live', str(self.path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['failing_occurrences'], 490)

    def test_priority_register_binds_all_critical_and_high_occurrences(self):
        register = live.priority_register(self.path)
        self.assertEqual(register, json.loads((live.LIVE / 'priority-register.json').read_text()))
        self.assertEqual(register['advisory_ids'], 37)
        self.assertEqual(register['occurrences'], 199)
        rows = [row for item in register['advisories'] for row in item['occurrences']]
        self.assertTrue(all(row['release_blocking'] and not row['risk_accepted'] for row in rows))

    def test_current_ledger_points_to_exact_live_evidence(self):
        ledger = json.loads((ROOT / 'docs/security-advisories.json').read_text())
        reference = ledger['latest_live_source_audit']
        comparison = live.reconcile(self.path)
        self.assertEqual(reference['coordinator_sha'], comparison['coordinator_sha'])
        self.assertEqual(reference['candidate_run'], comparison['candidate_run'])
        self.assertEqual(reference['maintenance_run'], comparison['maintenance_run'])
        for label in ('artifact_index', 'comparison', 'priority_register'):
            item = reference[label]
            self.assertEqual(hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest(), item['sha256'])

    def test_duplicate_replaces_occurrence_without_changing_count(self):
        def edit(report):
            report['matches'][0] = report['matches'][1].copy()
        self.candidate(edit)
        with self.assertRaisesRegex(ValueError, 'duplicate live occurrence'):
            live.reconcile(self.path)

    def test_missing_match_is_rejected(self):
        self.candidate(lambda report: report['matches'].pop())
        with self.assertRaisesRegex(ValueError, 'does not cover its findings exactly'):
            live.reconcile(self.path)

    def test_source_change_is_not_compared_as_same_source(self):
        def edit(report):
            report['source_sha'] = '0' * 40
        self.candidate(edit)
        # Keep the tool report bound to the altered source so source comparison is tested.
        self.mutate('candidate-dependency-audit-0', 'gradle-tool-audit.json',
                    lambda tool: tool.update(source_sha='0' * 40))
        with self.assertRaisesRegex(ValueError, 'source changed; comparison requires review'):
            live.reconcile(self.path)

    def test_changed_scope_is_rejected_even_with_valid_archive_digest(self):
        self.candidate(lambda report: report['matches'][0]['scopes'].pop())
        with self.assertRaisesRegex(ValueError, 'scope or advisory fingerprint mismatch'):
            live.reconcile(self.path)

    def test_changed_advisory_is_not_trusted_with_stale_fingerprint(self):
        def edit(report):
            advisory = report['advisories'][report['matches'][0]['advisory']]
            advisory['details'] += ' changed'
        self.candidate(edit)
        with self.assertRaisesRegex(ValueError, 'scope or advisory fingerprint mismatch'):
            live.reconcile(self.path)

    def test_metadata_timestamp_change_is_reported(self):
        def edit(report):
            report['advisories'][report['matches'][0]['advisory']]['modified'] = '2026-11-22T00:00:00Z'
        self.candidate(edit)
        report = live.reconcile(self.path)
        self.assertEqual(len(report['metadata_changed']), 1)
        self.assertEqual(report['failing_occurrences'], 490)

    def test_alias_change_with_updated_fingerprint_still_requires_review(self):
        def edit(report):
            identifier = report['matches'][0]['advisory']
            advisory = report['advisories'][identifier]
            advisory['aliases'].append('CVE-2099-99999')
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.candidate(edit)
        report = live.reconcile(self.path)
        self.assertTrue(report['metadata_changed'])
        self.assertTrue(report['changed_occurrences']['fingerprint'])
        self.assertEqual(report['failing_occurrences'], 490)

    def test_alias_shared_by_different_advisory_ids_is_reported_for_review(self):
        def edit(report):
            identifier = report['matches'][0]['advisory']
            other = next(row['advisory'] for row in report['matches'] if row['advisory'] != identifier)
            advisory = report['advisories'][identifier]
            advisory['aliases'].append(other)
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.candidate(edit)
        result = live.reconcile(self.path)
        self.assertTrue(result['aliases_shared_by_distinct_returned_ids'])

    def test_corrupted_archive_is_rejected_before_parsing(self):
        index = json.loads(self.index_path.read_text())
        item = index['artifacts'][0]
        path = self.path / 'raw' / (str(item['id']) + '.zip')
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'archive size or checksum mismatch'):
            live.reconcile(self.path)

    def test_snapshot_ref_must_match_report(self):
        index = json.loads(self.index_path.read_text())
        item = next(row for row in index['artifacts'] if row['name'].startswith('dependency-graph_'))
        path = self.path / 'raw' / (str(item['id']) + '.zip')
        with ZipFile(path) as zipped:
            member = zipped.namelist()[0]
        self.mutate(item['name'], member, lambda graph: graph.update(ref='refs/heads/wrong'))
        with self.assertRaisesRegex(ValueError, 'snapshot run or branch mismatch'):
            live.reconcile(self.path)

    def test_priority_export_retains_gradle_only_high_finding(self):
        def edit(report):
            # Choose a High advisory outside the focused set, then keep its
            # finding, scopes, and inventories internally consistent.
            row = next(row for row in report['matches'] if row['advisory'] == 'GHSA-4jrv-ppp4-jm57')
            purl = row['purl']
            self.assertIn('gradle', row['scopes'])
            for scope, packages in report['inventories'].items():
                if scope.startswith('runtime/') and purl in packages:
                    packages.remove(purl)
            row['scopes'] = ['gradle']
        self.candidate(edit)
        register = live.priority_register(self.path)
        advisory = next(row for row in register['advisories'] if row['advisory_id'] == 'GHSA-4jrv-ppp4-jm57')
        row = next(row for row in advisory['occurrences'] if row['group'] == '1.14-1.14.4')
        self.assertEqual(row['scopes'], ['gradle'])
        self.assertIn('Gradle-resolved', row['dependency_owner'])
        self.assertTrue(row['release_blocking'])


if __name__ == '__main__':
    unittest.main()
