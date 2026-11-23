#!/usr/bin/env python3
"""Validate bounded source-bound static evidence for a Netty TLS advisory.

This does not exercise certificate-validation failures, launch Minecraft, or
establish game-wide reachability or non-reachability.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, build_opener
from zipfile import BadZipFile, ZipFile

import inspect_issue45_mod_jars as products
import inspect_issue45_netty_bzip2_high as bzip
import inspect_issue45_netty_ipfilter_high as ipfilter
import inspect_issue45_sni_high as sni
import reconcile_issue45_live_audits as audits
from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
DIR = 'docs/dependency-evidence/issue45-netty-trust-high-2026-11-23'
UPSTREAM = DIR + '/upstream-advisory.json'
UPSTREAM_SHA = '83bf80b27550584bd3185f13d1a6478225de4d44aba6c1706a13f7178c36bff3'
SCAN = DIR + '/vanilla-classpath-scan.json'
KNOWN = DIR + '/known-handler-class-hits.json'
FABRIC = DIR + '/fabric-loader-static-scan.json'
PRODUCT = DIR + '/product-jar-static-scan.json'
MANAGEMENT = DIR + '/management-static-observations.json'
REVIEW = DIR + '/source-bound-review.json'
CURRENT = DIR + '/priority-register-v5.json'
TARGET = 'GHSA-c653-97m9-rcg9'
TERMS = ('io/netty/handler/ssl/util/TrustManagerFactoryWrapper',
         'io/netty/handler/ssl/util/SimpleTrustManagerFactory',
         'io/netty/handler/ssl/util/X509TrustManagerWrapper',
         'io/netty/handler/ssl/SslContextBuilder')
KNOWN_PATHS = frozenset({'io/netty/handler/ssl/SslContextBuilder.class'} | {
    'io/netty/handler/ssl/util/' + name + '.class' for name in (
        'FingerprintTrustManagerFactory', 'InsecureTrustManagerFactory',
        'SimpleTrustManagerFactory$1', 'SimpleTrustManagerFactory$2',
        'SimpleTrustManagerFactory$SimpleTrustManagerFactorySpi', 'SimpleTrustManagerFactory',
        'TrustManagerFactoryWrapper', 'X509TrustManagerWrapper')})
SAMPLE_PRIOR = {'1.21.9': '1.21.10', '1.21.10': '1.21.10', '1.21.11': '1.21.11',
                '26.1': '26.3', '26.1.1': '26.3', '26.1.2': '26.3'}
CALL_MARKERS = ('TrustManagerFactory.getDefaultAlgorithm', 'TrustManagerFactory.getInstance',
                'TrustManagerFactory.init', 'SslContextBuilder.forServer',
                'SslContextBuilder.trustManager', 'SslContextBuilder.build')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path, expected=None):
    return json.loads(sni.read(ROOT, path, expected), object_pairs_hook=unique_object)


def validate_target(target, previous):
    require(target['advisory_id'] == TARGET and target['severity'] == 'HIGH' and
            target['aliases'] == ['CVE-2026-50010'] and target['focused_evidence'] is None,
            'unexpected Trust Manager advisory baseline')
    old = {sni.identity(row): row for row in previous}
    seen = {sni.identity(row): row for row in target['occurrences']}
    require(len(old) == len(seen) == len(target['occurrences']) == 12 and set(old) == set(seen),
            'Trust Manager occurrence identities differ')
    for key, row in seen.items():
        require(row['scopes'] == old[key]['scopes'] and row['release_blocking'] is True and
                row['disposition'] == 'Further investigation' and row['risk_accepted'] is False,
                'Trust Manager scope or blocking state differs')
    ranges = target['affected_ranges']['pkg:maven/io.netty/netty-handler']
    events = {(r['events'][0]['introduced'], r['events'][1]['fixed'])
              for group in ranges for r in group if r.get('type') == 'ECOSYSTEM'}
    require(events == {('0', '4.1.135.Final'), ('4.2.0.Final', '4.2.15.Final')},
            'Trust Manager affected ranges differ')


def context():
    ledger, v3, btarget, reviewed, games, prior, mod = bzip.context()
    records = {p: sni.read(ROOT, p) for p in (bzip.CLIENTS, bzip.CODECS, bzip.FABRIC, bzip.PRODUCT, bzip.PIPELINE)}
    clients, codecs, fabric, product, pipeline = (json.loads(records[p], object_pairs_hook=unique_object)
                                                  for p in (bzip.CLIENTS, bzip.CODECS, bzip.FABRIC, bzip.PRODUCT, bzip.PIPELINE))
    bzip.validate_inputs(games, clients, codecs, fabric, product, pipeline)
    old_review = bzip.make_review(ledger, btarget, reviewed, games, codecs, records, mod)
    old_review_raw = sni.read(ROOT, bzip.REVIEW)
    require(json.loads(old_review_raw, object_pairs_hook=unique_object) == old_review,
            'historical Bzip2 review differs')
    reference = ledger['bzip2_high_focused_priority_register']
    old_raw = sni.read(ROOT, bzip.CURRENT, reference['sha256'])
    require(reference == {'path': bzip.CURRENT, 'sha256': sha(old_raw), 'advisory_ids': 23,
        'focused_occurrences': 130, 'remaining_unfocused_high_occurrences': 69, 'security_clearance': False},
        'historical Bzip2 register reference differs')
    v4 = json.loads(old_raw, object_pairs_hook=unique_object)
    require(v4 == bzip.make_register(v3, old_review, old_review_raw), 'historical Bzip2 register differs')
    _, _, _, previous, catalog, versions, prior_again = ipfilter.context()
    require(prior_again == prior, 'prior runtime inventory differs')
    target = next(row for row in v4['advisories'] if row['advisory_id'] == TARGET)
    validate_target(target, previous)
    upstream = read_json(UPSTREAM, UPSTREAM_SHA)
    require(upstream['ghsa_id'] == TARGET and upstream['cve_id'] == 'CVE-2026-50010' and
            upstream['severity'] == 'high' and upstream['withdrawn_at'] is None and
            upstream['vulnerabilities'] == [{'package': 'io.netty:netty-handler',
                'range': '<= 4.1.134.Final, <= 4.2.14.Final', 'patched': '4.1.135.Final, 4.2.15.Final'}],
            'Trust Manager upstream advisory differs')
    _, _, critical, _, _ = sni.load_inputs()
    ref = critical['supplemental_source_bound_evidence']['focused_bytecode_index']
    index = read_json(ref['path'], ref['sha256'])
    return ledger, v4, target, previous, catalog, versions, prior, mod, clients, ref, index


def scan_jar(raw):
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate Trust Manager JAR entry')
        hits, count = [], 0
        for name in sorted(n for n in names if n.endswith('.class')):
            content = archive.read(name)
            count += 1
            found = [term for term in TERMS if term.encode() in content]
            if found:
                hits.append({'class_file': name, 'sha256': sha(content), 'terms': found})
        return count, hits


def scan_runtime_artifact(cache, artifact, versions):
    path = (cache / artifact['cache_object']).resolve()
    require(path.is_relative_to(cache.resolve()), 'Trust Manager runtime cache path escapes root')
    raw = path.read_bytes()
    require(len(raw) == artifact['size_bytes'] and hashlib.sha1(raw).hexdigest() == artifact['sha1'] and
            sha(raw) == artifact['sha256'], 'Trust Manager runtime artifact checksum differs')
    count, hits = scan_jar(raw)
    require(count == artifact['class_files_scanned'], 'Trust Manager runtime class count differs')
    return {'sha1': artifact['sha1'], 'sha256': artifact['sha256'], 'size_bytes': len(raw),
            'coordinates': artifact['coordinates'],
            'minecraft_versions': sorted(set(artifact['minecraft_versions']) & set(versions)),
            'class_files_scanned': count, 'literal_hits': hits}


def inspect_fabric(raw):
    require(len(raw) == 1988880 and hashlib.sha1(raw).hexdigest() == ipfilter.FABRIC_SHA1 and
            sha(raw) == ipfilter.FABRIC_SHA256, 'Trust Manager Fabric checksum differs')
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
    return {'schema': 1, 'coordinate': 'net.fabricmc:fabric-loader:0.20.1', 'source_url': ipfilter.FABRIC_URL,
            'sha1': ipfilter.FABRIC_SHA1, 'sha256': ipfilter.FABRIC_SHA256, 'size_bytes': len(raw),
            'class_files_scanned': count, 'literal_hits': hits, 'nested_jars': nested, 'security_clearance': False}


def product_scan():
    original = products.NEEDLES
    try:
        products.NEEDLES = TERMS
        return products.collect()
    finally:
        products.NEEDLES = original


def calls_from_javap(text):
    return [line.strip().split('// ', 1)[-1] for line in text.splitlines()
            if any(marker in line for marker in CALL_MARKERS)]


def prior_management(index_ref, index, prior, versions):
    entries = {row['minecraft_version']: row for row in index['evidence_files']
               if row.get('symbol') == 'JsonRpcSslContextProvider'}
    require(set(entries) == {'1.21.10', '1.21.11', '26.3'}, 'management bytecode index coverage differs')
    artifacts = prior['runtime_classpath_scan']['all_artifacts']
    observations = []
    for game, prior_version in SAMPLE_PRIOR.items():
        require(game in versions, 'management game is outside reviewed versions')
        entry = entries[prior_version]
        raw = sni.read(ROOT, entry['javap_path'], entry['javap_sha256'])
        require(len(raw) == entry['javap_bytes'], 'management javap size differs')
        calls = calls_from_javap(raw.decode('utf-8'))
        require(len(calls) == len(CALL_MARKERS) and all(marker in call for marker, call in zip(CALL_MARKERS, calls)),
                'management javap call observations differ')
        client = [row for row in artifacts if 'minecraft-client:' + game in row['coordinates']]
        require(len(client) == 1, 'management client artifact differs')
        observations.append({'minecraft_version': game, 'client_sha1': client[0]['sha1'],
            'client_sha256': client[0]['sha256'], 'class_file': entry['class_entry'],
            'class_sha256': entry['class_sha256'], 'prior_disassembly_version': prior_version,
            'prior_disassembly_path': entry['javap_path'], 'prior_disassembly_sha256': entry['javap_sha256'],
            'selected_calls': calls})
    return {'schema': 1, 'prior_bytecode_index': index_ref, 'observations': observations,
            'scope': 'Static class references and disassembly; no runtime pipeline was observed.',
            'security_clearance': False}


def validate_inputs(prior, versions, catalog, index_ref, index, scan, known, fabric, product, management):
    selected = ipfilter.selected_artifacts(prior, versions)
    expected = {row['sha1']: row for row in selected}
    rows = {row['sha1']: row for row in scan['artifacts']}
    require(scan.get('schema') == 1 and scan.get('terms') == list(TERMS) and
            scan.get('minecraft_versions') == versions and scan.get('security_clearance') is False and
            len(expected) == len(selected) == len(rows) == len(scan['artifacts']) == 471 and
            set(rows) == set(expected), 'Trust Manager scan artifact coverage differs')
    libraries = {row['sha1']: row for row in catalog}
    saved = {row['sha1']: row for row in known['libraries']}
    require(known.get('schema') == 1 and known.get('security_clearance') is False and
            len(libraries) == len(catalog) == len(saved) == len(known['libraries']) == 6 and
            set(libraries) == set(saved), 'Trust Manager handler coverage differs')
    expected_management = prior_management(index_ref, index, prior, versions)
    require(management == expected_management, 'management source observations differ')
    external = []
    for identifier, row in rows.items():
        source = expected[identifier]
        require(row['sha256'] == source['sha256'] and row['size_bytes'] == source['size_bytes'] and
                row['coordinates'] == source['coordinates'] and
                row['minecraft_versions'] == sorted(set(source['minecraft_versions']) & set(versions)) and
                row['class_files_scanned'] == source['class_files_scanned'],
                'Trust Manager artifact identity differs')
        hits = {hit['class_file']: hit for hit in row['literal_hits']}
        require(len(hits) == len(row['literal_hits']) and all(
            re.fullmatch(r'[a-f0-9]{64}', hit['sha256']) and hit['terms'] and
            len(hit['terms']) == len(set(hit['terms'])) and all(t in TERMS for t in hit['terms'])
            for hit in hits.values()), 'Trust Manager class observation differs')
        if identifier in libraries:
            item, lib = saved[identifier], libraries[identifier]
            require(item['version'] == lib['version'] and item['sha256'] == lib['sha256'] and
                    'io.netty:netty-handler:' + lib['version'] in row['coordinates'] and
                    item['literal_hits'] == row['literal_hits'] and set(hits) == KNOWN_PATHS,
                    'Trust Manager known handler hits differ')
        else:
            external.extend({'sha1': identifier, **hit} for hit in row['literal_hits'])
    required_external = [{'sha1': obs['client_sha1'], 'class_file': obs['class_file'],
        'sha256': obs['class_sha256'], 'terms': [TERMS[3]]} for obs in expected_management['observations']]
    order = lambda item: (item['sha1'], item['class_file'])
    require(sorted(external, key=order) == sorted(required_external, key=order) and
            scan['external_hits'] == sorted(external, key=order), 'Trust Manager external observations differ')
    require(scan['handler_hits'] == sum(len(saved[k]['literal_hits']) for k in saved) == 54 and
            scan['class_files_scanned'] == sum(row['class_files_scanned'] for row in rows.values()) == 369335,
            'Trust Manager scan totals differ')
    require(fabric == {'schema': 1, 'coordinate': 'net.fabricmc:fabric-loader:0.20.1',
        'source_url': ipfilter.FABRIC_URL, 'sha1': ipfilter.FABRIC_SHA1, 'sha256': ipfilter.FABRIC_SHA256,
        'size_bytes': 1988880, 'class_files_scanned': 771, 'literal_hits': [], 'nested_jars': [{
            'path': 'META-INF/jars/mixinextras-fabric-0.5.5.jar',
            'sha256': '5da883dc4bfb16e4ceca3f16d8c4ad937bdfb1ce337ed5ba15472d4d81dd6242',
            'class_files_scanned': 506, 'literal_hits': []}], 'security_clearance': False},
        'Trust Manager Fabric observations differ')
    require(product == product_scan() and len(product['groups']) == 13 and all(
        not group['nested_jar_entries'] and all(not cls['matches'] for cls in group['classes'])
        for group in product['groups'].values()), 'Trust Manager product observations differ')


def verify_known_handler(raw, library, expected_count, expected_hits):
    sni.inspect_library(raw, library)
    count, hits = scan_jar(raw)
    require(count == expected_count and hits == expected_hits, 'downloaded Trust Manager handler hits differ')


def verify_known_downloads(catalog, prior, known):
    ref = prior['source_provenance']['netty_artifact_inventory']
    inventory = read_json(ref['path'], ref['sha256'])
    prior_artifacts = {row['sha1']: row for row in prior['runtime_classpath_scan']['all_artifacts']}
    saved = {row['sha1']: row for row in known['libraries']}
    for library in catalog:
        version = library['version']
        coordinate = 'io.netty:netty-handler:' + version
        matches = [row for row in inventory['netty_artifacts'] if row['coordinate'] == coordinate and
                   row['sha1'] == library['sha1'] and row['sha256'] == library['sha256']]
        require(len(matches) == 1, 'missing Trust Manager source-bound handler')
        item = matches[0]
        url = ('https://libraries.minecraft.net/io/netty/netty-handler/' + version +
               '/netty-handler-' + version + '.jar')
        require(item['url'] == url and item['size'] == prior_artifacts[library['sha1']]['size_bytes'],
                'Trust Manager handler source differs')
        raw = ipfilter.download_mojang_library(url, item['size'])
        verify_known_handler(raw, library, prior_artifacts[library['sha1']]['class_files_scanned'],
                             saved[library['sha1']]['literal_hits'])


def verify_management_client_bytes(raw, row, expected, javap):
    require(javap and len(raw) == row['client_size_bytes'] and
            hashlib.sha1(raw).hexdigest() == row['client_sha1'] and sha(raw) == row['client_sha256'],
            'management client checksum or javap differs')
    count, hits = scan_jar(raw)
    require(count == row['class_files_scanned'] and hits == [{'class_file': expected['class_file'],
            'sha256': expected['class_sha256'], 'terms': [TERMS[3]]}], 'management client class scan differs')
    with ZipFile(BytesIO(raw)) as archive:
        require(sha(archive.read(expected['class_file'])) == expected['class_sha256'],
                'management class bytes differ')
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG') if key in os.environ}
    with tempfile.TemporaryDirectory(prefix='issue45-trust-javap-') as directory:
        jar = Path(directory) / 'client.jar'
        jar.write_bytes(raw)
        symbol = expected['class_file'].removesuffix('.class').replace('/', '.')
        output = subprocess.run([str(javap), '-c', '-p', '-classpath', str(jar), symbol],
            check=True, capture_output=True, text=True, env=env, timeout=60).stdout
    require(calls_from_javap(output) == expected['selected_calls'], 'management disassembly differs')


def verify_management_download(clients, management, javap):
    require(javap, 'javap is required for the management client check')
    row = next(item for item in clients['games'] if item['minecraft_version'] == '26.1')
    expected = next(item for item in management['observations'] if item['minecraft_version'] == '26.1')
    url = 'https://piston-data.mojang.com/v1/objects/' + row['client_sha1'] + '/client.jar'
    require(row['client_url'] == url and row['client_sha1'] == expected['client_sha1'] and
            row['client_sha256'] == expected['client_sha256'] and 0 < row['client_size_bytes'] <= 64 * 1024 * 1024,
            'management client source differs')
    request = Request(url, headers={'User-Agent': 'issue45-trust-artifact-verifier'})
    with build_opener(ipfilter.NoRedirect()).open(request, timeout=60) as response:
        require(response.geturl() == url, 'unexpected management client redirect')
        raw = response.read(row['client_size_bytes'] + 1)
    verify_management_client_bytes(raw, row, expected, javap)


def fixed_runtime_example(prior, target):
    """Bind the 26.2 manifest's fixed-boundary version without clearing a finding."""
    group = '26.1-26.2'
    source = next(row for row in target['occurrences']
                  if row['source_kind'] == 'integrated' and row['group'] == group)
    historical, _, _ = audits.historic()
    _, reports, _ = audits.verify_live(audits.LIVE, historical)
    report, _, artifact = reports['integrated|' + group]
    purl = 'pkg:maven/io.netty/netty-handler@4.2.15.Final'
    coordinate = 'io.netty:netty-handler:4.2.15.Final'
    require(report['source_sha'] == source['source_sha'] and artifact['id'] == source['source_report_artifact_id'] and
            artifact['digest'] == 'sha256:' + source['source_report_archive_sha256'] and
            purl in report['inventories']['runtime/26.2'] and not any(
                row['advisory'] == TARGET and row['purl'] == purl for row in report['matches']),
            'fixed-boundary runtime inventory differs')
    metadata = prior['verified_manifest_versions']['26.2']
    artifacts = [row for row in prior['runtime_classpath_scan']['all_artifacts']
                 if coordinate in row['coordinates'] and '26.2' in row['minecraft_versions']]
    reference = prior['source_provenance']['netty_artifact_inventory']
    inventory = read_json(reference['path'], reference['sha256'])
    items = [row for row in inventory['netty_artifacts'] if row['coordinate'] == coordinate]
    require(len(artifacts) == len(items) == 1 and items[0]['sha1'] == artifacts[0]['sha1'] and
            items[0]['sha256'] == artifacts[0]['sha256'] and items[0]['size'] == artifacts[0]['size_bytes'] and
            {'source_kind': 'integrated', 'group': group, 'source_sha': source['source_sha']} in items[0]['source_groups'] and
            '26.2' in items[0]['minecraft_versions'], 'fixed-boundary handler provenance differs')
    return {'minecraft_version': '26.2', 'source_kind': 'integrated', 'group': group,
        'source_sha': source['source_sha'], 'scope': 'runtime/26.2',
        'source_report_artifact_id': artifact['id'], 'source_report_archive_sha256': artifact['digest'].removeprefix('sha256:'),
        'manifest': {'url': metadata['url'], 'sha1': metadata['sha1'], 'sha256': metadata['sha256'],
                     'size_bytes': metadata['size_bytes']},
        'handler': {'coordinate': coordinate, 'purl': purl, 'url': items[0]['url'], 'sha1': items[0]['sha1'],
                    'sha256': items[0]['sha256'], 'size_bytes': items[0]['size']},
        'scope_note': 'The retained manifest and audit inventory identify the upstream fixed-boundary version; '
            'a live runtime was not observed and the shared source group remains blocking.',
        'security_clearance': False}


def verify_fixed_manifest_bytes(raw, example):
    metadata = example['manifest']
    require(len(raw) == metadata['size_bytes'] and hashlib.sha1(raw).hexdigest() == metadata['sha1'] and
            sha(raw) == metadata['sha256'], 'fixed-boundary manifest checksum differs')
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    handler = example['handler']
    entries = [row['downloads']['artifact'] for row in manifest['libraries']
               if row.get('name') == handler['coordinate'] and 'artifact' in row.get('downloads', {})]
    require(len(entries) == 1 and entries[0]['sha1'] == handler['sha1'] and
            entries[0]['size'] == handler['size_bytes'] and entries[0]['url'] == handler['url'],
            'fixed-boundary manifest handler entry differs')


def verify_fixed_handler_bytes(raw, example):
    handler = example['handler']
    require(len(raw) == handler['size_bytes'] and hashlib.sha1(raw).hexdigest() == handler['sha1'] and
            sha(raw) == handler['sha256'], 'fixed-boundary handler checksum differs')


def verify_fixed_download(example):
    metadata, handler = example['manifest'], example['handler']
    expected_meta = 'https://piston-meta.mojang.com/v1/packages/' + metadata['sha1'] + '/26.2.json'
    expected_handler = ('https://libraries.minecraft.net/io/netty/netty-handler/4.2.15.Final/'
                        'netty-handler-4.2.15.Final.jar')
    require(metadata['url'] == expected_meta and handler['url'] == expected_handler and
            0 < metadata['size_bytes'] <= 1024 * 1024, 'fixed-boundary source URL or size differs')
    request = Request(expected_meta, headers={'User-Agent': 'issue45-trust-fixed-artifact-verifier'})
    with build_opener(ipfilter.NoRedirect()).open(request, timeout=60) as response:
        require(response.geturl() == expected_meta, 'unexpected fixed-boundary manifest redirect')
        raw = response.read(metadata['size_bytes'] + 1)
    verify_fixed_manifest_bytes(raw, example)
    verify_fixed_handler_bytes(ipfilter.download_mojang_library(expected_handler, handler['size_bytes']), example)


def report_hashes(target):
    index, _, _ = audits.historic()
    _, reports, _ = audits.verify_live(audits.LIVE, index)
    result = {}
    for row in target['occurrences']:
        key = row['source_kind'] + '|' + row['group']
        report, _, artifact = reports[key]
        member = 'candidate-dependency-audit.json' if row['source_kind'] == 'candidate' else 'dependency-audit.json'
        require(report['source_sha'] == row['source_sha'] and artifact['id'] == row['source_report_artifact_id'] and
                artifact['digest'] == 'sha256:' + row['source_report_archive_sha256'] and
                row['source_report_member'] == member,
                'Trust Manager report provenance differs')
        matches = [match for match in report['matches'] if match['advisory'] == TARGET and match['purl'] == row['purl']]
        require(len(matches) == 1 and matches[0]['scopes'] == row['scopes'] and
                matches[0]['fingerprint'] == row['fingerprint'] and matches[0]['failing'] is True,
                'Trust Manager report finding differs')
        archive_path = audits.LIVE / 'raw' / (str(artifact['id']) + '.zip')
        with ZipFile(archive_path) as archive:
            report_raw = archive.read(member)
        require(json.loads(report_raw, object_pairs_hook=unique_object) == report,
                'Trust Manager report bytes differ')
        result[key] = sha(report_raw)
    return result


def make_review(ledger, target, previous, known, management, records, prior):
    old = {sni.identity(row): row for row in previous}
    libraries = {row['version']: row for row in known['libraries']}
    reports = report_hashes(target)
    occurrences = []
    for row in target['occurrences']:
        item = old[sni.identity(row)]
        version = row['purl'].rsplit('@', 1)[1]
        games = [{**game, 'version_metadata_sha256': prior['verified_manifest_versions'][game['minecraft_version']]['sha256']}
                 for game in item['minecraft_artifacts']]
        occurrences.append({**row, 'source_report_sha256_uncompressed': reports[row['source_kind'] + '|' + row['group']],
            'minecraft_artifacts': games, 'dependency_sha1': item['dependency_sha1'],
            'dependency_sha256': item['dependency_sha256'], 'handler_classes': libraries[version]['literal_hits'],
            'product_jar_sha256': item['product_jar_sha256']})
    return {'schema': 1, 'advisory_id': TARGET, 'aliases': ['CVE-2026-50010'], 'severity': 'HIGH',
        'observed_on': '2026-11-23', 'analysis_base_commit': '0562566cb43248a80b158b593d1935af45f33a3a',
        'upstream_advisory': {'path': UPSTREAM, 'sha256': UPSTREAM_SHA},
        'baseline_priority_register': ledger['bzip2_high_focused_priority_register'],
        'evidence': {path: sha(raw) for path, raw in records.items()}, 'occurrence_count': len(occurrences),
        'source_group_count': len({(row['source_kind'], row['group']) for row in occurrences}),
        'minecraft_version_count': len({game['minecraft_version'] for row in occurrences for game in row['minecraft_artifacts']}),
        'occurrences': occurrences, 'dependency_owner': 'Minecraft runtime manifests; Gradle also resolves some coordinates.',
        'upstream_fixed_versions': {'4.1.x': '4.1.135.Final', '4.2.x': '4.2.15.Final'},
        'fixed_version_example': fixed_runtime_example(prior, target),
        'observations': ['Six pinned Netty handler JARs contain the selected trust-manager classes.',
            'Six client JARs contain selected SslContextBuilder references; prior hash-bound disassembly '
            'identifies management-server-related TLS construction calls.',
            'The inspected product JARs and one Fabric Loader artifact contain no selected name literals.'],
        'limitations': ['A literal reference or class presence is not a loaded or invoked configuration.',
            'No launcher, game, dedicated server, modpack or TLS certificate-validation behavior was run.',
            'Runtime provider, classpath, generated or reflective paths, third-party mods and agents remain unverified.',
            'Dedicated-server distributions and compatibility of a newer Minecraft-managed Netty are unverified.'],
        'remediation': 'Evaluate a compatible Minecraft-managed update; the separate Critical SNI advisory '
            'has later fixed-version boundaries. No override or compatible game-side fix was verified.',
        'reviewer': 'Codex automated static investigation; human security review pending',
        'responsible_owner': 'Project maintainer and upstream Minecraft/library owners', 'review_date': '2026-11-23',
        'disposition': 'Further investigation', 'release_blocking': True, 'risk_accepted': False,
        'security_clearance': False, 'follow_up_requirements': [
            'Observe supported launcher, mod and dedicated-server TLS configurations and their trust boundaries.',
            'Verify a compatible upstream game update addressing this and the Critical SNI advisory.']}


def make_register(v4, review, review_raw):
    current = copy.deepcopy(v4)
    target = next(row for row in current['advisories'] if row['advisory_id'] == TARGET)
    require(target['focused_evidence'] is None and len(target['occurrences']) == review['occurrence_count'] == 12,
            'Trust Manager priority baseline differs')
    target.update(focused_evidence=REVIEW, reviewer=review['reviewer'], review_date=review['review_date'],
                  responsible_owner=review['responsible_owner'], follow_up=review['follow_up_requirements'])
    current['trust_focused_evidence'] = {'path': REVIEW, 'sha256': sha(review_raw),
                                         'new_advisory_ids': 1, 'new_high_occurrences': 12}
    current['review_status'] = 'Adds bounded Trust Manager static observations; no finding is cleared or risk accepted.'
    focused = [row for row in current['advisories'] if row['focused_evidence']]
    critical = sum(len(row['occurrences']) for row in focused if row['severity'] == 'CRITICAL')
    high = sum(len(row['occurrences']) for row in focused if row['severity'] == 'HIGH')
    total_high = sum(len(row['occurrences']) for row in current['advisories'] if row['severity'] == 'HIGH')
    current['focused_coverage'] = {'advisory_ids': len(focused), 'critical_occurrences': critical,
        'high_occurrences': high, 'total_occurrences': critical + high,
        'high_occurrences_without_focused_evidence': total_high - high}
    require(current['focused_coverage'] == {'advisory_ids': 24, 'critical_occurrences': 22,
        'high_occurrences': 120, 'total_occurrences': 142, 'high_occurrences_without_focused_evidence': 57},
        'Trust Manager focused coverage differs')
    return current


def validate_cli_arguments(args):
    """Reject optional inputs that the selected CLI mode would ignore."""
    cache_inputs = {
        '--runtime-cache': args.runtime_cache,
        '--manifest-cache': args.manifest_cache,
        '--fabric-jar': args.fabric_jar,
    }
    supplied_cache_inputs = [name for name, value in cache_inputs.items() if value is not None]

    if args.write_inputs:
        require(args.runtime_cache and args.fabric_jar,
                '--write-inputs requires --runtime-cache and --fabric-jar')
        require(not args.manifest_cache and not args.javap,
                '--write-inputs does not use --manifest-cache or --javap; remove those options')
        require(not (args.write_review or args.verify_known_download or
                     args.verify_management_download or args.verify_fixed_download),
                'input generation and verification must run separately')
        return

    cache_mode = bool(supplied_cache_inputs)
    if cache_mode:
        missing = [name for name, value in (
            ('--runtime-cache', args.runtime_cache),
            ('--manifest-cache', args.manifest_cache),
            ('--fabric-jar', args.fabric_jar),
            ('--javap', args.javap),
        ) if value is None]
        require(not missing,
                'cached reinspection requires --runtime-cache, --manifest-cache, --fabric-jar, '
                '--javap; missing ' + ', '.join(missing))

    if args.javap and not cache_mode and not args.verify_management_download:
        raise ValueError('--javap is only used by cached reinspection or --verify-management-download')
    if args.verify_management_download and not args.javap:
        raise ValueError('--verify-management-download requires --javap')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-cache', type=Path)
    parser.add_argument('--manifest-cache', type=Path)
    parser.add_argument('--fabric-jar', type=Path)
    parser.add_argument('--javap', type=Path)
    parser.add_argument('--verify-known-download', action='store_true')
    parser.add_argument('--verify-management-download', action='store_true')
    parser.add_argument('--verify-fixed-download', action='store_true')
    parser.add_argument('--write-inputs', action='store_true')
    parser.add_argument('--write-review', action='store_true')
    args = parser.parse_args()
    try:
        # Run this before source-bound evidence reads, artifact access, or any
        # explicitly requested network verification.
        validate_cli_arguments(args)
        ledger, v4, target, previous, catalog, versions, prior, mod, clients, index_ref, index = context()
        management = prior_management(index_ref, index, prior, versions)
        if args.write_inputs:
            selected = ipfilter.selected_artifacts(prior, versions)
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda item: scan_runtime_artifact(args.runtime_cache, item, versions), selected))
            by_sha = {row['sha1']: row for row in rows}
            known = {'schema': 1, 'libraries': [{'version': lib['version'], 'sha1': lib['sha1'],
                'sha256': lib['sha256'], 'literal_hits': by_sha[lib['sha1']]['literal_hits']}
                for lib in catalog], 'security_clearance': False}
            ids = {lib['sha1'] for lib in catalog}
            external = sorted([{'sha1': row['sha1'], **hit} for row in rows if row['sha1'] not in ids
                               for hit in row['literal_hits']], key=lambda item: (item['sha1'], item['class_file']))
            scan = {'schema': 1, 'minecraft_versions': versions, 'terms': list(TERMS), 'artifacts': rows,
                'class_files_scanned': sum(row['class_files_scanned'] for row in rows),
                'handler_hits': sum(len(row['literal_hits']) for row in rows if row['sha1'] in ids),
                'external_hits': external, 'security_clearance': False}
            fabric, product = inspect_fabric(args.fabric_jar.read_bytes()), product_scan()
            validate_inputs(prior, versions, catalog, index_ref, index, scan, known, fabric, product, management)
            for path, value in ((SCAN, scan), (KNOWN, known), (FABRIC, fabric), (PRODUCT, product), (MANAGEMENT, management)):
                sni.write_new(ROOT / path, value)
            print('Recorded bounded Trust Manager static observations; no finding was cleared')
            return 0
        records = {p: sni.read(ROOT, p) for p in (SCAN, KNOWN, FABRIC, PRODUCT, MANAGEMENT)}
        scan, known, fabric, product, management = (json.loads(records[p], object_pairs_hook=unique_object)
                                                   for p in (SCAN, KNOWN, FABRIC, PRODUCT, MANAGEMENT))
        validate_inputs(prior, versions, catalog, index_ref, index, scan, known, fabric, product, management)
        if args.verify_known_download:
            verify_known_downloads(catalog, prior, known)
            print('Verified six source-bound Netty handler JARs and 54 selected class observations')
        if args.verify_management_download:
            verify_management_download(clients, management, args.javap)
            print('Verified one source-bound client and regenerated selected management disassembly')
        if args.verify_fixed_download:
            verify_fixed_download(fixed_runtime_example(prior, target))
            print('Verified the 26.2 manifest and its upstream fixed-boundary handler artifact')
        if args.runtime_cache:
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda item: scan_runtime_artifact(args.runtime_cache, item, versions),
                                     ipfilter.selected_artifacts(prior, versions)))
            require(rows == scan['artifacts'] and inspect_fabric(args.fabric_jar.read_bytes()) == fabric,
                    'Trust Manager cached observations differ')
            row = next(x for x in clients['games'] if x['minecraft_version'] == '26.1')
            expected = next(x for x in management['observations'] if x['minecraft_version'] == '26.1')
            artifact = next(x for x in prior['runtime_classpath_scan']['all_artifacts']
                            if x['sha1'] == row['client_sha1'])
            verify_management_client_bytes(bzip.cache_bytes(args.runtime_cache, artifact), row, expected, args.javap)
            example = fixed_runtime_example(prior, target)
            metadata_path = (args.manifest_cache / '26.2.json').resolve()
            require(metadata_path.is_relative_to(args.manifest_cache.resolve()), 'manifest cache path escapes root')
            verify_fixed_manifest_bytes(metadata_path.read_bytes(), example)
            fixed_artifact = next(x for x in prior['runtime_classpath_scan']['all_artifacts']
                                  if x['sha1'] == example['handler']['sha1'])
            verify_fixed_handler_bytes(bzip.cache_bytes(args.runtime_cache, fixed_artifact), example)
            print('Verified cached Trust Manager static observations offline')
        review = make_review(ledger, target, previous, known, management, records, prior)
        if args.write_review:
            sni.write_new(ROOT / REVIEW, review)
            review_raw = sni.read(ROOT, REVIEW)
            sni.write_new(ROOT / CURRENT, make_register(v4, review, review_raw))
            print('Recorded 12 blocking Trust Manager occurrences and focused coverage')
            return 0
        review_raw = sni.read(ROOT, REVIEW)
        require(json.loads(review_raw, object_pairs_hook=unique_object) == review, 'Trust Manager review differs')
        current_raw = sni.read(ROOT, CURRENT)
        require(json.loads(current_raw, object_pairs_hook=unique_object) == make_register(v4, review, review_raw),
                'Trust Manager priority register differs')
        require(ledger.get('trust_high_focused_priority_register') == {'path': CURRENT, 'sha256': sha(current_raw),
            'advisory_ids': 24, 'focused_occurrences': 142, 'remaining_unfocused_high_occurrences': 57,
            'security_clearance': False}, 'Trust Manager priority ledger reference differs')
        print('Validated 12 blocking Trust Manager occurrences and bounded static observations')
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, BadZipFile, subprocess.SubprocessError) as exc:
        print('Trust Manager investigation incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
