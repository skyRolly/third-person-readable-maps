import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
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
from urllib.parse import parse_qs, unquote, urlsplit

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
        self.plan = {'schema': 1, 'version': '1.0.0', 'release_date': '2026-11-04',
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

    def jar(self, name='1.21.11', *, major=65, namespace=None, version='1.0.0', duplicate=False):
        settings = self.config['groups'][name]
        path = self.root / release.archive_name('1.0.0', name)
        metadata = {'schemaVersion': 1, 'id': release.ID, 'version': version, 'environment': 'client',
                    'license': 'MIT', 'mixins': ['thirdpersonreadablemaps.mixins.json'],
                    'depends': {'minecraft': settings['minecraft'][0] if len(settings['minecraft']) == 1 else settings['minecraft'],
                                'java': f">={settings['java']}",
                                'fabricloader': f">={settings['loader']}"}}
        mixin = {'required': True, 'compatibilityLevel': f"JAVA_{settings['java']}",
                 'injectors': {'defaultRequire': 1}, 'client': settings['mixins'],
                 'package': 'tech.rolly.thirdpersonreadablemaps.mixin'}
        target = b'net/minecraft/class_123' if settings['namespace'] == 'intermediary' else b'net/minecraft/client/renderer/entity/layers/ItemInHandLayer'
        with ZipFile(path, 'w') as jar:
            jar.writestr('fabric.mod.json', json.dumps(metadata))
            jar.writestr('thirdpersonreadablemaps.mixins.json', json.dumps(mixin))
            jar.writestr('META-INF/MANIFEST.MF', f"Manifest-Version: 1.0\nFabric-Mapping-Namespace: {namespace or settings['namespace']}\nFabric-Minecraft-Version: {settings['target']}\n\n")
            jar.writestr('LICENSE', 'MIT')
            for mixin_name in settings['mixins']:
                jar.writestr(release.MIXIN_DIR + mixin_name + '.class', b'\xca\xfe\xba\xbe\x00\x00' + struct.pack('>H', major) + target)
            if duplicate:
                with self.assertWarns(UserWarning):
                    jar.writestr('fabric.mod.json', json.dumps(metadata))
        return path

    def test_release_plan_rejects_invalid_tags_and_version_drift(self):
        self.validate()
        for invalid in ('v1.0.0', '0.0.02', '0.0', '1.2.3-rc1'):
            self.plan['version'] = invalid
            with self.subTest(version=invalid), self.assertRaises(release.Invalid):
                self.validate()
        self.plan['version'] = '0.0.2'
        with self.assertRaisesRegex(release.Invalid, 'coordinated current version'):
            self.validate(candidate=True)
        self.plan['version'] = '1.0.0'
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

    def test_maintenance_heads_are_allowed_only_for_nonpublishing_candidates(self):
        self.plan['groups']['26.3']['source_branch'] = 'maintenance/26.3-2026-11-04'
        self.validate(candidate=True)
        with self.assertRaises(release.Invalid):
            self.validate()
        self.plan['groups']['26.3']['source_branch'] = 'feature/unapproved'
        with self.assertRaises(release.Invalid):
            self.validate(candidate=True)
        for wrong in ('candidate/mc-1.21.11', 'maintenance/mc-1.21.11-1.0.0',
                      'maintenance/26.30-1.0.0'):
            self.plan['groups']['26.3']['source_branch'] = wrong
            with self.subTest(branch=wrong), self.assertRaises(release.Invalid):
                self.validate(candidate=True)

    def test_jar_rejects_wrong_version_new_bytecode_namespace_and_duplicates(self):
        spec = self.config['groups']['1.21.11']
        good = self.jar()
        self.assertEqual(len(release.inspect_jar(good, '1.0.0', '1.21.11', spec)), 64)
        for kwargs in ({'version': '0.0.1'}, {'version': '0.0.2'}, {'major': 69}, {'namespace': 'named'}, {'duplicate': True}):
            with self.subTest(kwargs=kwargs):
                path = self.jar(**kwargs)
                with self.assertRaises(release.Invalid):
                    release.inspect_jar(path, '1.0.0', '1.21.11', spec)

    def test_legacy_java_targets_are_bounded_by_mojang_runtime_and_pinned_build_jdk(self):
        for version, java in [('1.14', 8), ('1.17', 16), ('1.20.1', 17), ('1.21.9', 21)]:
            with self.subTest(version=version):
                config = copy.deepcopy(self.config)
                spec = config['groups']['1.21.11']
                spec.update(target=version, minecraft=[version], java=java)
                path = self.root / 'compatibility.json'
                path.write_text(json.dumps(config), encoding='utf-8')
                release.load_plan(self.path, candidate=True, config_path=path)
                spec['java'] = 25
                path.write_text(json.dumps(config), encoding='utf-8')
                with self.assertRaises(release.Invalid):
                    release.load_plan(self.path, candidate=True, config_path=path)
                spec['java'] = java
                spec['build_jdk'] = 'latest'
                path.write_text(json.dumps(config), encoding='utf-8')
                with self.assertRaises(release.Invalid):
                    release.load_plan(self.path, candidate=True, config_path=path)
        config = copy.deepcopy(self.config)
        config['groups']['1.21.11'].update(target='1.12', minecraft=['1.12'])
        path = self.root / 'compatibility.json'
        path.write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaises(release.Invalid):
            release.load_plan(self.path, candidate=True, config_path=path)

    def test_all_configured_mixins_are_required_and_checked(self):
        spec = self.config['groups']['1.21.11']
        spec['mixins'] = ['ArmedEntityRenderStateMixin', 'ReadableMapLayerMixin']
        jar = self.jar()
        self.assertEqual(len(release.inspect_jar(jar, '1.0.0', '1.21.11', spec)), 64)
        with ZipFile(jar) as source:
            files = {item: source.read(item) for item in source.namelist()
                     if not item.endswith('ArmedEntityRenderStateMixin.class')}
        with ZipFile(jar, 'w') as target:
            for name, value in files.items():
                target.writestr(name, value)
        with self.assertRaises(release.Invalid):
            release.inspect_jar(jar, '1.0.0', '1.21.11', spec)

    def test_build_matrix_selects_each_reviewed_jdk(self):
        rows = release.matrix(self.config, self.plan)
        self.assertTrue(all(row['build_jdk'] == self.config['groups'][row['group']]['build_jdk'] for row in rows))
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertIn('java-version: ${{ matrix.build_jdk }}', workflow)

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
        with (bundle / release.archive_name('1.0.0', '1.21.11')).open('ab') as jar:
            jar.write(b'tampered')
        with self.assertRaises(release.Invalid):
            release_github.verified_files(cfg, plan, bundle, 'c' * 40)

    def test_simulated_prepare_and_publish_check_the_complete_authorization_boundary(self):
        # Exercise actual plan, bundle, branch/review/CI and deployment checks;
        # only GitHub's API and the final HTTP writes are simulated in memory.
        coordinator = 'c' * 40
        branch_shas = {'main': coordinator}
        for i, (name, entry) in enumerate(self.plan['groups'].items()):
            entry['commit'] = 'def'[i] * 40
            branch_shas[entry['source_branch']] = entry['commit']
            for ref in entry['runtime_evidence'].values():
                report = self.root / ref['report']
                data = json.loads(report.read_text())
                data['source_commit'] = entry['commit']
                report.write_text(json.dumps(data))
        cfg, plan = self.validate()
        artifacts = self.root / 'integration-artifacts'
        for name, spec in cfg['groups'].items():
            directory = artifacts / name
            directory.mkdir(parents=True)
            source = self.jar(name, major=spec['java'] + 44)
            source.rename(directory / source.name)
            digest = release.inspect_jar(directory / source.name, plan['version'], name, spec)
            for ref in plan['groups'][name]['runtime_evidence'].values():
                report = self.root / ref['report']
                data = json.loads(report.read_text())
                data['artifact_sha256'] = digest
                report.write_text(json.dumps(data))
        bundle = self.root / 'integration-bundle'
        release.aggregate(cfg, plan, artifacts, bundle, coordinator_sha=coordinator)
        files = release_github.verified_files(cfg, plan, bundle, coordinator)
        protection = {'required_pull_request_reviews': {'required_approving_review_count': 1,
            'dismiss_stale_reviews': True, 'require_code_owner_reviews': False, 'require_last_push_approval': False,
            'bypass_pull_request_allowances': {'users': [], 'teams': [], 'apps': []}},
            'enforce_admins': {'enabled': True}, 'allow_force_pushes': {'enabled': False},
            'allow_deletions': {'enabled': False}, 'required_status_checks': {'strict': True,
            'contexts': [], 'checks': []}}
        sha_branches = {sha: branch for branch, sha in branch_shas.items()}
        branches = list(branch_shas)
        run_ids = {branch: 100 + index for index, branch in enumerate(branches)}
        ids_branches = {value: key for key, value in run_ids.items()}
        env = {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_RUN_ID': '999', 'GITHUB_RUN_ATTEMPT': '1',
               'GH_TOKEN': 'write-token', 'RELEASE_AUDITOR_TOKEN': 'audit-token'}
        state = {'environment': 'release-draft', 'deployment_path': '.github/workflows/release.yml@main',
                 'failure': None, 'no_approval': False, 'writes': [], 'tag': False, 'draft': None}

        def api(path, **kwargs):
            parsed = urlsplit(path)
            route = parsed.path.removeprefix('repos/owner/repo/')
            query = parse_qs(parsed.query)
            if route.startswith('environments/'):
                return {'id': 77, 'protection_rules': [{'type': 'required_reviewers',
                    'reviewers': [{'type': 'User', 'reviewer': {'id': 5}}], 'prevent_self_review': True}]}
            if route.startswith('branches/'):
                branch = unquote(route[len('branches/'):].removesuffix('/protection'))
                if route.endswith('/protection'):
                    result = copy.deepcopy(protection)
                    required = sorted(authorize_release.role_checks(branch))
                    result['required_status_checks'].update(contexts=required, checks=[
                        {'context': n, 'app_id': 15368} for n in required])
                    return result
                return {'protected': True, 'commit': {'sha': branch_shas[branch]}}
            if route.startswith(('rules/branches/', 'rulesets')):
                return []
            if route.startswith('commits/') and route.endswith('/pulls'):
                sha = route.split('/')[1]
                branch = sha_branches[sha]
                return [{'number': 1, 'merged_at': '2026-11-04T00:00:00Z', 'merge_commit_sha': sha,
                         'base': {'ref': branch}, 'head': {'sha': 'b' * 40}, 'user': {'login': 'author'}}]
            if route.startswith('pulls/') and route.endswith('/reviews'):
                return [{'id': 1, 'user': {'login': 'reviewer'}, 'state': 'APPROVED', 'commit_id': 'b' * 40,
                         'submitted_at': '2026-11-03T00:00:00Z'}]
            if route.startswith('collaborators/'):
                return {'permission': 'write'}
            if route == 'actions/workflows/ci.yml':
                return {'id': 12, 'path': '.github/workflows/ci.yml', 'state': 'active'}
            if route == 'actions/workflows/release.yml':
                return {'id': 13, 'path': '.github/workflows/release.yml', 'state': 'active'}
            if route == 'actions/workflows/ci.yml/runs':
                branch = query['branch'][0]
                return {'workflow_runs': [{'id': run_ids[branch], 'created_at': '2026-11-04T00:00:00Z',
                    'workflow_id': 12, 'path': '.github/workflows/ci.yml@' + branch,
                    'head_sha': branch_shas[branch], 'head_branch': branch, 'event': 'push', 'run_attempt': 1,
                    'status': 'completed', 'conclusion': state['failure'] or 'success'}]}
            if route.startswith('actions/runs/') and '/attempts/' in route:
                run_id = int(route.split('/')[2])
                branch = ids_branches[run_id]
                sha = branch_shas[branch]
                required = sorted(authorize_release.role_checks(branch))
                return {'jobs': [{'id': run_id * 10 + i, 'run_id': run_id, 'run_attempt': 1, 'head_sha': sha,
                                  'name': name, 'status': 'completed', 'conclusion': 'success'}
                                 for i, name in enumerate(required)]}
            if route.startswith('commits/') and route.endswith('/check-runs'):
                sha = route.split('/')[1]
                branch = sha_branches[sha]
                run_id = run_ids[branch]
                required = sorted(authorize_release.role_checks(branch))
                return {'check_runs': [{'id': run_id * 10 + i, 'name': name, 'app': {'id': 15368},
                    'head_sha': sha, 'started_at': '2026-11-04T00:00:01Z', 'status': 'completed',
                    'conclusion': 'success'} for i, name in enumerate(required)]}
            if route == 'actions/runs/999':
                return {'id': 999, 'workflow_id': 13, 'event': 'workflow_dispatch', 'head_branch': 'main',
                        'head_sha': coordinator, 'path': state['deployment_path'], 'run_attempt': 1,
                        'actor': {'login': 'dispatcher'}, 'triggering_actor': {'login': 'dispatcher'}}
            if route == 'actions/runs/999/approvals':
                return [] if state['no_approval'] else [{'state': 'approved', 'user': {'id': 5, 'login': 'reviewer'},
                    'environments': [{'id': 77, 'name': state['environment']}]}]
            if route == 'releases/tags/1.0.0':
                return copy.deepcopy(state['draft'])
            if route == 'git/ref/tags/1.0.0':
                return {'object': {'type': 'tag', 'sha': 'tag-object'}} if state['tag'] else None
            if route == 'git/tags/tag-object':
                return {'tag': plan['version'], 'object': {'type': 'commit', 'sha': coordinator}}
            self.fail('Unexpected GitHub API path: ' + path)

        def graphql(query, variables):
            branch = variables['branch'].removeprefix('refs/heads/')
            return {'repository': {'ref': {'name': branch, 'target': {'oid': branch_shas[branch]},
                'branchProtectionRule': {'id': 'rule', 'requiresCodeOwnerReviews': False,
                    'requireLastPushApproval': False, 'bypassPullRequestAllowances': {'totalCount': 0}}}}}

        def fake_urlopen(request, timeout):
            # Only the intended fake upload / publish endpoints may be called.
            url = urlsplit(request.full_url)
            self.assertEqual(os.environ['GH_TOKEN'], 'write-token')
            result = {}
            if url.netloc == 'api.github.com' and url.path == '/repos/owner/repo/git/tags' and request.method == 'POST':
                data = json.loads(request.data)
                self.assertEqual((data['tag'], data['object'], data['type']), (plan['version'], coordinator, 'commit'))
                result = {'sha': 'tag-object'}
            elif url.netloc == 'api.github.com' and url.path == '/repos/owner/repo/git/refs' and request.method == 'POST':
                self.assertEqual(json.loads(request.data), {'ref': 'refs/tags/1.0.0', 'sha': 'tag-object'})
                state['tag'] = True
            elif url.netloc == 'api.github.com' and url.path == '/repos/owner/repo/releases' and request.method == 'POST':
                data = json.loads(request.data)
                self.assertTrue(state['tag'])
                self.assertEqual(data, {'tag_name': plan['version'], 'name': plan['version'],
                                        'body': release_github.release_body(cfg, plan), 'draft': True, 'prerelease': False})
                state['draft'] = dict(data, id=8, assets=[])
                result = copy.deepcopy(state['draft'])
            elif url.netloc == 'uploads.github.com' and request.method == 'POST':
                name = parse_qs(url.query)['name'][0]
                digest = hashlib.sha256(request.data).hexdigest()
                self.assertEqual(digest, files[name])
                state['draft']['assets'].append({'name': name, 'digest': 'sha256:' + digest})
            elif url.netloc == 'api.github.com' and url.path == '/repos/owner/repo/releases/8' and request.method == 'PATCH':
                self.assertEqual(json.loads(request.data), {'draft': False})
                state['draft']['draft'] = False
            else:
                self.fail('Unexpected HTTP write: ' + request.full_url)
            state['writes'].append((request.method, url.path))
            return io.BytesIO(json.dumps(result).encode())

        def invoke(mode):
            with patch.object(sys, 'argv', ['release_github.py', mode, '--plan', str(self.path),
                                         '--bundle', str(bundle), '--coordinator-sha', coordinator]), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return release_github.main()

        with patch.dict(os.environ, env), patch.object(authorize_release, 'api', side_effect=api), \
             patch.object(authorize_release, 'graphql', side_effect=graphql), \
             patch.object(release_github, 'api', side_effect=api), \
             patch.object(release_github, 'urlopen', side_effect=fake_urlopen):
            for field, value in [('failure', 'failure'), ('no_approval', True)]:
                state[field] = value
                with self.subTest(blocked_prepare=field):
                    self.assertEqual(invoke('prepare-draft'), 1)
                    self.assertEqual(state['writes'], [])
                    self.assertFalse(state['tag'])
                    self.assertIsNone(state['draft'])
                state[field] = None if field == 'failure' else False
            self.assertEqual(invoke('prepare-draft'), 0)
            self.assertTrue(state['tag'])
            self.assertEqual(len(state['draft']['assets']), len(files))
            self.assertEqual(len(state['writes']), 3 + len(files))
            state['environment'] = 'release-publication'
            state['deployment_path'] = '.github/workflows/release.yml'  # observed bare form
            for field, value in [('failure', 'failure'), ('no_approval', True)]:
                state[field] = value
                count = len(state['writes'])
                with self.subTest(blocked=field):
                    self.assertEqual(invoke('publish'), 1)
                    self.assertEqual(len(state['writes']), count)
                    self.assertTrue(state['draft']['draft'])
                state[field] = None if field == 'failure' else False
            self.assertEqual(invoke('publish'), 0)
            self.assertFalse(state['draft']['draft'])
            self.assertEqual(state['writes'][-1], ('PATCH', '/repos/owner/repo/releases/8'))

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

    def test_every_release_group_uses_checked_out_verifier_and_failure_propagates(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        build = workflow.split('  build:\n', 1)[1].split('  collect:\n', 1)[0]
        self.assertIn('ref: ${{ matrix.commit }}', build)
        command = 'python3 scripts/verify_supported_apis.py --jar build/libs'
        self.assertIn('run: ' + command, build)
        self.assertNotIn('if: matrix.multi_version', build)
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
                release_github.ensure_tag('owner/repo', '1.0.0', 'a' * 40, True)
            mutate.assert_not_called()
        with patch.object(release_github, 'api', return_value={'object': {'type': 'commit', 'sha': 'a' * 40}}):
            with self.assertRaises(release.Invalid):
                release_github.tag_target('owner/repo', '1.0.0')

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
