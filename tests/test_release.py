import copy
import os
import subprocess
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
        self.root_patch = patch.object(release, 'ROOT', self.root)
        self.root_patch.start()
        self.config = release.read_json(ROOT / 'release/compatibility.json')
        self.plan = {'schema': 1, 'version': '0.0.2', 'release_date': '2026-11-04',
                     'changes': ['Fix map rendering'], 'known_limitations': [], 'groups': {}}
        for name in self.config['groups']:
            self.plan['groups'][name] = {'source_branch': self.config['groups'][name]['branch'],
                                         'commit': 'a' * 40, 'verified_changes': ['Fix map rendering'],
                                         'runtime_evidence': {v: {'report': f'release/evidence/mc-{v.replace(".", "-")}.json'}
                                                              for v in self.config['groups'][name]['minecraft']}}
            for mc, ref in self.plan['groups'][name]['runtime_evidence'].items():
                report = self.root / ref['report']
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps({'group': name, 'minecraft': mc, 'source_commit': 'a' * 40,
                                              'artifact_sha256': 'b' * 64, 'installed_jar': 'Installed with Loader',
                                              'graphical': 'Observed map terrain'}), encoding='utf-8')
        self.path = self.root / 'plan.json'
        self.write_plan()

    def tearDown(self):
        self.root_patch.stop()
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
                    'depends': {'minecraft': settings['minecraft'][0] if len(settings['minecraft']) == 1 else settings['minecraft'],
                                'java': f">={settings['java']}",
                                'fabricloader': f">={settings['loader']}"}}
        mixin = {'required': True, 'compatibilityLevel': f"JAVA_{settings['java']}",
                 'injectors': {'defaultRequire': 1}, 'client': ['ReadableMapLayerMixin'],
                 'package': 'tech.rolly.thirdpersonreadablemaps.mixin'}
        target = b'net/minecraft/class_123' if settings['namespace'] == 'intermediary' else b'net/minecraft/client/renderer/entity/layers/ItemInHandLayer'
        with ZipFile(path, 'w') as jar:
            jar.writestr('fabric.mod.json', json.dumps(metadata))
            jar.writestr('thirdpersonreadablemaps.mixins.json', json.dumps(mixin))
            jar.writestr('META-INF/MANIFEST.MF', f"Manifest-Version: 1.0\nFabric-Mapping-Namespace: {namespace or settings['namespace']}\nFabric-Minecraft-Version: {settings['target']}\n\n")
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

    def test_overlapping_game_versions_are_rejected(self):
        config = copy.deepcopy(self.config)
        config['groups']['26.3']['minecraft'].append('26.2')
        path = self.root / 'compatibility.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaises(release.Invalid):
            release.load_plan(self.path, candidate=True, config_path=path)

    def test_aggregate_rechecks_artifacts_and_detects_tampering(self):
        cfg, plan = self.validate()
        artifacts = self.root / 'artifacts'
        for name, settings in cfg['groups'].items():
            directory = artifacts / name
            directory.mkdir(parents=True)
            source = self.jar(name, major=settings['java'] + 44)
            source.rename(directory / source.name)
            digest = release.inspect_jar(directory / source.name, plan['version'], name, settings)
            for ref in plan['groups'][name]['runtime_evidence'].values():
                report = self.root / ref['report']
                data = json.loads(report.read_text())
                data['artifact_sha256'] = digest
                report.write_text(json.dumps(data), encoding='utf-8')
        bundle = self.root / 'bundle'
        release.aggregate(cfg, plan, artifacts, bundle, coordinator_sha='c' * 40)
        files = release_github.verified_files(cfg, plan, bundle, 'c' * 40)
        self.assertEqual(len(files), len(cfg['groups']) + 2)
        with (bundle / release.archive_name('0.0.2', '1.21.11')).open('ab') as jar:
            jar.write(b'tampered')
        with self.assertRaises(release.Invalid):
            release_github.verified_files(cfg, plan, bundle, 'c' * 40)

    def test_runtime_reports_reject_urls_malformed_paths_and_wrong_associations(self):
        item = self.plan['groups']['26.3']['runtime_evidence']['26.3']
        for value in ('https://evil.example/report', 'https://github.com/owner/repo/issues/1',
                      'release/evidence/../other.json', 'release/evidence/x.json?redirect=evil',
                      'release/evidence/%2e%2e.json', '//github.com/owner/repo'):
            item['report'] = value
            with self.subTest(value=value), self.assertRaises((release.Invalid, OSError)):
                self.validate()
        item['report'] = 'release/evidence/mc-26-3.json'
        report = self.root / item['report']
        original = json.loads(report.read_text())
        for field, value in [('group', '1.21.11'), ('minecraft', '26.2'),
                             ('source_commit', 'b' * 40), ('artifact_sha256', 'x' * 64),
                             ('installed_jar', ''), ('graphical', '')]:
            data = dict(original, **{field: value})
            report.write_text(json.dumps(data))
            with self.subTest(field=field), self.assertRaises(release.Invalid):
                self.validate()
        report.write_text(json.dumps(original))
        self.validate()

    def test_evidence_artifact_digest_must_match_aggregate(self):
        cfg, plan = self.validate()
        artifacts = self.root / 'artifacts'
        for name, spec in cfg['groups'].items():
            directory = artifacts / name
            directory.mkdir(parents=True)
            source = self.jar(name, major=spec['java'] + 44)
            source.rename(directory / source.name)
        with self.assertRaisesRegex(release.Invalid, 'runtime-tested'):
            release.aggregate(cfg, plan, artifacts, self.root / 'bundle', coordinator_sha='c' * 40)

    def test_changed_authorization_prevents_each_write(self):
        calls = []
        def guard():
            calls.append('checked')
            raise release.Invalid('branch head changed')
        with patch.object(release_github, 'WRITE_GUARD', guard), \
             patch.object(release_github, 'urlopen') as request, \
             patch.dict(os.environ, {'GH_TOKEN': 'write-token'}):
            with self.assertRaises(release.Invalid):
                release_github.mutate('repos/owner/repo/releases', 'POST', {})
            request.assert_not_called()
        self.assertEqual(calls, ['checked'])

    def test_draft_notes_and_nonpublishing_modes_are_guarded(self):
        cfg, plan = self.validate()
        body = release_github.release_body(cfg, plan)
        draft = {'draft': True, 'tag_name': plan['version'], 'name': plan['version'],
                 'body': body, 'prerelease': False}
        release_github.check_draft(draft, plan['version'], body)
        with self.assertRaises(release.Invalid):
            release_github.check_draft(dict(draft, body='changed'), plan['version'], body)
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn("if: inputs.mode != 'dry-run' && github.ref == 'refs/heads/main'", workflow)
        with patch.object(release_github, 'mutate') as mutate, patch.object(sys, 'argv',
                ['release_github.py', 'dry-run', '--plan', str(self.path), '--bundle', str(self.root),
                 '--coordinator-sha', 'a' * 40]), self.assertRaises(SystemExit):
            release_github.main()
        mutate.assert_not_called()

    def test_multi_version_workflow_uses_checked_out_verifier_and_failure_propagates(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        build = workflow.split('  build:\n', 1)[1].split('  collect:\n', 1)[0]
        self.assertIn('ref: ${{ matrix.commit }}', build)
        command = 'python3 scripts/verify_supported_apis.py --jar build/libs'
        self.assertIn('if: matrix.multi_version\n        run: ' + command, build)
        self.assertLess(build.index('ref: ${{ matrix.commit }}'), build.index(command))
        self.assertLess(build.index(command), build.index('Upload group artifact'))
        self.assertEqual([e['group'] for e in release.matrix(self.config, self.plan) if e['multi_version']], ['26.1-26.2'])
        (self.root / 'scripts').mkdir()
        self.assertNotEqual(subprocess.run(command, cwd=self.root, shell=True, capture_output=True).returncode, 0)
        script = self.root / 'scripts/verify_supported_apis.py'
        script.write_text('import sys\nsys.exit(1)\n')
        self.assertNotEqual(subprocess.run(command, cwd=self.root, shell=True, capture_output=True).returncode, 0)
        script.write_text('import sys\nsys.exit(0 if sys.argv[1:] == ["--jar", "build/libs"] else 1)\n')
        self.assertEqual(subprocess.run(command, cwd=self.root, shell=True, capture_output=True).returncode, 0)

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
