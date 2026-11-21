#!/usr/bin/env python3
"""Fail closed unless exact integrated sources, CI and environments qualify."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from release import Invalid, load_plan, require

ACTIONS_APP = 15368
BUILD_CHECKS = {'Build (ubuntu-latest)', 'Build (windows-latest)'}
COORDINATION_CHECKS = {'Validate coordination', 'Validate live release prerequisites'}


def role_checks(branch):
    if branch == 'main':
        return COORDINATION_CHECKS
    require(branch.startswith('mc/'), f'{branch}: unsupported branch role')
    return BUILD_CHECKS


def api(path, *, allow_missing=False):
    token = os.environ.get('GH_TOKEN')
    require(bool(token), 'GH_TOKEN is required for release authorization')
    request = Request('https://api.github.com/' + path, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'readable-maps-release'})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404 and allow_missing:
            return None
        raise Invalid(f'GitHub authorization query failed with HTTP {exc.code}: {path}') from exc


def page_list(path, key=None):
    result = []
    for page in range(1, 101):
        data = api(path + ('&' if '?' in path else '?') + urlencode({'per_page': 100, 'page': page}))
        items = data.get(key) if key and isinstance(data, dict) else data
        require(isinstance(items, list), f'expected GitHub list: {path}')
        result.extend(items)
        if len(items) < 100:
            return result
    raise Invalid(f'too many pages: {path}')


def check_unprotected_policy(repo, branch, commit):
    """Require the stated owner policy: exact branch head and no active rules."""
    base = f'repos/{repo}'
    encoded = quote(branch, safe='')
    details = api(f'{base}/branches/{encoded}')
    require(details.get('protected') is False and details.get('commit', {}).get('sha') == commit,
            f'{branch}: branch must be unprotected and HEAD must equal the pinned commit')
    effective = page_list(f'{base}/rules/branches/{encoded}')
    require(not effective, f'{branch}: effective branch rules are present')
    rulesets = page_list(f'{base}/rulesets?includes_parents=true')
    require(not rulesets, 'repository or inherited rulesets are present')


def workflow_run_path_matches(path, repo, workflow_path, branch):
    """Accept documented run-path spellings for only this repository and ref."""
    if not isinstance(path, str):
        return False
    paths = (workflow_path, f'{repo}/{workflow_path}')
    return path in {candidate + suffix for candidate in paths
                    for suffix in ('', '@' + branch, '@refs/heads/' + branch)}


def check_ci(repo, branch, commit, required, role_required):
    base = f'repos/{repo}'
    workflow = api(f'{base}/actions/workflows/ci.yml')
    require(workflow.get('id') and workflow.get('path') == '.github/workflows/ci.yml' and
            workflow.get('state') == 'active', f'{branch}: CI workflow unavailable')
    runs = page_list(f"{base}/actions/workflows/ci.yml/runs?" + urlencode({
        'head_sha': commit, 'branch': branch, 'event': 'push'}), 'workflow_runs')
    require(runs, f'{branch}: no push CI run for pinned HEAD')
    require(all(r.get('id') and r.get('created_at') and r.get('workflow_id') == workflow['id'] and
                workflow_run_path_matches(r.get('path'), repo, '.github/workflows/ci.yml', branch) and
                r.get('head_sha') == commit and r.get('head_branch') == branch and r.get('event') == 'push'
                for r in runs), f'{branch}: inconsistent CI run identity')
    run = max(runs, key=lambda r: (r['created_at'], r['id']))
    attempt = run.get('run_attempt')
    require(isinstance(attempt, int) and attempt > 0 and run.get('status') == 'completed' and
            run.get('conclusion') == 'success', f'{branch}: latest push CI run is not successful')
    jobs = page_list(f"{base}/actions/runs/{run['id']}/attempts/{attempt}/jobs", 'jobs')
    for name in role_required:
        matching = [j for j in jobs if j.get('name') == name]
        require(len(matching) == 1, f'{branch}: missing or ambiguous {name} job')
        job = matching[0]
        require(job.get('run_id') == run['id'] and job.get('run_attempt') == attempt and
                job.get('head_sha') == commit and job.get('status') == 'completed' and
                job.get('conclusion') == 'success', f'{branch}: {name} is not successful on latest attempt')
    checks = page_list(f'{base}/commits/{commit}/check-runs?filter=latest', 'check_runs')
    for name, app_id in required.items():
        matching = [c for c in checks if c.get('name') == name and (c.get('app') or {}).get('id') == app_id]
        require(matching and all(c.get('head_sha') == commit and c.get('started_at') for c in matching),
                f'{branch}: required check {name} is missing or has an unavailable start time')
        if name in role_required:
            job_id = next(j['id'] for j in jobs if j.get('name') == name)
            own = [c for c in matching if c.get('id') == job_id]
            require(len(own) == 1, f'{branch}: {name} does not match push CI job')
            relevant = [c for c in matching if c['started_at'] >= own[0]['started_at']]
        else:
            latest = max(c['started_at'] for c in matching)
            relevant = [c for c in matching if c['started_at'] == latest]
        require(all(c.get('status') == 'completed' and c.get('conclusion') == 'success' for c in relevant),
                f'{branch}: current required check {name} is not successful')


def integrated_branch(repo, owner, branch, commit):
    """Verify an exact owner-merged PR tip and its voluntary branch-role CI."""
    check_unprotected_policy(repo, branch, commit)
    base = f'repos/{repo}'
    pulls = page_list(f'{base}/commits/{commit}/pulls')
    pulls = [p for p in pulls if p.get('merged_at') and p.get('merge_commit_sha') == commit and
             p.get('base', {}).get('ref') == branch]
    require(len(pulls) == 1, f'{branch}: HEAD must be the unambiguous merge commit of a PR into this branch')
    pr = pulls[0]
    require(pr.get('head', {}).get('sha') and
            (pr.get('merged_by') or {}).get('login', '').casefold() == owner.casefold(),
            f'{branch}: PR integration must be performed by repository owner {owner}')
    required = {name: ACTIONS_APP for name in role_checks(branch)}
    check_ci(repo, branch, commit, required, role_checks(branch))


def check_environment(repo, environment):
    details = api(f'repos/{repo}/environments/{quote(environment, safe="")}')
    rules = details.get('protection_rules', [])
    require(details.get('id'), f'environment {environment} has no stable identity')
    require(any(r.get('type') == 'required_reviewers' and r.get('reviewers') and
                r.get('prevent_self_review') is True for r in rules),
            f'environment {environment} must retain its required deployment reviewers')
    return details


def check_deployment_approval(repo, environment, coordinator_sha):
    # Deployment approval remains a separate release control, independent of
    # PR review policy. Only a first-attempt workflow dispatch is attributable.
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    require(run_id.isdigit() and os.environ.get('GITHUB_RUN_ATTEMPT') == '1',
            'a first-attempt workflow dispatch is required for deployment approval')
    details = check_environment(repo, environment)
    env_id = details['id']
    reviewers = {r.get('reviewer', {}).get('id') for rule in details['protection_rules']
                 if rule.get('type') == 'required_reviewers' and rule.get('prevent_self_review') is True
                 for r in rule.get('reviewers', []) if r.get('type') == 'User'}
    reviewers.discard(None)
    require(reviewers, f'environment {environment} needs an explicitly listed user reviewer')
    workflow = api(f'repos/{repo}/actions/workflows/release.yml')
    require(workflow.get('id') and workflow.get('path') == '.github/workflows/release.yml' and
            workflow.get('state') == 'active', 'release workflow unavailable')
    run = api(f'repos/{repo}/actions/runs/{run_id}')
    require(run.get('id') == int(run_id) and run.get('workflow_id') == workflow['id'] and
            run.get('event') == 'workflow_dispatch' and run.get('head_branch') == 'main' and
            run.get('head_sha') == coordinator_sha and
            workflow_run_path_matches(run.get('path'), repo, '.github/workflows/release.yml', 'main') and
            run.get('run_attempt') == 1, 'release workflow run identity does not match')
    actors = {(run.get('actor') or {}).get('login'), (run.get('triggering_actor') or {}).get('login')}
    require(None not in actors and all(actors), 'release workflow actor is unavailable')
    approvals = page_list(f'repos/{repo}/actions/runs/{run_id}/approvals')
    relevant = [a for a in approvals if any(e.get('id') == env_id and e.get('name') == environment
                                           for e in a.get('environments', []))]
    require(len(relevant) == 1 and relevant[0].get('state') == 'approved' and
            (relevant[0].get('user') or {}).get('login') not in actors and
            (relevant[0].get('user') or {}).get('login') and
            (relevant[0].get('user') or {}).get('id') in reviewers,
            f'environment {environment} lacks an unambiguous independent deployment approval for this run')


def authorize(repo, cfg, plan, coordinator_sha, environment):
    check_environment(repo, environment)
    repository = api(f'repos/{repo}')
    owner = (repository.get('owner') or {}).get('login')
    require(owner, 'repository owner identity is unavailable')
    integrated_branch(repo, owner, 'main', coordinator_sha)
    for name, spec in cfg['groups'].items():
        integrated_branch(repo, owner, spec['branch'], plan['groups'][name]['commit'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--coordinator-sha', required=True)
    parser.add_argument('--environment', required=True, choices=['release-draft', 'release-publication'])
    args = parser.parse_args()
    try:
        cfg, plan = load_plan(args.plan)
        repo = os.environ.get('GITHUB_REPOSITORY', '')
        require(repo and repo.count('/') == 1, 'GITHUB_REPOSITORY is missing')
        authorize(repo, cfg, plan, args.coordinator_sha, args.environment)
        print('Owner-integrated branch heads, current branch-role CI and release environment are authorized.')
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'release authorization failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
