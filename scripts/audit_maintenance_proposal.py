#!/usr/bin/env python3
"""Audit an exact, unmerged maintenance proposal without accepting ledger risk."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

import audit_dependencies as audit
import scan_dependency_snapshot as scanner
import validate_maintenance_targets as targets
from release import Invalid, read_json, require

ROOT = Path(__file__).resolve().parents[1]


def audit_proposal(snapshot, metadata, properties, group, branch, source_sha, observed_sha, registry, ledger, current):
    require(group in registry and branch == 'maintenance/mc-' + group + '-' + current['version'] and
            source_sha == observed_sha and re.fullmatch(r'[a-f0-9]{40}', source_sha),
            'proposal group, branch or source identity mismatch')
    spec = registry[group]
    targets.validate_source(group, spec, properties, metadata, True)
    targets.validate_coordinated_version(group, properties, metadata, current)
    require(snapshot.get('ref') == 'refs/heads/' + branch and snapshot.get('sha') == source_sha,
            'snapshot is not bound to the proposal source')
    packages, skipped = scanner.packages(snapshot)
    require(not skipped, 'unscanned snapshot entries: ' + ', '.join(skipped))
    inventories, manifests = audit.runtime_inventories(spec['minecraft'])
    inventories['gradle'] = sorted({audit.canonical(p) for p in packages})
    all_packages = sorted(set().union(*map(set, inventories.values())))
    findings = scanner.query(all_packages)
    advisories = {identifier: audit.get_json('https://api.osv.dev/v1/vulns/' + quote(identifier, safe=''))
                  for identifier in sorted({item for values in findings.values() for item in values})}
    comparison = audit.compare(group, inventories, findings, advisories, ledger, registry, source_sha=source_sha)
    for item in comparison['matches']:
        item['baseline_disposition'] = item['disposition']
        item['disposition'] = 'Further investigation'
        item['review_status'] = 'awaiting investigation'
        item['failing'] = True
    pending = sorted(comparison['resolved'] + comparison['resolved_needing_review'])
    return {'schema': 1, 'status': 'complete-unreviewed-maintenance-proposal', 'source_kind': 'maintenance-proposal',
            'group': group, 'branch': branch, 'source_sha': source_sha, 'snapshot_ref': snapshot['ref'],
            'scanned_on': date.today().isoformat(), 'risk_acceptance': False, 'inventories': inventories,
            'inventory_sha256': comparison['inventory_sha256'], 'runtime_manifests': manifests,
            'findings': findings, 'advisories': advisories, 'matches': comparison['matches'],
            'resolved_needing_review': pending, 'failing': bool(comparison['matches'] or pending)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'source', 'group', 'branch', 'source-sha', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        observed = subprocess.check_output(['git', '-C', args.source, 'rev-parse', 'HEAD'], text=True).strip()
        ref = 'refs/heads/' + args.branch
        remote = subprocess.run(['git', '-C', args.source, 'ls-remote', '--exit-code', '--heads', 'origin', ref],
                                check=True, capture_output=True, text=True, timeout=60)
        require(remote.stdout.splitlines() == [args.source_sha + '\t' + ref], 'proposal remote head changed')
        props = {}
        for line in (Path(args.source) / 'gradle.properties').read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                require(key.strip() not in props, 'duplicate Gradle property')
                props[key.strip()] = value.strip()
        result = audit_proposal(read_json(args.snapshot), read_json(Path(args.source) / 'src/main/resources/fabric.mod.json'),
            props, args.group, args.branch, args.source_sha, observed, read_json(ROOT / 'release/maintenance-targets.json')['groups'],
            read_json(ROOT / 'docs/security-advisories.json'), read_json(ROOT / 'release/current-version.json'))
        print(args.group + ': ' + str(len(result['matches'])) + ' unreviewed proposal matches; '
              + str(len(result['resolved_needing_review'])) + ' disappeared matches need review')
        status = 1 if result['failing'] else 0
    except (Invalid, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        result = {'schema': 1, 'status': 'incomplete', 'source_kind': 'maintenance-proposal',
                  'group': args.group, 'branch': args.branch, 'source_sha': args.source_sha, 'error': str(exc)}
        print('Maintenance proposal audit incomplete: ' + str(exc), file=sys.stderr)
        status = 2
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return status


if __name__ == '__main__':
    sys.exit(main())
