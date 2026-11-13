"""Keep the non-publishing rehearsal's retained manifest and checksums consistent."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/legacy-dry-run-1.0.0'


class CandidateRehearsalEvidenceTests(unittest.TestCase):
    def test_manifest_matches_the_candidate_plan_and_checksum_list(self):
        raw = (DIRECTORY / 'release-manifest.json').read_bytes()
        manifest = json.loads(raw)
        plan = json.loads((DIRECTORY / 'candidate-plan.json').read_text())
        config = json.loads((DIRECTORY / 'candidate-compatibility.json').read_text())
        matrix = json.loads((DIRECTORY / 'candidate-matrix.json').read_text())
        checksums = {}
        for line in (DIRECTORY / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ', 1)
            self.assertNotIn(name, checksums)
            checksums[name] = digest
        self.assertTrue(manifest['candidate'])
        self.assertEqual(manifest['version'], '1.0.0')
        self.assertEqual(manifest['version'], plan['version'])
        self.assertEqual(manifest['release_date'], plan['release_date'])
        self.assertRegex(manifest['coordinator_sha'], r'^[0-9a-f]{40}$')
        groups = {entry['id']: entry for entry in manifest['groups']}
        self.assertEqual(len(groups), 13)
        self.assertEqual(set(groups), set(plan['groups']))
        self.assertEqual(set(groups), set(config['groups']))
        self.assertEqual(set(groups), {entry['group'] for entry in matrix})
        versions = [version for group in groups.values() for version in group['minecraft']]
        self.assertEqual(len(versions), 48)
        self.assertEqual(len(set(versions)), 48)
        self.assertEqual(checksums['release-manifest.json'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(len(checksums), 14)
        for name, group in groups.items():
            with self.subTest(group=name):
                self.assertEqual(group['source_commit'], plan['groups'][name]['commit'])
                self.assertEqual(group['branch'], plan['groups'][name]['source_branch'])
                self.assertEqual(group['minecraft'], config['groups'][name]['minecraft'])
                self.assertEqual(checksums[group['artifact']], group['sha256'])

    def test_recorded_negative_controls_and_previous_manifest_are_preserved(self):
        controls = json.loads((DIRECTORY / 'negative-controls.json').read_text())
        expected = {'missing-group', 'wrong-mod-version', 'wrong-candidate-source',
                    'missing-strict-runtime-evidence', 'candidate-publication', 'duplicate-artifact',
                    'wrong-game-metadata', 'wrong-namespace', 'mixed-0.0.2-and-1.0.0-artifacts',
                    'wrong-artifact-classifier', 'duplicate-game-version', 'overlapping-game-version',
                    'strict-rejects-candidate-config', 'changed-artifact-after-checksum',
                    'wrong-remote-source-commit'}
        self.assertEqual(set(controls), expected)
        current = json.loads((DIRECTORY / 'release-manifest.json').read_text())
        histories = [ROOT / 'docs/historical-1.0.0-rehearsal-2026-11-12/evidence',
                     ROOT / 'docs/historical-1.0.0-rehearsal-2026-11-13-a30dff']
        for history in histories:
            with self.subTest(history=history):
                raw = (history / 'release-manifest.json').read_bytes()
                line = next(line for line in (history / 'SHA256SUMS').read_text().splitlines()
                            if line.endswith('  release-manifest.json'))
                self.assertEqual(line.split('  ', 1)[0], hashlib.sha256(raw).hexdigest())
                self.assertNotEqual(json.loads(raw)['coordinator_sha'], current['coordinator_sha'])
        log = (DIRECTORY / 'rehearsal.log').read_text()
        self.assertIn('Validated 13 artifacts for 1.0.0 (candidate=True)', log)
        self.assertIn('REHEARSAL COMPLETE 13 groups; 48 versions; coordinator ' + current['coordinator_sha'], log)


if __name__ == '__main__':
    unittest.main()
