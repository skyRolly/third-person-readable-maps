#!/usr/bin/env python3
"""Report OSV advisories for versioned Maven packages in a Gradle snapshot."""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from release import Invalid, read_json, require


def packages(snapshot):
    manifests = snapshot.get('manifests')
    require(isinstance(manifests, dict) and manifests, 'snapshot has no manifests')
    found, skipped = set(), set()
    for manifest in manifests.values():
        require(isinstance(manifest, dict) and isinstance(manifest.get('resolved'), dict),
                'snapshot has an invalid resolved dependency map')
        for key, dep in manifest['resolved'].items():
            require(isinstance(dep, dict), 'snapshot has an invalid dependency')
            purl = dep.get('package_url', '')
            if isinstance(purl, str) and re.fullmatch(r'pkg:maven/[^\s@]+@[^\s?#]+(?:\?[^\s#]+)?', purl):
                found.add(purl)
            else:
                skipped.add(str(key))
    require(found, 'snapshot contains no versioned Maven packages')
    return sorted(found), sorted(skipped)


def query(packages_list):
    findings = {purl: [] for purl in packages_list}
    pending = [(purl, None) for purl in packages_list]
    pages = 0
    while pending:
        batch, pending = pending[:100], pending[100:]
        queries = []
        for purl, token in batch:
            item = {'package': {'purl': purl}}
            if token:
                item['page_token'] = token
            queries.append(item)
        request = Request('https://api.osv.dev/v1/querybatch', data=json.dumps({'queries': queries}).encode(),
                          headers={'Content-Type': 'application/json', 'User-Agent': 'readable-maps-dependency-audit'})
        with urlopen(request, timeout=60) as response:
            result = json.load(response)
        results = result.get('results') if isinstance(result, dict) else None
        require(isinstance(results, list) and len(results) == len(batch), 'invalid OSV response')
        for (purl, _), item in zip(batch, results):
            require(isinstance(item, dict) and isinstance(item.get('vulns', []), list), 'invalid OSV result')
            for vulnerability in item.get('vulns', []):
                identifier = vulnerability.get('id') if isinstance(vulnerability, dict) else None
                require(isinstance(identifier, str) and re.fullmatch(r'[A-Za-z0-9._-]+', identifier),
                        'invalid OSV advisory identifier')
                findings[purl].append(identifier)
            token = item.get('next_page_token')
            require(token is None or (isinstance(token, str) and token), 'invalid OSV page token')
            if token:
                pending.append((purl, token))
        pages += 1
        require(pages <= 1000, 'too many OSV response pages')
    return {purl: sorted(set(ids)) for purl, ids in findings.items() if ids}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        require(re.fullmatch(r'mc/[0-9.\-]+', args.branch) is not None and
                re.fullmatch(r'[a-f0-9]{40}', args.source_sha) is not None,
                'a maintenance branch and full source SHA are required')
        snapshot = read_json(args.snapshot)
        require(isinstance(snapshot, dict) and snapshot.get('sha') == args.source_sha and
                snapshot.get('ref') == 'refs/heads/' + args.branch,
                'snapshot does not identify the checked-out branch and commit')
        purls, skipped = packages(snapshot)
        findings = query(purls)
        report = {'schema': 1, 'branch': args.branch, 'source_sha': args.source_sha,
                  'database': 'https://osv.dev', 'scanned_purls': purls,
                  'unscanned_snapshot_entries': skipped, 'findings': findings}
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'{args.branch} at {args.source_sha}: {len(purls)} Maven packages, '
              f'{len(skipped)} unscanned entries, {len(findings)} packages with advisories')
        for purl, ids in findings.items():
            print(f"{purl}: {', '.join('https://osv.dev/vulnerability/' + i for i in ids)}")
        if skipped:
            print('Unscanned snapshot entries: ' + ', '.join(skipped))
        return 1 if findings or skipped else 0
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print(f'dependency scan failed: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
