"""Keep the dated hierarchy-review observations tied to their original inputs."""
import hashlib
import json
import ast
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/version-consistency-1.0.0/hierarchy-2026-11-15'
REHEARSAL = ROOT / 'docs/legacy-dry-run-1.0.0-2026-11-14/hierarchy-2026-11-15'


class HierarchyHistoricalEvidenceTests(unittest.TestCase):
    def test_builds_and_static_checks_bind_historical_sources(self):
        plan = json.loads((REHEARSAL / 'candidate-plan.json').read_text())['groups']
        builds = json.loads((EVIDENCE / 'builds.json').read_text())
        static = json.loads((EVIDENCE / 'static.json').read_text())['results']
        inventory = json.loads((EVIDENCE / 'hierarchy-inventory.json').read_text())['groups']
        logs = json.loads((EVIDENCE / 'validation-logs.json').read_text())
        config = json.loads((REHEARSAL / 'candidate-compatibility.json').read_text())['groups']
        self.assertEqual(set(plan), set(builds))
        self.assertEqual(set(plan), set(inventory))
        self.assertEqual(set(plan), set(config))
        self.assertEqual(len(plan), 13)
        expected = {(group, version) for group, row in config.items() for version in row['minecraft']}
        self.assertEqual(len(expected), 48)
        self.assertEqual({(row['group'], row['version']) for row in static}, expected)
        self.assertEqual(len(static), len(expected))
        for group, row in builds.items():
            with self.subTest(group=group):
                self.assertEqual(row['source_commit'], plan[group]['commit'])
                self.assertEqual(row['same_as_previous'], row['sha256'] == row['previous_sha256'])
                self.assertEqual(inventory[group]['candidate_source'], row['source_commit'])
                self.assertEqual(inventory[group]['artifact_sha256'], row['sha256'])
                log = logs['builds'][group].encode()
                self.assertEqual(hashlib.sha256(log).hexdigest(), row['log_sha256'])
                self.assertIn(b'Verified Gradle ', log)
                self.assertIn(b'BUILD SUCCESSFUL', log)
        for row in static:
            with self.subTest(version=row['version']):
                self.assertEqual(row['exit_code'], 0)
                self.assertEqual(row['source_commit'], builds[row['group']]['source_commit'])
                self.assertEqual(row['artifact_sha256'], builds[row['group']]['sha256'])
                self.assertEqual(hashlib.sha256(logs['static'][row['version']].encode()).hexdigest(),
                                 row['log_sha256'])

    def test_negative_controls_and_candidate_rehearsal_remain_non_publishing(self):
        builds = json.loads((EVIDENCE / 'builds.json').read_text())
        negatives = json.loads((EVIDENCE / 'negative.json').read_text())
        logs = json.loads((EVIDENCE / 'validation-logs.json').read_text())
        self.assertEqual(len(negatives), 9)
        for key, row in negatives.items():
            self.assertTrue(row['discriminating_rejection'])
            self.assertNotEqual(row['exit_code'], 0)
            self.assertEqual(row['source_commit'], builds[row['group']]['source_commit'])
            self.assertEqual(hashlib.sha256(logs['negative'][key].encode()).hexdigest(), row['log_sha256'])
        controls = json.loads((REHEARSAL / 'negative-controls.json').read_text())
        self.assertEqual(len(controls), 18)
        self.assertTrue({'candidate-publication', 'missing-static-evidence', 'failed-static-evidence',
                         'missing-wrapper-preflight-evidence'} <= set(controls))
        tree = ast.parse((REHEARSAL / 'rehearse.py').read_text())
        harness_controls = set()
        for call in ast.walk(tree):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and
                    call.func.id == 'reject' and len(call.args) >= 2 and
                    isinstance(call.args[0], ast.Constant) and
                    any(isinstance(node, ast.Name) and node.id == 'verify_candidate_evidence'
                        for node in ast.walk(call.args[1]))):
                harness_controls.add(call.args[0].value)
        self.assertEqual(harness_controls, {'missing-static-evidence', 'failed-static-evidence',
                                            'missing-wrapper-preflight-evidence'})
        self.assertIn('checks by this harness, not new claims about the production aggregator',
                      (REHEARSAL / 'README.md').read_text())
        plan = json.loads((REHEARSAL / 'candidate-plan.json').read_text())
        self.assertEqual(plan['version'], '1.0.0')
        for group, row in builds.items():
            self.assertEqual(plan['groups'][group]['commit'], row['source_commit'])
            self.assertIn(row['sha256'] + '  ' + row['artifact'], (REHEARSAL / 'SHA256SUMS').read_text())

    def test_hosted_jobs_bind_synthetic_checkout_and_uploaded_jars(self):
        builds = json.loads((EVIDENCE / 'builds.json').read_text())
        hosted = json.loads((EVIDENCE / 'hosted-checks.json').read_text())['groups']
        self.assertEqual(set(hosted), set(builds))
        for group, row in hosted.items():
            with self.subTest(group=group):
                self.assertEqual(row['head_sha'], builds[group]['source_commit'])
                self.assertEqual(row['head_tree'], row['merge_tree'])
                self.assertEqual(set(row['checks']), {'ubuntu-latest', 'windows-latest'})
                for check in row['checks'].values():
                    self.assertEqual(check['conclusion'], 'SUCCESS')
                    self.assertEqual(check['checkout_merge_sha'], row['merge_sha'])
                    self.assertEqual(check['artifact_sha256'], builds[group]['sha256'])
                    self.assertEqual(check['artifact_filename'], builds[group]['artifact'])
                    self.assertTrue(check['archive_and_jar_verified'])
                    self.assertRegex(check['archive_sha256'], r'^[0-9a-f]{64}$')

    def test_dependency_continuity_does_not_relabel_old_reports(self):
        builds = json.loads((EVIDENCE / 'builds.json').read_text())
        continuity = json.loads((EVIDENCE / 'dependency-continuity.json').read_text())['groups']
        self.assertEqual(set(continuity), set(builds))
        for group, row in continuity.items():
            with self.subTest(group=group):
                self.assertEqual(row['previous_source'], builds[group]['previous_source'])
                self.assertEqual(row['current_source'], builds[group]['source_commit'])
                self.assertTrue(all(path.startswith(('scripts/', 'tests/', 'docs/verification/'))
                                    for path in row['changed_paths']))
                self.assertFalse(row['fresh_dependency_resolution'])
                self.assertFalse(row['strict_source_evidence_satisfied'])
                raw = (ROOT / row['retained_report']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['retained_report_sha256'])
                self.assertEqual(json.loads(raw)['source_sha'], row['previous_source'])

    def test_security_only_hosted_jars_preserve_002(self):
        rows = json.loads((EVIDENCE / 'security-hosted-checks.json').read_text())['prs']
        self.assertEqual(set(rows), {'34', '35', '35-previous', '36'})
        for pr, row in rows.items():
            with self.subTest(pr=pr):
                self.assertEqual(set(row['artifacts']), {'Linux', 'Windows'})
                linux, windows = row['artifacts']['Linux'], row['artifacts']['Windows']
                self.assertEqual(linux['artifact_sha256'], windows['artifact_sha256'])
                self.assertEqual((linux['mod_version'], windows['mod_version']), ('0.0.2', '0.0.2'))
                self.assertRegex(linux['archive_sha256'], r'^[0-9a-f]{64}$')
                self.assertRegex(windows['archive_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(rows['35']['artifacts']['Linux']['artifact_sha256'],
                         rows['35-previous']['artifacts']['Linux']['artifact_sha256'])

    def test_instrumented_lan_repeat_keeps_its_scope_and_provenance(self):
        directory = ROOT / 'docs/multiplayer-smoke-2026-11-14/instrumented-2026-11-15'
        evidence = json.loads((directory / 'index.json').read_text())
        build = json.loads((EVIDENCE / 'builds.json').read_text())['1.21.11']
        self.assertEqual(evidence['source_commit'], build['source_commit'])
        self.assertEqual(evidence['artifact_sha256'], build['sha256'])
        self.assertIn('observer-only Java agent', evidence['mode'])
        self.assertIn('No packet handler was instrumented', evidence['limitations'])
        for name, digest in evidence['files_sha256'].items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        with ZipFile(directory / 'diagnostic-agent.zip') as archive:
            self.assertEqual(hashlib.sha256(archive.read('probe-jdk.jar')).hexdigest(),
                             evidence['agent_jar_sha256'])
            self.assertEqual(archive.read('agent-manifest-input.mf'),
                             b'Manifest-Version: 1.0\nPremain-Class: tprm.probe.MapDataAgent\n\n')
        observer = (directory / 'observer.log').read_text()
        self.assertIn(evidence['first_unavailable'], observer)
        self.assertIn(evidence['first_available'], observer)
        self.assertLess(observer.index(evidence['first_unavailable']), observer.index(evidence['first_available']))
        self.assertIn('id=class_9209[id=2]', evidence['first_unavailable'])
        self.assertIn('data_available=false', evidence['first_unavailable'])
        self.assertIn('data_available=true', evidence['first_available'])
        self.assertIn(evidence['host_give'], (directory / 'host.log').read_text())
        self.assertEqual(evidence['host_give'][:10], evidence['first_available'][:10])


if __name__ == '__main__':
    unittest.main()
