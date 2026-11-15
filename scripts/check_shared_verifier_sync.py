#!/usr/bin/env python3
"""Compare actual shared files at all pinned candidate commits; never run them."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SHARED = (
    'scripts/jvm_linkage.py', 'scripts/game_linkage.py',
    'scripts/verify_gradle_wrapper.py', 'tests/test_jvm_linkage.py',
    'tests/test_nestmate_linkage.py', 'tests/test_hierarchy_linkage.py',
    'tests/hierarchy_entrypoint_fixtures.py', 'tests/test_verify_gradle_wrapper.py',
    'tests/test_shared_verifier_sync.py', 'docs/verification/linkage-contract.md',
)
ADAPTER = 'tests/test_verify_entrypoint.py'
SHA = re.compile(r'^[0-9a-f]{40}$')


def verify(groups, expected_groups, read_file):
    """Check bytes from each pinned commit, including each namespace variant."""
    if set(groups) != set(expected_groups) or not groups:
        raise ValueError('current source groups do not match the candidate and maintenance registries')
    canonical, adapters = {}, {}
    for group, row in sorted(groups.items()):
        commit, namespace = row.get('new_head'), row.get('namespace')
        if not isinstance(commit, str) or not SHA.fullmatch(commit):
            raise ValueError(group + ': invalid pinned commit')
        if namespace not in ('intermediary', 'official'):
            raise ValueError(group + ': unknown namespace')
        for path in SHARED:
            digest = hashlib.sha256(read_file(commit, path)).hexdigest()
            if path in canonical and canonical[path][1] != digest:
                raise ValueError(group + ': shared file differs from ' + canonical[path][0] + ': ' + path)
            canonical.setdefault(path, (group, digest))
        digest = hashlib.sha256(read_file(commit, ADAPTER)).hexdigest()
        if namespace in adapters and adapters[namespace][1] != digest:
            raise ValueError(group + ': ' + namespace + ' adapter fixture differs from ' + adapters[namespace][0])
        adapters.setdefault(namespace, (group, digest))
    if set(adapters) != {'intermediary', 'official'}:
        raise ValueError('both namespace adapters must be represented')
    return {'groups': len(groups), 'shared': {p: value[1] for p, value in canonical.items()},
            'adapters': {n: value[1] for n, value in adapters.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--fetch-missing', action='store_true',
                        help='fetch missing pinned public commits without executing their contents')
    args = parser.parse_args()
    try:
        groups = json.loads((ROOT/'docs/version-consistency-1.0.0/current-heads.json').read_text())['groups']
        candidates = json.loads((ROOT/'docs/legacy-candidate-evidence.json').read_text())['groups']
        maintenance = json.loads((ROOT/'release/maintenance-targets.json').read_text())['groups']
        commits = [row.get('new_head') for row in groups.values()]
        if any(not isinstance(c, str) or not SHA.fullmatch(c) for c in commits):
            raise ValueError('invalid pinned commit')
        missing = [c for c in commits if subprocess.run(
            ['git', 'cat-file', '-e', c + '^{commit}'], cwd=args.repo,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode]
        if missing and args.fetch_missing:
            subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', *missing],
                           cwd=args.repo, check=True, stdout=subprocess.DEVNULL)
        def read_file(commit, path):
            return subprocess.run(['git', 'show', commit + ':' + path], cwd=args.repo,
                                  check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        result = verify(groups, set(candidates) | set(maintenance), read_file)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        print('Shared verifier comparison failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
