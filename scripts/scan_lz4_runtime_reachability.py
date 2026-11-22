#!/usr/bin/env python3
"""Bind LZ4 caller-bytecode observations to the archived Minecraft artifacts."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
FINDING_INDEX = ARCHIVE / 'finding-index.json'
ARCHIVE_INDEX = ARCHIVE / 'archive-index.json'
HIGH_FAMILY = BASE / 'high-family-inspection.json.gz'
SOURCE_BOUND = BASE / 'source-bound-dispositions-2026-11-21.json'
TARGET_ADVISORY = 'GHSA-mcr4-qmvw-px4g'
CALLER_LITERAL = b'net/jpountz/lz4/LZ4BlockInputStream'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def scan(runtime_cache):
    finding_index = json.loads(FINDING_INDEX.read_text())
    high_family = json.loads(gzip.decompress(HIGH_FAMILY.read_bytes()))
    source_bound = json.loads(SOURCE_BOUND.read_text())
    lz4_finding = next(row for row in source_bound['findings']
                       if row['advisory_id'] == TARGET_ADVISORY)
    indexed = {(row['source_kind'], row['group'], row['purl']): row
               for row in finding_index['records']
               if row['advisory'] == TARGET_ADVISORY}
    archive_by_group = {}
    for report_key, report in finding_index['reports'].items():
        kind, group = report_key.split('|', 1)
        archive_by_group[(kind, group)] = report

    observations = []
    seen_versions = set()
    for occurrence in lz4_finding['occurrences']:
        key = (occurrence['source_kind'], occurrence['group'], occurrence['purl'])
        exact = indexed.get(key)
        if exact is None:
            raise ValueError(f'finding occurrence missing from exact-source index: {key}')
        if occurrence['source_sha'] != exact['source_sha']:
            raise ValueError(f'source SHA mismatch for {key}')
        if occurrence['source_sha'] != archive_by_group[(occurrence['source_kind'], occurrence['group'])]['source_sha']:
            raise ValueError(f'group source SHA mismatch for {key}')

        for artifact in occurrence['minecraft_artifacts']:
            version = artifact['minecraft_version']
            if version in seen_versions:
                continue
            seen_versions.add(version)
            game = high_family['games'].get(version)
            if game is None:
                raise ValueError(f'no high-family artifact record for Minecraft {version}')
            manifest_client = game.get('client', {})
            if manifest_client.get('sha1') != artifact['client_sha1'] or \
                    game.get('client_sha256') != artifact['client_sha256']:
                raise ValueError(f'Mojang client hash binding mismatch for Minecraft {version}')
            classes = game.get('literal_reference_matches', {}).get(
                'net/jpountz/lz4/LZ4BlockInputStream', [])
            if len(classes) != 1:
                raise ValueError(f'expected one direct LZ4 stream caller in Minecraft {version}, got {classes}')
            class_path = classes[0]
            archive_path = runtime_cache / artifact['client_sha1']
            if not archive_path.is_file():
                archive_path = runtime_cache / f"{artifact['client_sha1']}.jar"
            if not archive_path.is_file():
                raise ValueError(f'missing exact cached client jar for Minecraft {version}: {artifact["client_sha1"]}')
            jar_bytes = archive_path.read_bytes()
            if hashlib.sha1(jar_bytes).hexdigest() != artifact['client_sha1'] or \
                    sha256_bytes(jar_bytes) != artifact['client_sha256']:
                raise ValueError(f'client jar checksum mismatch for Minecraft {version}')
            with zipfile.ZipFile(archive_path) as jar:
                class_bytes = jar.read(class_path)
            if CALLER_LITERAL not in class_bytes:
                raise ValueError(f'LZ4 stream class reference absent from {version}:{class_path}')
            observations.append({
                'minecraft_version': version,
                'source_kind': occurrence['source_kind'],
                'source_group': occurrence['group'],
                'source_sha': occurrence['source_sha'],
                'version_metadata_sha1': next(
                    item['version_metadata_sha1'] for item in occurrence['minecraft_artifacts']
                    if item['minecraft_version'] == version),
                'client_sha1': artifact['client_sha1'],
                'client_sha256': artifact['client_sha256'],
                'client_url': manifest_client.get('url'),
                'direct_caller_class': class_path,
                'direct_caller_class_sha256': sha256_bytes(class_bytes),
                'literal_reference_verified': True,
            })

    expected_versions = {artifact['minecraft_version']
                         for occurrence in lz4_finding['occurrences']
                         for artifact in occurrence['minecraft_artifacts']}
    if seen_versions != expected_versions or len(observations) != len(expected_versions):
        raise ValueError(f'expected one observation for each of {len(expected_versions)} exact versions')
    return {
        'schema': 1,
        'status': 'complete_no_clearance',
        'observed_at': '2026-11-22',
        'target_advisory': TARGET_ADVISORY,
        'finding_index': {
            'path': FINDING_INDEX.relative_to(ROOT).as_posix(),
            'sha256': sha256_file(FINDING_INDEX),
        },
        'archive_index': {
            'path': ARCHIVE_INDEX.relative_to(ROOT).as_posix(),
            'sha256': sha256_file(ARCHIVE_INDEX),
        },
        'high_family_inspection': {
            'path': HIGH_FAMILY.relative_to(ROOT).as_posix(),
            'sha256': sha256_file(HIGH_FAMILY),
            'sha256_uncompressed': sha256_bytes(gzip.decompress(HIGH_FAMILY.read_bytes())),
        },
        'method': ('For all exact Minecraft client versions listed by the source-bound GHSA-mcr4 finding, '
                   'verify Mojang client SHA-1/SHA-256, locate the high-family scanner’s sole class literal '
                   'match for LZ4BlockInputStream, re-open that official jar, and verify the literal in the '
                   'class bytes. This literal scan locates callers; representative javap captures establish '
                   'the constructor and region-file call path.'),
        'occurrence_count': len(lz4_finding['occurrences']),
        'source_groups': [row['group'] for row in lz4_finding['occurrences']],
        'minecraft_version_count': len(observations),
        'observations': sorted(observations, key=lambda row: row['minecraft_version']),
        'security_clearance': False,
        'limitations': [
            'A class-literal match by itself does not prove invocation; use the source-bound javap captures for representative call paths.',
            'The scan covers official Minecraft client jars, including integrated-server classes, not arbitrary mods, launchers, agents, or reflective code.',
            'It does not test untrusted region files or a concurrent local attacker.'
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime-cache', type=Path, required=True,
                        help='directory containing official client jars named by Mojang SHA-1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.runtime_cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f"Scanned {result['minecraft_version_count']} exact clients across "
          f"{result['occurrence_count']} source groups; all remain blocked.")


if __name__ == '__main__':
    main()
