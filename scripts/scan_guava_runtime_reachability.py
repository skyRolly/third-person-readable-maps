#!/usr/bin/env python3
"""Hash-check and inspect official Minecraft runtime artifacts for Java serialization paths.

The scan is deliberately limited to literal class-file constant-pool references.
It does not claim a complete call graph or cover launchers, mods, agents, or
runtime instrumentation. Use --download only to fetch from the allow-listed
official Mojang hosts after validating the SHA-1 and manifest size.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
HIGH_FAMILY = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21/high-family-inspection.json.gz'
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_critical_runtime as runtime  # noqa: E402

TARGET_ADVISORY = 'GHSA-xxph-c9ww-hj94'
TARGETS = (
    'java/io/ObjectInputStream',
    'java/io/ObjectStreamClass',
    'java/io/Externalizable',
    'io/netty/handler/codec/serialization/ObjectDecoder',
    'io/netty/handler/codec/serialization/ObjectDecoderInputStream',
    'io/netty/handler/codec/serialization/ObjectEncoder',
    'org/apache/commons/lang3/SerializationUtils',
    'org/apache/commons/io/serialization/SerializationUtils',
    'org/apache/commons/io/input/ClassLoaderObjectInputStream',
    'org/apache/commons/io/serialization/ValidatingObjectInputStream',
    'com/google/common/collect/CompactHashMap',
    'com/google/common/collect/CompactHashSet',
    'com/google/common/collect/MapMakerInternalMap',
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_archive(path):
    result = {target: [] for target in TARGETS}
    class_count = 0
    with zipfile.ZipFile(path) as jar:
        for entry in jar.infolist():
            if not entry.filename.endswith('.class'):
                continue
            class_count += 1
            strings = runtime.constant_pool_strings(jar.read(entry))
            for target in TARGETS:
                dotted = target.replace('/', '.')
                if any(target in value or dotted in value for value in strings):
                    result[target].append(entry.filename)
    return class_count, {key: values for key, values in result.items() if values}


def artifact_record(cache, artifact, coordinates, versions, download):
    raw = runtime.verified_bytes(cache, artifact['sha1'], artifact.get('size'),
                                 artifact.get('url'), download=download)
    path = cache / artifact['sha1']
    class_count, matches = inspect_archive(path)
    return {
        'artifact': {
            'sha1': artifact['sha1'],
            'sha256': sha256(raw),
            'size': len(raw),
            'url': artifact['url'],
            'path': artifact.get('path'),
        },
        'coordinates': sorted(coordinates),
        'minecraft_versions': sorted(versions),
        'class_files_scanned': class_count,
        'constant_pool_matches': matches,
    }


def build_report(cache, download):
    finding_bytes = (ARCHIVE / 'finding-index.json').read_bytes()
    finding_index = json.loads(finding_bytes)
    high_raw = gzip.decompress(HIGH_FAMILY.read_bytes())
    high_family = json.loads(high_raw)
    matching = [row for row in finding_index['records']
                if row['advisory'] == TARGET_ADVISORY]
    if len(matching) != 16:
        raise ValueError('expected exactly 16 Guava finding-index rows')
    versions = sorted({scope.removeprefix('runtime/') for row in matching
                       for scope in row['scopes'] if scope.startswith('runtime/')})
    groups = sorted({(row['source_kind'], row['group'], row['source_sha']) for row in matching})
    game_rows = []
    runtime_artifacts = {}
    for version in versions:
        game = high_family['games'].get(version)
        if game is None:
            raise ValueError('missing exact official client observation for ' + version)
        metadata_raw = runtime.verified_bytes(cache, game['metadata_sha1'],
                                              url=game['metadata_url'], download=download)
        metadata = json.loads(metadata_raw)
        if metadata.get('id') != version:
            raise ValueError('Minecraft version metadata ID mismatch for ' + version)
        client_record = game['client']
        client_raw = runtime.verified_bytes(cache, client_record['sha1'], client_record['size'],
                                            client_record['url'], download=download)
        client_path = cache / client_record['sha1']
        client_classes, client_matches = inspect_archive(client_path)
        game_rows.append({
            'minecraft_version': version,
            'source_bindings': [
                {'source_kind': row['source_kind'], 'group': row['group'],
                 'source_sha': row['source_sha'], 'purl': row['purl'],
                 'package_version': row['purl'].rsplit('@', 1)[-1]}
                for row in matching if 'runtime/' + version in row['scopes']
            ],
            'version_metadata': {
                'sha1': game['metadata_sha1'],
                'sha256': sha256(metadata_raw),
                'url': game['metadata_url'],
            },
            'client_artifact': {
                'sha1': client_record['sha1'],
                'sha256': sha256(client_raw),
                'size': len(client_raw),
                'url': client_record['url'],
                'class_files_scanned': client_classes,
                'constant_pool_matches': client_matches,
            },
        })
        game_manifest_libs = [lib for lib in metadata.get('libraries', [])
                              if lib.get('name', '').startswith('com.google.guava:guava:')]
        if len(game_manifest_libs) != 1:
            raise ValueError('expected one Guava library in Minecraft ' + version)
        library = game_manifest_libs[0]
        artifact = library.get('downloads', {}).get('artifact')
        if artifact is None:
            raise ValueError('Guava artifact missing from manifest for ' + version)
        key = artifact['sha1']
        row = runtime_artifacts.setdefault(key, {
            'artifact': artifact,
            'coordinates': set(),
            'versions': set(),
        })
        row['coordinates'].add(library['name'])
        row['versions'].add(version)

        for library in metadata.get('libraries', []):
            artifact = library.get('downloads', {}).get('artifact')
            if not artifact:
                continue
            key = artifact['sha1']
            row = runtime_artifacts.setdefault(key, {
                'artifact': artifact,
                'coordinates': set(),
                'versions': set(),
            })
            row['coordinates'].add(library['name'])
            row['versions'].add(version)

    library_rows = [artifact_record(cache, row['artifact'], row['coordinates'], row['versions'], download)
                    for _, row in sorted(runtime_artifacts.items())]
    return {
        'schema': 1,
        'observed_on': '2026-11-22',
        'advisory_id': TARGET_ADVISORY,
        'finding_index_sha256': sha256(finding_bytes),
        'high_family_inspection_sha256': sha256(HIGH_FAMILY.read_bytes()),
        'source_groups': [
            {'source_kind': kind, 'group': group, 'source_sha': source_sha}
            for kind, group, source_sha in groups
        ],
        'minecraft_versions': game_rows,
        'runtime_artifacts_scanned': library_rows,
        'counts': {
            'minecraft_clients': len(game_rows),
            'runtime_artifacts': len(library_rows),
            'game_clients_with_literal_target_references': sum(
                bool(row['client_artifact']['constant_pool_matches']) for row in game_rows),
            'runtime_artifacts_with_literal_target_references': sum(
                bool(row['constant_pool_matches']) for row in library_rows),
        },
        'target_strings': list(TARGETS),
        'limitations': [
            'The scan reports exact class-file constant-pool strings only; it is not a call graph, data-flow analysis, reflection analysis, or proof of reachability.',
            'Official Minecraft client and manifest libraries are covered. Supported launcher implementations, Fabric/other mod loaders, arbitrary third-party mods, Java agents, runtime instrumentation, and local configuration are not covered.',
            'A third-party component can deserialize attacker-controlled data in the same JVM even when vanilla Minecraft packet decoding uses its typed packet codecs.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True,
                        help='cache directory containing artifacts named by official SHA-1')
    parser.add_argument('--output', type=Path, required=True,
                        help='write deterministic gzip JSON to this path')
    parser.add_argument('--download', action='store_true',
                        help='download missing bytes only from inspect_critical_runtime.py allow-listed hosts')
    args = parser.parse_args()
    report = build_report(args.cache, args.download)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    with args.output.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, filename='') as compressed:
            compressed.write(raw)
    print(json.dumps(report['counts'], sort_keys=True))
    print('finding-index sha256:', report['finding_index_sha256'])
    print('gzip output sha256:', sha256(args.output.read_bytes()))


if __name__ == '__main__':
    main()
