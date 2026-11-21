#!/usr/bin/env python3
"""Check the pinned Wrapper distribution against Gradle's upstream advisories.

This supplements the OSV dependency scan; it neither accepts risks nor proves
that an advisory is exploitable in a particular build environment.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import HTTPRedirectHandler, Request, build_opener

import verify_gradle_wrapper as wrapper

API = 'https://api.github.com/repos/gradle/gradle/security-advisories'
SHA = re.compile(r'[a-f0-9]{40}')
NUMBER = r'\d+(?:\.\d+){0,2}'
# Previously observed upstream records may not silently disappear or change.
# Updating these observations requires an explicit advisory review.
KNOWN_UPDATES = {
    'GHSA-3cfg-jpcr-gfp3': '2026-11-10T17:47:43Z',
    'GHSA-gqrr-4j89-5267': '2026-11-10T17:47:29Z',
    'GHSA-pcp8-98xm-c6pr': '2026-11-10T17:47:12Z',
    'GHSA-99wf-vhq9-wm2x': '2026-11-19T21:03:10Z',
    'GHSA-7f7r-77ff-fr6f': '2026-11-19T21:03:02Z',
    'GHSA-4mf6-7pm2-6wm8': '2026-11-19T21:02:56Z',
    'GHSA-35pj-rg5r-8rpv': '2026-11-19T21:02:49Z',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version(value):
    require(isinstance(value, str) and re.fullmatch(NUMBER, value), 'unsupported Gradle version: ' + str(value))
    return tuple((list(map(int, value.split('.'))) + [0, 0])[:3])


def affected(value, expression):
    """Interpret the upstream numeric range forms; reject unknown syntax."""
    current = version(value)
    require(isinstance(expression, str) and expression.strip(), 'missing advisory version range')
    expression = expression.strip()
    between = re.fullmatch(r'(' + NUMBER + r')\s+(?:to|through)\s+(' + NUMBER + r')(\.x)?', expression)
    if between:
        lower, upper = version(between[1]), version(between[2])
        if between[3]:
            upper = (upper[0], upper[1], sys.maxsize)
        return lower <= current <= upper
    # Historical upstream records use a union of one comparison and one
    # inclusive interval; commas between ordinary comparisons mean AND.
    union = re.fullmatch(r'(.+?),\s*\[(' + NUMBER + r'),\s*(' + NUMBER + r')\]', expression)
    if union:
        return affected(value, union[1]) or version(union[2]) <= current <= version(union[3])
    clauses = expression.split(',')
    results = []
    for clause in clauses:
        match = re.fullmatch(r'\s*(<=|>=|<|>|=)?\s*(' + NUMBER + r')\s*', clause)
        require(match is not None, 'unsupported advisory version range: ' + expression)
        op, target = match[1] or '=', version(match[2])
        results.append({'<': current < target, '<=': current <= target,
                        '>': current > target, '>=': current >= target,
                        '=': current == target}[op])
    return all(results)


class RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('unexpected upstream advisory redirect')


def open_request(request):
    # Never forward a workflow token to a redirect destination.
    return build_opener(RejectRedirect()).open(request, timeout=60)


def fetch_page(page):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'readable-maps-gradle-audit',
               'X-GitHub-Api-Version': '2022-11-28'}
    token = os.environ.get('GH_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(API + '?per_page=100&page=' + str(page), headers=headers)
    with open_request(request) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    require(len(raw) <= 4 * 1024 * 1024, 'upstream advisory response is too large')
    data = json.loads(raw)
    require(isinstance(data, list), 'invalid upstream advisory response')
    return data


def upstream(version_string, fetch=fetch_page, required=None):
    version(version_string)
    required = KNOWN_UPDATES if required is None else required
    matches, seen = [], set()
    for page in range(1, 21):
        rows = fetch(page)
        require(isinstance(rows, list) and len(rows) <= 100, 'invalid upstream advisory page')
        for row in rows:
            require(isinstance(row, dict) and isinstance(row.get('ghsa_id'), str) and
                    re.fullmatch(r'GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}', row['ghsa_id']) and
                    isinstance(row.get('vulnerabilities'), list), 'invalid upstream advisory')
            identifier = row['ghsa_id']
            require(identifier not in seen, 'duplicate upstream advisory: ' + identifier)
            seen.add(identifier)
            if identifier in required:
                require(row.get('state') == 'published' and row.get('withdrawn_at') is None and
                        row.get('updated_at') == required[identifier],
                        'upstream advisory changed or was withdrawn; review required: ' + identifier)
            require(row.get('state') in ('published', 'withdrawn', 'closed'),
                    'unknown upstream advisory state: ' + identifier)
            if row['state'] != 'published' or row.get('withdrawn_at') is not None:
                continue
            require(row['vulnerabilities'], 'missing upstream affected versions: ' + identifier)
            ranges, recognized = [], False
            for item in row['vulnerabilities']:
                require(isinstance(item, dict) and isinstance(item.get('package'), dict), 'invalid advisory package')
                package = item['package']
                if not (package.get('name') == 'Gradle' or
                        (package.get('name') == 'org.gradle:gradle-core' and package.get('ecosystem') == 'maven')):
                    continue
                recognized = True
                expression = item.get('vulnerable_version_range')
                if affected(version_string, expression):
                    ranges.append({'range': expression, 'fixed': item.get('patched_versions')})
            require(recognized, 'unsupported upstream advisory package: ' + identifier)
            if ranges:
                require(isinstance(row.get('summary'), str) and row['summary'] and
                        row.get('severity') in ('low', 'moderate', 'high', 'critical') and
                        isinstance(row.get('updated_at'), str) and row['updated_at'],
                        'incomplete upstream advisory: ' + identifier)
                matches.append({'id': identifier, 'summary': row['summary'], 'severity': row['severity'],
                                'updated_at': row['updated_at'], 'ranges': ranges,
                                'url': 'https://github.com/gradle/gradle/security/advisories/' + identifier})
        if len(rows) < 100:
            require(set(required) <= seen, 'upstream advisories disappeared; review required: ' +
                    ', '.join(sorted(set(required) - seen)))
            return sorted(matches, key=lambda item: item['id'])
    raise ValueError('too many upstream advisory pages')


def audit(root, source_sha, fetch=fetch_page):
    require(isinstance(source_sha, str) and SHA.fullmatch(source_sha), 'invalid source commit')
    root = Path(root)
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == source_sha, 'checked-out source does not match requested commit')
    name = 'gradle/wrapper/gradle-wrapper.properties'
    raw = (root / name).read_bytes()
    committed = subprocess.check_output(['git', '-C', str(root), 'show', source_sha + ':' + name])
    require(raw == committed, 'Wrapper properties differ from the pinned commit')
    properties = wrapper.canonical_properties(raw)
    distribution = wrapper.URL.fullmatch(properties['distributionUrl']).group(1)
    matches = upstream(distribution, fetch)
    return {'schema': 1, 'status': 'complete', 'source_sha': source_sha, 'gradle_version': distribution,
            'source': API, 'risk_accepted': False, 'advisories': matches, 'failing': bool(matches)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.root, args.source_sha)
        print('Gradle ' + report['gradle_version'] + ': ' + str(len(report['advisories'])) +
              ' upstream advisory match(es) at ' + args.source_sha)
        for row in report['advisories']:
            print(row['id'] + ' | ' + row['severity'] + ' | ' + row['summary'])
        code = 1 if report['failing'] else 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.CalledProcessError) as exc:
        report = {'schema': 1, 'status': 'incomplete', 'source_sha': args.source_sha, 'error': str(exc)}
        print('Gradle upstream advisory audit incomplete: ' + str(exc), file=sys.stderr)
        code = 2
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
