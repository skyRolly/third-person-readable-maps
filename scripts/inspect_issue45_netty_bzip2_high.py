#!/usr/bin/env python3
"""Check bounded source-bound observations for Netty's High Bzip2 advisory.

This inspects artifact bytes and selected vanilla class references only. It does
not exercise the vulnerable behavior or establish game-wide non-reachability.
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
import inspect_issue45_netty_ipfilter_high as ipfilter
import inspect_issue45_sni_high as sni
from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
DIR = 'docs/dependency-evidence/issue45-netty-bzip2-high-2026-11-22'
UPSTREAM = DIR + '/upstream-advisory.json'
UPSTREAM_SHA = '8678d3ce1f792642a618b917250ea69fe83d4d4451e69fa4cd5cee369ddd0126'
CLIENTS = DIR + '/minecraft-client-scan.json'
CODECS = DIR + '/codec-artifacts.json'
FABRIC = DIR + '/fabric-loader-static-scan.json'
PRODUCT = DIR + '/product-jar-static-scan.json'
PIPELINE = DIR + '/minecraft-26.2-pipeline-observation.json'
REVIEW = DIR + '/source-bound-review.json'
CURRENT = DIR + '/priority-register-v4.json'
TARGET = 'GHSA-558v-64gr-wgg4'
TERMS = ('Bzip2', 'BZip2', 'BZIP2')
DECODER = 'io/netty/handler/codec/compression/Bzip2Decoder.class'
MC_DECODER = 'net/minecraft/network/CompressionDecoder.class'
MC_CONNECTION = 'net/minecraft/network/Connection.class'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path, expected=None):
    return json.loads(sni.read(ROOT, path, expected), object_pairs_hook=unique_object)


def source_key(row, version):
    return row['source_kind'], row['group'], row['source_sha'], version


def coordinate(purl):
    match = re.fullmatch(r'pkg:maven/io\.netty/(netty-codec(?:-compression)?)@(4\.[12]\.\d+\.Final)', purl)
    require(match is not None, 'unsupported Bzip2 package identity')
    name, version = match.groups()
    require((name == 'netty-codec' and version.startswith('4.1.')) or
            (name == 'netty-codec-compression' and version.startswith('4.2.')),
            'Bzip2 module and version differ')
    limit = 135 if version.startswith('4.1.') else 15
    require(int(version.split('.')[2]) <= limit, 'Bzip2 package is outside the affected range')
    return 'io.netty:' + name + ':' + version


def context():
    ledger, v2, iptarget, previous, catalog, versions, prior = ipfilter.context()
    old_records = {p: sni.read(ROOT, p) for p in (ipfilter.KNOWN, ipfilter.SCAN, ipfilter.FABRIC, ipfilter.PRODUCT)}
    known, scan, fabric, product = (json.loads(old_records[p], object_pairs_hook=unique_object)
                                    for p in (ipfilter.KNOWN, ipfilter.SCAN, ipfilter.FABRIC, ipfilter.PRODUCT))
    ipfilter.validate_inputs(ledger, prior, versions, catalog, known, scan, fabric, product)
    ip_review = ipfilter.make_review(ledger, iptarget, previous, catalog, versions, old_records)
    ip_review_raw = sni.read(ROOT, ipfilter.REVIEW)
    require(json.loads(ip_review_raw, object_pairs_hook=unique_object) == ip_review,
            'historical IP-filter review differs')
    reference = ledger['ipfilter_high_focused_priority_register']
    v3_raw = sni.read(ROOT, ipfilter.CURRENT, reference['sha256'])
    require(reference == {'path': ipfilter.CURRENT, 'sha256': sha(v3_raw), 'advisory_ids': 22,
        'focused_occurrences': 117, 'remaining_unfocused_high_occurrences': 82, 'security_clearance': False},
        'historical IP-filter ledger reference differs')
    v3 = json.loads(v3_raw, object_pairs_hook=unique_object)
    require(v3 == ipfilter.make_register(v2, ip_review, ip_review_raw), 'historical IP-filter register differs')
    target = next(row for row in v3['advisories'] if row['advisory_id'] == TARGET)
    require(target['severity'] == 'HIGH' and target['aliases'] == ['CVE-2026-59901'] and
            target['focused_evidence'] is None and len(target['occurrences']) == 13,
            'unexpected Bzip2 priority baseline')
    expected_ranges = {'pkg:maven/io.netty/netty-codec': {('0', '4.1.136.Final')},
                       'pkg:maven/io.netty/netty-codec-compression': {('4.2.0.Final', '4.2.16.Final')}}
    actual_ranges = {pkg: {(r['events'][0]['introduced'], r['events'][1]['fixed'])
                    for group in ranges for r in group if r.get('type') == 'ECOSYSTEM'}
                    for pkg, ranges in target['affected_ranges'].items()}
    require(actual_ranges == expected_ranges, 'Bzip2 OSV ranges differ')
    upstream = read_json(UPSTREAM, UPSTREAM_SHA)
    require(upstream['ghsa_id'] == TARGET and upstream['cve_id'] == 'CVE-2026-59901' and
            upstream['severity'] == 'high' and upstream['withdrawn_at'] is None and
            {(x['package'], x['range'], x['patched']) for x in upstream['vulnerabilities']} == {
                ('io.netty:netty-codec', '< 4.1.136.Final', '4.1.136.Final'),
                ('io.netty:netty-codec-compression', '>=4.2.0.Final, < 4.2.16.Final', '4.2.16.Final')},
            'Bzip2 upstream advisory ranges differ')
    _, _, critical, _, mod = sni.load_inputs()
    reviewed, games = bind_target(target, critical, prior, mod)
    return ledger, v3, target, reviewed, games, prior, mod


def bind_target(target, critical, prior, mod):
    """Bind every retained occurrence to exact prior source and runtime artifacts."""
    reviewed = {source_key(row, row['package_version']): row for row in critical['occurrences']}
    require(len(reviewed) == len(critical['occurrences']), 'duplicate prior source occurrence')
    artifacts = prior['runtime_classpath_scan']['all_artifacts']
    occurrence_keys, games = set(), {}
    for row in target['occurrences']:
        version = row['purl'].rsplit('@', 1)[1]
        key = source_key(row, version)
        require(key not in occurrence_keys and key in reviewed and row['release_blocking'] is True and
                row['risk_accepted'] is False and row['disposition'] == 'Further investigation',
                'Bzip2 source identity or blocking state differs')
        occurrence_keys.add(key)
        prior_row = reviewed[key]
        runtime = sorted(x.split('/', 1)[1] for x in row['scopes'] if x.startswith('runtime/'))
        require(runtime and runtime == sorted(prior_row['minecraft_versions']), 'Bzip2 runtime scope differs')
        clients = {x['minecraft_version']: x for x in prior_row['minecraft_artifacts']}
        require(set(clients) == set(runtime), 'Bzip2 client coverage differs')
        require(mod['groups'][row['group']]['source_sha'] == row['source_sha'], 'Bzip2 product source differs')
        coord = coordinate(row['purl'])
        for game in runtime:
            manifest = prior['verified_manifest_versions'][game]
            client = [x for x in artifacts if 'minecraft-client:' + game in x['coordinates'] and game in x['minecraft_versions']]
            codec = [x for x in artifacts if coord in x['coordinates'] and game in x['minecraft_versions']]
            require(len(client) == len(codec) == 1 and clients[game]['version_metadata_sha1'] == manifest['sha1'] and
                    clients[game]['client_sha1'] == client[0]['sha1'] and clients[game]['client_sha256'] == client[0]['sha256'],
                    'Bzip2 Minecraft artifact provenance differs: ' + game)
            model = {'minecraft_version': game, 'manifest': manifest, 'client': client[0], 'codec': codec[0],
                     'purl': row['purl'], 'coordinate': coord}
            require(game not in games or games[game] == model, 'inconsistent Bzip2 game artifact')
            games[game] = model
    require(len(occurrence_keys) == 13 and len(games) == 28 and
            len({(r['source_kind'], r['group']) for r in target['occurrences']}) == 10,
            'incomplete Bzip2 occurrence coverage')
    return reviewed, games


def scan_classes(raw):
    with ZipFile(BytesIO(raw)) as jar:
        names = jar.namelist()
        require(len(names) == len(set(names)), 'duplicate inspected JAR member')
        hits, count = [], 0
        for name in sorted(n for n in names if n.endswith('.class')):
            content = jar.read(name)
            count += 1
            found = [term for term in TERMS if term.encode() in content]
            if found:
                hits.append({'class_file': name, 'sha256': sha(content), 'terms': found})
        return count, hits


def cache_bytes(cache, artifact):
    path = (cache / artifact['cache_object']).resolve()
    require(path.is_relative_to(cache.resolve()), 'artifact cache path escapes root')
    raw = path.read_bytes()
    require(len(raw) == artifact['size_bytes'] and hashlib.sha1(raw).hexdigest() == artifact['sha1'] and
            sha(raw) == artifact['sha256'], 'cached Bzip2 artifact checksum differs')
    return raw


def inspect_client(game, model, runtime_cache, manifest_cache):
    manifest_path = (manifest_cache / (game + '.json')).resolve()
    require(manifest_path.is_relative_to(manifest_cache.resolve()), 'manifest cache path escapes root')
    raw_manifest = manifest_path.read_bytes()
    metadata = model['manifest']
    require(len(raw_manifest) == metadata['size_bytes'] and hashlib.sha1(raw_manifest).hexdigest() == metadata['sha1'] and
            sha(raw_manifest) == metadata['sha256'], 'Minecraft version metadata checksum differs: ' + game)
    manifest = json.loads(raw_manifest, object_pairs_hook=unique_object)
    libs = [x['downloads']['artifact'] for x in manifest['libraries']
            if x.get('name') == model['coordinate'] and 'artifact' in x.get('downloads', {})]
    codec = model['codec']
    require(len(libs) == 1 and libs[0]['sha1'] == codec['sha1'] and libs[0]['size'] == codec['size_bytes'],
            'Minecraft codec manifest entry differs: ' + game)
    client = model['client']
    require(manifest['downloads']['client']['sha1'] == client['sha1'] and
            manifest['downloads']['client']['size'] == client['size_bytes'], 'Minecraft client manifest differs: ' + game)
    raw = cache_bytes(runtime_cache, client)
    count, hits = scan_classes(raw)
    require(count == client['class_files_scanned'], 'Minecraft client class count differs')
    return {'minecraft_version': game, 'manifest_sha1': metadata['sha1'], 'manifest_sha256': metadata['sha256'],
            'manifest_url': metadata['url'], 'client_sha1': client['sha1'], 'client_sha256': client['sha256'],
            'client_size_bytes': client['size_bytes'], 'client_url': manifest['downloads']['client']['url'],
            'codec_purl': model['purl'], 'codec_url': libs[0]['url'],
            'codec_sha1': codec['sha1'], 'codec_sha256': codec['sha256'], 'codec_size_bytes': codec['size_bytes'],
            'class_files_scanned': count, 'literal_hits': hits}


def inspect_codec(raw, artifact, purl, url):
    require(len(raw) == artifact['size_bytes'] and hashlib.sha1(raw).hexdigest() == artifact['sha1'] and
            sha(raw) == artifact['sha256'], 'Bzip2 codec JAR checksum differs')
    with ZipFile(BytesIO(raw)) as jar:
        names = jar.namelist()
        require(len(names) == len(set(names)), 'duplicate codec JAR member')
        data = jar.read(DECODER)
    return {'purl': purl, 'url': url, 'sha1': artifact['sha1'], 'sha256': artifact['sha256'],
            'size_bytes': len(raw), 'class_file': DECODER, 'class_sha256': sha(data), 'class_size_bytes': len(data)}


def inspect_fabric(raw):
    require(hashlib.sha1(raw).hexdigest() == ipfilter.FABRIC_SHA1 and sha(raw) == ipfilter.FABRIC_SHA256 and
            len(raw) == 1988880, 'Fabric loader checksum differs')
    count, hits = scan_classes(raw)
    nested = []
    with ZipFile(BytesIO(raw)) as jar:
        for name in sorted(n for n in jar.namelist() if n.lower().endswith('.jar')):
            child = jar.read(name)
            child_count, child_hits = scan_classes(child)
            with ZipFile(BytesIO(child)) as inner:
                require(not any(n.lower().endswith('.jar') for n in inner.namelist()), 'uninspected nested Fabric JAR')
            nested.append({'path': name, 'sha256': sha(child), 'class_files_scanned': child_count, 'literal_hits': child_hits})
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


def inspect_pipeline(raw_client, javap):
    with ZipFile(BytesIO(raw_client)) as jar:
        connection, decoder = jar.read(MC_CONNECTION), jar.read(MC_DECODER)
    require(b'setupCompression' in connection and b'net/minecraft/network/CompressionDecoder' in connection and
            b'addAfter' in connection and b'java/util/zip/Inflater' in decoder and
            b'io/netty/handler/codec/ByteToMessageDecoder' in decoder,
            'Minecraft 26.2 compression class references differ')
    # The source artifact is read by javap only; no Minecraft code is executed.
    env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG') if key in os.environ}
    with tempfile.TemporaryDirectory(prefix='issue45-bzip2-javap-') as directory:
        jar_path = Path(directory) / 'client.jar'
        jar_path.write_bytes(raw_client)
        def disassemble(name):
            return subprocess.run([str(javap), '-c', '-p', '-classpath', str(jar_path), name],
                                  check=True, capture_output=True, text=True, env=env, timeout=60).stdout
        conn_text = disassemble('net.minecraft.network.Connection')
        decoder_text = disassemble('net.minecraft.network.CompressionDecoder')
    lines = conn_text.splitlines()
    begin = next(i for i, line in enumerate(lines) if 'setupCompression(int, boolean)' in line)
    end = next((i for i in range(begin + 1, len(lines))
                if re.match(r'^  (public|private|protected) .*\);$', lines[i])), len(lines))
    method = '\n'.join(lines[begin:end]) + '\n'
    require('class net/minecraft/network/CompressionDecoder' in method and 'ChannelPipeline.addAfter' in method and
            'extends io.netty.handler.codec.ByteToMessageDecoder' in decoder_text and
            'java/util/zip/Inflater' in decoder_text, 'Minecraft 26.2 pipeline disassembly differs')
    return {'schema': 1, 'minecraft_version': '26.2', 'connection_class': MC_CONNECTION,
            'connection_sha256': sha(connection), 'decoder_class': MC_DECODER, 'decoder_sha256': sha(decoder),
            'connection_method': 'setupCompression(int, boolean)', 'connection_disassembly': method,
            'decoder_inflater_lines': [line.strip() for line in decoder_text.splitlines()
                                       if 'java/util/zip/Inflater' in line or
                                       'extends io.netty.handler.codec.ByteToMessageDecoder' in line],
            'scope': 'Static class disassembly only; no launcher or game process was observed.',
            'security_clearance': False}


def validate_inputs(games, clients, codecs, fabric, product, pipeline):
    rows = {row['minecraft_version']: row for row in clients['games']}
    require(clients.get('schema') == 1 and clients.get('terms') == list(TERMS) and
            clients.get('security_clearance') is False and len(rows) == len(clients['games']) == 28 and
            set(rows) == set(games), 'Bzip2 client coverage differs')
    by_purl = {}
    for game, model in games.items():
        row = rows[game]
        require(row['manifest_sha1'] == model['manifest']['sha1'] and row['manifest_sha256'] == model['manifest']['sha256'] and
                row['manifest_url'] == model['manifest']['url'] and row['client_sha1'] == model['client']['sha1'] and
                row['client_sha256'] == model['client']['sha256'] and row['client_size_bytes'] == model['client']['size_bytes'] and
                row['client_url'] == 'https://piston-data.mojang.com/v1/objects/' + model['client']['sha1'] + '/client.jar' and
                row['codec_purl'] == model['purl'] and row['codec_sha1'] == model['codec']['sha1'] and
                row['codec_sha256'] == model['codec']['sha256'] and row['codec_size_bytes'] == model['codec']['size_bytes'] and
                row['class_files_scanned'] == model['client']['class_files_scanned'] and row['literal_hits'] == [],
                'Bzip2 client artifact or literal observations differ: ' + game)
        coord = coordinate(model['purl']).split(':')
        expected_url = ('https://libraries.minecraft.net/io/netty/' + coord[1] + '/' + coord[2] + '/' + coord[1] + '-' + coord[2] + '.jar')
        require(row['codec_url'] == expected_url, 'Bzip2 codec source URL differs')
        spec = {'purl': model['purl'], 'url': expected_url, 'sha1': model['codec']['sha1'],
                'sha256': model['codec']['sha256'], 'size_bytes': model['codec']['size_bytes']}
        require(model['purl'] not in by_purl or by_purl[model['purl']] == spec, 'inconsistent Bzip2 codec artifact')
        by_purl[model['purl']] = spec
    require(clients['class_files_scanned'] == sum(row['class_files_scanned'] for row in rows.values()) == 242984,
            'Bzip2 client class total differs')
    libraries = {row['purl']: row for row in codecs['libraries']}
    require(codecs.get('schema') == 1 and codecs.get('security_clearance') is False and
            len(libraries) == len(codecs['libraries']) == 7 and set(libraries) == set(by_purl),
            'Bzip2 codec coverage differs')
    for purl, spec in by_purl.items():
        item = libraries[purl]
        require(all(item[k] == value for k, value in spec.items()) and item['class_file'] == DECODER and
                re.fullmatch(r'[a-f0-9]{64}', item['class_sha256']) and item['class_size_bytes'] > 0,
                'Bzip2 codec class identity differs')
    require(fabric.get('schema') == 1 and fabric.get('coordinate') == 'net.fabricmc:fabric-loader:0.20.1' and
            fabric.get('source_url') == ipfilter.FABRIC_URL and fabric.get('sha1') == ipfilter.FABRIC_SHA1 and
            fabric.get('sha256') == ipfilter.FABRIC_SHA256 and fabric.get('size_bytes') == 1988880 and
            fabric.get('class_files_scanned') == 771 and fabric.get('literal_hits') == [] and
            fabric.get('security_clearance') is False and fabric.get('nested_jars') == [{
                'path': 'META-INF/jars/mixinextras-fabric-0.5.5.jar',
                'sha256': '5da883dc4bfb16e4ceca3f16d8c4ad937bdfb1ce337ed5ba15472d4d81dd6242',
                'class_files_scanned': 506, 'literal_hits': []}], 'Bzip2 Fabric observations differ')
    require(product == product_scan() and len(product['groups']) == 13 and
            all(not row['nested_jar_entries'] and all(not cls['matches'] for cls in row['classes'])
                for row in product['groups'].values()), 'Bzip2 product JAR observations differ')
    require(pipeline.get('schema') == 1 and pipeline.get('minecraft_version') == '26.2' and
            pipeline.get('connection_class') == MC_CONNECTION and pipeline.get('decoder_class') == MC_DECODER and
            re.fullmatch(r'[a-f0-9]{64}', pipeline['connection_sha256']) and
            re.fullmatch(r'[a-f0-9]{64}', pipeline['decoder_sha256']) and
            pipeline.get('connection_method') == 'setupCompression(int, boolean)' and
            'class net/minecraft/network/CompressionDecoder' in pipeline['connection_disassembly'] and
            'ChannelPipeline.addAfter' in pipeline['connection_disassembly'] and
            any('java/util/zip/Inflater' in line for line in pipeline['decoder_inflater_lines']) and
            any('ByteToMessageDecoder' in line for line in pipeline['decoder_inflater_lines']) and
            pipeline.get('security_clearance') is False, 'Minecraft 26.2 compression observation differs')


def verify_codec_downloads(codecs):
    for item in codecs['libraries']:
        raw = ipfilter.download_mojang_library(item['url'], item['size_bytes'])
        artifact = {'sha1': item['sha1'], 'sha256': item['sha256'], 'size_bytes': item['size_bytes']}
        require(inspect_codec(raw, artifact, item['purl'], item['url']) == item,
                'downloaded Bzip2 codec class differs')


def verify_client_bytes(raw, row, pipeline):
    require(len(raw) == row['client_size_bytes'] and hashlib.sha1(raw).hexdigest() == row['client_sha1'] and
            sha(raw) == row['client_sha256'], 'downloaded Minecraft client checksum differs')
    count, hits = scan_classes(raw)
    require(count == row['class_files_scanned'] and hits == row['literal_hits'], 'downloaded Minecraft client scan differs')
    with ZipFile(BytesIO(raw)) as jar:
        connection, decoder = jar.read(MC_CONNECTION), jar.read(MC_DECODER)
    require(sha(connection) == pipeline['connection_sha256'] and sha(decoder) == pipeline['decoder_sha256'] and
            b'setupCompression' in connection and b'net/minecraft/network/CompressionDecoder' in connection and
            b'addAfter' in connection and b'java/util/zip/Inflater' in decoder and
            b'io/netty/handler/codec/ByteToMessageDecoder' in decoder,
            'downloaded Minecraft compression classes differ')


def verify_client_download(clients, pipeline, javap):
    require(javap, 'javap is required to verify the downloaded Minecraft pipeline')
    row = next(item for item in clients['games'] if item['minecraft_version'] == '26.2')
    url = 'https://piston-data.mojang.com/v1/objects/' + row['client_sha1'] + '/client.jar'
    require(row['client_url'] == url and 0 < row['client_size_bytes'] <= 64 * 1024 * 1024,
            'Minecraft client source URL or size differs')
    request = Request(url, headers={'User-Agent': 'issue45-bzip2-artifact-verifier'})
    with build_opener(ipfilter.NoRedirect()).open(request, timeout=60) as response:
        require(response.geturl() == url, 'unexpected Minecraft client redirect')
        raw = response.read(row['client_size_bytes'] + 1)
    verify_client_bytes(raw, row, pipeline)
    require(inspect_pipeline(raw, javap) == pipeline, 'downloaded Minecraft pipeline disassembly differs')


def verify_runtime_cache(args, games, clients, codecs, fabric, pipeline):
    require(args.runtime_cache and args.manifest_cache and args.fabric_jar and args.javap,
            'runtime, manifest, Fabric and javap inputs are required')
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda game: inspect_client(game, games[game], args.runtime_cache, args.manifest_cache),
                             sorted(games)))
    require(rows == clients['games'], 'cached Minecraft client observations differ')
    for item in codecs['libraries']:
        game = next(game for game in games if games[game]['purl'] == item['purl'])
        model = games[game]
        require(inspect_codec(cache_bytes(args.runtime_cache, model['codec']), model['codec'], item['purl'], item['url']) == item,
                'cached Bzip2 codec observation differs')
    require(inspect_fabric(args.fabric_jar.read_bytes()) == fabric, 'cached Fabric observation differs')
    require(inspect_pipeline(cache_bytes(args.runtime_cache, games['26.2']['client']), args.javap) == pipeline,
            'cached Minecraft pipeline observation differs')


def make_review(ledger, target, reviewed, games, codecs, records, mod):
    by_purl = {row['purl']: row for row in codecs['libraries']}
    occurrences = []
    for row in target['occurrences']:
        previous = reviewed[source_key(row, row['purl'].rsplit('@', 1)[1])]
        runtime = sorted(x.split('/', 1)[1] for x in row['scopes'] if x.startswith('runtime/'))
        occurrences.append({**row, 'minecraft_artifacts': [{**next(x for x in previous['minecraft_artifacts']
            if x['minecraft_version'] == game), 'version_metadata_sha256': games[game]['manifest']['sha256']}
            for game in runtime], 'codec_artifact': by_purl[row['purl']],
            'product_jar_sha256': mod['groups'][row['group']]['jar_sha256']})
    return {'schema': 1, 'advisory_id': TARGET, 'aliases': ['CVE-2026-59901'], 'severity': 'HIGH',
            'observed_on': '2026-11-22', 'analysis_base_commit': '9548d03bff815bf0576e3b23e2e007f5be84e0af',
            'upstream_advisory': {'path': UPSTREAM, 'sha256': UPSTREAM_SHA},
            'baseline_priority_register': ledger['ipfilter_high_focused_priority_register'],
            'evidence': {path: sha(raw) for path, raw in records.items()}, 'occurrence_count': len(occurrences),
            'source_group_count': len({(x['source_kind'], x['group']) for x in occurrences}),
            'minecraft_version_count': len(games), 'minecraft_versions': sorted(games), 'occurrences': occurrences,
            'dependency_owner': 'Minecraft runtime manifests; some coordinates also occur in Gradle resolution.',
            'upstream_fixed_versions': {'4.1.x': '4.1.136.Final', '4.2.x': '4.2.16.Final'},
            'reachability': 'The inspected vanilla client JARs, retained product JARs and one Fabric Loader JAR '
                'had no selected Bzip2 class-name literals. Static Minecraft 26.2 bytecode shows its normal '
                'compression setup installing a Minecraft inflater-based decoder. Neither observation establishes '
                'the effective pipeline or excludes indirect, generated or third-party paths.',
            'input_boundary': 'The advisory concerns the Bzip2 decoder processing compressed input; whether a supported '
                'configuration installs it for untrusted input remains unverified.',
            'remediation': 'A compatible Minecraft-managed update is required; no library replacement was made. '
                'The separate Critical Netty SNI advisory requires later fixed versions.',
            'limitations': ['No launcher, Fabric or game process was run; build resolution does not prove runtime classpath.',
                'Other runtime libraries, dedicated servers, other mods, agents and generated paths remain unverified.',
                'No malformed input, remote test or vulnerability reproduction was performed.',
                'Compatibility of newer libraries with affected older Minecraft versions is not established.'],
            'reviewer': 'Codex automated static investigation; human security review pending',
            'responsible_owner': 'Project maintainer and upstream Minecraft/library owners', 'review_date': '2026-11-22',
            'disposition': 'Further investigation', 'release_blocking': True, 'risk_accepted': False,
            'security_clearance': False, 'follow_up_requirements': [
                'Observe supported launcher, Fabric and dedicated-server pipelines and their input boundaries.',
                'Verify a compatible upstream update addressing this and the Critical SNI advisory.']}


def make_register(v3, review, review_raw):
    current = copy.deepcopy(v3)
    row = next(item for item in current['advisories'] if item['advisory_id'] == TARGET)
    require(row['focused_evidence'] is None and len(row['occurrences']) == review['occurrence_count'] == 13,
            'Bzip2 priority baseline differs')
    row.update(focused_evidence=REVIEW, reviewer=review['reviewer'], review_date=review['review_date'],
               responsible_owner=review['responsible_owner'], follow_up=review['follow_up_requirements'])
    current['bzip2_focused_evidence'] = {'path': REVIEW, 'sha256': sha(review_raw),
                                         'new_advisory_ids': 1, 'new_high_occurrences': 13}
    current['review_status'] = 'Adds bounded Bzip2 static observations; no finding is cleared or risk accepted.'
    focused = [item for item in current['advisories'] if item['focused_evidence']]
    critical = sum(len(item['occurrences']) for item in focused if item['severity'] == 'CRITICAL')
    high = sum(len(item['occurrences']) for item in focused if item['severity'] == 'HIGH')
    total_high = sum(len(item['occurrences']) for item in current['advisories'] if item['severity'] == 'HIGH')
    current['focused_coverage'] = {'advisory_ids': len(focused), 'critical_occurrences': critical,
        'high_occurrences': high, 'total_occurrences': critical + high,
        'high_occurrences_without_focused_evidence': total_high - high}
    require(current['focused_coverage'] == {'advisory_ids': 23, 'critical_occurrences': 22,
        'high_occurrences': 108, 'total_occurrences': 130, 'high_occurrences_without_focused_evidence': 69},
        'Bzip2 focused coverage differs')
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-cache', type=Path)
    parser.add_argument('--manifest-cache', type=Path)
    parser.add_argument('--fabric-jar', type=Path)
    parser.add_argument('--javap', type=Path)
    parser.add_argument('--verify-codec-download', action='store_true')
    parser.add_argument('--verify-client-download', action='store_true')
    parser.add_argument('--verify-runtime-cache', action='store_true')
    parser.add_argument('--write-inputs', action='store_true')
    parser.add_argument('--write-review', action='store_true')
    args = parser.parse_args()
    try:
        require(not (args.write_inputs and (args.verify_codec_download or args.verify_client_download or
                                           args.verify_runtime_cache)), 'input generation and verification must run separately')
        ledger, v3, target, reviewed, games, prior, mod = context()
        if args.write_inputs:
            require(args.runtime_cache and args.manifest_cache and args.fabric_jar and args.javap and not args.write_review,
                    'runtime, manifest, Fabric and javap inputs are required')
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda game: inspect_client(game, games[game], args.runtime_cache, args.manifest_cache),
                                     sorted(games)))
            by_purl = {}
            for row in rows:
                if row['codec_purl'] not in by_purl:
                    model = games[row['minecraft_version']]
                    raw = cache_bytes(args.runtime_cache, model['codec'])
                    by_purl[row['codec_purl']] = inspect_codec(raw, model['codec'], row['codec_purl'], row['codec_url'])
            clients = {'schema': 1, 'terms': list(TERMS), 'games': rows,
                'class_files_scanned': sum(row['class_files_scanned'] for row in rows), 'security_clearance': False}
            codecs = {'schema': 1, 'libraries': [by_purl[p] for p in sorted(by_purl)], 'security_clearance': False}
            fabric, product = inspect_fabric(args.fabric_jar.read_bytes()), product_scan()
            pipeline = inspect_pipeline(cache_bytes(args.runtime_cache, games['26.2']['client']), args.javap)
            validate_inputs(games, clients, codecs, fabric, product, pipeline)
            for path, value in ((CLIENTS, clients), (CODECS, codecs), (FABRIC, fabric), (PRODUCT, product), (PIPELINE, pipeline)):
                sni.write_new(ROOT / path, value)
            print('Recorded source-bound Bzip2 static observations; no finding was cleared')
            return 0
        records = {path: sni.read(ROOT, path) for path in (CLIENTS, CODECS, FABRIC, PRODUCT, PIPELINE)}
        clients, codecs, fabric, product, pipeline = (json.loads(records[path], object_pairs_hook=unique_object)
                                                       for path in (CLIENTS, CODECS, FABRIC, PRODUCT, PIPELINE))
        validate_inputs(games, clients, codecs, fabric, product, pipeline)
        if args.verify_codec_download:
            verify_codec_downloads(codecs)
            print('Verified seven source-bound Mojang codec JARs and their decoder class hashes')
        if args.verify_client_download:
            verify_client_download(clients, pipeline, args.javap)
            print('Verified source-bound Minecraft 26.2 client and compression pipeline disassembly')
        if args.verify_runtime_cache:
            verify_runtime_cache(args, games, clients, codecs, fabric, pipeline)
            print('Verified cached Minecraft, codec, Fabric and pipeline observations offline')
        review = make_review(ledger, target, reviewed, games, codecs, records, mod)
        if args.write_review:
            sni.write_new(ROOT / REVIEW, review)
            review_raw = sni.read(ROOT, REVIEW)
            sni.write_new(ROOT / CURRENT, make_register(v3, review, review_raw))
            print('Recorded 13 blocking Bzip2 occurrences and focused coverage')
            return 0
        review_raw = sni.read(ROOT, REVIEW)
        require(json.loads(review_raw, object_pairs_hook=unique_object) == review, 'Bzip2 source-bound review differs')
        current_raw = sni.read(ROOT, CURRENT)
        require(json.loads(current_raw, object_pairs_hook=unique_object) == make_register(v3, review, review_raw),
                'Bzip2 priority register differs')
        require(ledger['bzip2_high_focused_priority_register'] == {'path': CURRENT, 'sha256': sha(current_raw),
            'advisory_ids': 23, 'focused_occurrences': 130, 'remaining_unfocused_high_occurrences': 69,
            'security_clearance': False}, 'Bzip2 priority ledger reference differs')
        print('Validated 13 blocking Bzip2 occurrences and bounded static observations')
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, BadZipFile, subprocess.SubprocessError) as exc:
        print('Bzip2 investigation incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
