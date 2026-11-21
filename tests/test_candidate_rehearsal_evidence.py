"""Keep the non-publishing rehearsal's retained manifest and checksums consistent."""
import hashlib
import json
from io import BytesIO
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/legacy-dry-run-1.0.0'


class CandidateRehearsalEvidenceTests(unittest.TestCase):
    def test_current_rehearsal_is_source_bound_and_keeps_historical_snapshot(self):
        selection = json.loads((ROOT / 'docs/version-consistency-1.0.0/current-evidence.json').read_text())
        fresh = ROOT / selection['candidate_rehearsal']['index'].rsplit('/', 1)[0]
        index = json.loads((fresh / 'index.json').read_text())
        old = ROOT / 'docs/version-consistency-1.0.0/current-validation/rehearsal'
        historical = json.loads((old / 'index.json').read_text())
        workflow_sha = hashlib.sha256((ROOT / '.github/workflows/release.yml').read_bytes()).hexdigest()
        self.assertNotEqual(historical['coordinator_code_sha256']['.github/workflows/release.yml'], workflow_sha)
        self.assertEqual(index['coordinator_code_sha256']['.github/workflows/release.yml'], workflow_sha)
        self.assertEqual(index['authorizes_release'], False)
        self.assertEqual(index['candidate'], True)
        inputs_raw = (fresh / index['input_record'].split('/')[-1]).read_bytes()
        self.assertEqual(hashlib.sha256(inputs_raw).hexdigest(), index['input_record_sha256'])
        inputs = json.loads(inputs_raw)['groups']
        heads = json.loads((ROOT / 'docs/version-consistency-1.0.0/current-heads.json').read_text())['groups']
        manifest = json.loads((ROOT / selection['candidate_rehearsal']['manifest']).read_text())
        groups = {row['id']: row for row in manifest['groups']}
        self.assertEqual(set(inputs), set(groups))
        self.assertEqual(set(inputs), set(heads))
        for group, row in inputs.items():
            with self.subTest(group=group):
                self.assertEqual(row['source_commit'], heads[group]['new_head'])
                archive = (ROOT / row['archive_path']).read_bytes()
                self.assertEqual(hashlib.sha256(archive).hexdigest(), row['archive_sha256'])
                with ZipFile(BytesIO(archive)) as zipped:
                    self.assertEqual(zipped.namelist(), [groups[group]['artifact']])
                    self.assertEqual(hashlib.sha256(zipped.read(groups[group]['artifact'])).hexdigest(),
                                     groups[group]['sha256'])
                windows_archive = (ROOT / row['windows_archive_path']).read_bytes()
                self.assertEqual(hashlib.sha256(windows_archive).hexdigest(), row['windows_archive_sha256'])
                with ZipFile(BytesIO(windows_archive)) as zipped:
                    self.assertEqual(zipped.namelist(), [groups[group]['artifact']])
                    self.assertEqual(hashlib.sha256(zipped.read(groups[group]['artifact'])).hexdigest(),
                                     groups[group]['sha256'])
        preserved = fresh / 'superseded-current-state'
        snapshot = json.loads((preserved / 'index.json').read_text())
        for original, record in snapshot['files'].items():
            with self.subTest(preserved=original):
                self.assertEqual(hashlib.sha256((ROOT / record['snapshot_path']).read_bytes()).hexdigest(),
                                 record['sha256'])

    def test_new_product_ci_results_match_transition_heads(self):
        transition = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        evidence = json.loads((ROOT / 'docs/hosted-builds-verifier-followup-2026-11-13.json').read_text())['groups']
        self.assertEqual(len(transition), 13)
        self.assertEqual(set(transition), set(evidence))
        for group, row in evidence.items():
            with self.subTest(group=group):
                self.assertEqual(row['source_commit'], transition[group]['new_head'])
                self.assertEqual(set(row['checks']), {'Build (ubuntu-latest)', 'Build (windows-latest)'})
                for check in row['checks'].values():
                    self.assertEqual((check['status'], check['conclusion']), ('COMPLETED', 'SUCCESS'))
                    self.assertTrue(check['completedAt'])
                    self.assertTrue(check['detailsUrl'].startswith('https://github.com/skyRolly/third-person-readable-maps/actions/runs/'))

    def test_pre_followup_snapshot_keeps_original_source_and_manifest_identity(self):
        history = ROOT / 'docs/historical-verifier-followup-2026-11-13'
        transition = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        raw = (history / 'release-manifest.json').read_bytes()
        manifest = json.loads(raw)
        checksums = dict(line.split('  ', 1)[::-1] for line in (history / 'SHA256SUMS').read_text().splitlines())
        self.assertEqual(checksums['release-manifest.json'], hashlib.sha256(raw).hexdigest())
        self.assertEqual({group['id'] for group in manifest['groups']}, set(transition))
        for group in manifest['groups']:
            self.assertEqual(group['source_commit'], transition[group['id']]['old_head'])
            self.assertEqual(group['sha256'], transition[group['id']]['artifact_sha256_before_rebuild'])

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
