#!/usr/bin/env python3
"""Verify bounded, source-bound static evidence for a High Netty IP-filter advisory.

No vulnerable network behavior is exercised. Literal references do not establish
that a class executes or that unobserved runtime configurations are safe.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

import inspect_issue45_mod_jars as products
import inspect_issue45_sni_high as sni
import reconcile_issue45_live_audits as audits
from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
DIR = 'docs/dependency-evidence/issue45-netty-ipfilter-high-2026-11-22'
UPSTREAM = DIR + '/upstream-advisory.json'
UPSTREAM_SHA = 'f97d417e1cfe727ceb28de5d459c23db77032983765171be8a743f1475f5bb33'
KNOWN = DIR + '/known-library-class-hits.json'
SCAN = DIR + '/vanilla-classpath-scan.json'
FABRIC = DIR + '/fabric-loader-static-scan.json'
PRODUCT = DIR + '/product-jar-static-scan.json'
REVIEW = DIR + '/source-bound-review.json'
CURRENT = DIR + '/priority-register-v3.json'
TARGET = 'GHSA-3qp7-7mw8-wx86'
TERMS = ('IpSubnetFilter', 'RuleBasedIpFilter', 'IpFilterRule', 'AbstractRemoteAddressFilter')
FABRIC_SHA1 = '7c7f9831e9f27b303d5d08decb5f4258a9f03296'
FABRIC_SHA256 = 'd0c5a082e07410aaff9de7ab196aa6b4236002870f9ba3ad5c1260fcce5110ad'
FABRIC_URL = 'https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.20.1/fabric-loader-0.20.1.jar'
KNOWN_PATHS = frozenset('io/netty/handler/ipfilter/' + name + '.class' for name in (
    'AbstractRemoteAddressFilter', 'IpFilterRule', 'IpFilterRuleType', 'IpSubnetFilter',
    'IpSubnetFilterRule$1', 'IpSubnetFilterRule$Ip4SubnetFilterRule',
    'IpSubnetFilterRule$Ip6SubnetFilterRule', 'IpSubnetFilterRule',
    'IpSubnetFilterRuleComparator', 'RuleBasedIpFilter', 'UniqueIpFilter'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path, expected=None):
    return json.loads(sni.read(ROOT, path, expected), object_pairs_hook=unique_object)


def validate_target(target, previous):
    require(target['severity'] == 'HIGH' and target['aliases'] == ['CVE-2026-44249'] and
            target['focused_evidence'] is None and len(target['occurrences']) == 12,
            'unexpected IP-filter priority baseline')
    old = {sni.identity(row): row for row in previous}
    observed = {sni.identity(row): row for row in target['occurrences']}
    require(len(old) == len(observed) == 12 and set(old) == set(observed),
            'IP-filter occurrence identities differ from reviewed source artifacts')
    for key, row in observed.items():
        require(row['scopes'] == old[key]['scopes'] and row['release_blocking'] is True and
                row['disposition'] == 'Further investigation' and row['risk_accepted'] is False,
                'IP-filter occurrence scope or blocking state differs')
    ranges = target['affected_ranges']['pkg:maven/io.netty/netty-handler']
    events = {(row['events'][0]['introduced'], row['events'][1]['fixed'])
              for group in ranges for row in group if row.get('type') == 'ECOSYSTEM'}
    require(events == {('0', '4.1.135.Final'), ('4.2.0.Final', '4.2.15.Final')},
            'IP-filter OSV ranges differ')


def context():
    ledger, priority, critical, prior_scan, mod = sni.load_inputs()
    v2_raw = sni.read(ROOT, sni.CURRENT, ledger['sni_high_focused_priority_register']['sha256'])
    sni.validate_ledger_reference(ledger, v2_raw)
    v2 = json.loads(v2_raw, object_pairs_hook=unique_object)
    high = next(row for row in priority['advisories'] if row['advisory_id'] == sni.HIGH)
    catalog, previous, versions = sni.bind_occurrences(high, critical, prior_scan, mod)
    sni_review = sni.make_review(ledger, critical, prior_scan, catalog, previous, versions,
        sni.read(ROOT, sni.ARTIFACTS), sni.read(ROOT, sni.BASE_SCAN))
    sni.validate_outputs(priority, sni.read(ROOT, sni.REVIEW), v2_raw, sni_review)
    target = next(row for row in v2['advisories'] if row['advisory_id'] == TARGET)
    validate_target(target, previous)
    upstream = read_json(UPSTREAM, UPSTREAM_SHA)
    require(upstream['ghsa_id'] == TARGET and upstream['cve_id'] == 'CVE-2026-44249' and
            upstream['severity'] == 'high' and upstream['withdrawn_at'] is None and
            {(row['package'], row['range'], row['patched']) for row in upstream['vulnerabilities']} == {
                ('io.netty:netty-handler', '<=4.1.134.Final', '4.1.135.Final'),
                ('io.netty:netty-handler', '>=4.2.0.Final, <=4.2.14.Final', '4.2.15.Final')},
            'Netty upstream advisory ranges differ')
    return ledger, v2, target, previous, catalog, versions, prior_scan


def scan_jar(raw):
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate JAR entry')
        hits, count = [], 0
        for name in sorted(n for n in names if n.endswith('.class')):
            contents = archive.read(name)
            count += 1
            found = [term for term in TERMS if term.encode() in contents]
            if found:
                hits.append({'class_file': name, 'sha256': sha(contents), 'terms': found})
        return count, hits


def scan_runtime_artifact(cache, artifact, versions):
    path = (cache / artifact['cache_object']).resolve()
    require(path.is_relative_to(cache.resolve()), 'runtime cache path escapes root')
    raw = path.read_bytes()
    require(len(raw) == artifact['size_bytes'] and hashlib.sha1(raw).hexdigest() == artifact['sha1'] and
            sha(raw) == artifact['sha256'], 'runtime artifact checksum differs')
    count, hits = scan_jar(raw)
    require(count == artifact['class_files_scanned'], 'runtime class count differs')
    return {'sha1': artifact['sha1'], 'sha256': artifact['sha256'], 'size_bytes': len(raw),
            'coordinates': artifact['coordinates'], 'minecraft_versions': sorted(set(artifact['minecraft_versions']) & set(versions)),
            'class_files_scanned': count, 'literal_hits': hits}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('unexpected Mojang artifact redirect')


def download_mojang_library(url, size):
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname == 'libraries.minecraft.net' and
            parsed.port in (None, 443) and not parsed.username and not parsed.password and
            not parsed.query and not parsed.fragment and 0 < size <= 8 * 1024 * 1024,
            'invalid Mojang library URL or size')
    request = Request(url, headers={'User-Agent': 'issue45-netty-ipfilter-verifier'})
    with build_opener(NoRedirect()).open(request, timeout=45) as response:
        require(response.geturl() == url, 'unexpected Mojang artifact redirect')
        raw = response.read(size + 1)
    require(len(raw) == size, 'Mojang library size differs')
    return raw


def verify_known_library(raw, library, expected_hits, expected_count):
    # Verify the reviewed JAR hashes independently before inspecting class bytes.
    sni.inspect_library(raw, library)
    count, hits = scan_jar(raw)
    require(count == expected_count and hits == expected_hits,
            'downloaded Netty class observations differ')


def verify_known_downloads(catalog, prior_scan, known):
    ref = prior_scan['source_provenance']['netty_artifact_inventory']
    inventory = read_json(ref['path'], ref['sha256'])
    saved = {row['sha1']: row for row in known['libraries']}
    prior = {row['sha1']: row for row in prior_scan['runtime_classpath_scan']['all_artifacts']}
    for library in catalog:
        coordinate = 'io.netty:netty-handler:' + library['version']
        matches = [row for row in inventory['netty_artifacts'] if row['coordinate'] == coordinate and
                   row['sha1'] == library['sha1'] and row['sha256'] == library['sha256']]
        require(len(matches) == 1, 'missing source-bound Mojang Netty artifact')
        item = matches[0]
        expected_url = ('https://libraries.minecraft.net/io/netty/netty-handler/' + library['version'] +
                        '/netty-handler-' + library['version'] + '.jar')
        require(item['url'] == expected_url and item['size'] == prior[library['sha1']]['size_bytes'],
                'Mojang Netty source URL or size differs')
        raw = download_mojang_library(expected_url, item['size'])
        verify_known_library(raw, library, saved[library['sha1']]['literal_hits'],
                             prior[library['sha1']]['class_files_scanned'])


def selected_artifacts(prior_scan, versions):
    return [row for row in prior_scan['runtime_classpath_scan']['all_artifacts']
            if set(row['minecraft_versions']) & set(versions)]


def inspect_fabric(raw):
    require(len(raw) == 1988880 and hashlib.sha1(raw).hexdigest() == FABRIC_SHA1 and sha(raw) == FABRIC_SHA256,
            'Fabric loader checksum differs')
    count, hits = scan_jar(raw)
    nested = []
    with ZipFile(BytesIO(raw)) as archive:
        for name in sorted(n for n in archive.namelist() if n.lower().endswith('.jar')):
            child = archive.read(name)
            child_count, child_hits = scan_jar(child)
            with ZipFile(BytesIO(child)) as inner:
                require(not any(n.lower().endswith('.jar') for n in inner.namelist()),
                        'uninspected nested Fabric JAR')
            nested.append({'path': name, 'sha256': sha(child), 'class_files_scanned': child_count,
                           'literal_hits': child_hits})
    return {'schema': 1, 'coordinate': 'net.fabricmc:fabric-loader:0.20.1', 'source_url': FABRIC_URL,
            'source_sha1_sidecar': FABRIC_URL + '.sha1', 'sha1': FABRIC_SHA1, 'sha256': FABRIC_SHA256,
            'size_bytes': len(raw), 'class_files_scanned': count, 'literal_hits': hits,
            'nested_jars': nested, 'security_clearance': False}


def product_scan():
    original = products.NEEDLES
    try:
        products.NEEDLES = TERMS
        return products.collect()
    finally:
        products.NEEDLES = original


def validate_inputs(ledger, prior_scan, versions, catalog, known, scan, fabric, product):
    selected = selected_artifacts(prior_scan, versions)
    expected = {row['sha1']: row for row in selected}
    rows = scan['artifacts']
    require(scan.get('schema') == 1 and scan.get('terms') == list(TERMS) and
            scan.get('security_clearance') is False and scan.get('minecraft_versions') == versions and
            len(expected) == len(selected) == len(rows) == 471 and
            len({row['sha1'] for row in rows}) == len(rows), 'IP-filter scan coverage differs')
    libraries = {row['sha1']: row for row in catalog}
    recorded = {row['sha1']: row for row in known['libraries']}
    require(known.get('schema') == 1 and known.get('security_clearance') is False and
            len(libraries) == len(recorded) == len(known['libraries']) == 6 and set(libraries) == set(recorded),
            'IP-filter library coverage differs')
    expected_hits = {}
    for key, lib in libraries.items():
        saved = recorded[key]
        require(saved['version'] == lib['version'] and saved['sha256'] == lib['sha256'],
                'IP-filter library identity differs')
        classes = {hit['class_file']: hit for hit in saved['literal_hits']}
        require(len(classes) == len(saved['literal_hits']) == 11 and set(classes) == KNOWN_PATHS,
                'IP-filter known class coverage differs')
        expected_hits[key] = classes
    seen, internal, external = set(), 0, []
    for row in rows:
        original = expected.get(row['sha1'])
        require(original is not None and row['sha256'] == original['sha256'] and
                row['size_bytes'] == original['size_bytes'] and row['coordinates'] == original['coordinates'] and
                row['minecraft_versions'] == sorted(set(original['minecraft_versions']) & set(versions)) and
                row['class_files_scanned'] == original['class_files_scanned'], 'IP-filter artifact identity differs')
        hits = {hit['class_file']: hit for hit in row['literal_hits']}
        require(len(hits) == len(row['literal_hits']), 'duplicate IP-filter class observation')
        if row['sha1'] in libraries:
            require('io.netty:netty-handler:' + libraries[row['sha1']]['version'] in row['coordinates'] and
                    hits == expected_hits[row['sha1']], 'IP-filter known library hits differ')
            seen.add(row['sha1'])
            internal += len(hits)
        else:
            external.extend((row['sha1'], hit['class_file']) for hit in row['literal_hits'])
    require(seen == set(libraries) and internal == scan['netty_internal_hits'] == 66 and
            not external and scan['external_hits'] == [] and
            scan['class_files_scanned'] == sum(row['class_files_scanned'] for row in rows) == 369335,
            'IP-filter scan has missing known hits or external callers')
    require(fabric.get('schema') == 1 and fabric.get('coordinate') == 'net.fabricmc:fabric-loader:0.20.1' and
            fabric.get('source_url') == FABRIC_URL and fabric.get('source_sha1_sidecar') == FABRIC_URL + '.sha1' and
            fabric.get('sha1') == FABRIC_SHA1 and fabric.get('sha256') == FABRIC_SHA256 and
            fabric.get('size_bytes') == 1988880 and fabric.get('class_files_scanned') == 771 and
            fabric.get('literal_hits') == [] and fabric.get('security_clearance') is False and
            fabric.get('nested_jars') == [{'path': 'META-INF/jars/mixinextras-fabric-0.5.5.jar',
                'sha256': '5da883dc4bfb16e4ceca3f16d8c4ad937bdfb1ce337ed5ba15472d4d81dd6242',
                'class_files_scanned': 506, 'literal_hits': []}], 'Fabric static scan differs')
    index, _, _ = audits.historic()
    _, reports, _ = audits.verify_live(audits.LIVE, index)
    require(all('pkg:maven/net.fabricmc/fabric-loader@0.20.1' in report['inventories']['gradle']
                for report, _, _ in reports.values()), 'Fabric loader differs from source-bound build inventories')
    require(product == product_scan() and len(product['groups']) == 13 and
            all(not group['nested_jar_entries'] and all(not cls['matches'] for cls in group['classes'])
                for group in product['groups'].values()), 'product static scan differs')


def make_review(ledger, target, previous, catalog, versions, records):
    old = {sni.identity(row): row for row in previous}
    occurrences = [{**row, 'minecraft_artifacts': old[sni.identity(row)]['minecraft_artifacts'],
                    'dependency_sha1': old[sni.identity(row)]['dependency_sha1'],
                    'dependency_sha256': old[sni.identity(row)]['dependency_sha256'],
                    'product_jar_sha256': old[sni.identity(row)]['product_jar_sha256']}
                   for row in target['occurrences']]
    return {'schema': 1, 'advisory_id': TARGET, 'aliases': ['CVE-2026-44249'], 'severity': 'HIGH',
            'observed_on': '2026-11-22', 'analysis_base_commit': 'e646bf66204eb3e7ee165f10a3110f46351f3dd2',
            'upstream_advisory': {'path': UPSTREAM, 'sha256': UPSTREAM_SHA},
            'baseline_priority_register': ledger['sni_high_focused_priority_register'],
            'evidence': {path: sha(raw) for path, raw in records.items()},
            'occurrence_count': len(occurrences), 'source_group_count': len({(r['source_kind'], r['group']) for r in occurrences}),
            'minecraft_version_count': len(versions), 'minecraft_versions': versions, 'occurrences': occurrences,
            'dependency_owner': 'Minecraft runtime manifests; some coordinates also occur in Gradle resolution.',
            'upstream_fixed_versions': {'4.1.x': '4.1.135.Final', '4.2.x': '4.2.15.Final'},
            'reachability': 'The inspected vanilla client/default-runtime JARs, selected product JARs and a Fabric loader JAR '
                'had no non-Netty literal references to the selected IP-filter class names. This is not a runtime '
                'execution trace and does not exclude indirect, generated, reflective or third-party paths.',
            'input_boundary': 'The advisory concerns IPv6 access rules when an affected Netty subnet filter is installed. '
                'Whether a supported configuration installs that filter for an untrusted connection remains unverified.',
            'remediation': 'A compatible Minecraft-managed update is required; no library replacement was made. '
                'The separate Critical Netty SNI advisory requires later fixed versions.',
            'limitations': ['No launcher or Fabric process was run; Gradle inventory does not prove runtime loader selection.',
                'Dedicated-server distributions, other mods, agents and generated pipelines remain unverified.',
                'No network exploitation, payload or live vulnerability reproduction was performed.',
                'Compatibility of a newer library with affected older Minecraft versions has not been established.'],
            'reviewer': 'Codex automated static investigation; human security review pending',
            'responsible_owner': 'Project maintainer and upstream Minecraft/library owners', 'review_date': '2026-11-22',
            'disposition': 'Further investigation', 'release_blocking': True, 'risk_accepted': False,
            'security_clearance': False,
            'follow_up_requirements': ['Observe supported launcher, Fabric and dedicated-server pipelines.',
                'Verify a compatible upstream game update addressing this and the Critical SNI advisory.']}


def make_register(v2, review, review_raw):
    current = copy.deepcopy(v2)
    row = next(item for item in current['advisories'] if item['advisory_id'] == TARGET)
    require(row['focused_evidence'] is None and len(row['occurrences']) == review['occurrence_count'] == 12,
            'IP-filter priority baseline differs')
    row.update(focused_evidence=REVIEW, reviewer=review['reviewer'], review_date=review['review_date'],
               responsible_owner=review['responsible_owner'], follow_up=review['follow_up_requirements'])
    current['ipfilter_focused_evidence'] = {'path': REVIEW, 'sha256': sha(review_raw),
                                            'new_advisory_ids': 1, 'new_high_occurrences': 12}
    current['review_status'] = 'Adds bounded IP-filter static observations; no finding is cleared or risk accepted.'
    focused = [item for item in current['advisories'] if item['focused_evidence']]
    critical = sum(len(item['occurrences']) for item in focused if item['severity'] == 'CRITICAL')
    high = sum(len(item['occurrences']) for item in focused if item['severity'] == 'HIGH')
    total_high = sum(len(item['occurrences']) for item in current['advisories'] if item['severity'] == 'HIGH')
    current['focused_coverage'] = {'advisory_ids': len(focused), 'critical_occurrences': critical,
        'high_occurrences': high, 'total_occurrences': critical + high,
        'high_occurrences_without_focused_evidence': total_high - high}
    require(current['focused_coverage'] == {'advisory_ids': 22, 'critical_occurrences': 22,
        'high_occurrences': 95, 'total_occurrences': 117, 'high_occurrences_without_focused_evidence': 82},
        'IP-filter focused coverage differs')
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-cache', type=Path)
    parser.add_argument('--fabric-jar', type=Path)
    parser.add_argument('--verify-known-download', action='store_true',
                        help='download six source-bound Mojang Netty JARs and verify their class hits')
    parser.add_argument('--write-inputs', action='store_true')
    parser.add_argument('--write-review', action='store_true')
    args = parser.parse_args()
    try:
        require(not (args.write_inputs and args.verify_known_download),
                'input generation and independent download verification must run separately')
        ledger, v2, target, previous, catalog, versions, prior = context()
        if args.write_inputs:
            require(args.runtime_cache and args.fabric_jar and not args.write_review, 'both cached inputs are required')
            selected = selected_artifacts(prior, versions)
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda item: scan_runtime_artifact(args.runtime_cache, item, versions), selected))
            by_sha = {row['sha1']: row for row in selected}
            known = {'schema': 1, 'libraries': [], 'security_clearance': False}
            for lib in catalog:
                observed = scan_runtime_artifact(args.runtime_cache, by_sha[lib['sha1']], versions)
                known['libraries'].append({'version': lib['version'], 'sha1': lib['sha1'], 'sha256': lib['sha256'],
                                           'literal_hits': observed['literal_hits']})
            known_ids = {item['sha1'] for item in catalog}
            result = {'schema': 1, 'minecraft_versions': versions, 'terms': list(TERMS), 'artifacts': rows,
                'class_files_scanned': sum(row['class_files_scanned'] for row in rows),
                'netty_internal_hits': sum(len(row['literal_hits']) for row in rows if row['sha1'] in known_ids),
                'external_hits': [{'sha1': row['sha1'], 'class_file': hit['class_file']}
                    for row in rows if row['sha1'] not in known_ids for hit in row['literal_hits']],
                'security_clearance': False}
            fabric, product = inspect_fabric(args.fabric_jar.read_bytes()), product_scan()
            validate_inputs(ledger, prior, versions, catalog, known, result, fabric, product)
            for path, value in ((KNOWN, known), (SCAN, result), (FABRIC, fabric), (PRODUCT, product)):
                sni.write_new(ROOT / path, value)
            print('Recorded hash-verified static class observations; no finding was cleared')
            return 0
        records = {path: sni.read(ROOT, path) for path in (KNOWN, SCAN, FABRIC, PRODUCT)}
        known, scan, fabric, product = (json.loads(records[path], object_pairs_hook=unique_object)
                                        for path in (KNOWN, SCAN, FABRIC, PRODUCT))
        validate_inputs(ledger, prior, versions, catalog, known, scan, fabric, product)
        if args.verify_known_download:
            verify_known_downloads(catalog, prior, known)
            print('Verified 66 known IP-filter class hits against six Mojang JARs')
        if args.runtime_cache:
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda item: scan_runtime_artifact(args.runtime_cache, item, versions),
                                     selected_artifacts(prior, versions)))
            require(rows == scan['artifacts'], 'runtime reinspection differs')
        if args.fabric_jar:
            require(inspect_fabric(args.fabric_jar.read_bytes()) == fabric, 'Fabric reinspection differs')
        review = make_review(ledger, target, previous, catalog, versions, records)
        if args.write_review:
            sni.write_new(ROOT / REVIEW, review)
            review_raw = sni.read(ROOT, REVIEW)
            sni.write_new(ROOT / CURRENT, make_register(v2, review, review_raw))
            print('Recorded 12 blocking IP-filter occurrences and focused coverage')
            return 0
        review_raw = sni.read(ROOT, REVIEW)
        require(json.loads(review_raw, object_pairs_hook=unique_object) == review, 'IP-filter review differs')
        current_raw = sni.read(ROOT, CURRENT)
        require(json.loads(current_raw, object_pairs_hook=unique_object) == make_register(v2, review, review_raw),
                'IP-filter priority register differs')
        reference = ledger['latest_focused_priority_register']
        require(reference == {'path': CURRENT, 'sha256': sha(current_raw), 'advisory_ids': 22,
            'focused_occurrences': 117, 'remaining_unfocused_high_occurrences': 82, 'security_clearance': False},
            'IP-filter priority ledger reference differs')
        print('Validated 12 blocking IP-filter occurrences and bounded static observations')
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, BadZipFile) as exc:
        print('IP-filter investigation incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
