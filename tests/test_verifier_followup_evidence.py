"""Keep advanced-head build and partial runtime evidence source-bound."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / 'docs/builds-verifier-followup-2026-11-13'
RUNTIME = ROOT / 'docs/runtime-smoke-verifier-followup-2026-11-13'
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_candidate_dependencies as candidate_audit


class VerifierFollowupEvidenceTests(unittest.TestCase):
    def test_candidate_monitoring_pins_advanced_heads(self):
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        evidence = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())
        rows = candidate_audit.candidate_matrix(evidence)['include']
        self.assertEqual(len(rows), 10)
        for row in rows:
            self.assertEqual(row['sha'], refs[row['group']]['new_head'])
            self.assertEqual(row['branch'], refs[row['group']]['branch'])

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
                required = {'movement.json', 'ending-player.dat', 'walking-1.png', 'walking-2.png', 'client.log'}
                self.assertTrue(required <= set(row['files_sha256']))
                self.assertLessEqual(set(row['files_sha256']) - required,
                                     {'launcher-pins.json', 'operator-note.txt', 'world-upgrade-prompt.png'})
                for name, digest in row['files_sha256'].items():
                    self.assertEqual(hashlib.sha256((RUNTIME / version / name).read_bytes()).hexdigest(), digest)
                if 'launcher-pins.json' in row['files_sha256']:
                    pins = json.loads((RUNTIME / version / 'launcher-pins.json').read_text())
                    self.assertTrue(pins['libraries'])
                    for library in pins['libraries']:
                        self.assertRegex(library['sha1'], r'^[0-9a-f]{40}$')
                        self.assertRegex(library['sha256'], r'^[0-9a-f]{64}$')
                movement = json.loads((RUNTIME / version / 'movement.json').read_text())
                self.assertEqual(movement['source_commit'], row['source_commit'])
                self.assertEqual(movement['candidate_sha256'], row['artifact_sha256'])
                self.assertGreater(movement['horizontal_distance'], 0.5)
                log = (RUNTIME / version / 'client.log').read_text(errors='replace')
                self.assertIn('MapSmokeTest joined the game', log)
                self.assertFalse(any(err in log for err in ('MixinApplyError', 'InvalidInjectionException', 'NoSuchMethodError', 'MixinTransformerError')))

    def test_failed_initialization_attempt_remains_separate(self):
        attempt = RUNTIME / '1.21.11-initialization-attempt'
        row = json.loads((attempt / 'index.json').read_text())
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        self.assertEqual(row['source_commit'], builds['1.21.11']['source_commit'])
        self.assertEqual(row['artifact_sha256'], builds['1.21.11']['sha256'])
        self.assertIn('FAILED', row['result'])
        for name, digest in row['files_sha256'].items():
            self.assertEqual(hashlib.sha256((attempt / name).read_bytes()).hexdigest(), digest)
        self.assertIn('No mixin global property service is available', (attempt / 'client.log').read_text())

    def test_world_upgrade_timeout_remains_separate(self):
        attempt = RUNTIME / '26.1-upgrade-timeout-attempt'
        row = json.loads((attempt / 'index.json').read_text())
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        self.assertEqual(row['source_commit'], builds['26.1-26.2']['source_commit'])
        self.assertEqual(row['artifact_sha256'], builds['26.1-26.2']['sha256'])
        self.assertIn('NOT COMPLETED', row['result'])
        for name, digest in row['files_sha256'].items():
            self.assertEqual(hashlib.sha256((attempt / name).read_bytes()).hexdigest(), digest)
        self.assertIn('timeouterror', (attempt / 'runner.log').read_text().lower())

    def test_artifact_operation_inventory_matches_proposed_sources(self):
        path = ROOT / 'docs/artifact-linkage-inventory-2026-11-13/index.json'
        index = json.loads(path.read_text())
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        self.assertEqual(set(index['groups']), set(builds))
        self.assertRegex(index['parser_sha256'], r'^[0-9a-f]{64}$')
        for group, row in index['groups'].items():
            with self.subTest(group=group):
                self.assertEqual(row['source_commit'], builds[group]['source_commit'])
                self.assertEqual(row['artifact'], builds[group]['artifact'])
                self.assertEqual(row['artifact_sha256'], builds[group]['sha256'])
                self.assertGreater(row['class_count'], 0)
                self.assertEqual(row['external_or_inherited_field_writes'], [])
                self.assertEqual(row['external_or_inherited_nonconstructor_invokespecial'], [])

    def test_tracked_tree_inventory_is_bound_to_all_product_heads(self):
        path = ROOT / 'docs/repository-file-inventory-2026-11-13/index.json'
        index = json.loads(path.read_text())
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        products = {group: row for group, row in index['sources'].items()
                    if row['kind'] == 'proposed-product-head'}
        self.assertEqual(set(products), set(refs))
        for group, source in products.items():
            self.assertEqual(source['commit'], refs[group]['new_head'])
            self.assertEqual(source['mod_version'], '1.0.0')
            self.assertTrue(source['readme_title_and_introduction_match'])
            self.assertTrue(source['readme_branch_badge_matches'])
            self.assertEqual(source['tracked_files'], sum(group in row['product_objects']
                                                           for row in index['paths'].values()))
        common = [row for row in index['paths'].values() if len(row['product_objects']) == len(products)]
        self.assertEqual(index['product_common_paths'], len(common))
        identical = [row for row in common
                     if len({(v['mode'], v['type'], v['object']) for v in row['product_objects'].values()}) == 1]
        self.assertEqual(index['product_common_identical_paths'], len(identical))
        self.assertEqual(index['sources']['coordination-snapshot']['commit'],
                         '28a707a1adab682cfd3984ca7b69ca80f6c00552')


if __name__ == '__main__':
    unittest.main()
