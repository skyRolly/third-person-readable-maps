import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import authorize_release
import release
import release_github


class ReleaseValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = release.read_json(ROOT / 'release/compatibility.json')
        self.plan = {'schema': 1, 'version': '0.0.2', 'release_date': '2026-11-04',
                     'changes': ['Fix map rendering'], 'known_limitations': [], 'groups': {}}
        for name in self.config['groups']:
            self.plan['groups'][name] = {'source_branch': self.config['groups'][name]['branch'],
                                         'commit': 'a' * 40, 'verified_changes': ['Fix map rendering'],
                                         'runtime_evidence': {name: {'installed_jar': 'https://example.org/installed',
                                                                     'graphical': 'https://example.org/visual'}}}
        self.path = self.root / 'plan.json'
        self.write_plan()

    def tearDown(self):
        self.tmp.cleanup()

    def write_plan(self):
        self.path.write_text(json.dumps(self.plan), encoding='utf-8')

    def validate(self, candidate=False):
        self.write_plan()
        return release.load_plan(self.path, candidate)

    def jar(self, name='1.21.11', *, major=65, namespace=None, version='0.0.2', duplicate=False):
        settings = self.config['groups'][name]
        path = self.root / release.archive_name('0.0.2', name)
        metadata = {'schemaVersion': 1, 'id': release.ID, 'version': version, 'environment': 'client',
                    'license': 'MIT', 'mixins': ['thirdpersonreadablemaps.mixins.json'],
                    'depends': {'minecraft': name, 'java': f">={settings['java']}",
                                'fabricloader': f">={settings['loader']}"}}
        mixin = {'required': True, 'compatibilityLevel': f"JAVA_{settings['java']}",
                 'injectors': {'defaultRequire': 1}, 'client': ['ReadableMapLayerMixin'],
                 'package': 'tech.rolly.thirdpersonreadablemaps.mixin'}
        target = b'net/minecraft/class_123' if settings['namespace'] == 'intermediary' else b'net/minecraft/client/renderer/entity/layers/ItemInHandLayer'
        with ZipFile(path, 'w') as jar:
            jar.writestr('fabric.mod.json', json.dumps(metadata))
            jar.writestr('thirdpersonreadablemaps.mixins.json', json.dumps(mixin))
            jar.writestr('META-INF/MANIFEST.MF', f"Manifest-Version: 1.0\nFabric-Mapping-Namespace: {namespace or settings['namespace']}\nFabric-Minecraft-Version: {name}\n\n")
            jar.writestr('LICENSE', 'MIT')
            jar.writestr(release.MIXIN_CLASS, b'\xca\xfe\xba\xbe\x00\x00' + struct.pack('>H', major) + target)
            if duplicate:
                with self.assertWarns(UserWarning):
                    jar.writestr('fabric.mod.json', json.dumps(metadata))
        return path

    def test_release_plan_rejects_invalid_tags_and_version_drift(self):
        self.validate()
        for invalid in ('v0.0.2', '0.0.02', '0.0', '1.2.3-rc1'):
            self.plan['version'] = invalid
            with self.subTest(version=invalid), self.assertRaises(release.Invalid):
                self.validate()
        self.plan['version'] = '0.0.2'
        self.plan['groups']['26.3']['verified_changes'] = []
        with self.assertRaises(release.Invalid):
            self.validate()

    def test_all_groups_source_revisions_and_runtime_evidence_required(self):
        self.plan['groups']['26.3']['commit'] = '0' * 40
        with self.assertRaises(release.Invalid):
            self.validate(candidate=True)
        self.plan['groups']['26.3']['commit'] = 'b' * 40
        self.plan['groups']['26.3']['runtime_evidence'] = {}
        self.plan['groups']['26.3']['source_branch'] = 'candidate/mc-26.3'
        self.validate(candidate=True)
        with self.assertRaises(release.Invalid):
            self.validate()
        self.plan['groups']['26.3']['source_branch'] = 'mc/26.3'
        with self.assertRaises(release.Invalid):
            self.validate()
        del self.plan['groups']['26.3']
        with self.assertRaises(release.Invalid):
            self.validate(candidate=True)

    def test_jar_rejects_wrong_version_new_bytecode_namespace_and_duplicates(self):
        spec = self.config['groups']['1.21.11']
        good = self.jar()
        self.assertEqual(len(release.inspect_jar(good, '0.0.2', '1.21.11', spec)), 64)
        for kwargs in ({'version': '0.0.1'}, {'major': 69}, {'namespace': 'named'}, {'duplicate': True}):
            with self.subTest(kwargs=kwargs):
                path = self.jar(**kwargs)
                with self.assertRaises(release.Invalid):
                    release.inspect_jar(path, '0.0.2', '1.21.11', spec)

    def test_duplicate_json_keys_rejected(self):
        self.path.write_text('{"schema":1,"schema":1}', encoding='utf-8')
        with self.assertRaises(release.Invalid):
            release.read_json(self.path)

    def test_aggregate_rechecks_artifacts_and_detects_tampering(self):
        cfg, plan = self.validate()
        artifacts = self.root / 'artifacts'
        for name, settings in cfg['groups'].items():
            directory = artifacts / name
            directory.mkdir(parents=True)
            source = self.jar(name, major=settings['java'] + 44)
            source.rename(directory / source.name)
        bundle = self.root / 'bundle'
        release.aggregate(cfg, plan, artifacts, bundle)
        files = release_github.verified_files(cfg, plan, bundle)
        self.assertEqual(len(files), 4)
        with (bundle / release.archive_name('0.0.2', '1.21.11')).open('ab') as jar:
            jar.write(b'tampered')
        with self.assertRaises(release.Invalid):
            release_github.verified_files(cfg, plan, bundle)

    def test_conflicting_or_lightweight_release_tag_is_rejected(self):
        with patch.object(release_github, 'tag_target', return_value='b' * 40), \
             patch.object(release_github, 'mutate') as mutate:
            with self.assertRaises(release.Invalid):
                release_github.ensure_tag('owner/repo', '0.0.2', 'a' * 40, True)
            mutate.assert_not_called()
        with patch.object(release_github, 'api', return_value={'object': {'type': 'commit', 'sha': 'a' * 40}}):
            with self.assertRaises(release.Invalid):
                release_github.tag_target('owner/repo', '0.0.2')

    def test_unprotected_source_is_rejected_before_release(self):
        with patch.object(authorize_release, 'api', return_value={'protected': False, 'commit': {'sha': 'a' * 40}}):
            with self.assertRaises(release.Invalid):
                authorize_release.protected_branch('owner/repo', 'mc/1.21.11', 'a' * 40)

    def test_conflicting_draft_asset_is_rejected(self):
        release_data = {'assets': [{'name': 'file.jar', 'digest': 'sha256:' + 'b' * 64}]}
        with self.assertRaises(release.Invalid):
            release_github.check_assets(release_data, {'file.jar': 'a' * 64}, False)


if __name__ == '__main__':
    unittest.main()
