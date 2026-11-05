import copy
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_candidate_dependencies as candidate
from release import Invalid


class CandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.group = '1.14-1.14.4'
        self.branch = 'candidate/mc-' + self.group
        self.sha = 'a' * 40
        self.evidence = {'schema': 1, 'groups': {self.group: {
            'candidate_head': self.sha, 'versions': ['1.14', '1.14.4'],
            'pull_request': 'https://github.com/skyRolly/third-person-readable-maps/pull/23'}}}
        self.metadata = {'id': 'thirdpersonreadablemaps', 'depends': {'minecraft': ['1.14', '1.14.4']}}
        self.purl = 'pkg:maven/example/package@1.0'
        self.snapshot = {'sha': self.sha, 'ref': 'refs/heads/' + self.branch,
                         'manifests': {'build': {'resolved': {'x': {'package_url': self.purl}}}}}
        self.inventories = {'runtime/1.14': [self.purl], 'runtime/1.14.4': [self.purl]}
        self.manifests = {'1.14': {'sha1': 'b' * 40}, '1.14.4': {'sha1': 'c' * 40}}
        self.advisory = {'id': 'OSV-TEST-1', 'modified': '2026-11-05T00:00:00Z',
                         'details': 'test advisory', 'affected': [{'package': {'name': 'example'}}],
                         'database_specific': {'severity': 'HIGH'}}

    def run_audit(self, snapshot=None, metadata=None, evidence=None, branch=None, sha=None, observed=None):
        return candidate.audit_candidate(snapshot or self.snapshot, metadata or self.metadata,
                evidence or self.evidence, self.group, branch or self.branch,
                sha or self.sha, observed or self.sha)

    def test_matrix_covers_reviewed_source_pins_and_rejects_overlap(self):
        matrix = candidate.candidate_matrix(self.evidence)
        self.assertEqual(matrix['include'], [{'group': self.group, 'branch': self.branch, 'sha': self.sha}])
        evidence = copy.deepcopy(self.evidence)
        evidence['groups']['1.14.4'] = {'candidate_head': 'd' * 40, 'versions': ['1.14.4'],
                                       'pull_request': self.evidence['groups'][self.group]['pull_request']}
        with self.assertRaises(Invalid):
            candidate.candidate_matrix(evidence)

    def test_match_is_unreviewed_failing_and_scoped_to_each_runtime(self):
        with patch.object(candidate.audit, 'runtime_inventories', return_value=(copy.deepcopy(self.inventories), self.manifests)), \
             patch.object(candidate.scanner, 'query', return_value={self.purl: ['OSV-TEST-1']}) as query, \
             patch.object(candidate.audit, 'get_json', return_value=self.advisory):
            report = self.run_audit()
        query.assert_called_once_with([self.purl])
        self.assertFalse(report['risk_acceptance'])
        self.assertEqual(report['snapshot_ref'], 'refs/heads/' + self.branch)
        match = report['matches'][0]
        self.assertEqual(match['scopes'], ['gradle', 'runtime/1.14', 'runtime/1.14.4'])
        self.assertEqual(match['key'], self.group + '|' + self.purl + '|OSV-TEST-1')
        self.assertEqual(match['review_status'], 'awaiting investigation')
        self.assertEqual(match['disposition'], 'Further investigation')
        self.assertTrue(match['failing'])

    def test_wrong_ref_head_metadata_and_missing_package_fail_before_osv(self):
        bad_snap = copy.deepcopy(self.snapshot)
        bad_snap['ref'] = 'refs/pull/24/merge'
        bad_sha = copy.deepcopy(self.snapshot)
        bad_sha['sha'] = 'f' * 40
        bad_meta = copy.deepcopy(self.metadata)
        bad_meta['depends']['minecraft'] = ['1.14']
        skipped = copy.deepcopy(self.snapshot)
        skipped['manifests']['build']['resolved']['unknown'] = {}
        with patch.object(candidate.scanner, 'query') as query:
            for kwargs in ({'snapshot': bad_snap}, {'snapshot': bad_sha}, {'metadata': bad_meta}, {'snapshot': skipped},
                           {'branch': 'candidate/mc-1.15'}, {'observed': 'e' * 40}):
                with self.subTest(kwargs=kwargs), self.assertRaises(Invalid):
                    self.run_audit(**kwargs)
            query.assert_not_called()

    def test_matching_pr_merge_ref_preserves_actual_ref(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['ref'] = 'refs/pull/23/merge'
        with patch.object(candidate.audit, 'runtime_inventories', return_value=(copy.deepcopy(self.inventories), self.manifests)), \
             patch.object(candidate.scanner, 'query', return_value={}):
            report = self.run_audit(snapshot=snapshot)
        self.assertEqual(report['snapshot_ref'], 'refs/pull/23/merge')
        self.assertEqual(report['matches'], [])

    def test_unqueried_package_and_missing_advisory_fail(self):
        with patch.object(candidate.audit, 'runtime_inventories', return_value=(copy.deepcopy(self.inventories), self.manifests)), \
             patch.object(candidate.scanner, 'query', return_value={'pkg:maven/other/item@1': ['OSV-TEST-1']}):
            with self.assertRaises(Invalid):
                self.run_audit()
        with patch.object(candidate.audit, 'runtime_inventories', return_value=(copy.deepcopy(self.inventories), self.manifests)), \
             patch.object(candidate.scanner, 'query', return_value={self.purl: ['OSV-TEST-1']}), \
             patch.object(candidate.audit, 'get_json', return_value={'id': 'OSV-TEST-1'}):
            with self.assertRaises(Invalid):
                self.run_audit()

    def test_advisory_with_malformed_severity_is_incomplete(self):
        advisory = copy.deepcopy(self.advisory)
        advisory['database_specific'] = ['not', 'an', 'object']
        with patch.object(candidate.audit, 'runtime_inventories', return_value=(copy.deepcopy(self.inventories), self.manifests)), \
             patch.object(candidate.scanner, 'query', return_value={self.purl: ['OSV-TEST-1']}), \
             patch.object(candidate.audit, 'get_json', return_value=advisory):
            with self.assertRaises(Invalid):
                self.run_audit()

    def test_api_error_writes_incomplete_report_and_returns_two(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            path = source / 'src/main/resources/fabric.mod.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(self.metadata))
            snapshot = Path(temp) / 'snapshot.json'
            snapshot.write_text(json.dumps(self.snapshot))
            evidence = Path(temp) / 'evidence.json'
            evidence.write_text(json.dumps(self.evidence))
            output = Path(temp) / 'report.json'
            argv = ['audit_candidate_dependencies.py', 'audit', '--snapshot', str(snapshot), '--source', str(source),
                    '--group', self.group, '--branch', self.branch, '--source-sha', self.sha,
                    '--output', str(output), '--evidence', str(evidence)]
            with patch.object(sys, 'argv', argv), \
                 patch.object(candidate.subprocess, 'check_output', return_value=self.sha + '\n'), \
                 patch.object(candidate.audit, 'runtime_inventories', side_effect=OSError('unavailable')), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(candidate.main(), 2)
            self.assertEqual(json.loads(output.read_text())['status'], 'incomplete')

    def test_match_returns_failure_and_writes_report(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            path = source / 'src/main/resources/fabric.mod.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(self.metadata))
            snapshot, evidence, output = (Path(temp) / name for name in ('snapshot.json', 'evidence.json', 'report.json'))
            snapshot.write_text(json.dumps(self.snapshot))
            evidence.write_text(json.dumps(self.evidence))
            report = {'status': 'complete-unreviewed-candidate-scan', 'risk_acceptance': False,
                      'matches': [{'failing': True}]}
            argv = ['audit_candidate_dependencies.py', 'audit', '--snapshot', str(snapshot), '--source', str(source),
                    '--group', self.group, '--branch', self.branch, '--source-sha', self.sha,
                    '--output', str(output), '--evidence', str(evidence)]
            with patch.object(sys, 'argv', argv), \
                 patch.object(candidate.subprocess, 'check_output', return_value=self.sha + '\n'), \
                 patch.object(candidate, 'audit_candidate', return_value=report), redirect_stdout(io.StringIO()):
                self.assertEqual(candidate.main(), 1)
            self.assertTrue(json.loads(output.read_text())['matches'][0]['failing'])

    def test_retained_live_report_binds_source_and_fails_on_every_match(self):
        evidence = ROOT / 'docs/dependency-evidence'
        snapshot = json.loads((evidence / 'candidate-audit-114-snapshot-2026-11-05.json').read_text())
        report = json.loads((evidence / 'candidate-audit-114-live-2026-11-05.json').read_text())
        self.assertEqual(report['source_sha'], snapshot['sha'])
        self.assertEqual(report['snapshot_ref'], snapshot['ref'])
        self.assertEqual(report['snapshot_ref'], 'refs/pull/23/merge')
        self.assertFalse(report['risk_acceptance'])
        self.assertTrue(report['matches'])
        purls, skipped = candidate.scanner.packages(snapshot)
        self.assertFalse(skipped)
        self.assertEqual(set(report['inventories']['gradle']), {candidate.audit.canonical(p) for p in purls})
        self.assertEqual({s for s in report['inventories'] if s.startswith('runtime/')},
                         {'runtime/1.14', 'runtime/1.14.1', 'runtime/1.14.2', 'runtime/1.14.3', 'runtime/1.14.4'})
        for match in report['matches']:
            self.assertTrue(match['failing'])
            self.assertEqual(match['review_status'], 'awaiting investigation')
            self.assertEqual(match['fingerprint'], candidate.audit.advisory_fingerprint(report['advisories'][match['advisory']]))
            self.assertEqual(match['scopes'], sorted(k for k, v in report['inventories'].items() if match['purl'] in v))

    def test_scheduled_workflow_uses_read_only_candidate_sources_and_fails_closed(self):
        text = (ROOT / '.github/workflows/candidate-dependency-audit.yml').read_text()
        self.assertIn('schedule:', text)
        self.assertIn('contents: read', text)
        self.assertNotIn('contents: write', text)
        self.assertIn('audit_candidate_dependencies.py matrix', text)
        self.assertIn('audit_candidate_dependencies.py audit', text)
        self.assertIn('git -C source rev-parse HEAD', text)
        self.assertIn('--refresh-dependencies', text)
        self.assertIn('if: always()', text)


if __name__ == '__main__':
    unittest.main()
