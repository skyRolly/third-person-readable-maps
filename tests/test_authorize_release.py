import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import authorize_release as auth
from release import Invalid


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.commit = 'a' * 40
        self.head = 'b' * 40
        self.branch = 'mc/1.21.11'
        self.required = {name: auth.ACTIONS_APP for name in auth.BUILD_CHECKS}
        self.run = {'id': 10, 'created_at': '2026-11-04T00:00:00Z', 'workflow_id': 12,
                    'path': '.github/workflows/ci.yml', 'head_sha': self.commit, 'head_branch': self.branch,
                    'event': 'push', 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success'}
        self.runs = [self.run]
        self.jobs = [{'id': i, 'run_id': 10, 'run_attempt': 1, 'head_sha': self.commit, 'name': n,
                      'status': 'completed', 'conclusion': 'success'}
                     for i, n in enumerate(sorted(self.required), 101)]
        self.checks = [{'id': j['id'], 'name': j['name'], 'app': {'id': auth.ACTIONS_APP},
                        'head_sha': self.commit, 'started_at': '2026-11-04T00:00:01Z',
                        'status': 'completed', 'conclusion': 'success'} for j in self.jobs]
        self.pr = {'number': 1, 'merged_at': '2026-11-04T00:00:00Z', 'merge_commit_sha': self.commit,
                   'base': {'ref': self.branch}, 'head': {'sha': self.head}, 'user': {'login': 'author'},
                   'merged_by': {'login': 'owner'}}
        self.branch_details = {'protected': False, 'commit': {'sha': self.commit}}
        self.effective_rules = []
        self.rulesets = []
        self.mock = patch.object(auth, 'api', side_effect=self.api)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()

    def api(self, path, **kwargs):
        branch_path = '/branches/' + quote(self.branch, safe='')
        if branch_path in path and '/rules/' not in path:
            return self.branch_details
        if '/rules/branches/' in path:
            return self.effective_rules
        if '/rulesets?' in path:
            return self.rulesets
        if '/commits/' in path and '/pulls' in path:
            return [self.pr]
        if '/actions/workflows/ci.yml/runs?' in path:
            return {'workflow_runs': self.runs}
        if path.endswith('/actions/workflows/ci.yml'):
            return {'id': 12, 'path': '.github/workflows/ci.yml', 'state': 'active'}
        if '/jobs?' in path:
            return {'jobs': self.jobs}
        if '/check-runs?' in path:
            return {'check_runs': self.checks}
        raise AssertionError(path)

    def authorize(self):
        auth.integrated_branch('owner/repo', 'owner', self.branch, self.commit)

    def test_valid_owner_integrated_unprotected_branch_without_pr_approval(self):
        self.authorize()

    def test_owner_merge_actor_is_required_without_self_approval(self):
        self.pr['merged_by'] = {'login': 'another-maintainer'}
        with self.assertRaisesRegex(Invalid, 'performed by repository owner'):
            self.authorize()

    def test_unprotected_exact_tip_and_empty_rules_are_required(self):
        self.branch_details['protected'] = True
        with self.assertRaisesRegex(Invalid, 'must be unprotected'):
            self.authorize()
        self.branch_details['protected'] = False
        self.effective_rules = [{'type': 'pull_request'}]
        with self.assertRaisesRegex(Invalid, 'effective branch rules'):
            self.authorize()
        self.effective_rules = []
        self.rulesets = [{'id': 7}]
        with self.assertRaisesRegex(Invalid, 'rulesets are present'):
            self.authorize()
        self.rulesets = []
        self.branch_details['commit']['sha'] = 'c' * 40
        with self.assertRaisesRegex(Invalid, 'HEAD must equal'):
            self.authorize()

    def test_head_must_be_one_merged_pr_into_the_same_branch(self):
        self.pr['base']['ref'] = 'other'
        with self.assertRaisesRegex(Invalid, 'unambiguous merge commit'):
            self.authorize()
        self.pr['base']['ref'] = self.branch
        self.pr['merge_commit_sha'] = 'c' * 40
        with self.assertRaisesRegex(Invalid, 'unambiguous merge commit'):
            self.authorize()
        self.pr['merge_commit_sha'] = self.commit
        self.pr['merged_at'] = None
        with self.assertRaisesRegex(Invalid, 'unambiguous merge commit'):
            self.authorize()

    def test_main_requires_both_exact_coordination_jobs(self):
        self.branch = 'main'
        self.required = {name: auth.ACTIONS_APP for name in auth.COORDINATION_CHECKS}
        self.run['head_branch'] = 'main'
        self.run['path'] = '.github/workflows/ci.yml@main'
        self.jobs = [dict(self.jobs[i], name=name) for i, name in enumerate(sorted(self.required))]
        self.checks = [dict(self.checks[i], name=name) for i, name in enumerate(sorted(self.required))]
        self.pr['base']['ref'] = 'main'
        self.authorize()
        self.jobs[0]['name'] = 'Build (ubuntu-latest)'
        with self.assertRaisesRegex(Invalid, 'missing or ambiguous'):
            self.authorize()

    def test_game_branch_cannot_use_coordination_check_in_place_of_builds(self):
        self.checks = [dict(self.checks[0], name='Validate coordination')]
        with self.assertRaises(Invalid):
            self.authorize()
        with self.assertRaises(Invalid):
            auth.role_checks('candidate/unapproved')

    def test_ci_run_path_accepts_only_expected_workflow_and_ref(self):
        path = '.github/workflows/ci.yml'
        for value in (path, f'{path}@{self.branch}', f'{path}@refs/heads/{self.branch}',
                      f'owner/repo/{path}@{self.branch}', f'owner/repo/{path}'):
            self.runs = [dict(self.run, path=value)]
            with self.subTest(accepted=value):
                self.authorize()
        for value in (f'{path}@main', f'{path}@refs/tags/{self.branch}', f'{path}@{self.commit}',
                      f'{path}@{self.branch}@other', path + '@', path + '/extra',
                      f'other/repo/{path}@{self.branch}', f'{path}.backup@{self.branch}',
                      './' + path, ' ' + path, path + '\n', None):
            self.runs = [dict(self.run, path=value)]
            with self.subTest(rejected=value), self.assertRaises(Invalid):
                self.authorize()

    def test_latest_run_and_attempt_must_succeed(self):
        for status, conclusion in [('completed', 'failure'), ('completed', 'cancelled'), ('in_progress', None),
                                   ('queued', None)]:
            later = dict(self.run, id=20, created_at='2026-11-05T00:00:00Z', status=status, conclusion=conclusion)
            self.runs = [self.run, later]
            with self.subTest(status=status, conclusion=conclusion), self.assertRaises(Invalid):
                self.authorize()
        self.runs = []
        with self.assertRaises(Invalid):
            self.authorize()
        self.runs = [dict(self.run, run_attempt=2)]
        with self.assertRaises(Invalid):
            self.authorize()

    def test_missing_failed_cancelled_pending_or_wrong_job_fails(self):
        original = copy.deepcopy(self.jobs)
        for change in ({'conclusion': 'failure'}, {'conclusion': 'cancelled'},
                       {'status': 'in_progress', 'conclusion': None}, {'head_sha': 'c' * 40},
                       {'run_id': 99}, {'run_attempt': 2}):
            self.jobs = copy.deepcopy(original)
            self.jobs[0].update(change)
            with self.subTest(change=change), self.assertRaises(Invalid):
                self.authorize()
        self.jobs = original[:1]
        with self.assertRaises(Invalid):
            self.authorize()

    def test_required_check_failure_or_missing_blocks(self):
        original = copy.deepcopy(self.checks)
        for state, conclusion in [('completed', 'failure'), ('completed', 'cancelled'), ('queued', None)]:
            self.checks = copy.deepcopy(original)
            self.checks[0].update(status=state, conclusion=conclusion)
            with self.subTest(state=state, conclusion=conclusion), self.assertRaises(Invalid):
                self.authorize()
        self.checks = original[:1]
        with self.assertRaises(Invalid):
            self.authorize()

    def test_newer_failed_check_blocks_but_old_failure_does_not_poison_rerun(self):
        older = dict(self.checks[0], id=300, started_at='2026-11-03T00:00:00Z', conclusion='failure')
        self.checks.append(older)
        self.authorize()
        older['started_at'] = '2026-11-05T00:00:00Z'
        with self.assertRaises(Invalid):
            self.authorize()

    def test_wrong_head_branch_event_and_workflow_fail(self):
        for field, value in [('head_sha', 'c' * 40), ('head_branch', 'other'), ('event', 'pull_request'),
                             ('workflow_id', 99), ('path', '.github/workflows/other.yml')]:
            self.runs = [dict(self.run, **{field: value})]
            with self.subTest(field=field), self.assertRaises(Invalid):
                self.authorize()
        self.runs = [self.run]
        self.branch_details['commit']['sha'] = 'c' * 40
        with self.assertRaises(Invalid):
            self.authorize()

    def test_environment_still_requires_a_separate_deployment_approval(self):
        environment = {'id': 77, 'protection_rules': [{'type': 'required_reviewers',
                       'reviewers': [{'type': 'User', 'reviewer': {'id': 5}}], 'prevent_self_review': True}]}
        workflow = {'id': 13, 'path': '.github/workflows/release.yml', 'state': 'active'}
        run = {'id': 123, 'workflow_id': 13, 'event': 'workflow_dispatch', 'head_branch': 'main',
               'head_sha': self.commit, 'path': '.github/workflows/release.yml', 'run_attempt': 1,
               'actor': {'login': 'dispatcher'}, 'triggering_actor': {'login': 'dispatcher'}}
        approval = {'state': 'approved', 'user': {'login': 'reviewer', 'id': 5},
                    'environments': [{'id': 77, 'name': 'release-publication'}]}
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}):
            replies = [environment, workflow, run, [approval]]
            with patch.object(auth, 'api', side_effect=replies):
                auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
            for bad in ([], [dict(approval, state='rejected')],
                        [dict(approval, user={'login': 'dispatcher'})], [approval, approval]):
                with self.subTest(approval=bad), patch.object(auth, 'api',
                        side_effect=[environment, workflow, run, bad]), self.assertRaises(Invalid):
                    auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
        environment['protection_rules'][0]['prevent_self_review'] = False
        with patch.object(auth, 'api', return_value=environment), self.assertRaises(Invalid):
            auth.check_environment('owner/repo', 'release-publication')


if __name__ == '__main__':
    unittest.main()
