#!/usr/bin/env python3
"""Inspect hash-verified Minecraft artifacts for the critical advisory worklist.

The cache contains files named by their Mojang SHA-1. This command runs offline.
It records literal references and configurations, and leaves reachability
classification to the accompanying investigation.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import struct
import re
import zipfile
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
TARGETS = ('io/netty/handler/ssl/SniHandler', 'io/netty/handler/ssl/AbstractSniHandler',
           'io/netty/handler/ssl/SslClientHelloHandler', 'io/netty/handler/ssl/SslContext',
           'io/netty/handler/ssl/SslHandler', 'io/netty/bootstrap/ServerBootstrap',
           'org/apache/logging/log4j/core/net/server/TcpSocketServer',
           'org/apache/logging/log4j/core/net/server/UdpSocketServer',
           'io/netty/handler/ipfilter/IpSubnetFilterRule', 'io/netty/handler/codec/compression/Bzip2Decoder',
           'io/netty/handler/codec/http/HttpClientCodec', 'io/netty/handler/codec/http/HttpServerCodec',
           'io/netty/handler/codec/http/HttpContentDecompressor', 'io/netty/handler/codec/spdy/',
           'io/netty/handler/codec/compression/Lz4FrameDecoder', 'io/netty/channel/epoll/',
           'net/jpountz/lz4/LZ4BlockInputStream', 'net/jpountz/lz4/LZ4Factory',
           'com/fasterxml/jackson/databind/ObjectMapper', 'activateDefaultTyping', 'enableDefaultTyping',
           'com/fasterxml/jackson/core/json/UTF8DataInputJsonParser',
           'java/io/ObjectInputStream', 'com/google/common/collect/CompactHashMap',
           'com/google/common/collect/MapMakerInternalMap',
           'org/apache/commons/compress/archivers/sevenz/SevenZFile',
           'org/apache/commons/compress/archivers/tar/TarArchiveInputStream',
           'org/apache/commons/compress/archivers/zip/ZipFile',
           'org/apache/commons/compress/archivers/zip/ZipArchiveInputStream',
           'org/apache/commons/io/input/XmlStreamReader')


def verified_bytes(cache, digest, size=None, url=None, download=False):
    if not re.fullmatch(r'[a-f0-9]{40}', digest):
        raise ValueError('invalid artifact digest')
    path = cache / digest
    if not path.exists() and download:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in
                ('piston-meta.mojang.com', 'piston-data.mojang.com', 'libraries.minecraft.net') or
                parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('untrusted Mojang artifact URL')
        with urlopen(url, timeout=120) as response:
            raw = response.read()
        if hashlib.sha1(raw).hexdigest() != digest or (size is not None and len(raw) != size):
            raise ValueError('downloaded artifact identity mismatch')
        path.write_bytes(raw)
    raw = path.read_bytes()
    if hashlib.sha1(raw).hexdigest() != digest or (size is not None and len(raw) != size):
        raise ValueError('artifact identity mismatch for ' + digest)
    return raw


def constant_pool_strings(raw):
    if raw[:4] != b'\xca\xfe\xba\xbe':
        raise ValueError('invalid JVM class magic')
    count = struct.unpack_from('>H', raw, 8)[0]
    offset, index = 10, 1
    strings = []
    while index < count:
        tag = raw[offset]
        offset += 1
        if tag == 1:
            length = struct.unpack_from('>H', raw, offset)[0]
            offset += 2
            strings.append(raw[offset:offset + length].decode('utf-8', errors='replace'))
            offset += length
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            offset += 2
        elif tag == 15:
            offset += 3
        else:
            raise ValueError('unsupported JVM constant-pool tag ' + str(tag))
        index += 1
    return strings


def inspect_jar(path, parse_pool):
    matches = {target: [] for target in TARGETS}
    count = 0
    with zipfile.ZipFile(path) as jar:
        for entry in jar.infolist():
            if not entry.filename.endswith('.class'):
                continue
            raw = jar.read(entry)
            count += 1
            values = "\n".join(constant_pool_strings(raw)) if parse_pool else None
            for target in TARGETS:
                spellings = (target, target.replace('/', '.'))
                found = (any(text in values for text in spellings) if parse_pool
                         else any(text.encode() in raw for text in spellings))
                if found:
                    matches[target].append(entry.filename)
        embedded = jar.read('log4j2.xml') if 'log4j2.xml' in jar.namelist() else None
    return {'class_files': count, 'literal_reference_matches': matches,
            'embedded_log4j2_xml': embedded.decode('utf-8') if embedded else None,
            'embedded_log4j2_sha256': hashlib.sha256(embedded).hexdigest() if embedded else None}


def inspect(cache, download=False):
    finding_raw = (ARCHIVE / 'finding-index.json').read_bytes()
    findings = json.loads(finding_raw)
    critical = [row for row in findings['records'] if row['severity'] in ('CRITICAL', 'HIGH')]
    versions = {}
    bindings = []
    for row in critical:
        report_raw = gzip.decompress((ROOT / row['report']).read_bytes())
        if hashlib.sha256(report_raw).hexdigest() != row['report_sha256_uncompressed']:
            raise ValueError('report digest mismatch')
        report = json.loads(report_raw)
        if report['source_sha'] != row['source_sha']:
            raise ValueError('report source mismatch')
        for scope in row['scopes']:
            if not scope.startswith('runtime/'):
                continue
            version = scope.removeprefix('runtime/')
            spec = report['runtime_manifests'][version]
            if version in versions and versions[version] != spec:
                raise ValueError('conflicting version manifests')
            versions[version] = spec
            bindings.append({'key': row['key'], 'source_kind': row['source_kind'],
                             'source_sha': row['source_sha'], 'scope': scope, 'minecraft': version,
                             'owner': 'Minecraft runtime manifest', 'release_blocking': True})
    games, libraries = {}, {}
    for version, spec in sorted(versions.items()):
        raw = verified_bytes(cache, spec['sha1'], url=spec['url'], download=download)
        manifest = json.loads(raw)
        if manifest['id'] != version:
            raise ValueError('manifest version mismatch')
        client = manifest['downloads']['client']
        client_raw = verified_bytes(cache, client['sha1'], client['size'], client['url'], download)
        game = inspect_jar(cache / client['sha1'], True)
        game.update(metadata_url=spec['url'], metadata_sha1=spec['sha1'],
                    client=client, client_sha256=hashlib.sha256(client_raw).hexdigest(),
                    logging=manifest.get('logging'),
                    relevant_library_order=[{'index': index, 'coordinate': lib['name']}
                                            for index, lib in enumerate(manifest['libraries'])
                                            if lib['name'].startswith(('io.netty:netty-handler:',
                                                                      'org.apache.logging.log4j:log4j-core:',
                                                                      'com.mojang:patchy:'))])
        games[version] = game
        for lib in manifest['libraries']:
            artifact = lib.get('downloads', {}).get('artifact')
            if not artifact or lib['name'].startswith('io.netty:'):
                continue
            entry = libraries.setdefault(artifact['sha1'], {'artifact': artifact, 'coordinates': set(), 'versions': set()})
            entry['coordinates'].add(lib['name'])
            entry['versions'].add(version)
    library_results = []
    for digest, entry in sorted(libraries.items()):
        raw = verified_bytes(cache, digest, entry['artifact']['size'], entry['artifact']['url'], download)
        result = inspect_jar(cache / digest, False)
        result.update(artifact=entry['artifact'], sha256=hashlib.sha256(raw).hexdigest(),
                      coordinates=sorted(entry['coordinates']), versions=sorted(entry['versions']))
        library_results.append(result)
    return {'schema': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'status': 'complete', 'security_clearance': False,
            'method': 'Game constant-pool UTF-8 and library class-byte literal searches for slash and dotted spellings. Netty library artifacts are excluded from caller search.',
            'limitations': ['Literal searches cannot establish general absence of dynamically constructed or reflective paths.',
                            'Launcher binaries, Fabric loader dependencies, Gradle plugin classpaths and arbitrary installed mods require separate inspection.'],
            'finding_index_sha256': hashlib.sha256(finding_raw).hexdigest(),
            'collector_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'bindings': bindings, 'games': games, 'libraries': library_results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--download', action='store_true', help='fetch missing pinned artifacts from Mojang')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    result = inspect(args.cache, args.download)
    raw = json.dumps(result, indent=2).encode() + b'\n'
    with args.output.open('xb') as stream:
        stream.write(gzip.compress(raw, mtime=0))
    print(f"Inspected {len(result['games'])} clients and {len(result['libraries'])} library artifacts")


if __name__ == '__main__':
    main()
