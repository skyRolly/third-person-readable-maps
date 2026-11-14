import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_maintenance_targets as targets


class MaintenanceTargetTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / 'release/maintenance-targets.json').read_text())
        self.config = (ROOT / '.github/dependabot.yml').read_text()
        self.legacy = {'branch': 'mc/1.14-1.14.4', 'target': '1.14.4',
                       'minecraft': ['1.14', '1.14.1', '1.14.2', '1.14.3', '1.14.4'],
                       'integrated_commit': 'a' * 40}
        self.legacy_entries = '''  - package-ecosystem: gradle
    directory: /
    target-branch: mc/1.14-1.14.4
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: /
    target-branch: mc/1.14-1.14.4
    schedule:
      interval: weekly
'''

    def test_candidates_do_not_activate_dependency_updates(self):
        # Neither a proposed candidate nor a placeholder name adds an active target.
        targets.validate_configuration(self.registry, self.config)
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            targets.validate_configuration(self.registry, self.config + self.legacy_entries)

    def test_integrated_branch_requires_both_updates_and_matching_source(self):
        self.registry['groups']['1.14-1.14.4'] = self.legacy
        with self.assertRaisesRegex(ValueError, 'missing'):
            targets.validate_configuration(self.registry, self.config)
        targets.validate_configuration(self.registry, self.config + self.legacy_entries)
        metadata = {'id': 'thirdpersonreadablemaps', 'depends': {'minecraft': self.legacy['minecraft']}}
        props = {'minecraft_version': '1.14.4', 'minecraft_group': '1.14-1.14.4'}
        targets.validate_source('1.14-1.14.4', self.legacy, props, metadata, True)
        for changed in ({**props, 'minecraft_version': '1.21.11'}, {**props, 'minecraft_group': '1.21.11'}):
            with self.assertRaises(ValueError):
                targets.validate_source('1.14-1.14.4', self.legacy, changed, metadata, True)
        with self.assertRaisesRegex(ValueError, 'different Minecraft'):
            targets.validate_source('1.14-1.14.4', self.legacy, props,
                                    {'id': 'thirdpersonreadablemaps', 'depends': {'minecraft': '1.21.11'}}, True)
        with self.assertRaisesRegex(ValueError, 'not an ancestor'):
            targets.validate_source('1.14-1.14.4', self.legacy, props, metadata, False)

    def test_duplicate_and_stale_entries_fail(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            targets.validate_configuration(self.registry, self.config + self.config[self.config.index('  - package-ecosystem:'):])
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            targets.validate_configuration(self.registry, self.config + self.legacy_entries)
        duplicate = copy.deepcopy(self.registry)
        duplicate['groups']['26.4'] = copy.deepcopy(duplicate['groups']['26.3'])
        with self.assertRaises(ValueError):
            targets.registry_entries(duplicate)

    def test_existing_single_version_template_is_checked(self):
        spec = self.registry['groups']['1.21.11']
        targets.validate_source('1.21.11', spec, {'minecraft_version': '1.21.11'},
                                {'id': 'thirdpersonreadablemaps', 'depends': {'minecraft': '${minecraft_version}'}}, True)
        with self.assertRaises(ValueError):
            targets.validate_source('1.21.11', spec, {'minecraft_version': '1.14.4'},
                                    {'id': 'thirdpersonreadablemaps', 'depends': {'minecraft': '${minecraft_version}'}}, True)

    def test_release_verifier_dependency_blocks_incomplete_source(self):
        required = {'scripts/verify_supported_apis.py', 'scripts/game_linkage.py', 'scripts/jvm_linkage.py',
                    'scripts/verify_gradle_wrapper.py', 'tests/test_jvm_linkage.py',
                    'tests/test_verify_entrypoint.py', 'tests/test_verify_gradle_wrapper.py', 'tests/test_nestmate_linkage.py',
                    'tests/test_shared_verifier_sync.py'}
        targets.validate_release_verifier_files('1.21.11', required)
        with self.assertRaisesRegex(ValueError, 'lacks the required'):
            targets.validate_release_verifier_files('1.21.11', required - {'scripts/jvm_linkage.py'})

    def test_integrated_anchor_allows_an_advancing_maintenance_head(self):
        spec = self.registry['groups']['1.21.11']
        props = {'minecraft_version': '1.21.11', 'mod_version': '1.0.0'}
        metadata = {'id':'thirdpersonreadablemaps', 'version':'${version}',
                    'depends':{'minecraft':'${minecraft_version}'}}
        targets.validate_source('1.21.11', spec, props, metadata, True)
        targets.validate_coordinated_version('1.21.11', props, metadata, {'schema':1, 'version':'1.0.0'})
        with self.assertRaisesRegex(ValueError, 'not an ancestor'):
            targets.validate_source('1.21.11', spec, props, metadata, False)

    def test_release_prerequisite_rejects_mixed_integrated_versions(self):
        current = {'schema': 1, 'version': '1.0.0'}
        metadata = {'version': '${version}'}
        targets.validate_coordinated_version('1.21.11', {'mod_version': '1.0.0'}, metadata, current)
        for props, item in [({'mod_version': '0.0.2'}, metadata), ({}, metadata),
                            ({'mod_version': '1.0.0'}, {'version': '0.0.2'})]:
            with self.subTest(props=props, metadata=item), self.assertRaisesRegex(ValueError, 'differs'):
                targets.validate_coordinated_version('1.21.11', props, item, current)

    def test_staged_maintenance_updates_keep_live_gate_failing_until_all_three(self):
        required = {'scripts/verify_supported_apis.py', 'scripts/game_linkage.py', 'scripts/jvm_linkage.py',
                    'scripts/verify_gradle_wrapper.py', 'tests/test_jvm_linkage.py',
                    'tests/test_verify_entrypoint.py', 'tests/test_verify_gradle_wrapper.py',
                    'tests/test_nestmate_linkage.py', 'tests/test_shared_verifier_sync.py'}
        groups = ('1.21.11', '26.1-26.2', '26.3')
        for updated in range(4):
            failures = []
            for index, group in enumerate(groups):
                files = required if index < updated else required - {'scripts/jvm_linkage.py'}
                version = '1.0.0' if index < updated else '0.0.2'
                try:
                    targets.validate_release_verifier_files(group, files)
                    targets.validate_coordinated_version(group, {'mod_version':version},
                        {'version':'${version}'}, {'schema':1, 'version':'1.0.0'})
                except ValueError:
                    failures.append(group)
            self.assertEqual(failures, list(groups[updated:]))


if __name__ == '__main__':
    unittest.main()
