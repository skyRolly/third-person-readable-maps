#!/usr/bin/env python3
"""Fail closed unless release sources, CI, reviews and the environment are protected."""
import argparse
import json
import os
import sys
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from release import Invalid, load_plan, require


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


def page_list(path):
    result = []
    for page in range(1, 101):
        items = api(path + ('&' if '?' in path else '?') + urlencode({'per_page': 100, 'page': page}))
        require(isinstance(items, list), f'expected GitHub list: {path}')
        result.extend(items)
        if len(items) < 100:
            return result
    raise Invalid(f'too many pages: {path}')


def protected_branch(repo, branch, commit):
    base = f'repos/{repo}'
    encoded = quote(branch, safe='')
    details = api(f'{base}/branches/{encoded}')
    require(details.get('protected') and details.get('commit', {}).get('sha') == commit,
            f'{branch}: protected branch HEAD must equal the pinned commit')
    protection = api(f'{base}/branches/{encoded}/protection')
    reviews = protection.get('required_pull_request_reviews') or {}
    require(reviews.get('required_approving_review_count', 0) >= 1 and reviews.get('dismiss_stale_reviews') is True,
            f'{branch}: branch protection must require approval and dismiss stale approvals')
    require((protection.get('enforce_admins') or {}).get('enabled') is True,
            f'{branch}: branch protection must include administrators')
    checks = protection.get('required_status_checks') or {}
    require(checks.get('contexts') or checks.get('checks'), f'{branch}: required CI checks are not configured')
    # A reviewed merge commit on this branch avoids treating a directly-pushed
    # commit as approved, even if someone changes protection later.
    pulls = page_list(f'{base}/commits/{commit}/pulls')
    pulls = [p for p in pulls if p.get('merged_at') and p.get('merge_commit_sha') == commit
             and p.get('base', {}).get('ref') == branch]
    require(pulls, f'{branch}: HEAD must be the merge commit of a reviewed PR into this branch')
    reviewed = False
    for pr in pulls:
        latest = {}
        for review in page_list(f"{base}/pulls/{pr['number']}/reviews"):
            login = (review.get('user') or {}).get('login')
            if login and review.get('state') not in ('COMMENTED', 'PENDING'):
                latest[login] = review.get('state')
        reviewed |= 'APPROVED' in latest.values()
    require(reviewed, f'{branch}: merged PR has no current approving review')
    runs = api(f'{base}/actions/workflows/ci.yml/runs?' + urlencode({
        'head_sha': commit, 'branch': branch, 'event': 'push', 'status': 'completed', 'per_page': 100}))
    passing = [r for r in runs.get('workflow_runs', []) if r.get('head_sha') == commit and
               r.get('head_branch') == branch and r.get('conclusion') == 'success']
    for run in passing:
        jobs = api(f"{base}/actions/runs/{run['id']}/jobs?per_page=100").get('jobs', [])
        passed = {j.get('name') for j in jobs if j.get('conclusion') == 'success'}
        if {'Build (ubuntu-latest)', 'Build (windows-latest)'} <= passed:
            return
    raise Invalid(f'{branch}: no successful push CI run for this SHA with both OS builds')


def check_environment(repo, environment):
    details = api(f'repos/{repo}/environments/{quote(environment, safe="")}')
    rules = details.get('protection_rules', [])
    require(any(r.get('type') == 'required_reviewers' and r.get('reviewers') for r in rules),
            f'environment {environment} must require at least one reviewer')


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
        check_environment(repo, args.environment)
        protected_branch(repo, 'main', args.coordinator_sha)
        for name, spec in cfg['groups'].items():
            protected_branch(repo, spec['branch'], plan['groups'][name]['commit'])
        print('Release environment, reviewed branch heads and Linux/Windows CI are authorized.')
    except (Invalid, OSError, ValueError, TypeError) as exc:
        print(f'release authorization failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
