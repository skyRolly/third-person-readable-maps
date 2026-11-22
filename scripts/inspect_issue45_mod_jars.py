#!/usr/bin/env python3
"""Inspect retained, hash-bound product JARs for selected direct references.

This byte search does not establish runtime non-reachability: it cannot rule out
indirect game calls, reflection, dynamic code, agents, launchers, or other mods.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
INPUTS = 'docs/version-consistency-1.0.0/current-validation/rehearsal-2026-11-21-owner-policy/artifact-inputs.json'
HEADS_SNAPSHOT = 'docs/dependency-evidence/issue45-live-source-2026-11-22/product-heads-snapshot.json'
BUILDS_SNAPSHOT = 'docs/dependency-evidence/issue45-live-source-2026-11-22/product-builds-snapshot.json'
HEADS_SHA256 = '49e23765f2bbe912112cf18198b2d6b2933e479b2d3568b7bcd6a92fb676eb13'
BUILDS_SHA256 = '1c98da271fbf0bb4d6ce94e7831c7ae044e5a6bffceca36d0942e93be9820bd1'
NEEDLES = ('io/netty/', 'io.netty.', 'SniHandler', 'SslHandler', 'ChannelPipeline',
           'org/apache/logging/log4j', 'org.apache.logging.log4j', 'ThreadContext',
           'javax/naming/', 'javax.naming.', 'Jndi', 'jndi')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_archive(raw, record):
    require(digest(raw) == record['archive_sha256'], 'product archive checksum mismatch')
    with ZipFile(BytesIO(raw)) as archive:
        require(archive.namelist() == [record['artifact_filename']], 'unexpected product archive content')
        jar = archive.read(record['artifact_filename'])
    require(digest(jar) == record['artifact_sha256'], 'product JAR checksum mismatch')
    with ZipFile(BytesIO(jar)) as zipped:
        names = zipped.namelist()
        require(len(names) == len(set(names)), 'duplicate JAR entry')
        meta = json.loads(zipped.read('fabric.mod.json'), object_pairs_hook=unique_object)
        require(meta.get('id') == 'thirdpersonreadablemaps', 'unexpected Fabric mod identity')
        nested = sorted(name for name in names if name.lower().endswith('.jar'))
        classes = []
        for name in sorted(n for n in names if n.endswith('.class')):
            content = zipped.read(name)
            classes.append({'path': name, 'sha256': digest(content),
                            'matches': [needle for needle in NEEDLES if needle.encode() in content]})
        require(classes, 'product JAR has no class files')
        return {'archive_sha256': record['archive_sha256'], 'jar_sha256': digest(jar),
                'jar_filename': record['artifact_filename'], 'nested_jar_entries': nested,
                'fabric_declared_jars': meta.get('jars', []), 'classes': classes}


def collect(root=ROOT):
    inputs = json.loads((root / INPUTS).read_bytes(), object_pairs_hook=unique_object)['groups']
    heads_raw, builds_raw = (root / HEADS_SNAPSHOT).read_bytes(), (root / BUILDS_SNAPSHOT).read_bytes()
    require(digest(heads_raw) == HEADS_SHA256 and digest(builds_raw) == BUILDS_SHA256,
            'historical source or build snapshot checksum mismatch')
    heads = json.loads(heads_raw, object_pairs_hook=unique_object)['groups']
    builds = json.loads(builds_raw, object_pairs_hook=unique_object)
    require(len(inputs) == 13 and set(inputs) == set(heads) == set(builds), 'product group set mismatch')
    result = {}
    for group, row in sorted(inputs.items()):
        require(row['source_commit'] == heads[group]['new_head'] == builds[group]['source_commit'] and
                row['artifact_sha256'] == builds[group]['sha256'], 'product source or JAR mismatch: ' + group)
        path = (root / row['archive_path']).resolve()
        require(path.is_relative_to(root.resolve()), 'product archive path escapes repository')
        result[group] = {'source_sha': row['source_commit'], 'archive_path': row['archive_path'],
                         **inspect_archive(path.read_bytes(), row)}
    return {'schema': 1, 'scope': 'selected literal class-file byte references in retained product JARs',
            'input_record': INPUTS, 'input_record_sha256': digest((root / INPUTS).read_bytes()),
            'source_snapshot': {'path': HEADS_SNAPSHOT, 'sha256': HEADS_SHA256},
            'build_snapshot': {'path': BUILDS_SNAPSHOT, 'sha256': BUILDS_SHA256},
            'search_terms': list(NEEDLES), 'groups': result, 'security_clearance': False,
            'limitations': 'No runtime launch, indirect paths, generated strings, other mods or agents are excluded.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = json.dumps(collect(), indent=2, sort_keys=True) + '\n'
        if args.output:
            args.output.write_text(result, encoding='utf-8')
        else:
            print(result, end='')
        return 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as exc:
        print('Product JAR inspection incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
