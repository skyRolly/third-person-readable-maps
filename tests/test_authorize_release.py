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
        self.protection = {
            'required_pull_request_reviews': {'required_approving_review_count': 1, 'dismiss_stale_reviews': True,
                                              'require_code_owner_reviews': False, 'require_last_push_approval': False,
                                              'bypass_pull_request_allowances': {'users': [], 'teams': [], 'apps': []}},
            'enforce_admins': {'enabled': True}, 'allow_force_pushes': {'enabled': False},
            'allow_deletions': {'enabled': False},
            'required_status_checks': {'strict': True, 'contexts': sorted(self.required),
                                       'checks': [{'context': n, 'app_id': a} for n, a in self.required.items()]}}
        self.run = {'id': 10, 'created_at': '2026-11-04T00:00:00Z', 'workflow_id': 12,
                    'path': '.github/workflows/ci.yml', 'head_sha': self.commit, 'head_branch': self.branch,
                    'event': 'push', 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success'}
        self.runs = [self.run]
        self.jobs = [{'id': i, 'run_id': 10, 'run_attempt': 1, 'head_sha': self.commit, 'name': n,
                      'status': 'completed', 'conclusion': 'success'} for i, n in enumerate(sorted(self.required), 101)]
        self.checks = [{'id': j['id'], 'name': j['name'], 'app': {'id': auth.ACTIONS_APP},
                        'head_sha': self.commit, 'started_at': '2026-11-04T00:00:01Z',
                        'status': 'completed', 'conclusion': 'success'} for j in self.jobs]
        self.pr = {'number': 1, 'merged_at': '2026-11-04T00:00:00Z', 'merge_commit_sha': self.commit,
                   'base': {'ref': self.branch}, 'head': {'sha': self.head}, 'user': {'login': 'author'}}
        self.reviews = [{'id': 1, 'user': {'login': 'reviewer'}, 'state': 'APPROVED', 'commit_id': self.head,
                         'submitted_at': '2026-11-03T00:00:00Z'}]
        self.rulesets = []
        self.effective_rules = []
        self.rule_detail = {}
        self.branch_details = {'protected': True, 'commit': {'sha': self.commit}}
        self.mock = patch.object(auth, 'api', side_effect=self.api)
        self.mock.start()
        self.graph = patch.object(auth, 'graphql', return_value={'repository': {'ref': {
            'name': self.branch, 'target': {'oid': self.commit}, 'branchProtectionRule': {
                'id': 'rule', 'requiresCodeOwnerReviews': False, 'requireLastPushApproval': False,
                'bypassPullRequestAllowances': {'totalCount': 0}}}}})
        self.graph.start()

    def tearDown(self):
        self.mock.stop()
        self.graph.stop()

    def api(self, path, **kwargs):
        branch_path = '/branches/' + quote(self.branch, safe='')
        if branch_path + '/protection' in path:
            return self.protection
        if branch_path in path and '/rules/' not in path:
            return self.branch_details
        if '/rules/branches/' in path:
            return self.effective_rules
        if '/rulesets?' in path:
            return self.rulesets
        if '/rulesets/' in path:
            return self.rule_detail
        if '/commits/' in path and '/pulls' in path:
            return [self.pr]
        if '/reviews' in path:
            return self.reviews
        if '/collaborators/' in path:
            return {'permission': 'write'}
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
        auth.protected_branch('owner/repo', self.branch, self.commit)

    def test_valid_current_protected_reviewed_sources(self):
        self.authorize()

    def test_main_requires_its_own_exact_coordination_job(self):
        self.branch = 'main'
        self.required = {name: auth.ACTIONS_APP for name in auth.COORDINATION_CHECKS}
        checks = self.protection['required_status_checks']
        checks['contexts'] = sorted(self.required)
        checks['checks'] = [{'context': n, 'app_id': a} for n, a in self.required.items()]
        self.run['head_branch'] = 'main'
        self.run['path'] = '.github/workflows/ci.yml@main'
        self.jobs = [dict(self.jobs[0], name='Validate coordination')]
        self.checks = [dict(self.checks[0], name='Validate coordination')]
        self.pr['base']['ref'] = 'main'
        graph = {'repository': {'ref': {'name': 'main', 'target': {'oid': self.commit},
                 'branchProtectionRule': {'id': 'rule', 'requiresCodeOwnerReviews': False,
                 'requireLastPushApproval': False, 'bypassPullRequestAllowances': {'totalCount': 0}}}}}
        with patch.object(auth, 'graphql', return_value=graph):
            self.authorize()
            # A successful build, another workflow's check, an old run, or the
            # wrong app must not substitute for this exact push job.
            self.jobs[0]['name'] = 'Build (ubuntu-latest)'
            with self.assertRaises(Invalid):
                self.authorize()
            self.jobs[0]['name'] = 'Validate coordination'
            self.checks[0]['id'] += 1
            with self.assertRaises(Invalid):
                self.authorize()
            self.checks[0]['id'] -= 1
            self.run['path'] = '.github/workflows/other.yml@main'
            with self.assertRaises(Invalid):
                self.authorize()
            self.run['path'] = '.github/workflows/ci.yml@main'
            self.runs.append(dict(self.run, id=99, created_at='2026-11-05T00:00:00Z', conclusion='failure'))
            with self.assertRaises(Invalid):
                self.authorize()
            self.runs.pop()
            checks['checks'][0]['app_id'] = 123
            with self.assertRaises(Invalid):
                self.authorize()

    def test_game_branch_cannot_use_coordination_check_in_place_of_builds(self):
        self.protection['required_status_checks'] = {'strict': True, 'contexts': ['Validate coordination'],
            'checks': [{'context': 'Validate coordination', 'app_id': auth.ACTIONS_APP}]}
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

    def test_deployment_run_path_and_workflow_identity(self):
        environment = {'id': 77, 'protection_rules': [{'type': 'required_reviewers',
                       'reviewers': [{'type': 'User', 'reviewer': {'id': 5}}], 'prevent_self_review': True}]}
        workflow = {'id': 13, 'path': '.github/workflows/release.yml', 'state': 'active'}
        path = workflow['path']
        run = {'id': 123, 'workflow_id': 13, 'event': 'workflow_dispatch', 'head_branch': 'main',
               'head_sha': self.commit, 'path': path, 'run_attempt': 1,
               'actor': {'login': 'dispatcher'}, 'triggering_actor': {'login': 'dispatcher'}}
        approval = {'state': 'approved', 'user': {'login': 'reviewer', 'id': 5},
                    'environments': [{'id': 77, 'name': 'release-publication'}]}
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}):
            for value in (path, path + '@main', path + '@refs/heads/main', 'owner/repo/' + path + '@main'):
                with self.subTest(accepted=value), patch.object(auth, 'api',
                        side_effect=[environment, workflow, dict(run, path=value), [approval]]):
                    auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
            for change in ({'path': path + '@other'}, {'path': path + '@main@other'},
                           {'path': '.github/workflows/ci.yml@main'}, {'path': 'evil/repo/' + path + '@main'},
                           {'id': 124}, {'workflow_id': 14}, {'head_sha': 'c' * 40},
                           {'head_branch': 'other'}, {'event': 'push'}):
                with self.subTest(rejected=change), patch.object(auth, 'api',
                        side_effect=[environment, workflow, dict(run, **change)]), self.assertRaises(Invalid):
                    auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
            for bad in (dict(workflow, path='.github/workflows/other.yml'), dict(workflow, state='disabled_manually')):
                with patch.object(auth, 'api', side_effect=[environment, bad]), self.assertRaises(Invalid):
                    auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)

    def test_unrelated_unpinned_or_wrong_app_checks_fail(self):
        for checks in ([{'context': 'Unrelated', 'app_id': 123}],
                       [{'context': n, 'app_id': -1} for n in self.required],
                       [{'context': n, 'app_id': 123} for n in self.required]):
            self.protection['required_status_checks']['checks'] = checks
            with self.subTest(checks=checks), self.assertRaises(Invalid):
                self.authorize()

    def test_missing_rest_bypass_uses_complete_graphql_count(self):
        del self.protection['required_pull_request_reviews']['bypass_pull_request_allowances']
        response = {'repository': {'ref': {'name': self.branch, 'target': {'oid': self.commit},
                    'branchProtectionRule': {'id': 'rule', 'requiresCodeOwnerReviews': False, 'requireLastPushApproval': False,
                                             'bypassPullRequestAllowances': {'totalCount': 0}}}}}
        with patch.object(auth, 'graphql', return_value=response):
            self.authorize()
        response['repository']['ref']['branchProtectionRule']['bypassPullRequestAllowances']['totalCount'] = 1
        with patch.object(auth, 'graphql', return_value=response), self.assertRaises(Invalid):
            self.authorize()
        with patch.object(auth, 'graphql', side_effect=OSError('unavailable')), self.assertRaises(OSError):
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
        for change in ({'conclusion': 'failure'}, {'conclusion': 'cancelled'}, {'status': 'in_progress', 'conclusion': None},
                       {'head_sha': 'c' * 40}, {'run_id': 99}, {'run_attempt': 2}):
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

    def test_stale_dismissed_missing_or_author_approval_fails(self):
        original = self.reviews[0]
        for change in ({'state': 'DISMISSED'}, {'state': 'CHANGES_REQUESTED'}, {'commit_id': 'c' * 40},
                       {'submitted_at': '2026-11-05T00:00:00Z'}, {'user': {'login': 'author'}}):
            self.reviews = [dict(original, **change)]
            with self.subTest(change=change), self.assertRaises(Invalid):
                self.authorize()
        self.reviews = []
        with self.assertRaises(Invalid):
            self.authorize()
        self.reviews = [original, dict(original, id=2, state='DISMISSED', submitted_at='2026-11-05T00:00:00Z')]
        with self.assertRaises(Invalid):
            self.authorize()

    def test_environment_requires_a_real_independent_approval_for_this_dispatch(self):
        environment = {'id': 77, 'protection_rules': [{'type': 'required_reviewers',
                       'reviewers': [{'type': 'User', 'reviewer': {'id': 5}}], 'prevent_self_review': True}]}
        workflow = {'id': 13, 'path': '.github/workflows/release.yml', 'state': 'active'}
        run = {'id': 123, 'workflow_id': 13, 'event': 'workflow_dispatch', 'head_branch': 'main', 'head_sha': self.commit,
               'path': '.github/workflows/release.yml', 'run_attempt': 1,
               'actor': {'login': 'dispatcher'}, 'triggering_actor': {'login': 'dispatcher'}}
        approval = {'state': 'approved', 'user': {'login': 'reviewer', 'id': 5},
                    'environments': [{'id': 77, 'name': 'release-publication'}]}
        replies = [environment, workflow, run, [approval]]
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1'}):
            with patch.object(auth, 'api', side_effect=replies):
                auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
            for bad in ([], [dict(approval, state='rejected')], [dict(approval, user={'login': 'dispatcher'})],
                        [approval, approval]):
                with self.subTest(approval=bad), patch.object(auth, 'api', side_effect=[environment, workflow, run, bad]):
                    with self.assertRaises(Invalid):
                        auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '2'}):
            with self.assertRaises(Invalid):
                auth.check_deployment_approval('owner/repo', 'release-publication', self.commit)
        environment['protection_rules'][0]['prevent_self_review'] = False
        with patch.object(auth, 'api', return_value=environment), self.assertRaises(Invalid):
            auth.check_environment('owner/repo', 'release-publication')

    def test_protection_changes_ruleset_bypasses_and_unavailable_data_block(self):
        self.authorize()
        self.protection['enforce_admins']['enabled'] = False
        with self.assertRaises(Invalid):
            self.authorize()
        self.protection['enforce_admins']['enabled'] = True
        self.effective_rules = [{'type': 'required_status_checks', 'ruleset_id': 7}]
        with self.assertRaises(Invalid):
            self.authorize()
        self.effective_rules = [{'type': 'pull_request', 'ruleset_id': 7}]
        with self.assertRaises(Invalid):
            self.authorize()
        with patch.object(auth, 'api', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                self.authorize()


if __name__ == '__main__':
    unittest.main()
