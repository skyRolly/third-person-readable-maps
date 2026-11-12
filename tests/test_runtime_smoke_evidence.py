"""Protect the identity and retained files of partial local runtime observations."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/runtime-smoke-1.0.0'


class RuntimeSmokeEvidenceTests(unittest.TestCase):
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
        self.assertTrue(index['versions'])
        expected_files = {'movement.json', 'ending-player.dat', 'walking-1.png', 'walking-2.png', 'client.log'}
        for version, evidence in index['versions'].items():
            with self.subTest(version=version):
                group = groups[evidence['group']]
                self.assertIn(version, group['minecraft'])
                self.assertEqual(evidence['candidate_head'], group['source_commit'])
                self.assertEqual(evidence['artifact_sha256'], group['sha256'])
                expected_kind = 'maintenance-proposal' if group['branch'].startswith('maintenance/') else 'legacy-candidate'
                self.assertEqual(evidence['source_kind'], expected_kind)
                self.assertEqual(set(evidence['files_sha256']), expected_files)
                for name, digest in evidence['files_sha256'].items():
                    raw = (DIRECTORY / version / name).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
                    if name.endswith('.png'):
                        self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
                movement = json.loads((DIRECTORY / version / 'movement.json').read_text())
                self.assertEqual(movement['minecraft'], version)
                self.assertEqual(movement['candidate_sha256'], evidence['artifact_sha256'])
                self.assertGreater(movement['horizontal_distance'], 0.5)
                log = (DIRECTORY / version / 'client.log').read_text(errors='replace')
                self.assertIn('MapSmokeTest joined the game', log)
                self.assertFalse(any(error in log for error in ('MixinApplyError', 'InvalidInjectionException',
                                                                 'NoSuchMethodError', 'MixinTransformerError')))


if __name__ == '__main__':
    unittest.main()
