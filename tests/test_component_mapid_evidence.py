"""Keep the recorded component-codec observation tied to its original inputs."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'docs/dependency-evidence/component-mapid-codec-2026-11-12'


class ComponentMapIdEvidenceTests(unittest.TestCase):
    def test_probe_and_metadata_match_recorded_observations(self):
        report = json.loads((DIRECTORY / 'results.json').read_text())
        self.assertEqual(hashlib.sha256((DIRECTORY / 'MapCodecProbe.java').read_bytes()).hexdigest(),
                         report['probe_source_sha256'])
        self.assertEqual(hashlib.sha256((DIRECTORY / 'run.py').read_bytes()).hexdigest(), report['runner_sha256'])
        self.assertIn('25', report['java_version'])
        self.assertEqual(set(report['cases']), {'1.21.11', '26.1.2'})
        expected = ['explicit_zero=0', 'explicit_seven=7', 'fractional_double=0',
                    'overflow_long=0', 'nan_double=0', 'string=error']
        for version, result in report['cases'].items():
            with self.subTest(version=version):
                raw = (DIRECTORY / (version + '-metadata.json')).read_bytes()
                metadata = json.loads(raw)
                self.assertEqual(hashlib.sha1(raw).hexdigest(), result['metadata_sha1'])
                self.assertEqual(metadata['id'], version)
                self.assertEqual(metadata['downloads']['client']['sha1'], result['client_sha1'])
                self.assertEqual(metadata['downloads']['client']['url'], result['client_url'])
                library = next(lib for lib in metadata['libraries'] if lib['name'] == result['datafixerupper'])
                artifact = library['downloads']['artifact']
                self.assertEqual(artifact['sha1'], result['datafixerupper_sha1'])
                self.assertEqual(result['verified_library_artifacts'][artifact['path']], artifact['sha1'])
                self.assertEqual(result['output'], expected)
                if version == '1.21.11':
                    self.assertEqual(result['official_mapping']['sha1'], metadata['downloads']['client_mappings']['sha1'])


if __name__ == '__main__':
    unittest.main()
