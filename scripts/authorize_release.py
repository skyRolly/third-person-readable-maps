#!/usr/bin/env python3
"""Fail closed unless current release sources, reviews, checks and environments qualify."""
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


def graphql(query, variables):
    token = os.environ.get('GH_TOKEN')
    require(bool(token), 'GH_TOKEN is required for release authorization')
    request = Request('https://api.github.com/graphql', data=json.dumps({'query': query, 'variables': variables}).encode(),
                      headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                               'Content-Type': 'application/json', 'User-Agent': 'readable-maps-release'})
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise Invalid(f'GitHub GraphQL authorization query failed with HTTP {exc.code}') from exc
    require(isinstance(result, dict) and not result.get('errors') and isinstance(result.get('data'), dict),
            'GitHub GraphQL authorization data is unavailable')
    return result['data']


def no_review_bypass(repo, branch, commit, bypass):
    if bypass is not None:
        require(isinstance(bypass, dict) and all(k in bypass and not bypass[k] for k in ('users', 'teams', 'apps')),
                f'{branch}: PR review bypass permissions are present or unavailable')
    # Inspect the applicable rule even when REST omits optional settings.
    owner, name = repo.split('/')
    query = """query($owner:String!,$name:String!,$branch:String!){
      repository(owner:$owner,name:$name){ref(qualifiedName:$branch){name target{oid}
        branchProtectionRule{id requiresCodeOwnerReviews requireLastPushApproval
          bypassPullRequestAllowances(first:1){totalCount}}}}}
    """
    data = graphql(query, {'owner': owner, 'name': name, 'branch': 'refs/heads/' + branch})
    ref = ((data.get('repository') or {}).get('ref') or {})
    rule = ref.get('branchProtectionRule') or {}
    count = (rule.get('bypassPullRequestAllowances') or {}).get('totalCount')
    require(ref.get('name') == branch and (ref.get('target') or {}).get('oid') == commit and
            rule.get('id') and type(count) is int and count == 0 and
            rule.get('requiresCodeOwnerReviews') is False and rule.get('requireLastPushApproval') is False,
            f'{branch}: PR review bypass permissions are present or unavailable')


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


def check_rulesets(repo, branch):
    # Rulesets can add requirements or bypasses that the legacy protection
    # response does not describe. Until those semantics can be verified in
    # full, allow the supported legacy-protection configuration only.
    base = f'repos/{repo}'
    effective = page_list(f'{base}/rules/branches/{quote(branch, safe="")}')
    require(not effective, f'{branch}: effective branch rulesets are not supported for release authorization')
    # Also require the ruleset inventory to be readable; an unavailable API is
    # not evidence that no additional rules apply.
    page_list(f'{base}/rulesets?includes_parents=true')


def check_ci(repo, branch, commit, required):
    base = f'repos/{repo}'
    workflow = api(f'{base}/actions/workflows/ci.yml')
    require(workflow.get('id') and workflow.get('path') == '.github/workflows/ci.yml' and
            workflow.get('state') == 'active', f'{branch}: CI workflow unavailable')
    runs = page_list(f"{base}/actions/workflows/ci.yml/runs?" + urlencode({
        'head_sha': commit, 'branch': branch, 'event': 'push'}), 'workflow_runs')
    require(runs, f'{branch}: no push CI run for pinned HEAD')
    require(all(r.get('id') and r.get('created_at') and r.get('workflow_id') == workflow['id'] and
                r.get('path') == '.github/workflows/ci.yml' and r.get('head_sha') == commit and
                r.get('head_branch') == branch and r.get('event') == 'push' for r in runs),
            f'{branch}: inconsistent CI run identity')
    run = max(runs, key=lambda r: (r['created_at'], r['id']))
    attempt = run.get('run_attempt')
    require(isinstance(attempt, int) and attempt > 0 and run.get('status') == 'completed' and
            run.get('conclusion') == 'success', f'{branch}: latest push CI run is not successful')
    jobs = page_list(f"{base}/actions/runs/{run['id']}/attempts/{attempt}/jobs", 'jobs')
    for name in BUILD_CHECKS:
        matching = [j for j in jobs if j.get('name') == name]
        require(len(matching) == 1, f'{branch}: missing or ambiguous {name} job')
        job = matching[0]
        require(job.get('run_id') == run['id'] and job.get('run_attempt') == attempt and
                job.get('head_sha') == commit and job.get('status') == 'completed' and
                job.get('conclusion') == 'success', f'{branch}: {name} is not successful on latest attempt')
    # Confirm GitHub's currently visible latest check runs, including additional
    # required checks. Reject ambiguous or unpinned publishers rather than
    # treating a similarly named status from another app as equivalent.
    checks = page_list(f'{base}/commits/{commit}/check-runs?filter=latest', 'check_runs')
    for name, app_id in required.items():
        matching = [c for c in checks if c.get('name') == name and (c.get('app') or {}).get('id') == app_id]
        require(matching and all(c.get('head_sha') == commit and c.get('started_at') for c in matching),
                f'{branch}: required check {name} is missing or has an unavailable start time')
        if name in BUILD_CHECKS:
            job_id = next(j['id'] for j in jobs if j.get('name') == name)
            own = [c for c in matching if c.get('id') == job_id]
            require(len(own) == 1, f'{branch}: {name} does not match push CI job')
            # A later check on the same SHA may supersede the push job (e.g. a
            # PR run). Older failures must not permanently poison a rerun.
            relevant = [c for c in matching if c['started_at'] >= own[0]['started_at']]
        else:
            latest = max(c['started_at'] for c in matching)
            relevant = [c for c in matching if c['started_at'] == latest]
        require(all(c.get('status') == 'completed' and c.get('conclusion') == 'success' for c in relevant),
                f'{branch}: current required check {name} is not successful')



def protected_branch(repo, branch, commit):
    base = f'repos/{repo}'
    encoded = quote(branch, safe='')
    details = api(f'{base}/branches/{encoded}')
    require(details.get('protected') is True and details.get('commit', {}).get('sha') == commit,
            f'{branch}: protected branch HEAD must equal the pinned commit')
    protection = api(f'{base}/branches/{encoded}/protection')
    reviews = protection.get('required_pull_request_reviews') or {}
    require(reviews.get('required_approving_review_count', 0) >= 1 and reviews.get('dismiss_stale_reviews') is True,
            f'{branch}: protection must require approval and dismiss stale approvals')
    require(reviews.get('require_code_owner_reviews') is False and
            reviews.get('require_last_push_approval') in (None, False),
            f'{branch}: code-owner or last-push approval rules are unsupported')
    require((protection.get('enforce_admins') or {}).get('enabled') is True,
            f'{branch}: protection must include administrators')
    bypass = reviews.get('bypass_pull_request_allowances')
    no_review_bypass(repo, branch, commit, bypass)
    require((protection.get('allow_force_pushes') or {}).get('enabled') is False and
            (protection.get('allow_deletions') or {}).get('enabled') is False,
            f'{branch}: force pushes or deletion are permitted or unavailable')
    checks = protection.get('required_status_checks') or {}
    configured = checks.get('checks')
    require(checks.get('strict') is True and isinstance(configured, list) and configured,
            f'{branch}: strict, app-pinned required checks are unavailable')
    required = {}
    for check in configured:
        name, app = check.get('context'), check.get('app_id')
        require(isinstance(name, str) and name and isinstance(app, int) and app > 0 and name not in required,
                f'{branch}: required checks must have unique names and pinned apps')
        required[name] = app
    require(all(required.get(name) == ACTIONS_APP for name in BUILD_CHECKS),
            f'{branch}: both Linux and Windows checks must be required from GitHub Actions')
    require(set(checks.get('contexts', [])) == set(required), f'{branch}: ambiguous required check configuration')
    check_rulesets(repo, branch)
    pulls = page_list(f'{base}/commits/{commit}/pulls')
    pulls = [p for p in pulls if p.get('merged_at') and p.get('merge_commit_sha') == commit
             and p.get('base', {}).get('ref') == branch]
    require(len(pulls) == 1, f'{branch}: HEAD must be the unambiguous merge commit of a PR into this branch')
    pr = pulls[0]
    head = (pr.get('head') or {}).get('sha')
    author = (pr.get('user') or {}).get('login')
    require(head and author and pr.get('number'), f'{branch}: incomplete merged PR identity')
    latest = {}
    for review in page_list(f"{base}/pulls/{pr['number']}/reviews"):
        login = (review.get('user') or {}).get('login')
        state = review.get('state')
        if login and state not in ('COMMENTED', 'PENDING'):
            require(review.get('submitted_at'), f'{branch}: review timestamp unavailable')
            if login not in latest or (review['submitted_at'], review.get('id', 0)) > (latest[login]['submitted_at'], latest[login].get('id', 0)):
                latest[login] = review
    approvals = [login for login, r in latest.items() if login != author and r.get('state') == 'APPROVED' and
                 r.get('commit_id') == head and r['submitted_at'] <= pr['merged_at']]
    eligible = []
    for login in approvals:
        permission = api(f'{base}/collaborators/{quote(login, safe="")}/permission')
        if permission.get('permission') in ('admin', 'maintain', 'write'):
            eligible.append(login)
    require(len(eligible) >= reviews['required_approving_review_count'] and
            not any(r.get('state') == 'CHANGES_REQUESTED' for r in latest.values()),
            f'{branch}: merged PR lacks current, non-stale approvals')
    check_ci(repo, branch, commit, required)


def check_environment(repo, environment):
    details = api(f'repos/{repo}/environments/{quote(environment, safe="")}')
    rules = details.get('protection_rules', [])
    require(details.get('id'), f'environment {environment} has no stable identity')
    require(any(r.get('type') == 'required_reviewers' and r.get('reviewers') and
                r.get('prevent_self_review') is True for r in rules),
            f'environment {environment} must require independent reviewers')
    return details


def check_deployment_approval(repo, environment, coordinator_sha):
    # The REST environment response does not expose administrator bypass. Check
    # that this run has an actual independent approval rather than inferring one
    # from configuration or the fact that a job started. Approval history has no
    # attempt number, so retries need a fresh workflow dispatch.
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
    run = api(f'repos/{repo}/actions/runs/{run_id}')
    require(run.get('event') == 'workflow_dispatch' and run.get('head_branch') == 'main' and
            run.get('head_sha') == coordinator_sha and run.get('path') == '.github/workflows/release.yml' and
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
            f'environment {environment} lacks an unambiguous independent approval for this run')


def authorize(repo, cfg, plan, coordinator_sha, environment):
    check_environment(repo, environment)
    protected_branch(repo, 'main', coordinator_sha)
    for name, spec in cfg['groups'].items():
        protected_branch(repo, spec['branch'], plan['groups'][name]['commit'])


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
        print('Release environment, reviewed branch heads and current Linux/Windows CI are authorized.')
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'release authorization failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
