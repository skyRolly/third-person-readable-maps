#!/usr/bin/env python3
"""Check a candidate pin, including a narrowly defined post-merge deletion.

An auto-deleted candidate remains monitorable at its pinned commit only when
GitHub proves that the matching PR was merged without changing that tree and
the maintenance branch has not moved since that merge. The scan remains a
candidate scan; a reviewed transition is still required for maintenance scans.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import audit_candidate_dependencies as audit
from release import Invalid, require, read_json

REPO = 'skyRolly/third-person-readable-maps'
API = 'https://api.github.com/repos/' + REPO + '/'


def branch_head(info):
    return info.get('commit', {}).get('sha') if isinstance(info, dict) else None


def verify_live_source(group, branch, sha, entry, get):
    require(branch in ('candidate/mc-' + group, 'mc/' + group) and audit.SHA.fullmatch(sha),
            group + ': invalid source identity')
    actual = get('branches/' + quote(branch, safe=''), allow_missing=True)
    if actual is not None:
        require(branch_head(actual) == sha, group + ': monitored source branch changed')
        return 'pinned-branch'

    require(branch.startswith('candidate/'), group + ': required maintenance source is missing')
    match = audit.PR.fullmatch(entry.get('pull_request', ''))
    require(match is not None and entry.get('candidate_head') == sha, group + ': invalid candidate pin')
    pr = get('pulls/' + match.group(1))
    require(pr.get('merged_at') and pr.get('state') == 'closed' and
            pr.get('head', {}).get('sha') == sha and pr['head'].get('ref') == branch and
            (pr['head'].get('repo') or {}).get('full_name') == REPO and
            pr.get('base', {}).get('ref') == 'mc/' + group and
            (pr['base'].get('repo') or {}).get('full_name') == REPO,
            group + ': missing source was not the pinned merged candidate PR')
    merged = pr.get('merge_commit_sha')
    require(isinstance(merged, str) and audit.SHA.fullmatch(merged), group + ': missing merged commit')
    target = get('branches/' + quote('mc/' + group, safe=''))
    require(branch_head(target) == merged, group + ': maintenance source moved; reviewed transition required')
    candidate_commit, merged_commit = get('git/commits/' + sha), get('git/commits/' + merged)
    candidate_tree = candidate_commit.get('tree', {}).get('sha')
    merged_tree = merged_commit.get('tree', {}).get('sha')
    require(isinstance(candidate_tree, str) and audit.SHA.fullmatch(candidate_tree) and
            candidate_tree == merged_tree, group + ': merged maintenance tree differs from the pinned candidate')
    return 'deleted-merged-candidate'


def get_api(path, allow_missing=False):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'tprm-candidate-audit',
               'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with urlopen(Request(API + path, headers=headers), timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        if allow_missing and exc.code == 404:
            return None
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('group', 'branch', 'source-sha'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--evidence', default=str(audit.EVIDENCE))
    args = parser.parse_args()
    try:
        evidence = read_json(Path(args.evidence))
        rows = audit.candidate_matrix(evidence, read_json(audit.MAINTENANCE), read_json(audit.AUTHORITATIVE),
                                      read_json(audit.LEDGER), audit.MAINTENANCE_WORKFLOW.read_text())['include']
        require({'group': args.group, 'branch': args.branch, 'sha': args.source_sha} in rows,
                'source does not match the reviewed monitoring matrix')
        status = verify_live_source(args.group, args.branch, args.source_sha,
                                    evidence['groups'][args.group], get_api)
        print(args.group + ': ' + status + '; auditing exact source ' + args.source_sha)
        if status == 'deleted-merged-candidate':
            print('Candidate was merged and auto-deleted; this remains candidate evidence. '
                  'Review and activate the integrated-maintenance transition.')
        return 0
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print('Candidate source verification failed: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
