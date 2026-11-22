#!/usr/bin/env python3
"""Reinspect Mojang client XML and Realms caller bytes for the Issue #45 review.

Artifacts are selected by the retained Mojang metadata and the prior inspection.
Downloads are treated as data and checked before the JAR entries are inspected.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
METADATA = BASE / 'log4j-mojang-runtime-2026-11-22/metadata/current-version-metadata'
HIGH_FAMILY = BASE / 'high-family-inspection.json.gz'
REALMS_VERSIONS = {'1.14': '1.14.14', '1.14.1': '1.14.15',
                   '1.14.2': '1.14.16', '1.14.3': '1.14.17'}
CLIENT_VERSIONS = ('1.14.4', '1.17.1', '1.18.1')
CALLERS = ('realms/c.class', 'realms/ah.class', 'realms/ab.class')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('unexpected artifact redirect')


def digest(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def artifact_bytes(artifact, expected_sha256, host, cache):
    url = urlsplit(artifact['url'])
    if url.scheme != 'https' or url.hostname != host or url.username or url.password or \
            url.port not in (None, 443) or url.query or url.fragment:
        raise ValueError('untrusted Mojang artifact URL')
    path = cache / artifact['sha1']
    if not path.exists():
        with build_opener(NoRedirect()).open(artifact['url'], timeout=90) as response:
            if response.geturl() != artifact['url']:
                raise ValueError('unexpected artifact redirect')
            data = response.read(artifact['size'] + 1)
        if len(data) != artifact['size'] or digest(data, 'sha1') != artifact['sha1'] or \
                digest(data, 'sha256') != expected_sha256:
            raise ValueError('downloaded artifact identity mismatch')
        path.write_bytes(data)
    data = path.read_bytes()
    if len(data) != artifact['size'] or digest(data, 'sha1') != artifact['sha1'] or \
            digest(data, 'sha256') != expected_sha256:
        raise ValueError('cached artifact identity mismatch')
    return path


def metadata_for(version, game):
    path = METADATA / (version + '-' + game['metadata_sha1'] + '.json')
    raw = path.read_bytes()
    if digest(raw, 'sha1') != game['metadata_sha1']:
        raise ValueError('Mojang metadata SHA-1 mismatch: ' + version)
    value = json.loads(raw)
    if value['id'] != version:
        raise ValueError('Mojang metadata version mismatch: ' + version)
    return value


def inspect(cache):
    packed = HIGH_FAMILY.read_bytes()
    family = json.loads(gzip.decompress(packed))
    result = {'schema': 1, 'observed_on': '2026-11-22',
              'analysis_source_commit': '1da853baf68ea35ba0628c5ed033b5be682397d7',
              'high_family_sha256': digest(packed, 'sha256'),
              'security_clearance': False, 'risk_accepted': False, 'release_blocking': True,
              'method': 'Verify retained metadata SHA-1 and official artifact size, SHA-1, and SHA-256 before reading ZIP entries; downloaded artifacts are never executed.',
              'clients': [], 'realms': []}
    for version in CLIENT_VERSIONS:
        game = family['games'][version]
        metadata = metadata_for(version, game)
        if metadata['downloads']['client'] != game['client']:
            raise ValueError('client artifact differs from retained metadata: ' + version)
        path = artifact_bytes(game['client'], game['client_sha256'], 'piston-data.mojang.com', cache)
        with ZipFile(path) as jar:
            xml = jar.read('log4j2.xml')
        xml_sha256 = digest(xml, 'sha256')
        if xml_sha256 != game['embedded_log4j2_sha256']:
            raise ValueError('client XML differs from previous inspection: ' + version)
        result['clients'].append({'minecraft_version': version, 'metadata_sha1': game['metadata_sha1'],
                                  'artifact': game['client'], 'artifact_sha256': game['client_sha256'],
                                  'entry': 'log4j2.xml', 'entry_size': len(xml), 'entry_sha256': xml_sha256})
    for version, realms_version in REALMS_VERSIONS.items():
        game = family['games'][version]
        metadata = metadata_for(version, game)
        coordinate = 'com.mojang:realms:' + realms_version
        libraries = [row for row in family['libraries']
                     if coordinate in row.get('coordinates', []) and version in row.get('versions', [])]
        declared = [row['downloads']['artifact'] for row in metadata['libraries'] if row['name'] == coordinate]
        if len(libraries) != 1 or len(declared) != 1 or declared[0] != libraries[0]['artifact']:
            raise ValueError('Realms artifact differs from retained metadata: ' + version)
        lib = libraries[0]
        path = artifact_bytes(lib['artifact'], lib['sha256'], 'libraries.minecraft.net', cache)
        with ZipFile(path) as jar:
            callers = [{'path': name, 'sha256': digest(jar.read(name), 'sha256')} for name in CALLERS]
        result['realms'].append({'minecraft_version': version, 'coordinate': coordinate,
                                 'metadata_sha1': game['metadata_sha1'], 'artifact': lib['artifact'],
                                 'artifact_sha256': lib['sha256'], 'related_call_path_classes': callers})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inspect(args.cache), indent=2) + '\n')
    print('Verified three client XML resources and four Realms caller sets.')


if __name__ == '__main__':
    main()
