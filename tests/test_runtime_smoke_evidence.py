"""Protect the identity and retained files of partial local runtime observations."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/runtime-smoke-1.0.0'


class RuntimeSmokeEvidenceTests(unittest.TestCase):
    def test_additional_no_mod_controls_remain_separate_from_candidates(self):
        directory = ROOT / 'docs/foreground-comparisons-2026-11-13'
        evidence = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        groups = {group['id']: group for group in manifest['groups']}
        self.assertEqual(hashlib.sha256((directory / 'run.py').read_bytes()).hexdigest(), evidence['runner_sha256'])
        self.assertEqual(set(evidence['versions']), {'1.21.1', '1.21.5', '1.21.10'})
        for version, row in evidence['versions'].items():
            with self.subTest(version=version):
                group = groups[row['group']]
                self.assertIn(version, group['minecraft'])
                self.assertEqual(row['candidate_head'], group['source_commit'])
                self.assertEqual(row['candidate_artifact_sha256'], group['sha256'])
                for name, digest in row['control_files_sha256'].items():
                    self.assertEqual(hashlib.sha256((directory / version / name).read_bytes()).hexdigest(), digest)
                control = json.loads((directory / version / 'movement.json').read_text())
                candidate = json.loads((ROOT / row['candidate_evidence'] / 'movement.json').read_text())
                self.assertEqual(control['paired_candidate_sha256'], candidate['candidate_sha256'])
                self.assertEqual(control['start'], candidate['start'])
                self.assertGreater(control['horizontal_distance'], 0.5)
                log = (directory / version / 'client.log').read_text(errors='replace')
                self.assertIn('MapSmokeTest joined the game', log)
                self.assertNotIn('thirdpersonreadablemaps', log.lower())
                self.assertIn('thirdpersonreadablemaps', (ROOT / row['candidate_evidence'] / 'client.log').read_text(errors='replace').lower())

    def test_1_20_6_no_mod_control_is_separate_from_the_candidate(self):
        directory = ROOT / 'docs/foreground-comparison-1.20.6-2026-11-13'
        evidence = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        group = next(group for group in manifest['groups'] if group['id'] == '1.20.5-1.20.6')
        self.assertEqual(evidence['candidate_head'], group['source_commit'])
        self.assertEqual(evidence['candidate_artifact_sha256'], group['sha256'])
        for name, digest in evidence['control_files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        control = json.loads((directory / 'movement.json').read_text())
        candidate = json.loads((ROOT / evidence['candidate_evidence'] / 'movement.json').read_text())
        self.assertEqual(control['paired_candidate_sha256'], candidate['candidate_sha256'])
        self.assertEqual(control['start'], candidate['start'])
        self.assertGreater(control['horizontal_distance'], 0.5)
        self.assertIn('MapSmokeTest joined the game', (directory / 'client.log').read_text(errors='replace'))
        self.assertNotIn('thirdpersonreadablemaps', (directory / 'client.log').read_text(errors='replace').lower())
        self.assertIn('thirdpersonreadablemaps', (ROOT / evidence['candidate_evidence'] / 'client.log').read_text(errors='replace').lower())

    def test_26_3_egl_startup_records_the_harness_failure(self):
        directory = DIRECTORY / '26.3-egl-startup-attempt'
        evidence = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        group = next(group for group in manifest['groups'] if group['id'] == '26.3')
        self.assertEqual(evidence['status'], 'PASS local-world startup; walking harness failed')
        self.assertEqual(evidence['source_commit'], group['source_commit'])
        self.assertEqual(evidence['artifact_sha256'], group['sha256'])
        for name, digest in evidence['files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        log = (directory / 'client.log').read_text(errors='replace')
        self.assertIn('Using graphics backend OpenGL', log)
        self.assertIn('MapSmokeTest joined the game', log)
        self.assertIn('AssertionError', (directory / 'runner.log').read_text(errors='replace'))
        self.assertFalse(any(error in log for error in ('MixinApplyError', 'InvalidInjectionException',
                                                         'NoSuchMethodError', 'MixinTransformerError')))

    def test_26_3_backend_failure_is_not_counted_as_a_success(self):
        directory = DIRECTORY / '26.3-backend-attempt'
        evidence = json.loads((directory / 'index.json').read_text())
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        group = next(group for group in manifest['groups'] if group['id'] == '26.3')
        self.assertTrue(evidence['status'].startswith('blocked:'))
        self.assertEqual(evidence['source_commit'], group['source_commit'])
        self.assertEqual(evidence['artifact_sha256'], group['sha256'])
        for name, digest in evidence['files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        log = (directory / 'client.log').read_text(errors='replace')
        self.assertIn('Failed to create backend OpenGL', log)
        self.assertIn('Failed to create backend Vulkan', log)
        self.assertNotIn('MapSmokeTest joined the game', log)

    def test_archived_harness_checksums(self):
        directory = DIRECTORY / 'harness'
        lines = (directory / 'SHA256SUMS').read_text().splitlines()
        self.assertTrue(lines)
        for line in lines:
            digest, name = line.split('  ', 1)
            self.assertEqual(Path(name).name, name)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)

    def test_walk_observations_match_proposed_artifacts_and_retained_files(self):
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        groups = {group['id']: group for group in manifest['groups']}
        index = json.loads((DIRECTORY / 'index.json').read_text())
        self.assertEqual(index['schema'], 1)
        expected_versions = {version for group in manifest['groups'] for version in group['minecraft']}
        self.assertEqual(set(index['versions']), expected_versions)
        expected_files = {'movement.json', 'ending-player.dat', 'walking-1.png', 'walking-2.png', 'client.log'}
        for version, evidence in index['versions'].items():
            with self.subTest(version=version):
                group = groups[evidence['group']]
                self.assertIn(version, group['minecraft'])
                self.assertEqual(evidence['candidate_head'], group['source_commit'])
                self.assertEqual(evidence['artifact_sha256'], group['sha256'])
                expected_kind = 'maintenance-proposal' if group['branch'].startswith('maintenance/') else 'legacy-candidate'
                self.assertEqual(evidence['source_kind'], expected_kind)
                files = set(evidence['files_sha256'])
                self.assertTrue(expected_files <= files)
                self.assertTrue(files <= expected_files | {'runner.log'})
                for name, digest in evidence['files_sha256'].items():
                    raw = (DIRECTORY / version / name).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
                    if name.endswith('.png'):
                        self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
                movement = json.loads((DIRECTORY / version / 'movement.json').read_text())
                self.assertEqual(movement['minecraft'], version)
                self.assertEqual(movement['candidate_sha256'], evidence['artifact_sha256'])
                self.assertGreater(movement['horizontal_distance'], 0.5)
                if version == '26.3':
                    self.assertIn('manual', movement['note'])
                    self.assertIn('Client exited before All dimensions are saved',
                                  (DIRECTORY / version / 'runner.log').read_text(errors='replace'))
                log = (DIRECTORY / version / 'client.log').read_text(errors='replace')
                self.assertIn('MapSmokeTest joined the game', log)
                self.assertFalse(any(error in log for error in ('MixinApplyError', 'InvalidInjectionException',
                                                                 'NoSuchMethodError', 'MixinTransformerError')))


if __name__ == '__main__':
    unittest.main()
