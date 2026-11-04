#!/usr/bin/env python3
"""Audit resolved Gradle and authoritative game-runtime inventories against a reviewed ledger."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote
from urllib.request import urlopen

from release import Invalid, read_json, require
import scan_dependency_snapshot as snapshot_scan

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
DISPOSITIONS = {'Fixed', 'Actionable', 'Upstream-dependent', 'Not applicable', 'Risk accepted',
                'Further investigation', 'Resolved upstream'}


def canonical(purl):
    require(isinstance(purl, str), 'invalid package URL')
    value = unquote(purl.split('?', 1)[0])
    require(re.fullmatch(r'pkg:maven/[^\s/@]+/[^\s/@]+@[^\s/@]+', value), 'invalid Maven package URL')
    return value


def package_name(purl):
    return canonical(purl).split('@')[0]


def get_json(url, sha1=None):
    with urlopen(url, timeout=60) as response:
        raw = response.read()
    if sha1:
        require(hashlib.sha1(raw).hexdigest() == sha1, 'Mojang metadata SHA-1 mismatch')
    value = json.loads(raw)
    require(isinstance(value, dict), 'invalid JSON object from ' + url)
    return value


def runtime_inventories(versions):
    manifest = get_json(MANIFEST)
    result, evidence = {}, {}
    for version in versions:
        matches = [x for x in manifest['versions'] if x.get('id') == version and x.get('type') == 'release']
        require(len(matches) == 1, version + ': stable runtime metadata unavailable')
        spec = matches[0]
        require(spec['url'].startswith('https://piston-meta.mojang.com/') and
                re.fullmatch(r'[a-f0-9]{40}', spec['sha1']), 'untrusted Mojang metadata reference')
        metadata = get_json(spec['url'], spec['sha1'])
        require(metadata.get('id') == version and isinstance(metadata.get('libraries'), list) and
                metadata['libraries'], version + ': missing runtime inventory')
        purls = set()
        for library in metadata['libraries']:
            parts = library['name'].split(':')
            require(len(parts) in (3, 4), version + ': invalid runtime coordinate')
            # A Maven classifier is a platform variant of the same advisory package.
            purls.add(canonical(f'pkg:maven/{parts[0]}/{parts[1]}@{parts[2]}'))
        result['runtime/' + version] = sorted(purls)
        evidence[version] = {'url': spec['url'], 'sha1': spec['sha1'],
                             'library_entries': len(metadata['libraries']),
                             'maven_packages': len(purls),
                             'scope': 'all listed platform variants; native code advisories may be absent from OSV'}
    return result, evidence


def advisory_fingerprint(advisory):
    require(isinstance(advisory, dict) and advisory.get('id') and advisory.get('modified') and
            advisory.get('details') and isinstance(advisory.get('affected'), list) and advisory['affected'],
            'incomplete advisory data')
    # Any changed applicability, severity vector, or vulnerability description needs review.
    fields = {k: advisory.get(k) for k in ('id', 'aliases', 'affected', 'severity', 'details', 'withdrawn')}
    fields['severity_label'] = (advisory.get('database_specific') or {}).get('severity')
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def identity(group, purl, advisory):
    return group + '|' + canonical(purl) + '|' + advisory


def load_ledger(value, groups, today=None):
    today = today or date.today()
    require(isinstance(value, dict) and value.get('schema') == 1 and isinstance(value.get('records'), list)
            and isinstance(value.get('inventories'), dict), 'malformed advisory ledger')
    require(set(value['inventories']) == set(groups), 'ledger compatibility groups differ')
    reviewed = date.fromisoformat(value['reviewed_on'])
    require(0 <= (today - reviewed).days <= 90, 'stale inventory baseline')
    index = {}
    for group, spec in groups.items():
        inventories = value['inventories'][group]
        expected = {'gradle'} | {'runtime/' + v for v in spec['minecraft']}
        require(isinstance(inventories, dict) and set(inventories) == expected, 'ledger inventory scopes differ')
        for names in inventories.values():
            require(isinstance(names, list) and names and len(names) == len(set(names)) and
                    all(isinstance(n, str) and package_name(n + '@0') == n for n in names),
                    'malformed inventory baseline')
    for record in value['records']:
        require(isinstance(record, dict), 'malformed advisory record')
        group, purl, advisory = record.get('group'), record.get('purl'), record.get('advisory')
        require(group in groups and isinstance(advisory, str) and re.fullmatch(r'[A-Za-z0-9._-]+', advisory),
                'invalid advisory identity')
        key = identity(group, purl, advisory)
        require(record.get('key') == key and key not in index, 'duplicate or inconsistent ledger identity')
        require(record.get('disposition') in DISPOSITIONS and
                record.get('review_status') in ('reviewed', 'awaiting investigation'), 'invalid disposition')
        require(all(isinstance(record.get(k), str) and record[k].strip()
                    for k in ('rationale', 'follow_up', 'owner', 'recheck_when')), 'missing review rationale or follow-up')
        reviewed, due = date.fromisoformat(record['reviewed_on']), date.fromisoformat(record['review_due'])
        require(reviewed <= today <= due and 0 < (due - reviewed).days <= 90, 'stale or invalid review dates')
        require(re.fullmatch(r'[a-f0-9]{64}', record.get('fingerprint', '')), 'invalid advisory fingerprint')
        scopes = record.get('scopes')
        require(isinstance(scopes, list) and scopes and len(scopes) == len(set(scopes)) and
                set(scopes) <= set(value['inventories'][group]), 'invalid reviewed scopes')
        if record['disposition'] == 'Risk accepted':
            require(record.get('acceptance_reference') and record.get('accepted_by'), 'risk acceptance lacks authorization')
        index[key] = record
    return index


def compare(group, inventories, findings, advisories, ledger, groups, today=None):
    index = load_ledger(ledger, groups, today)
    require(set(inventories) == set(ledger['inventories'][group]), 'incomplete dependency inventory scopes')
    for scope, purls in inventories.items():
        require(purls and len(purls) == len(set(purls)), 'empty or duplicated inventory')
        actual = {package_name(p) for p in purls}
        missing = set(ledger['inventories'][group][scope]) - actual
        require(not missing, f'{scope}: incomplete inventory; missing {sorted(missing)}; review legitimate removals')
    queried = set().union(*map(set, inventories.values()))
    require(set(findings) <= queried, 'OSV returned an unqueried dependency')
    current = {}
    for purl, identifiers in findings.items():
        require(isinstance(identifiers, list) and identifiers, 'invalid advisory list')
        for identifier in identifiers:
            advisory = advisories.get(identifier)
            require(advisory and advisory['id'] == identifier, 'missing advisory data: ' + identifier)
            fingerprint = advisory_fingerprint(advisory)
            key = identity(group, purl, identifier)
            scopes = sorted(s for s, packages in inventories.items() if purl in packages)
            old = index.get(key)
            state = 'new' if old is None else ('changed' if old['fingerprint'] != fingerprint or
                    old['scopes'] != scopes else 'known')
            disposition = old['disposition'] if old else 'Further investigation'
            # A reviewed ledger is not risk acceptance. Unknown, actionable, high/critical
            # upstream risk and previously fixed findings always remain failing.
            severity = (advisory.get('database_specific') or {}).get('severity', 'UNKNOWN')
            visible_only = old and old['review_status'] == 'reviewed' and (
                disposition in ('Not applicable', 'Risk accepted') or
                (disposition == 'Upstream-dependent' and severity in ('LOW', 'MODERATE')))
            failing = state != 'known' or not visible_only
            require(key not in current, 'duplicate advisory identity in scan')
            current[key] = {'key': key, 'purl': purl, 'advisory': identifier, 'scopes': scopes,
                            'state': state, 'disposition': disposition, 'failing': failing,
                            'severity': severity, 'fingerprint': fingerprint}
    resolved = sorted(key for key, record in index.items() if record['group'] == group and key not in current)
    return {'matches': list(current.values()), 'resolved': resolved,
            'failing': any(x['failing'] for x in current.values())}


def audit(snapshot, branch, source_sha, ledger, groups):
    require(branch in {x['branch'] for x in groups.values()} and
            re.fullmatch(r'[a-f0-9]{40}', source_sha), 'invalid branch or source commit')
    group = next(g for g, spec in groups.items() if spec['branch'] == branch)
    require(snapshot.get('sha') == source_sha and snapshot.get('ref') == 'refs/heads/' + branch,
            'snapshot does not identify checked-out maintenance branch and commit')
    purls, skipped = snapshot_scan.packages(snapshot)
    require(not skipped, 'unscanned snapshot entries: ' + ', '.join(skipped))
    inventories, evidence = runtime_inventories(groups[group]['minecraft'])
    inventories['gradle'] = sorted({canonical(p) for p in purls})
    all_packages = sorted(set().union(*map(set, inventories.values())))
    findings = snapshot_scan.query(all_packages)
    advisories = {}
    for identifier in sorted({i for ids in findings.values() for i in ids}):
        advisories[identifier] = get_json('https://api.osv.dev/v1/vulns/' + quote(identifier, safe=''))
    comparison = compare(group, inventories, findings, advisories, ledger, groups)
    return {'schema': 1, 'status': 'complete', 'branch': branch, 'source_sha': source_sha,
            'scanned_on': date.today().isoformat(), 'inventories': inventories,
            'runtime_manifests': evidence, 'findings': findings, 'advisories': advisories, **comparison}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('snapshot', 'branch', 'source-sha', 'output'):
        parser.add_argument('--' + argument, required=True)
    parser.add_argument('--ledger', default=str(ROOT / 'docs/security-advisories.json'))
    parser.add_argument('--config', default=str(ROOT / 'release/compatibility.json'))
    args = parser.parse_args()
    try:
        report = audit(read_json(args.snapshot), args.branch, args.source_sha,
                       read_json(args.ledger), read_json(args.config)['groups'])
        counts = {state: sum(m['state'] == state for m in report['matches']) for state in ('new', 'changed', 'known')}
        print(f"{args.branch} at {args.source_sha}: {counts}; resolved: {len(report['resolved'])}; "
              f"unresolved/failing matches: {sum(m['failing'] for m in report['matches'])}")
        for match in report['matches']:
            print(f"{match['state']} | {match['key']} | {match['severity']} | {match['disposition']}")
        result = 1 if report['failing'] else 0
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        report = {'schema': 1, 'status': 'incomplete', 'branch': args.branch,
                  'source_sha': args.source_sha, 'error': str(exc)}
        print('Dependency audit incomplete: ' + str(exc), file=sys.stderr)
        result = 2
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    sys.exit(main())
