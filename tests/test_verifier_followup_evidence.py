"""Keep advanced-head build and partial runtime evidence source-bound."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / 'docs/builds-verifier-followup-2026-11-13'
RUNTIME = ROOT / 'docs/runtime-smoke-verifier-followup-2026-11-13'


class VerifierFollowupEvidenceTests(unittest.TestCase):
    def test_adjacent_version_negative_controls_match_new_sources(self):
        directory = ROOT / 'docs/negative-verifier-followup-2026-11-13'
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
        groups = {row['id']: row for row in manifest['groups']}
        evidence = json.loads((directory / 'index.json').read_text())
        self.assertEqual(len(evidence), 9)
        for key, row in evidence.items():
            with self.subTest(case=key):
                group = row['group']
                self.assertEqual(row['source_commit'], refs[group]['new_head'])
                self.assertEqual(row['artifact_sha256'], builds[group]['sha256'])
                self.assertNotIn(row['unsupported_version'], groups[group]['minecraft'])
                self.assertNotEqual(row['exit_code'], 0)
                self.assertTrue(row['discriminating_rejection'])
                raw = (directory / row['log']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['log_sha256'])
                self.assertTrue(any(needle in raw for needle in (b'missing Mixin target', b'missing classes',
                                b'missing game members', b'missing game or descriptor classes')))

    def test_clean_build_records_match_advanced_source_heads(self):
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        evidence = json.loads((BUILDS / 'index.json').read_text())
        self.assertEqual(set(evidence['groups']), set(refs))
        self.assertEqual(hashlib.sha256((BUILDS / 'run.py').read_bytes()).hexdigest(), evidence['runner_sha256'])
        for group, row in evidence['groups'].items():
            with self.subTest(group=group):
                self.assertEqual(row['source_commit'], refs[group]['new_head'])
                self.assertEqual(row['branch'], refs[group]['branch'])
                self.assertTrue(row['same_as_previous'])
                self.assertEqual(row['sha256'], refs[group]['artifact_sha256_before_rebuild'])
                self.assertIn(row['runner_variant'], {'initial runner, exact source not retained', 'retained resumed runner'})
                raw = (BUILDS / (group + '-build.log')).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['log_sha256'])
                self.assertIn(b'BUILD SUCCESSFUL', raw)

    def test_partial_runtime_observations_match_new_heads_and_artifacts(self):
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        manifest = json.loads((ROOT / 'docs/historical-verifier-followup-2026-11-13/release-manifest.json').read_text())
        expected = {version: group['id'] for group in manifest['groups'] for version in group['minecraft']}
        index = json.loads((RUNTIME / 'index.json').read_text())
        self.assertEqual(len(expected), 48)
        self.assertEqual(set(index['expected_versions']), set(expected))
        self.assertTrue(index['versions'])
        self.assertEqual(set(index['pending_versions']), set(expected) - set(index['versions']))
        for name, digest in index['harness_sha256'].items():
            self.assertEqual(hashlib.sha256((RUNTIME / 'harness' / name).read_bytes()).hexdigest(), digest)
        for version, row in index['versions'].items():
            with self.subTest(version=version):
                group = expected[version]
                self.assertEqual(row['group'], group)
                self.assertEqual(row['source_commit'], refs[group]['new_head'])
                self.assertEqual(row['artifact_sha256'], builds[group]['sha256'])
                self.assertEqual(set(row['files_sha256']), {'movement.json', 'ending-player.dat', 'walking-1.png', 'walking-2.png', 'client.log'})
                for name, digest in row['files_sha256'].items():
                    self.assertEqual(hashlib.sha256((RUNTIME / version / name).read_bytes()).hexdigest(), digest)
                movement = json.loads((RUNTIME / version / 'movement.json').read_text())
                self.assertEqual(movement['source_commit'], row['source_commit'])
                self.assertEqual(movement['candidate_sha256'], row['artifact_sha256'])
                self.assertGreater(movement['horizontal_distance'], 0.5)
                log = (RUNTIME / version / 'client.log').read_text(errors='replace')
                self.assertIn('MapSmokeTest joined the game', log)
                self.assertFalse(any(err in log for err in ('MixinApplyError', 'InvalidInjectionException', 'NoSuchMethodError', 'MixinTransformerError')))


if __name__ == '__main__':
    unittest.main()
