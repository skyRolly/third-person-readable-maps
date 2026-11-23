#!/usr/bin/env python3
"""Validate source-bound static evidence for Netty Lz4FrameDecoder.

The investigation checks exact retained Minecraft artifacts and static class
references. It does not launch Minecraft, exercise a network pipeline, or
establish game-wide reachability.
"""
import argparse
import copy
from hashlib import sha1, sha256
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.request import build_opener
from zipfile import BadZipFile, ZipFile

import inspect_issue45_mod_jars as products
import inspect_issue45_netty_bzip2_high as bzip
import inspect_issue45_netty_ipfilter_high as ipfilter
import inspect_issue45_netty_trust_high as trust
import inspect_issue45_sni_high as sni
import reconcile_issue45_live_audits as audits
from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
DIR = 'docs/dependency-evidence/issue45-netty-lz4-high-2026-11-23'
UPSTREAM = DIR + '/upstream-advisory.json'
UPSTREAM_SHA256 = 'cfaeba6cf6352a1708c76d39db0c360fc6e54cbef7505f8704dadaee6693da4b'
RUNTIME_SCAN = DIR + '/runtime-classpath-scan.json'
SERVER_SCAN = DIR + '/dedicated-server-scan.json'
FABRIC_SCAN = DIR + '/fabric-loader-static-scan.json'
PRODUCT_SCAN = DIR + '/product-jar-static-scan.json'
FIXED_SCAN = DIR + '/fixed-boundary-runtime.json'
PIPELINE_SCAN = DIR + '/pipeline-static-observations.json'
SOURCE_INDEX = DIR + '/netty-source-observations.json'
REVIEW = DIR + '/source-bound-review.json'
CURRENT = DIR + '/priority-register-v6.json'
MANIFEST_DIR = DIR + '/minecraft-version-manifests'
SOURCE_DIR = DIR + '/netty-upstream'
TARGET = 'GHSA-mj4r-2hfc-f8p6'
ALIAS = 'CVE-2026-42583'
DEPENDENCY_OWNER = 'Minecraft runtime manifest; Gradle resolution also contains this coordinate when scoped gradle'
CLASS_NAME = 'io/netty/handler/codec/compression/Lz4FrameDecoder'
CLASS_FILE = CLASS_NAME + '.class'
TERMS = (CLASS_NAME, 'io.netty.handler.codec.compression.Lz4FrameDecoder')
CLIENT_VERSIONS = (
    '1.19', '1.19.1', '1.19.2', '1.19.3', '1.19.4', '1.20', '1.20.1',
    '1.20.2', '1.20.3', '1.20.4', '1.20.5', '1.20.6', '1.21', '1.21.1',
    '1.21.2', '1.21.3', '1.21.4', '1.21.5', '1.21.6', '1.21.7', '1.21.8',
    '1.21.9', '1.21.10', '1.21.11', '26.1', '26.1.1', '26.1.2',
)
FIXED_VERSIONS = ('26.2', '26.3')
ALL_MANIFEST_VERSIONS = tuple(sorted((*CLIENT_VERSIONS, *FIXED_VERSIONS)))
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024

SOURCE_COMMITS = {
    '4.1.76.Final': '3b3420ffc4f19fdfcfbe7865277a159a347b510e',
    '4.1.77.Final': '764975699608f10e39f1a1e75ffcc6abee8fa1af',
    '4.1.82.Final': 'dfcc831c8eea51af78796ade02660d141e521848',
    '4.1.97.Final': 'b202efcb282765fd5369c7715f5802c85cee6e5e',
    '4.1.115.Final': '91c92b5454727d993e6bca30b5c44b9e7a466b40',
    '4.1.118.Final': '07db0d26ed3199578d4b3ba5439af6584d6f5652',
    '4.1.132.Final': '92bdca0f99c202b7b0f46de6f86cf216ad7f5b2e',
    '4.1.133.Final': '4374d71208b0c9bfb2844fab610d3bfaf24f4733',
    '4.2.7.Final': '2fdba8c02a8f9b049c2f0d3a9bdd41ddd438efd6',
    '4.2.12.Final': 'c2ed1e8456f6e46e07f627828744f9257ef52ddb',
    '4.2.13.Final': '51df6d50dbd29df3e8f214e133d4363b89a7c624',
    '4.2.15.Final': '54004fa26dd12da3880b6caa4ed4436c5f1d985a',
    '4.2.16.Final': '260c56c410a39f7b74a00b0e79b9b51d3ceec6cd',
}
SOURCE_PATHS = {
    version: ('codec-compression' if version.startswith('4.2.') else 'codec') +
             '/src/main/java/io/netty/handler/codec/compression/Lz4FrameDecoder.java'
    for version in SOURCE_COMMITS
}
SOURCE_SHA256 = {
    '4.1.76.Final': '222eb9a7f9ec35dfe35cb81b03f0172389e37b8b98115249fa7642439dc955f1',
    '4.1.77.Final': '222eb9a7f9ec35dfe35cb81b03f0172389e37b8b98115249fa7642439dc955f1',
    '4.1.82.Final': '222eb9a7f9ec35dfe35cb81b03f0172389e37b8b98115249fa7642439dc955f1',
    '4.1.97.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.1.115.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.1.118.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.1.132.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.1.133.Final': 'b727ffc470ea2ebb1754f3fe11926cb49f9301ac525a71726acfc83b532635e6',
    '4.2.7.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.2.12.Final': 'da3c4808f53ac5540b09e42400ba6a00ef5da580faade9e11b7ad24d8240621b',
    '4.2.13.Final': 'b727ffc470ea2ebb1754f3fe11926cb49f9301ac525a71726acfc83b532635e6',
    '4.2.15.Final': 'b727ffc470ea2ebb1754f3fe11926cb49f9301ac525a71726acfc83b532635e6',
    '4.2.16.Final': 'b727ffc470ea2ebb1754f3fe11926cb49f9301ac525a71726acfc83b532635e6',
}
CONSTANT_SHA256 = {
    'Lz4Constants-4.1.77.Final.java': '9fe095da91e408bc30b042808e8e15ec874f95d5b0d272d3fbaef26979ff3737',
    'Lz4Constants-4.2.7.Final.java': 'd30a0b3bc32dd01844e6d5e496ad18a018493f6f435d00be4fff3400c24439a2',
    'Lz4Constants-4.1.133.Final.java': 'd30a0b3bc32dd01844e6d5e496ad18a018493f6f435d00be4fff3400c24439a2',
    'Lz4Constants-4.2.13.Final.java': 'd30a0b3bc32dd01844e6d5e496ad18a018493f6f435d00be4fff3400c24439a2',
}
POM_SHA256 = {
    'netty-4.1.133.Final-root-pom.xml': '381cded637c9df7c3fc6c72520a5ecd4cc3f27ed4b22078055d5ff263be2ff2c',
    'netty-4.1.133.Final-module-pom.xml': '3d542c35892ffe5c65d008f56eb1868ed1d7b204fbd17a2680567dae38130ee7',
    'netty-4.1.135.Final-root-pom.xml': '57fba2cf45d7151f0019c12da97e414515a9b28fafa5ac332ae429dc6c09003e',
    'netty-4.1.135.Final-module-pom.xml': 'c7fbaaf7fd5c425e0caa602adc4a154b71895062825d69d79766bbe51a7ca3bd',
    'netty-4.2.13.Final-root-pom.xml': '98d3eb48dde1a8e0724c93d0d2df78ef5d6accb8a6fc89dcaeb19d112de6d491',
    'netty-4.2.13.Final-module-pom.xml': 'b24cff1d2ea518c06abe7f3841b557b4fc987e5861b9c286ff56dc2424615b77',
    'netty-4.2.15.Final-root-pom.xml': 'e065158c6a9e5a238d2e5058bdb41e4aa3b83c9b0b57da4f5bc9029ed45ae7af',
    'netty-4.2.15.Final-module-pom.xml': '5a672c723d97d0a913fa4f92fb92f33d56b7fe4e3ff9f013dfcbd5fa69ce702e',
}
CODEC_CLASS_HASHES = {
    'io/netty/handler/codec/compression/Lz4FrameDecoder$1.class':
        '69bcdb70c53bd10b3e7a392c0dfa4030d9109cb1410e73959a7beeab4f74a4ae',
    'io/netty/handler/codec/compression/Lz4FrameDecoder$State.class':
        'ec4c7c17259a62ebe50dbca08920e96d9f819cd61519cacd71f691383574d56d',
}
COMPRESSION_CLASS_HASHES = {
    'io/netty/handler/codec/compression/Lz4FrameDecoder$1.class':
        '98f6550654d969f94d68687694e03593e785629f1a47798c988bd70e059429f2',
    'io/netty/handler/codec/compression/Lz4FrameDecoder$State.class':
        'acaffa5f0fb9b4daebad40f46b0fa72ed3d993b375fe332cd984f76722e60186',
}
MAIN_CLASS_HASHES = {
    'pkg:maven/io.netty/netty-codec@4.1.77.Final':
        '45e91d41924b5e1d077fdd495ca9cd57e658a3928678073d96c7434a3b1f3649',
    'pkg:maven/io.netty/netty-codec@4.1.82.Final':
        '45e91d41924b5e1d077fdd495ca9cd57e658a3928678073d96c7434a3b1f3649',
    'pkg:maven/io.netty/netty-codec@4.1.97.Final':
        '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    'pkg:maven/io.netty/netty-codec@4.1.115.Final':
        '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    'pkg:maven/io.netty/netty-codec@4.1.118.Final':
        '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    'pkg:maven/io.netty/netty-codec-compression@4.2.7.Final':
        '7ea25a15db981bb9e60cd6ce8a17539e2893d1ba52e43d939c1a7a5061ee7183',
}
SERVER_CODEC_MAIN_CLASS_HASHES = {
    '4.1.76.Final': '45e91d41924b5e1d077fdd495ca9cd57e658a3928678073d96c7434a3b1f3649',
    '4.1.77.Final': '45e91d41924b5e1d077fdd495ca9cd57e658a3928678073d96c7434a3b1f3649',
    '4.1.82.Final': '45e91d41924b5e1d077fdd495ca9cd57e658a3928678073d96c7434a3b1f3649',
    '4.1.97.Final': '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    '4.1.115.Final': '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    '4.1.118.Final': '15ebf8c8a8101e14e86c50d45bfb81693e76197d3480b20115e9179250a83de9',
    '4.2.7.Final': '7ea25a15db981bb9e60cd6ce8a17539e2893d1ba52e43d939c1a7a5061ee7183',
}
PIPELINE_CLASS_HASHES = {
    'net/minecraft/network/Connection.class': {
        'sha256': '0f0fea41351c3f1a741dcff9c42deba6923099ac4e0ad88327ff1e2eea53e935',
        'size_bytes': 33129},
    'net/minecraft/network/CompressionDecoder.class': {
        'sha256': '4488436c5f2677b478d15f248259364a9f8458fed1510c09882a83d19c190f8d',
        'size_bytes': 4225},
}
RUNTIME_HIT_ARTIFACTS = {
    'io.netty:netty-codec:4.1.77.Final', 'io.netty:netty-codec:4.1.82.Final',
    'io.netty:netty-codec:4.1.97.Final', 'io.netty:netty-codec:4.1.115.Final',
    'io.netty:netty-codec:4.1.118.Final', 'io.netty:netty-codec-compression:4.2.7.Final',
}


def require_digest(value, size=64, message='invalid SHA-256 digest'):
    require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{%d}' % size, value) is not None,
            message)


def read(path, expected=None):
    return sni.read(ROOT, path, expected)


def read_json(path, expected=None):
    return json.loads(read(path, expected), object_pairs_hook=unique_object)


def write_new(path, value):
    sni.write_new(ROOT / path, value)


def coordinate(purl):
    match = re.fullmatch(r'pkg:maven/io\.netty/(netty-codec(?:-compression)?)@(4\.[12]\.\d+\.Final)', purl)
    require(match is not None, 'unsupported Lz4 advisory package identity')
    module, version = match.groups()
    require((module == 'netty-codec' and version.startswith('4.1.')) or
            (module == 'netty-codec-compression' and version.startswith('4.2.')),
            'Lz4 module and version line differ')
    upper = 132 if version.startswith('4.1.') else 12
    require(int(version.split('.')[2]) <= upper, 'Lz4 package is outside the affected range')
    return 'io.netty:' + module + ':' + version


def baseline_context():
    """Rebuild the trust v5 baseline and retain its audit reports."""
    ledger, v4, trust_target, previous, catalog, versions, prior, mod, clients, index_ref, index = trust.context()
    evidence_paths = (trust.SCAN, trust.KNOWN, trust.FABRIC, trust.PRODUCT, trust.MANAGEMENT)
    evidence_raw = {path: read(path) for path in evidence_paths}
    scan, known, fabric, product, management = (
        json.loads(evidence_raw[path], object_pairs_hook=unique_object) for path in evidence_paths)
    trust.validate_inputs(prior, versions, catalog, index_ref, index, scan, known, fabric, product, management)
    trust_review = trust.make_review(ledger, trust_target, previous, known, management, evidence_raw, prior)
    trust_review_raw = read(trust.REVIEW)
    require(json.loads(trust_review_raw, object_pairs_hook=unique_object) == trust_review,
            'historical Trust Manager review differs')
    v5 = trust.make_register(v4, trust_review, trust_review_raw)
    v5_raw = read(trust.CURRENT)
    require(json.loads(v5_raw, object_pairs_hook=unique_object) == v5, 'historical Trust Manager register differs')
    v5_ref = {'path': trust.CURRENT, 'sha256': sha256(v5_raw).hexdigest(), 'advisory_ids': 24,
              'focused_occurrences': 142, 'remaining_unfocused_high_occurrences': 57,
              'security_clearance': False}
    require(ledger.get('trust_high_focused_priority_register', ledger.get('latest_focused_priority_register')) == v5_ref,
            'Trust Manager stage pointer differs')
    historical, _, _ = audits.historic()
    _, reports, _ = audits.verify_live(audits.LIVE, historical)
    target = next(row for row in v5['advisories'] if row['advisory_id'] == TARGET)
    require(target['severity'] == 'HIGH' and target['aliases'] == [ALIAS] and
            target['focused_evidence'] is None and len(target['occurrences']) == 12,
            'unexpected Lz4 priority baseline')
    return {'ledger': ledger, 'v5': v5, 'v5_raw': v5_raw, 'target': target, 'prior': prior,
            'versions': versions, 'reports': reports, 'product': mod,
            'trust_evidence': evidence_raw, 'trust_review': trust_review}


def advisory_ranges(advisory):
    require(advisory.get('ghsa_id') == TARGET and advisory.get('cve_id') == ALIAS and
            advisory.get('severity') == 'high' and advisory.get('withdrawn_at') is None,
            'authoritative Lz4 advisory identity differs')
    actual = {(item['package']['name'], item['vulnerable_version_range'],
               item['first_patched_version']) for item in advisory['vulnerabilities']}
    require(actual == {
        ('io.netty:netty-codec', '<= 4.1.132.Final', '4.1.133.Final'),
        ('io.netty:netty-codec-compression', '<= 4.2.12.Final', '4.2.13.Final'),
    }, 'authoritative Lz4 version boundaries differ')
    return actual


def validate_occurrences(target, reports):
    """Require exact equality with source report matches, including archive identity."""
    expected = []
    for key, (report, _tool, artifact) in reports.items():
        source_kind, group = key.split('|', 1)
        for match in report['matches']:
            if match.get('advisory') != TARGET:
                continue
            require(match.get('severity') == 'HIGH' and match.get('failing') is True and
                    match.get('disposition') == 'Further investigation',
                    'Lz4 source match is not a blocking High occurrence')
            expected.append({
                'source_kind': source_kind, 'group': group,
                'source_sha': report['source_sha'], 'purl': match['purl'],
                'scopes': match['scopes'], 'fingerprint': match['fingerprint'],
                'source_report_artifact_id': artifact['id'],
                'source_report_archive_sha256': artifact['digest'].removeprefix('sha256:'),
                'source_report_member': ('candidate-dependency-audit.json' if
                    source_kind == 'candidate' else 'dependency-audit.json'),
                'source_report_name': artifact['name'], 'source_report_run': artifact['run'],
                'dependency_owner': DEPENDENCY_OWNER, 'disposition': match['disposition'],
                'release_blocking': match['failing'], 'risk_accepted': False,
            })
    expected.sort(key=lambda row: (row['source_kind'], row['group'], row['purl']))
    actual = []
    seen = set()
    for row in target['occurrences']:
        identity = (row['source_kind'], row['group'], row['source_sha'], row['purl'])
        require(identity not in seen, 'duplicate Lz4 occurrence identity')
        seen.add(identity)
        require(row['release_blocking'] is True and row['risk_accepted'] is False and
                row['disposition'] == 'Further investigation', 'Lz4 occurrence is not blocking')
        coordinate(row['purl'])
        source_key = row['source_kind'] + '|' + row['group']
        _report, _tool, artifact = reports[source_key]
        source_kind, group = source_key.split('|', 1)
        actual.append({
            'source_kind': source_kind, 'group': group, 'source_sha': row['source_sha'],
            'purl': row['purl'], 'scopes': row['scopes'], 'fingerprint': row['fingerprint'],
            'source_report_artifact_id': row['source_report_artifact_id'],
            'source_report_archive_sha256': row['source_report_archive_sha256'],
            'source_report_member': row['source_report_member'],
            'source_report_name': artifact['name'], 'source_report_run': artifact['run'],
            'dependency_owner': row['dependency_owner'], 'disposition': row['disposition'],
            'release_blocking': row['release_blocking'], 'risk_accepted': row['risk_accepted'],
        })
    actual.sort(key=lambda row: (row['source_kind'], row['group'], row['purl']))
    require(len(expected) == len(actual) == 12 and actual == expected,
            'Lz4 source occurrence set differs from the exact audit reports')
    require(len({(row['source_kind'], row['group']) for row in actual}) == 10,
            'Lz4 source group count differs')
    return actual


def manifest_bytes(game, manifest_cache=None):
    if manifest_cache:
        cache_root = manifest_cache.resolve()
        path = (cache_root / (game + '.json')).resolve()
        require(path.is_relative_to(cache_root), 'Minecraft manifest cache path escapes root')
        return path.read_bytes()
    return (ROOT / MANIFEST_DIR / (game + '.json')).resolve().read_bytes()


def validate_manifest(game, raw, prior):
    metadata = prior['verified_manifest_versions'].get(game)
    require(metadata is not None and len(raw) == metadata['size_bytes'] and
            sha1(raw).hexdigest() == metadata['sha1'] and sha256(raw).hexdigest() == metadata['sha256'],
            'Minecraft manifest identity differs: ' + game)
    manifest = json.loads(raw, object_pairs_hook=unique_object)
    require(manifest.get('id') == game, 'Minecraft manifest version differs: ' + game)
    return manifest


def manifest_artifact(manifest, game, coord):
    if coord == 'minecraft-client:' + game:
        return manifest['downloads']['client']
    rows = [row for row in manifest['libraries'] if row.get('name') == coord]
    require(len(rows) == 1 and isinstance(rows[0].get('downloads', {}).get('artifact'), dict),
            'Minecraft manifest library identity differs: ' + game + ' ' + coord)
    return rows[0]['downloads']['artifact']


def scan_jar(raw):
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate JAR entry in Lz4 scan')
        count, hits = 0, []
        for name in sorted(item for item in names if item.endswith('.class')):
            content = archive.read(name)
            count += 1
            found = [term for term in TERMS if term.encode('ascii') in content]
            if found:
                hits.append({'class_file': name, 'sha256': sha256(content).hexdigest(), 'terms': found})
        nested = sorted(item for item in names if item.lower().endswith('.jar'))
    return count, hits, nested


def cache_bytes(cache, relative, size, expected_sha1, expected_sha256):
    cache_root = cache.resolve()
    path = (cache_root / relative).resolve()
    if not path.exists() and path.suffix == '':
        path = path.with_suffix('.jar')
    path = path.resolve()
    require(path.is_relative_to(cache_root), 'Lz4 cache path escapes root')
    raw = path.read_bytes()
    require(type(size) is int and 0 < size <= MAX_ARTIFACT_BYTES and len(raw) == size and
            sha1(raw).hexdigest() == expected_sha1 and sha256(raw).hexdigest() == expected_sha256,
            'cached Lz4 artifact checksum differs')
    return raw


def build_runtime_scan(prior, versions, manifests, runtime_cache):
    selected = ipfilter.selected_artifacts(prior, versions)
    rows = []
    for artifact in selected:
        coord = artifact['coordinates'][0]
        manifest_rows = []
        for game in artifact['minecraft_versions']:
            entry = manifest_artifact(manifests[game], game, coord)
            require(entry['sha1'] == artifact['sha1'] and entry['size'] == artifact['size_bytes'],
                    'runtime manifest artifact differs: ' + game + ' ' + coord)
            manifest_rows.append({'minecraft_version': game, 'manifest_sha1':
                prior['verified_manifest_versions'][game]['sha1'], 'url': entry['url'],
                'sha1': entry['sha1'], 'size_bytes': entry['size']})
        require(len({(row['url'], row['sha1'], row['size_bytes']) for row in manifest_rows}) == 1,
                'shared runtime artifact changes identity between manifests: ' + coord)
        raw = cache_bytes(runtime_cache, artifact['cache_object'], artifact['size_bytes'],
                          artifact['sha1'], artifact['sha256'])
        count, hits, nested = scan_jar(raw)
        require(count == artifact['class_files_scanned'] and not nested,
                'runtime artifact class coverage differs: ' + coord)
        rows.append({'sha1': artifact['sha1'], 'sha256': artifact['sha256'],
            'size_bytes': artifact['size_bytes'], 'coordinates': artifact['coordinates'],
            'minecraft_versions': artifact['minecraft_versions'], 'class_files_scanned': count,
            'download_url': manifest_rows[0]['url'], 'manifest_artifacts': manifest_rows,
            'decoder_reference_hits': hits})
    return {'schema': 1, 'minecraft_versions': versions, 'terms': list(TERMS),
            'artifacts': rows, 'class_files_scanned': sum(row['class_files_scanned'] for row in rows),
            'artifact_count': len(rows), 'security_clearance': False}


def build_server_scan(prior, versions, manifests, server_cache):
    servers = []
    for game in versions:
        manifest = manifests[game]
        metadata = manifest['downloads'].get('server')
        require(metadata is not None and metadata['size'] <= MAX_ARTIFACT_BYTES,
                'Minecraft manifest server artifact is unavailable or too large: ' + game)
        raw = cache_bytes(server_cache, game + '.jar', metadata['size'], metadata['sha1'],
                          _sha256_from_server_scan_cache(server_cache, game, metadata))
        # The official version manifest carries SHA-1 and size. The SHA-256 is
        # computed here and retained; the cache helper uses that computed value.
        outer_count, outer_hits, nested_names = scan_jar(raw)
        nested_rows, all_hits, total_classes = [], list(outer_hits), outer_count
        with ZipFile(BytesIO(raw)) as archive:
            for name in nested_names:
                child = archive.read(name)
                child_count, child_hits, inner_nested = scan_jar(child)
                require(not inner_nested, 'uninspected nested server library: ' + game + ' ' + name)
                nested_rows.append({'path': name, 'sha1': sha1(child).hexdigest(),
                    'sha256': sha256(child).hexdigest(), 'size_bytes': len(child),
                    'class_files_scanned': child_count, 'decoder_reference_hits': child_hits})
                all_hits.extend({'class_file': name + '!' + hit['class_file'],
                    'sha256': hit['sha256'], 'terms': hit['terms']} for hit in child_hits)
                total_classes += child_count
        java = manifest.get('javaVersion', {})
        servers.append({'minecraft_version': game,
            'manifest_sha1': prior['verified_manifest_versions'][game]['sha1'],
            'server_url': metadata['url'], 'server_sha1': metadata['sha1'],
            'server_sha256': sha256(raw).hexdigest(), 'server_size_bytes': len(raw),
            'java_component': java.get('component'), 'java_major_version': java.get('majorVersion'),
            'top_level_class_files_scanned': outer_count, 'nested_jars': nested_rows,
            'total_class_files_scanned': total_classes, 'decoder_reference_hits': all_hits})
    return {'schema': 1, 'scan_type': 'static class literal scan; no server launched',
            'terms': list(TERMS), 'minecraft_versions': list(versions),
            'servers': servers, 'server_artifact_count': len(servers),
            'nested_jar_count': sum(len(row['nested_jars']) for row in servers),
            'class_files_scanned': sum(row['total_class_files_scanned'] for row in servers),
            'security_clearance': False}


def _sha256_from_server_scan_cache(cache, game, metadata):
    """Compute SHA-256 after confirming the server cache matches Mojang metadata."""
    cache_root = cache.resolve()
    path = (cache_root / (game + '.jar')).resolve()
    require(path.is_relative_to(cache_root), 'server cache path escapes root')
    raw = path.read_bytes()
    require(len(raw) == metadata['size'] and sha1(raw).hexdigest() == metadata['sha1'],
            'Minecraft server SHA-1 or size differs: ' + game)
    return sha256(raw).hexdigest()


def build_fabric_scan(raw):
    require(len(raw) == 1988880 and sha1(raw).hexdigest() == ipfilter.FABRIC_SHA1 and
            sha256(raw).hexdigest() == ipfilter.FABRIC_SHA256, 'Fabric Loader artifact identity differs')
    count, hits, nested = scan_jar(raw)
    nested_rows = []
    with ZipFile(BytesIO(raw)) as archive:
        for name in nested:
            child = archive.read(name)
            child_count, child_hits, child_nested = scan_jar(child)
            require(not child_nested, 'uninspected nested Fabric JAR')
            nested_rows.append({'path': name, 'sha256': sha256(child).hexdigest(),
                'size_bytes': len(child), 'class_files_scanned': child_count,
                'decoder_reference_hits': child_hits})
    return {'schema': 1, 'coordinate': 'net.fabricmc:fabric-loader:0.20.1',
        'source_url': ipfilter.FABRIC_URL, 'sha1': ipfilter.FABRIC_SHA1,
        'sha256': ipfilter.FABRIC_SHA256, 'size_bytes': len(raw),
        'class_files_scanned': count, 'decoder_reference_hits': hits,
        'nested_jars': nested_rows, 'security_clearance': False}


def product_scan():
    old = products.NEEDLES
    try:
        products.NEEDLES = TERMS
        report = products.collect()
    finally:
        products.NEEDLES = old
    report = copy.deepcopy(report)
    report['decoder_terms'] = list(TERMS)
    return report


def build_fixed_scan(manifests, fixed_cache, baseline):
    rows = []
    for game in FIXED_VERSIONS:
        manifest = manifests[game]
        expected_name = 'io.netty:netty-codec-compression:' + ('4.2.15.Final' if game == '26.2' else '4.2.16.Final')
        library = [row for row in manifest['libraries'] if row.get('name') == expected_name]
        require(len(library) == 1, 'fixed-boundary Netty module is missing: ' + game)
        netty = library[0]['downloads']['artifact']
        codec_raw = cache_bytes(fixed_cache, 'codec-' + game + '.jar', netty['size'], netty['sha1'],
                                _fixed_cache_sha256(fixed_cache, 'codec-' + game + '.jar', netty))
        client_info, server_info = manifest['downloads']['client'], manifest['downloads']['server']
        client_raw = cache_bytes(fixed_cache, 'client-' + game + '.jar', client_info['size'],
            client_info['sha1'], _fixed_cache_sha256(fixed_cache, 'client-' + game + '.jar', client_info))
        server_raw = cache_bytes(fixed_cache, 'server-' + game + '.jar', server_info['size'],
            server_info['sha1'], _fixed_cache_sha256(fixed_cache, 'server-' + game + '.jar', server_info))
        client_count, client_hits, client_nested = scan_jar(client_raw)
        require(not client_nested, 'unexpected nested Minecraft client archive')
        server_outer_count, server_outer_hits, server_nested = scan_jar(server_raw)
        server_hits = list(server_outer_hits)
        nested_lz4 = []
        with ZipFile(BytesIO(server_raw)) as archive:
            for name in server_nested:
                child = archive.read(name)
                child_count, child_hits, child_nested = scan_jar(child)
                require(not child_nested, 'uninspected fixed server nested JAR')
                server_hits.extend({'class_file': name + '!' + hit['class_file'],
                    'sha256': hit['sha256'], 'terms': hit['terms']} for hit in child_hits)
                if 'netty-codec-compression/' in name:
                    lz4 = [item for item in child_hits if item['class_file'] == CLASS_FILE]
                    nested_lz4.append({'path': name, 'sha1': sha1(child).hexdigest(),
                        'sha256': sha256(child).hexdigest(), 'size_bytes': len(child),
                        'class_files_scanned': child_count,
                        'decoder_class_sha256': lz4[0]['sha256'] if len(lz4) == 1 else None})
        codec_count, codec_hits, codec_nested = scan_jar(codec_raw)
        require(not codec_nested and codec_count > 0 and
                len([hit for hit in codec_hits if hit['class_file'] == CLASS_FILE]) == 1,
                'fixed-boundary Netty decoder class is missing')
        java = manifest.get('javaVersion', {})
        rows.append({'minecraft_version': game,
            'manifest_sha1': baseline['prior']['verified_manifest_versions'][game]['sha1'],
            'runtime_source': _fixed_source_identity(game, baseline['reports']),
            'java_component': java.get('component'), 'java_major_version': java.get('majorVersion'),
            'codec': {'coordinate': expected_name, 'purl': 'pkg:maven/io.netty/netty-codec-compression@' +
                expected_name.rsplit(':', 1)[1], 'url': netty['url'], 'sha1': netty['sha1'],
                'sha256': sha256(codec_raw).hexdigest(), 'size_bytes': len(codec_raw),
                'class_files_scanned': codec_count, 'decoder_reference_hits': codec_hits},
            'client': {'url': client_info['url'], 'sha1': client_info['sha1'],
                'sha256': sha256(client_raw).hexdigest(), 'size_bytes': len(client_raw),
                'class_files_scanned': client_count, 'decoder_reference_hits': client_hits},
            'server': {'url': server_info['url'], 'sha1': server_info['sha1'],
                'sha256': sha256(server_raw).hexdigest(), 'size_bytes': len(server_raw),
                'top_level_class_files_scanned': server_outer_count,
                'decoder_reference_hits': server_hits, 'bundled_codec_compression': nested_lz4}})
    return {'schema': 1, 'scope': 'Static Mojang manifest, client, server bundle, and Netty JAR verification; no launch observed.',
            'artifacts': rows, 'security_clearance': False}


def _fixed_cache_sha256(cache, name, metadata):
    root = cache.resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root), 'fixed artifact cache path escapes root')
    raw = path.read_bytes()
    require(len(raw) == metadata['size'] and sha1(raw).hexdigest() == metadata['sha1'],
            'fixed artifact SHA-1 or size differs: ' + name)
    return sha256(raw).hexdigest()


def _fixed_source_identity(game, reports):
    group = 'integrated|26.1-26.2' if game == '26.2' else 'integrated|26.3'
    report, _tool, artifact = reports[group]
    source_kind, group_name = group.split('|', 1)
    runtime_key = 'runtime/' + game
    require(game in report['runtime_manifests'] and runtime_key in report['inventories'],
            'fixed Minecraft version is outside the exact integrated report: ' + game)
    return {'source_kind': source_kind, 'group': group_name, 'source_sha': report['source_sha'],
        'source_report_artifact_id': artifact['id'],
        'source_report_archive_sha256': artifact['digest'].removeprefix('sha256:'),
        'source_report_member': 'dependency-audit.json',
        'runtime_manifest_sha1': report['runtime_manifests'][game]['sha1'],
        'runtime_scope': runtime_key}


def build_pipeline_observation(client_raw, server_raw):
    import subprocess

    def disassemble(jar, context):
        outputs = {}
        for class_name in ('net.minecraft.network.Connection', 'net.minecraft.network.CompressionDecoder'):
            result = subprocess.run(['java', '-m', 'jdk.jdeps/com.sun.tools.javap.Main', '-c', '-p',
                '-classpath', str(jar), class_name], check=True, capture_output=True, text=True, timeout=60)
            lines = result.stdout.splitlines()
            if class_name.endswith('Connection'):
                starts = [idx for idx, line in enumerate(lines) if 'setupCompression(int, boolean)' in line]
                require(len(starts) == 1, 'static Minecraft compression setup method differs')
                begin = starts[0]
                end = next((idx for idx in range(begin + 1, len(lines)) if lines[idx].startswith(
                    ('  public ', '  private ', '  protected '))), len(lines))
                method = '\n'.join(lines[begin:end])
                require('net/minecraft/network/CompressionDecoder' in method and
                        'ChannelPipeline.addAfter' in method and 'Lz4FrameDecoder' not in method,
                        'Minecraft compression pipeline literals differ')
                outputs['connection_setup_compression'] = method
            else:
                selected = [line for line in lines if 'public class net.minecraft.network.CompressionDecoder' in line or
                    'Inflater' in line or 'ByteToMessageDecoder' in line or 'decode(' in line or 'inflate(' in line]
                require(any('java.util.zip.Inflater' in line for line in selected) and
                        any('ByteToMessageDecoder' in line for line in selected),
                        'Minecraft CompressionDecoder class differs')
                outputs['compression_decoder_disassembly_lines'] = selected
        with ZipFile(jar) as archive:
            outputs['class_files'] = {name: {'sha256': sha256(archive.read(name)).hexdigest(),
                'size_bytes': len(archive.read(name))} for name in
                ('net/minecraft/network/Connection.class', 'net/minecraft/network/CompressionDecoder.class')}
        outputs['jar_sha256'] = sha256(Path(jar).read_bytes()).hexdigest()
        outputs['jar_size_bytes'] = Path(jar).stat().st_size
        outputs['context'] = context
        return outputs

    with ZipFile(BytesIO(server_raw)) as archive:
        names = archive.namelist()
        inner_name = next((name for name in names if name.endswith('.jar') and
                           '/versions/26.1.2/server-26.1.2.jar' in name), None)
        require(inner_name is not None, '26.1.2 dedicated-server class archive is missing')
        server_inner_raw = archive.read(inner_name)
    import tempfile
    with tempfile.TemporaryDirectory(prefix='issue45-lz4-javap-') as directory:
        client_path = Path(directory) / 'client.jar'
        server_path = Path(directory) / 'server-inner.jar'
        client_path.write_bytes(client_raw)
        server_path.write_bytes(server_inner_raw)
        client = disassemble(client_path, 'Mojang client artifact from manifest 26.1.2')
        server = disassemble(server_path, 'server-26.1.2.jar embedded in exact Mojang server bundle')
    return {'schema': 1, 'minecraft_version': '26.1.2',
        'tool': 'OpenJDK javap module via java -m jdk.jdeps/com.sun.tools.javap.Main',
        'tool_version': subprocess.run(['java', '-m', 'jdk.jdeps/com.sun.tools.javap.Main', '-version'],
            check=True, capture_output=True, text=True, timeout=30).stdout.strip(),
        'scope': 'Static disassembly of exact client and dedicated-server class bytes; neither process was launched.',
        'client': client, 'server_inner': server,
        'observations': [
            'Connection.setupCompression(int, boolean) installs Minecraft CompressionDecoder after splitter and CompressionEncoder after prepender when the threshold is enabled.',
            'CompressionDecoder extends Netty ByteToMessageDecoder and uses java.util.zip.Inflater.',
            'No Lz4FrameDecoder reference is present in the selected Connection or CompressionDecoder class bytes.',
            'This is static pipeline construction evidence, not an observation of a running channel.'
        ], 'security_clearance': False}


def _expected_runtime_hits(prior, versions):
    expected = {}
    for artifact in ipfilter.selected_artifacts(prior, versions):
        coord = artifact['coordinates'][0]
        if coord in RUNTIME_HIT_ARTIFACTS:
            group, artifact_name, version = coord.split(':')
            purl = 'pkg:maven/' + group + '/' + artifact_name + '@' + version
            main = MAIN_CLASS_HASHES[purl]
            expected[artifact['sha1']] = [
                {'class_file': path, 'sha256': digest, 'terms': [TERMS[0]]}
                for path, digest in sorted({**(COMPRESSION_CLASS_HASHES if version.startswith('4.2.')
                                               else CODEC_CLASS_HASHES), CLASS_FILE: main}.items())]
    return expected


def validate_runtime_scan(scan, prior, versions, manifests):
    selected = ipfilter.selected_artifacts(prior, versions)
    actual = {row['sha1']: row for row in scan.get('artifacts', [])}
    require(scan.get('schema') == 1 and scan.get('minecraft_versions') == versions and
            scan.get('terms') == list(TERMS) and
            len(actual) == len(scan.get('artifacts', [])) == len(selected) == 471 and
            set(actual) == {row['sha1'] for row in selected},
            'Lz4 runtime classpath artifact coverage differs')
    by_sha = {row['sha1']: row for row in selected}
    expected_hits = _expected_runtime_hits(prior, versions)
    for identifier, row in actual.items():
        source = by_sha[identifier]
        require(row['sha256'] == source['sha256'] and row['size_bytes'] == source['size_bytes'] and
                row['coordinates'] == source['coordinates'] and row['minecraft_versions'] == source['minecraft_versions'] and
                row['class_files_scanned'] == source['class_files_scanned'],
                'Lz4 runtime artifact identity differs: ' + str(row['coordinates']))
        coordinate_name = row['coordinates'][0]
        manifest_rows = row.get('manifest_artifacts')
        require(isinstance(manifest_rows, list) and
                {item['minecraft_version'] for item in manifest_rows} == set(row['minecraft_versions']),
                'Lz4 runtime manifest coverage differs: ' + coordinate_name)
        for item in manifest_rows:
            game = item['minecraft_version']
            manifest = manifests[game]
            entry = manifest_artifact(manifest, game, coordinate_name)
            require(item['manifest_sha1'] == row_manifest_sha(prior, game) and item['url'] == entry['url'] and
                    item['sha1'] == entry['sha1'] == row['sha1'] and
                    item['size_bytes'] == entry['size'] == row['size_bytes'],
                    'Lz4 runtime manifest package identity differs: ' + game + ' ' + coordinate_name)
        require(row['download_url'] == manifest_rows[0]['url'], 'Lz4 runtime URL differs')
        expected = expected_hits.get(identifier, [])
        require(row['decoder_reference_hits'] == expected,
                'Lz4 runtime decoder reference observation differs: ' + coordinate_name)
    require(scan['class_files_scanned'] == sum(row['class_files_scanned'] for row in selected) == 369335 and
            sum(len(row['decoder_reference_hits']) for row in actual.values()) == 18,
            'Lz4 runtime scan totals differ')
    require(len(expected_hits) == 6, 'Lz4 runtime codec coverage differs')


def row_manifest_sha(prior, game):
    return prior['verified_manifest_versions'][game]['sha1']


def server_codec_rows(server):
    return [row for row in server['nested_jars'] if
            '/io/netty/netty-codec/' in row['path'] or
            '/io/netty/netty-codec-compression/' in row['path']]


def expected_server_codec_hits(path):
    parts = path.split('/')
    module = next((name for name in ('netty-codec', 'netty-codec-compression') if name in parts), None)
    require(module is not None, 'unsupported bundled Netty codec path')
    version = parts[parts.index(module) + 1]
    require(version in SERVER_CODEC_MAIN_CLASS_HASHES, 'unsupported bundled Netty codec version: ' + version)
    inner = COMPRESSION_CLASS_HASHES if module == 'netty-codec-compression' else CODEC_CLASS_HASHES
    hashes = {**inner, CLASS_FILE: SERVER_CODEC_MAIN_CLASS_HASHES[version]}
    return [{'class_file': name, 'sha256': digest, 'terms': [TERMS[0]]}
            for name, digest in sorted(hashes.items())]


def validate_server_scan(scan, prior, versions, manifests):
    servers = {row['minecraft_version']: row for row in scan.get('servers', [])}
    require(scan.get('schema') == 1 and scan.get('minecraft_versions') == list(versions) and
            len(servers) == len(scan.get('servers', [])) == 27 and set(servers) == set(versions),
            'dedicated-server artifact coverage differs')
    seen_server_shas, class_total, nested_total, hits_total = set(), 0, 0, 0
    for game, row in servers.items():
        manifest = manifests[game]
        source = manifest['downloads'].get('server')
        require(source is not None and row['manifest_sha1'] == row_manifest_sha(prior, game) and
                row['server_url'] == source['url'] and row['server_sha1'] == source['sha1'] and
                row['server_size_bytes'] == source['size'] and row['java_major_version'] ==
                manifest.get('javaVersion', {}).get('majorVersion'),
                'dedicated-server manifest provenance differs: ' + game)
        require_digest(row['server_sha256'])
        nested = row['nested_jars']
        require(len({item['path'] for item in nested}) == len(nested) and
                all(item['size_bytes'] > 0 and item['class_files_scanned'] >= 0 for item in nested),
                'dedicated-server nested archive inventory differs: ' + game)
        require(row['total_class_files_scanned'] == row['top_level_class_files_scanned'] +
                sum(item['class_files_scanned'] for item in nested),
                'dedicated-server class-file totals differ: ' + game)
        refs = row['decoder_reference_hits']
        for hit in refs:
            owner = next((item for item in nested if hit['class_file'].startswith(item['path'] + '!')), None)
            require(owner is not None and
                    ('/io/netty/netty-codec/' in owner['path'] or
                     '/io/netty/netty-codec-compression/' in owner['path']),
                    'Lz4 server reference appears outside a Netty codec JAR: ' + game)
        for item in nested:
            require_digest(item['sha1'], 40, 'invalid nested server artifact SHA-1')
            require_digest(item['sha256'])
            if '/io/netty/netty-codec/' in item['path'] or '/io/netty/netty-codec-compression/' in item['path']:
                version = item['path'].split('/')[-2]
                require(item['path'].endswith('/' + item['path'].split('/')[-1]) and
                        re.fullmatch(r'4\.[12]\.\d+\.Final', version),
                        'invalid server Netty codec path')
                require(item['decoder_reference_hits'] == expected_server_codec_hits(item['path']),
                        'dedicated-server Netty decoder class observation differs: ' + game)
        expected_refs = [{'class_file': item['path'] + '!' + hit['class_file'],
            'sha256': hit['sha256'], 'terms': hit['terms']}
            for item in nested for hit in item['decoder_reference_hits']]
        require(refs == expected_refs,
                'dedicated-server decoder reference aggregation differs: ' + game)
        seen_server_shas.add(row['server_sha1'])
        class_total += row['total_class_files_scanned']
        nested_total += len(nested)
        hits_total += len(refs)
    require(len(seen_server_shas) == 27 and class_total == scan['class_files_scanned'] == 782120 and
            nested_total == scan['nested_jar_count'] == 983 and hits_total == 81,
            'dedicated-server scan totals differ')
    # 1.19.0's server bundle includes 4.1.76.Final although the client manifest
    # occurrence is 4.1.77.Final. Preserve it as an out-of-index observation.
    v119 = server_codec_rows(servers['1.19'])
    require(any(row['path'].endswith('/4.1.76.Final/netty-codec-4.1.76.Final.jar') for row in v119),
            'Minecraft 1.19 dedicated-server Netty variant differs')
    for row in scan['servers']:
        codecs = server_codec_rows(row)
        expected_hit_count = 3 * len(codecs)
        require(len(row['decoder_reference_hits']) == expected_hit_count,
                'dedicated-server decoder hits are not limited to bundled Netty codec classes')


def validate_fabric_scan(scan):
    require(scan == {'schema': 1, 'coordinate': 'net.fabricmc:fabric-loader:0.20.1',
        'source_url': ipfilter.FABRIC_URL, 'sha1': ipfilter.FABRIC_SHA1,
        'sha256': ipfilter.FABRIC_SHA256, 'size_bytes': 1988880,
        'class_files_scanned': 771, 'decoder_reference_hits': [],
        'nested_jars': [{'path': 'META-INF/jars/mixinextras-fabric-0.5.5.jar',
            'sha256': '5da883dc4bfb16e4ceca3f16d8c4ad937bdfb1ce337ed5ba15472d4d81dd6242',
            'size_bytes': 727864, 'class_files_scanned': 506, 'decoder_reference_hits': []}],
        'security_clearance': False}, 'Fabric Loader Lz4 observation differs')


def validate_product_scan(scan):
    expected = product_scan()
    require(scan == expected and len(scan['groups']) == 13 and
            all(not row['nested_jar_entries'] and all(not cls['matches'] for cls in row['classes'])
                for row in scan['groups'].values()), 'product JAR Lz4 observations differ')


def validate_fixed_scan(scan, baseline, reports, manifests):
    rows = {row['minecraft_version']: row for row in scan.get('artifacts', [])}
    require(scan.get('schema') == 1 and scan.get('security_clearance') is False and
            set(rows) == set(FIXED_VERSIONS) and len(rows) == 2,
            'fixed-boundary Minecraft artifact coverage differs')
    expected_versions = {'26.2': '4.2.15.Final', '26.3': '4.2.16.Final'}
    for game, row in rows.items():
        manifest = manifests[game]
        version = expected_versions[game]
        source_name = 'io.netty:netty-codec-compression:' + version
        libs = [item for item in manifest['libraries'] if item.get('name') == source_name]
        require(len(libs) == 1 and row['codec']['coordinate'] == source_name and
                row['codec']['purl'] == 'pkg:maven/io.netty/netty-codec-compression@' + version and
                row['codec']['sha1'] == libs[0]['downloads']['artifact']['sha1'] and
                row['codec']['url'] == libs[0]['downloads']['artifact']['url'] and
                row['codec']['size_bytes'] == libs[0]['downloads']['artifact']['size'],
                'fixed-boundary Netty coordinate differs: ' + game)
        require(row['manifest_sha1'] == row_manifest_sha(baseline['prior'], game) and
                row['runtime_source'] == _fixed_source_identity(game, reports) and
                row['java_major_version'] == 25,
                'fixed-boundary Minecraft source or Java identity differs: ' + game)
        client_info, server_info = manifest['downloads']['client'], manifest['downloads']['server']
        require(row['client']['url'] == client_info['url'] and row['client']['sha1'] == client_info['sha1'] and
                row['client']['size_bytes'] == client_info['size'] and
                row['server']['url'] == server_info['url'] and row['server']['sha1'] == server_info['sha1'] and
                row['server']['size_bytes'] == server_info['size'],
                'fixed-boundary client or server manifest identity differs: ' + game)
        require_digest(row['client']['sha256'])
        require_digest(row['server']['sha256'])
        require(len([hit for hit in row['codec']['decoder_reference_hits'] if
                     hit['class_file'] == CLASS_FILE]) == 1 and
                row['codec']['decoder_reference_hits'] == [
                    {'class_file': 'io/netty/handler/codec/compression/Lz4FrameDecoder$1.class',
                     'sha256': '409530ec002169729cb62bfafebb673c86e28d378c1e90bd75d8e68ed570c80c', 'terms': [TERMS[0]]},
                    {'class_file': 'io/netty/handler/codec/compression/Lz4FrameDecoder$State.class',
                     'sha256': 'f3237dc9f1d1970b65985bb366b75b5edfeace8ed193bf800be8b073360085cb', 'terms': [TERMS[0]]},
                    {'class_file': CLASS_FILE,
                     'sha256': 'dfda9abab6b4187ae29fdad8b10d2eafdb98bf926e8c6d97a4978441e91daab7', 'terms': [TERMS[0]]}],
                'fixed-boundary Netty decoder class differs')
        require(row['client']['decoder_reference_hits'] == [] and
                all(any(hit['class_file'].startswith(item['path'] + '!') for item in
                        row['server']['bundled_codec_compression'])
                    for hit in row['server']['decoder_reference_hits']),
                'fixed-boundary server reference appears outside its bundled Netty codec')
        bundled = row['server']['bundled_codec_compression']
        require(len(bundled) == 1 and bundled[0]['sha1'] == row['codec']['sha1'] and
                bundled[0]['sha256'] == row['codec']['sha256'] and
                bundled[0]['size_bytes'] == row['codec']['size_bytes'] and
                bundled[0]['decoder_class_sha256'] == row['codec']['decoder_reference_hits'][-1]['sha256'],
                'fixed-boundary server bundle differs from manifest Netty codec')


def source_observation_index():
    rows = []
    for version in sorted(SOURCE_COMMITS, key=lambda value: tuple(int(x) for x in value.split('.')[:3])):
        path = SOURCE_DIR + '/' + version + '.java'
        raw = read(path)
        require(sha256(raw).hexdigest() == SOURCE_SHA256[version], 'Netty upstream source checksum differs: ' + version)
        text = raw.decode('utf-8')
        alloc = 'ctx.alloc().buffer(decompressedLength, decompressedLength)'
        require(alloc in text and 'int decompressedLength = Integer.reverseBytes(in.readInt())' in text,
                'Netty Lz4 allocation source code differs: ' + version)
        fixed = 'private final int maxDecompressedLength' in text
        require(fixed == (version in ('4.1.133.Final', '4.2.13.Final', '4.2.15.Final', '4.2.16.Final')),
                'Netty max-decompressed-length boundary differs: ' + version)
        if fixed:
            require('ObjectUtil.checkInRange(maxDecompressedLength, 0, MAX_BLOCK_SIZE' in text and
                    'this.maxDecompressedLength = maxDecompressedLength == 0 ? MAX_BLOCK_SIZE' in text,
                    'fixed Netty decoder maximum implementation differs: ' + version)
        else:
            require('final int maxDecompressedLength = 1 << compressionLevel' in text,
                    'affected Netty decoder header maximum differs: ' + version)
        rows.append({'coordinate': 'io.netty:' + ('netty-codec-compression' if version.startswith('4.2.') else 'netty-codec') + ':' + version,
            'tag': 'netty-' + version, 'tag_commit': SOURCE_COMMITS[version],
            'source_url': 'https://raw.githubusercontent.com/netty/netty/netty-' + version + '/' + SOURCE_PATHS[version],
            'path': path, 'sha256': SOURCE_SHA256[version], 'configurable_max': fixed,
            'allocation_expression': alloc, 'decompressed_length_source': 'Integer.reverseBytes(in.readInt())'})
    constants = []
    for filename, expected in sorted(CONSTANT_SHA256.items()):
        raw = read(SOURCE_DIR + '/' + filename, expected)
        text = raw.decode('utf-8')
        require('HEADER_LENGTH = 8 +' in text and
                '1 << COMPRESSION_LEVEL_BASE + 0x0F' in text,
                'Netty Lz4 header or maximum block constant differs')
        constants.append({'path': SOURCE_DIR + '/' + filename, 'sha256': expected,
            'header_length_bytes': 21, 'max_block_size_bytes': 33554432})
    poms = []
    for filename, expected in sorted(POM_SHA256.items()):
        raw = read(SOURCE_DIR + '/' + filename, expected)
        content = raw.decode('utf-8')
        match = re.fullmatch(r'netty-(4\.[12]\.\d+\.Final)-(root|module)-pom\.xml', filename)
        require(match is not None, 'fixed Netty POM filename differs')
        version, pom_kind = match.groups()
        if pom_kind == 'module':
            require('<version>' + version + '</version>' in content,
                    'fixed Netty module POM version differs')
            java_source_target = java_release = None
        else:
            require(re.search(r'<maven\.compiler\.source>1\.8</maven\.compiler\.source>', content) and
                    re.search(r'<maven\.compiler\.target>1\.8</maven\.compiler\.target>', content),
                    'fixed Netty root Java source/target differs')
            require('<maven.compiler.release>8</maven.compiler.release>' in content,
                    'fixed Netty root Java release target differs')
            java_source_target = java_release = 8
        poms.append({'path': SOURCE_DIR + '/' + filename, 'sha256': expected,
                     'java_source_target': java_source_target, 'java_release': java_release,
                     'module_pom': pom_kind == 'module'})
    return {'schema': 1, 'source_url': 'https://github.com/netty/netty', 'snapshots': rows,
        'lz4_constants': constants, 'compatibility_poms': poms,
        'mechanism': 'The compressed path trusts a header-declared decompressed length when sizing ByteBuf before LZ4 decompression.',
        'fixed_release_note': '4.1.133.Final and 4.2.13.Final add a configurable per-decoder maximum. The default remains MAX_BLOCK_SIZE (32 MiB); this is not evidence of an application-level per-channel or aggregate limit.',
        'security_clearance': False}


def validate_pipeline_observation(observation, runtime_scan, server_scan):
    require(observation.get('schema') == 1 and observation.get('minecraft_version') == '26.1.2' and
            observation.get('security_clearance') is False and
            observation.get('tool_version') == '21.0.12.1', 'static pipeline observation identity differs')
    client_artifact = next(row for row in runtime_scan['artifacts']
                           if row['coordinates'] == ['minecraft-client:26.1.2'])
    server = next(row for row in server_scan['servers'] if row['minecraft_version'] == '26.1.2')
    server_inner = next(row for row in server['nested_jars']
                        if row['path'] == 'META-INF/versions/26.1.2/server-26.1.2.jar')
    require(observation['client']['jar_sha256'] == client_artifact['sha256'] and
            observation['client']['jar_size_bytes'] == client_artifact['size_bytes'] and
            observation['server_inner']['jar_sha256'] == server_inner['sha256'] and
            observation['server_inner']['jar_size_bytes'] == server_inner['size_bytes'],
            'pipeline disassembly JAR identity differs from exact Minecraft artifacts')
    for context in ('client', 'server_inner'):
        row = observation[context]
        method = row['connection_setup_compression']
        require('new           #695                // class net/minecraft/network/CompressionDecoder' in method and
                'ChannelPipeline.addAfter' in method and 'net.minecraft.network.CompressionDecoder' in
                '\n'.join(row['compression_decoder_disassembly_lines']) and
                any('java.util.zip.Inflater' in line for line in row['compression_decoder_disassembly_lines']) and
                'Lz4FrameDecoder' not in method and
                not any('Lz4FrameDecoder' in line for line in row['compression_decoder_disassembly_lines']) and
                row['class_files'] == PIPELINE_CLASS_HASHES,
                'static Minecraft compression pipeline class evidence differs')
    require(observation['client']['class_files'] == observation['server_inner']['class_files'],
            'client and dedicated-server compression class observations differ')
    require('not an observation' in observation['observations'][-1],
            'pipeline limitation is missing')


def source_reports_and_runtime(baseline, runtime_scan, server_scan, manifests, product):
    target = baseline['target']
    matched = validate_occurrences(target, baseline['reports'])
    runtime_rows = {row['sha1']: row for row in runtime_scan['artifacts']}
    server_rows = {row['minecraft_version']: row for row in server_scan['servers']}
    product_groups = product['groups']
    artifacts = baseline['prior']['runtime_classpath_scan']['all_artifacts']
    occurrences = []
    for row in target['occurrences']:
        source_key = row['source_kind'] + '|' + row['group']
        report, _tool, report_artifact = baseline['reports'][source_key]
        report_raw = (ROOT / audits.LIVE / 'raw' / (str(report_artifact['id']) + '.zip')).read_bytes()
        with ZipFile(BytesIO(report_raw)) as archive:
            member = row['source_report_member']
            source_report_sha256 = sha256(archive.read(member)).hexdigest()
        purl = row['purl']
        coord = coordinate(purl)
        runtime_versions = sorted(scope.split('/', 1)[1] for scope in row['scopes'] if scope.startswith('runtime/'))
        require(runtime_versions, 'Lz4 occurrence has no runtime scopes')
        per_version = []
        for game in runtime_versions:
            manifest = manifests[game]
            report_manifest = report['runtime_manifests'].get(game)
            require(report_manifest is not None and report_manifest['sha1'] ==
                    baseline['prior']['verified_manifest_versions'][game]['sha1'],
                    'Lz4 source report manifest identity differs: ' + game)
            require(purl in report['inventories']['runtime/' + game],
                    'Lz4 source report runtime package is missing: ' + game)
            lib = manifest_artifact(manifest, game, coord)
            prior_client = [item for item in artifacts if item['coordinates'] == ['minecraft-client:' + game]
                            and game in item['minecraft_versions']]
            prior_codec = [item for item in artifacts if coord in item['coordinates'] and
                           game in item['minecraft_versions']]
            require(len(prior_client) == len(prior_codec) == 1 and
                    prior_codec[0]['sha1'] == lib['sha1'] and prior_codec[0]['size_bytes'] == lib['size'],
                    'Lz4 client/codec artifact mapping differs: ' + game)
            client_observation = runtime_rows[prior_client[0]['sha1']]
            codec_observation = runtime_rows[prior_codec[0]['sha1']]
            class_hash = MAIN_CLASS_HASHES[purl]
            require(any(hit['class_file'] == CLASS_FILE and hit['sha256'] == class_hash
                        for hit in codec_observation['decoder_reference_hits']),
                    'Lz4 decoder class digest is missing from affected codec: ' + game)
            server = server_rows[game]
            product_row = product_groups.get(row['group'])
            require(product_row is not None and product_row['source_sha'] == row['source_sha'],
                    'Lz4 product JAR source group differs')
            manifests_meta = baseline['prior']['verified_manifest_versions'][game]
            per_version.append({'minecraft_version': game,
                'manifest': {'sha1': manifests_meta['sha1'], 'sha256': manifests_meta['sha256'],
                             'size_bytes': manifests_meta['size_bytes'], 'url': manifests_meta['url']},
                'minecraft_java_major_version': manifest.get('javaVersion', {}).get('majorVersion'),
                'client': {'sha1': client_observation['sha1'], 'sha256': client_observation['sha256'],
                           'size_bytes': client_observation['size_bytes']},
                'netty_codec': {'purl': purl, 'coordinate': coord, 'url': lib['url'],
                    'sha1': codec_observation['sha1'], 'sha256': codec_observation['sha256'],
                    'size_bytes': codec_observation['size_bytes'],
                    'lz4_frame_decoder_class_sha256': class_hash},
                'dedicated_server': {'sha1': server['server_sha1'], 'sha256': server['server_sha256'],
                    'size_bytes': server['server_size_bytes'],
                    'netty_codec_artifacts': [item for item in server_codec_rows(server)]},
                'product_mod_jar_sha256': product_row['jar_sha256']})
        occurrences.append({
            'source_kind': row['source_kind'], 'group': row['group'], 'source_sha': row['source_sha'],
            'purl': purl, 'package_version': purl.rsplit('@', 1)[1], 'scopes': row['scopes'],
            'fingerprint': row['fingerprint'], 'source_report_artifact_id': row['source_report_artifact_id'],
            'source_report_run': report_artifact['run'], 'source_report_name': report_artifact['name'],
            'source_report_member': row['source_report_member'],
            'source_report_archive_sha256': row['source_report_archive_sha256'],
            'source_report_sha256_uncompressed': source_report_sha256,
            'dependency_owner': row['dependency_owner'], 'disposition': row['disposition'],
            'release_blocking': row['release_blocking'], 'risk_accepted': row['risk_accepted'],
            'minecraft_versions': runtime_versions, 'runtime_artifacts': per_version})
    occurrences.sort(key=lambda item: (item['source_kind'], item['group'], item['purl']))
    require(len(occurrences) == len(matched) == 12, 'Lz4 occurrence evidence is incomplete')
    return occurrences


def make_review(baseline, input_rows):
    advisory, source_index, runtime_scan, server_scan, fabric, product, fixed, pipeline, manifests = input_rows
    advisory_ranges(advisory)
    occurrences = source_reports_and_runtime(baseline, runtime_scan, server_scan,
                                             manifests, product)
    lz4_server = next(row for row in server_scan['servers'] if row['minecraft_version'] == '1.19')
    extra_codec = next(row for row in server_codec_rows(lz4_server)
                       if row['path'].endswith('/4.1.76.Final/netty-codec-4.1.76.Final.jar'))
    focused_versions = sorted({version for row in occurrences for version in row['minecraft_versions']})
    require(focused_versions == sorted(baseline['versions']) and len(focused_versions) == 27,
            'Lz4 runtime version coverage differs')
    source_groups = sorted({(row['source_kind'], row['group']) for row in occurrences})
    evidence_paths = [UPSTREAM, SOURCE_INDEX, RUNTIME_SCAN, SERVER_SCAN, FABRIC_SCAN,
        PRODUCT_SCAN, FIXED_SCAN, PIPELINE_SCAN]
    evidence = {path: sha256(read(path)).hexdigest() for path in evidence_paths}
    manifest_refs = {game: {'path': MANIFEST_DIR + '/' + game + '.json',
        'sha1': sha1(read(MANIFEST_DIR + '/' + game + '.json')).hexdigest(),
        'sha256': sha256(read(MANIFEST_DIR + '/' + game + '.json')).hexdigest()}
        for game in ALL_MANIFEST_VERSIONS}
    fixed_rows = fixed['artifacts']
    return {'schema': 1, 'advisory_id': TARGET, 'aliases': [ALIAS], 'severity': 'HIGH',
        'observed_on': '2026-11-23', 'upstream_advisory': {'path': UPSTREAM,
            'sha256': UPSTREAM_SHA256, 'api_url': 'https://api.github.com/advisories/' + TARGET,
            'web_url': 'https://github.com/advisories/' + TARGET},
        'baseline_priority_register': {'path': trust.CURRENT,
            'sha256': sha256(baseline['v5_raw']).hexdigest(), 'advisory_ids': 24,
            'focused_occurrences': 142, 'remaining_unfocused_high_occurrences': 57,
            'security_clearance': False},
        'evidence': evidence, 'minecraft_manifest_identities': manifest_refs,
        'occurrence_count': len(occurrences), 'source_group_count': len(source_groups),
        'minecraft_version_count': len(focused_versions), 'minecraft_versions': focused_versions,
        'occurrences': occurrences,
        'static_observations': {
            'minecraft_client_and_runtime': {'path': RUNTIME_SCAN, 'artifact_count': 471,
                'class_files_scanned': runtime_scan['class_files_scanned'],
                'decoder_reference_hits': sum(len(row['decoder_reference_hits']) for row in runtime_scan['artifacts']),
                'non_netty_caller_count': 0, 'selected_version_manifests': 27,
                'scope': 'Exact manifest-listed client and runtime libraries; class-literal search only.'},
            'dedicated_server_bundles': {'path': SERVER_SCAN, 'server_artifact_count': 27,
                'nested_jar_count': server_scan['nested_jar_count'],
                'class_files_scanned': server_scan['class_files_scanned'],
                'decoder_reference_hits': sum(len(row['decoder_reference_hits']) for row in server_scan['servers']),
                'non_netty_caller_count': 0,
                'scope': 'Exact official server bundles and every bundled nested JAR scanned; no server launched.'},
            'fabric_loader': {'path': FABRIC_SCAN, 'coordinate': fabric['coordinate'],
                'classes_scanned': fabric['class_files_scanned'] + sum(row['class_files_scanned'] for row in fabric['nested_jars']),
                'decoder_reference_hits': 0},
            'product_mod_jars': {'path': PRODUCT_SCAN, 'jar_count': len(product['groups']),
                'decoder_reference_hits': 0},
            'pipeline_static_disassembly': {'path': PIPELINE_SCAN, 'minecraft_version': '26.1.2',
                'contexts': ['client', 'dedicated-server'],
                'summary': 'Static Connection.setupCompression installs Minecraft CompressionDecoder; that class uses java.util.zip.Inflater. No Netty Lz4FrameDecoder reference is present in those classes.'},
        },
        'upstream_implementation': source_index,
        'upstream_mechanism': 'The affected decoder reads an untrusted decompressedLength from the frame header and allocates ctx.alloc().buffer(decompressedLength, decompressedLength) before invoking the LZ4 decompressor. MAX_BLOCK_SIZE is 32 MiB. Fixed releases add a configurable per-decoder cap; their default remains 32 MiB, and no aggregate or per-channel application limit is established here.',
        'reachability': 'Across the exact selected client/runtime artifact set, the only decoder-name references are the decoder and its two inner classes in the six affected Netty JARs. The same pattern is present in the exact server bundles. No non-Netty literal caller or Lz4FrameDecoder installation was observed in the inspected Minecraft client/server or Fabric Loader bytecode. This bounded static search does not rule out reflective, generated, agent, or third-party mod paths.',
        'input_boundary': 'The advisory requires the affected decoder to process untrusted LZ4 frames. The statically inspected Minecraft 26.1.2 client/server setup path uses Minecraft CompressionDecoder backed by java.util.zip.Inflater. No Lz4FrameDecoder path was observed, but no running channel or arbitrary modpack was inspected.',
        'server_occurrence_difference': {'scope': 'Additional artifact observation outside the indexed 12 source-audit occurrences; not added to or counted in that exact occurrence set.',
            'minecraft_version': '1.19', 'server_sha1': lz4_server['server_sha1'],
            'server_sha256': lz4_server['server_sha256'], 'netty_codec_artifact': extra_codec,
            'package_version': '4.1.76.Final',
            'assessment': 'Affected by the same upstream range. Reconcile the server/client dependency discrepancy with the dependency owner.'},
        'upstream_game_update': {'observations': fixed_rows,
            'assessment': 'The 26.2 and 26.3 Mojang version manifests and dedicated-server bundles select Netty 4.2.15.Final and 4.2.16.Final respectively, both beyond the advisory fixed boundary. These updates do not clear older supported Minecraft lines and do not prove a launcher selected a live classpath.'},
        'java_compatibility': {'netty_fixed_release_compiler_target': 8,
            'minecraft_runtime_major_versions': sorted({row['java_major_version'] for row in server_scan['servers']}),
            'fixed_game_line_major_versions': sorted({row['java_major_version'] for row in fixed_rows}),
            'assessment': 'Upstream Netty fixed modules compile for Java 8, below the Java 17, 21, and 25 requirements in retained Minecraft manifests. Java bytecode level alone does not establish Minecraft, Fabric, module-family, or ABI compatibility; no override was tested.'},
        'remediation': 'Netty publishes 4.1.133.Final and 4.2.13.Final as Lz4 fixed boundaries. The separate Critical Netty SNI finding requires 4.1.135.Final or 4.2.15.Final, so an Lz4-only override would not resolve that blocker. Minecraft 26.2/26.3 now ship 4.2.15/4.2.16, but older game lines remain on affected versions. No Minecraft-managed dependency override was made.',
        'scope_separation': 'This is Netty Lz4FrameDecoder / CVE-2026-42583. It is separate from Netty Bzip2Decoder / CVE-2026-59901, LZ4 Java LZ4BlockInputStream findings, Netty SNI, and Netty Trust Manager findings.',
        'limitations': ['No Minecraft client, server, Fabric runtime, launcher, or modpack was started.',
            'No untrusted frame, PoC, remote target, or resource-exhaustion behavior was exercised.',
            'Static literal search does not exclude reflective, generated, agent, native, or uninspected third-party mod paths.',
            'No per-channel or aggregate memory-control behavior was measured.',
            'Compatibility of fixed Netty modules with affected Minecraft/Fabric versions was not tested.',
            'The 1.19 server bundle 4.1.76.Final observation is outside the indexed 12 occurrence set and remains to be reconciled.'],
        'reviewer': 'Codex automated source-bound static investigation; human security review pending',
        'responsible_owner': 'Project maintainer and upstream Minecraft/Netty owners',
        'review_date': '2026-11-23', 'disposition': 'Further investigation', 'release_blocking': True,
        'risk_accepted': False, 'security_clearance': False,
        'follow_up_requirements': [
            'Reconcile the additional 1.19 dedicated-server Netty 4.1.76.Final observation with source audit scope.',
            'Observe actual supported client, Fabric, and dedicated-server classpaths and pipelines separately.',
            'Check per-channel and aggregate limits if any supported pipeline installs Lz4FrameDecoder.',
            'Ask Minecraft/Fabric owners for compatible updates across affected game lines, including the Critical SNI fix.',
            'Keep all 12 indexed occurrences release-blocking until the source-bound review and owner decision are complete.']}


def make_register(v5, review, review_raw):
    current = copy.deepcopy(v5)
    target = next(row for row in current['advisories'] if row['advisory_id'] == TARGET)
    require(target['focused_evidence'] is None and len(target['occurrences']) == review['occurrence_count'] == 12,
            'Lz4 priority baseline differs')
    target.update(focused_evidence=REVIEW, reviewer=review['reviewer'], review_date=review['review_date'],
        responsible_owner=review['responsible_owner'], follow_up=review['follow_up_requirements'])
    current['lz4_focused_evidence'] = {'path': REVIEW, 'sha256': sha256(review_raw).hexdigest(),
        'new_advisory_ids': 1, 'new_high_occurrences': 12}
    current['review_status'] = 'Adds bounded Lz4FrameDecoder static observations; all findings remain blocking and risk is not accepted.'
    focused = [row for row in current['advisories'] if row.get('focused_evidence')]
    critical = sum(len(row['occurrences']) for row in focused if row['severity'] == 'CRITICAL')
    high = sum(len(row['occurrences']) for row in focused if row['severity'] == 'HIGH')
    total_high = sum(len(row['occurrences']) for row in current['advisories'] if row['severity'] == 'HIGH')
    current['focused_coverage'] = {'advisory_ids': len(focused), 'critical_occurrences': critical,
        'high_occurrences': high, 'total_occurrences': critical + high,
        'high_occurrences_without_focused_evidence': total_high - high}
    require(current['focused_coverage'] == {'advisory_ids': 25, 'critical_occurrences': 22,
        'high_occurrences': 132, 'total_occurrences': 154,
        'high_occurrences_without_focused_evidence': 45}, 'Lz4 focused coverage differs')
    require(len(current['advisories']) == 37 and sum(len(row['occurrences']) for row in current['advisories']) == 199,
            'Critical/High priority inventory total differs')
    require(all(row['release_blocking'] and not row['risk_accepted']
                for advisory in current['advisories'] for row in advisory['occurrences']),
            'Lz4 focus changed a blocking or acceptance state')
    return current


def load_evidence(baseline):
    advisory_raw = read(UPSTREAM, UPSTREAM_SHA256)
    advisory = json.loads(advisory_raw, object_pairs_hook=unique_object)
    advisory_ranges(advisory)
    source_index = source_observation_index()
    saved_index_raw = read(SOURCE_INDEX)
    require(json.loads(saved_index_raw, object_pairs_hook=unique_object) == source_index,
            'Netty source observation index differs')
    manifests = {game: validate_manifest(game, read(MANIFEST_DIR + '/' + game + '.json'), baseline['prior'])
                 for game in ALL_MANIFEST_VERSIONS}
    runtime_scan = read_json(RUNTIME_SCAN)
    validate_runtime_scan(runtime_scan, baseline['prior'], baseline['versions'], manifests)
    server_scan = read_json(SERVER_SCAN)
    validate_server_scan(server_scan, baseline['prior'], baseline['versions'], manifests)
    fabric = read_json(FABRIC_SCAN)
    validate_fabric_scan(fabric)
    product = read_json(PRODUCT_SCAN)
    validate_product_scan(product)
    fixed = read_json(FIXED_SCAN)
    validate_fixed_scan(fixed, baseline, baseline['reports'], manifests)
    pipeline = read_json(PIPELINE_SCAN)
    validate_pipeline_observation(pipeline, runtime_scan, server_scan)
    return (advisory, source_index, runtime_scan, server_scan, fabric, product, fixed, pipeline, manifests)


def validate_current():
    baseline = baseline_context()
    inputs = load_evidence(baseline)
    review = make_review(baseline, inputs)
    review_raw = read(REVIEW)
    require(json.loads(review_raw, object_pairs_hook=unique_object) == review,
            'Lz4 source-bound review differs')
    register = make_register(baseline['v5'], review, review_raw)
    register_raw = read(CURRENT)
    require(json.loads(register_raw, object_pairs_hook=unique_object) == register,
            'Lz4 priority register differs')
    latest = {'path': CURRENT, 'sha256': sha256(register_raw).hexdigest(), 'advisory_ids': 25,
        'focused_occurrences': 154, 'remaining_unfocused_high_occurrences': 45, 'security_clearance': False}
    require(baseline['ledger']['latest_focused_priority_register'] == latest and
            baseline['ledger'].get('lz4_high_focused_priority_register') == latest,
            'Lz4 priority ledger pointer differs')
    return baseline, review, register


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-cache', type=Path)
    parser.add_argument('--server-cache', type=Path)
    parser.add_argument('--manifest-cache', type=Path)
    parser.add_argument('--fabric-jar', type=Path)
    parser.add_argument('--fixed-cache', type=Path)
    parser.add_argument('--write-inputs', action='store_true',
        help='scan locally supplied, hash-verified caches and write previously absent evidence inputs')
    parser.add_argument('--write-review', action='store_true',
        help='write the source-bound review and derived priority register from retained evidence inputs')
    parser.add_argument('--verify-cache', action='store_true',
        help='re-scan all source-bound runtime, server, Fabric, and fixed-boundary artifacts from local caches')
    args = parser.parse_args()
    supplied = (args.runtime_cache, args.server_cache, args.manifest_cache, args.fabric_jar, args.fixed_cache)
    try:
        require(sum((args.write_inputs, args.write_review, args.verify_cache)) <= 1,
                '--write-inputs, --write-review, and --verify-cache are mutually exclusive')
        require(args.write_inputs or args.verify_cache or not any(value is not None for value in supplied),
                'cache inputs are only consumed with --write-inputs or --verify-cache')
        require(not (args.write_inputs or args.verify_cache) or all(value is not None for value in supplied),
                '--write-inputs and --verify-cache require --runtime-cache, --server-cache, --manifest-cache, --fabric-jar, and --fixed-cache')
        if args.write_inputs:
            baseline = baseline_context()
            manifests = {game: validate_manifest(game, manifest_bytes(game, args.manifest_cache), baseline['prior'])
                         for game in ALL_MANIFEST_VERSIONS}
            runtime_scan = build_runtime_scan(baseline['prior'], baseline['versions'], manifests, args.runtime_cache)
            server_scan = build_server_scan(baseline['prior'], baseline['versions'], manifests, args.server_cache)
            fabric = build_fabric_scan(args.fabric_jar.read_bytes())
            product = product_scan()
            fixed = build_fixed_scan(manifests, args.fixed_cache, baseline)
            client = next(row for row in ipfilter.selected_artifacts(baseline['prior'], baseline['versions'])
                          if row['coordinates'] == ['minecraft-client:26.1.2'])
            client_raw = cache_bytes(args.runtime_cache, client['cache_object'], client['size_bytes'],
                                     client['sha1'], client['sha256'])
            server_meta = manifests['26.1.2']['downloads']['server']
            server_raw = cache_bytes(args.server_cache, '26.1.2.jar', server_meta['size'], server_meta['sha1'],
                                     _sha256_from_server_scan_cache(args.server_cache, '26.1.2', server_meta))
            pipeline = build_pipeline_observation(client_raw, server_raw)
            source_index = source_observation_index()
            for path, value in ((RUNTIME_SCAN, runtime_scan), (SERVER_SCAN, server_scan),
                                (FABRIC_SCAN, fabric), (PRODUCT_SCAN, product), (FIXED_SCAN, fixed),
                                (PIPELINE_SCAN, pipeline), (SOURCE_INDEX, source_index)):
                write_new(path, value)
            print('Wrote seven source-bound static input files from hash-verified local caches; no process was launched')
            return 0
        if args.write_review:
            baseline = baseline_context()
            inputs = load_evidence(baseline)
            review = make_review(baseline, inputs)
            write_new(REVIEW, review)
            review_raw = read(REVIEW)
            write_new(CURRENT, make_register(baseline['v5'], review, review_raw))
            print('Wrote source-bound review for 12 blocking Lz4 occurrences and priority register v6')
            return 0
        if args.verify_cache:
            require(all(value is not None for value in supplied),
                    '--verify-cache requires --runtime-cache, --server-cache, --manifest-cache, --fabric-jar, and --fixed-cache')
        baseline, review, register = validate_current()
        if args.verify_cache:
            manifests = {game: validate_manifest(game, manifest_bytes(game, args.manifest_cache), baseline['prior'])
                         for game in ALL_MANIFEST_VERSIONS}
            saved_runtime = read_json(RUNTIME_SCAN)
            saved_server = read_json(SERVER_SCAN)
            saved_fabric = read_json(FABRIC_SCAN)
            saved_product = read_json(PRODUCT_SCAN)
            saved_fixed = read_json(FIXED_SCAN)
            saved_pipeline = read_json(PIPELINE_SCAN)
            scan_runtime = build_runtime_scan(baseline['prior'], baseline['versions'], manifests, args.runtime_cache)
            scan_server = build_server_scan(baseline['prior'], baseline['versions'], manifests, args.server_cache)
            fabric = build_fabric_scan(args.fabric_jar.read_bytes())
            fixed = build_fixed_scan(manifests, args.fixed_cache, baseline)
            client = next(row for row in ipfilter.selected_artifacts(baseline['prior'], baseline['versions'])
                          if row['coordinates'] == ['minecraft-client:26.1.2'])
            client_raw = cache_bytes(args.runtime_cache, client['cache_object'], client['size_bytes'],
                                     client['sha1'], client['sha256'])
            server_meta = manifests['26.1.2']['downloads']['server']
            server_raw = cache_bytes(args.server_cache, '26.1.2.jar', server_meta['size'], server_meta['sha1'],
                                     _sha256_from_server_scan_cache(args.server_cache, '26.1.2', server_meta))
            pipeline = build_pipeline_observation(client_raw, server_raw)
            require(scan_runtime == saved_runtime and scan_server == saved_server and fabric == saved_fabric and
                    product_scan() == saved_product and fixed == saved_fixed and pipeline == saved_pipeline,
                    'cached Lz4 reinspection differs from retained static evidence')
        print('Validated 12 blocking Lz4 occurrences, 471 client/runtime artifacts, 27 dedicated-server bundles, and static source evidence; no security clearance')
        print('Priority coverage: 25 focused advisory IDs, 154 focused Critical/High occurrences, 45 unfocused High occurrences')
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, BadZipFile) as exc:
        print('Lz4 investigation incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
