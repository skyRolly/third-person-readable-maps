#!/usr/bin/env python3
"""Compare current pinned candidate verifier copies and report maintenance drift."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import check_shared_verifier_sync as shared


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ONLY = (shared.ADAPTER, 'tests/test_invokedynamic_cp.py',
                  'tests/test_annotation_constants.py', 'tests/test_windows_preflight.py')


def compare(candidates, maintenance, read_file):
    if not isinstance(candidates, dict) or not candidates or not isinstance(maintenance, dict) or not maintenance:
        raise ValueError('candidate and maintenance groups are required')
    if set(candidates) & set(maintenance):
        raise ValueError('candidate and maintenance groups overlap')
    baseline = {}
    for group, row in sorted(candidates.items()):
        sha = row.get('candidate_head') if isinstance(row, dict) else None
        if not isinstance(sha, str) or not shared.SHA.fullmatch(sha):
            raise ValueError(group + ': invalid candidate head')
        for path in (*shared.SHARED, *CANDIDATE_ONLY):
            digest = hashlib.sha256(read_file(sha, path)).hexdigest()
            if path in baseline and baseline[path] != digest:
                raise ValueError(group + ': candidate shared file differs: ' + path)
            baseline[path] = digest
    pending = []
    for group, row in sorted(maintenance.items()):
        sha = row.get('integrated_commit') if isinstance(row, dict) else None
        if not isinstance(sha, str) or not shared.SHA.fullmatch(sha):
            raise ValueError(group + ': invalid integrated head')
        for path in shared.SHARED:
            if hashlib.sha256(read_file(sha, path)).hexdigest() != baseline[path]:
                pending.append(group + ': shared file differs: ' + path)
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-missing', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    try:
        candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
        maintenance = json.loads((ROOT / 'release/maintenance-targets.json').read_text())['groups']
        shas = [row.get('candidate_head') for row in candidates.values()]
        shas += [row.get('integrated_commit') for row in maintenance.values()]
        if any(not isinstance(sha, str) or not shared.SHA.fullmatch(sha) for sha in shas):
            raise ValueError('invalid pinned source')
        missing = [sha for sha in shas if subprocess.run(
            ['git', 'cat-file', '-e', sha + '^{commit}'], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode]
        if missing and args.fetch_missing:
            subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', *missing],
                           cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        def read_file(sha, path):
            return subprocess.run(['git', 'show', sha + ':' + path], cwd=ROOT, check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        pending = compare(candidates, maintenance, read_file)
        print('Pinned shared verifier copies: ' + ('PENDING: ' + '; '.join(pending) if pending else 'consistent'))
        return 1 if args.require_complete and pending else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print('Pinned shared verifier comparison failed: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
