"""Keep advanced-head build and smoke-test evidence source-bound."""
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

    def test_runtime_observations_match_new_heads_and_artifacts(self):
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        manifest = json.loads((ROOT / 'docs/historical-verifier-followup-2026-11-13/release-manifest.json').read_text())
        expected = {version: group['id'] for group in manifest['groups'] for version in group['minecraft']}
        index = json.loads((RUNTIME / 'index.json').read_text())
        self.assertEqual(len(expected), 48)
        self.assertEqual(set(index['expected_versions']), set(expected))
        self.assertTrue(index['versions'])
        self.assertEqual(set(index['pending_versions']), set(expected) - set(index['versions']))
        if not index['pending_versions']:
            self.assertTrue(index['status'].startswith('COMPLETE version coverage'))
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
                                     {'launcher-pins.json', 'operator-note.txt', 'world-upgrade-prompt.png',
                                      'world-upgrade-ocr.txt', 'world-upgrade-completed-prompt.png',
                                      'world-upgrade-completed-ocr.txt'})
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

    def test_inconclusive_item_loading_probe_is_preserved(self):
        directory = ROOT / 'docs/component-map-id-item-loading-2026-11-13/playerdata-only-attempt'
        index = json.loads((directory / 'index.json').read_text())
        self.assertTrue(index['status'].startswith('INCONCLUSIVE'))
        for name, digest in index['files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        self.assertIn('level.dat', index['explanation'])

    def test_corrected_item_loading_probe_is_source_bound(self):
        directory = ROOT / 'docs/component-map-id-item-loading-2026-11-13/host-inventory-attempt'
        index = json.loads((directory / 'index.json').read_text())
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        self.assertEqual(index['source_commit'], builds['1.21.11']['source_commit'])
        self.assertEqual(index['artifact_sha256'], builds['1.21.11']['sha256'])
        self.assertEqual(index['selected_slot'], 3)
        self.assertGreater(index['map_zero_nonblank_color_count'], 1000)
        for name, digest in index['files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        before, after = index['input_inventory'], index['saved_inventory']
        self.assertEqual((before['1']['value'], after['1']['value']), (0, 0))
        self.assertEqual((before['2']['value'], after['2']['value']), (7, 7))
        self.assertEqual((before['3']['tag'], before['3']['value']), ('Double', 0.5))
        self.assertEqual((before['4']['tag'], before['4']['value']), ('Long', 4294967296))
        self.assertEqual((after['3']['tag'], after['3']['value']), ('Int', 0))
        self.assertEqual((after['4']['tag'], after['4']['value']), ('Int', 0))
        self.assertIsNone(before['8']['value'])
        self.assertIsNone(after['8']['value'])

    def test_no_mod_item_loading_control_uses_the_same_inputs(self):
        root = ROOT / 'docs/component-map-id-item-loading-2026-11-13'
        candidate = json.loads((root / 'host-inventory-attempt/index.json').read_text())
        directory = root / 'no-mod-control'
        control = json.loads((directory / 'index.json').read_text())
        self.assertEqual(control['paired_candidate_source_commit'], candidate['source_commit'])
        self.assertEqual(control['paired_candidate_artifact_sha256'], candidate['artifact_sha256'])
        for name in ('level', 'player', 'map_zero'):
            self.assertEqual(control['input_' + name + '_sha256'],
                             candidate['files_sha256']['input-' + name.replace('_', '-') + '.dat'])
        self.assertEqual(control['saved_inventory'], candidate['saved_inventory'])
        for name, digest in control['files_sha256'].items():
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), digest)
        log = (directory / 'client.log').read_text(errors='replace')
        self.assertIn('Loading 4 mods:', log)
        self.assertNotIn('thirdpersonreadablemaps', log)

    def test_foreground_item_controls_retain_identity_and_failed_attempt(self):
        directory = ROOT / 'docs/foreground-item-entities-2026-11-13'
        index = json.loads((directory / 'index.json').read_text())
        builds = json.loads((BUILDS / 'index.json').read_text())['groups']
        self.assertEqual(set(index['variants']), {'candidate', 'control'})
        for name in ('foreground-items-104.py', 'x11-foreground-items-104.py'):
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(),
                             index[name + '_sha256'])
        for variant, row in index['variants'].items():
            self.assertEqual(row['source_commit'], builds['1.21.11']['source_commit'])
            self.assertEqual(row['paired_candidate_sha256'], builds['1.21.11']['sha256'])
            self.assertEqual(row['mod_installed'], variant == 'candidate')
            self.assertEqual(row['nearest_item'], 'minecraft:wheat_seeds')
            self.assertEqual(row['item_entities_cleared'], 8)
            for name, digest in row['files_sha256'].items():
                self.assertEqual(hashlib.sha256((directory / variant / name).read_bytes()).hexdigest(), digest)
            log = (directory / variant / 'client.log').read_text(errors='replace')
            self.assertIn('Wheat Seeds has the following entity data', log)
            self.assertIn('Killed 8 entities', log)
            self.assertEqual('thirdpersonreadablemaps 1.0.0' in log, variant == 'candidate')
        failed = directory / 'invalid-selector-attempt'
        row = json.loads((failed / 'index.json').read_text())
        self.assertTrue(row['status'].startswith('INCONCLUSIVE'))
        for name, digest in row['files_sha256'].items():
            self.assertEqual(hashlib.sha256((failed / name).read_bytes()).hexdigest(), digest)

    def test_managed_submission_runs_do_not_imply_settings_access(self):
        path = ROOT / 'docs/dependency-evidence/automatic-submission-2026-11-13.json'
        index = json.loads(path.read_text())
        refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
        self.assertEqual(set(index['runs']), set(refs))
        self.assertIn('settings access remains unavailable', index['description'])
        for group, run in index['runs'].items():
            self.assertEqual(run['headSha'], refs[group]['new_head'])
            self.assertEqual(run['workflowName'], 'Automatic Dependency Submission')
            self.assertEqual((run['event'], run['status'], run['conclusion']), ('dynamic', 'completed', 'success'))
        steps = [step for job in index['example_job']['jobs'] for step in job['steps']]
        self.assertIn({'name': 'submit-dependency-snapshot', 'conclusion': 'success'}, steps)
        latest = json.loads((ROOT / 'docs/dependency-evidence/automatic-submission-state-2026-11-14.json').read_text())
        self.assertEqual(latest['workflow']['path'], 'dynamic/dependency-graph/auto-submission')
        self.assertEqual(latest['workflow']['state'], 'active')
        self.assertIn('does not expose', latest['limitation'])

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
