#!/usr/bin/env python3
"""Fetch and hash-check affected Netty artifacts from exact Mojang manifests.

This supplements the game-client constant-pool survey with the actual Netty
handler and HTTP codec JARs named by each source-bound finding. The script only
downloads Mojang metadata and library artifact URLs selected by that metadata.
It never executes a downloaded artifact.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import ZipFile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
TARGETS = {'GHSA-c4c3-7fpv-j4q5', 'GHSA-pwqr-wmgm-9rr8'}
ALLOWED_HOSTS = {'piston-meta.mojang.com', 'libraries.minecraft.net'}
MAX_BYTES = 32 * 1024 * 1024
PURL = re.compile(r'^pkg:maven/([^/]+)/([^/@]+)@([^/?#]+)$')


def fetch(url, expected_host):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname != expected_host or parsed.username or
            parsed.password or parsed.port not in (None, 443)):
        raise ValueError('unexpected artifact URL host or scheme')
    request = Request(url, headers={'User-Agent': 'issue45-netty-manifest-inspector'})
    with urlopen(request, timeout=45) as response:
        final = urlsplit(response.geturl())
        if (final.scheme != 'https' or final.hostname not in ALLOWED_HOSTS or final.username or
                final.password or final.port not in (None, 443)):
            raise ValueError('unexpected redirect host')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('download exceeds evidence size limit')
    return data


def verify_digest(data, algorithm, expected, label):
    actual = hashlib.new(algorithm, data).hexdigest()
    if actual.lower() != expected.lower():
        raise ValueError(label + ' checksum mismatch')
    return actual


def display_output_path(path):
    """Display repository paths relatively and external paths absolutely."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21/netty-manifest-artifacts-2026-11-21.json')
    args = parser.parse_args()
    index = json.loads(INDEX.read_text())
    rows = [row for row in index['records'] if row['advisory'] in TARGETS and
            row['purl'].startswith('pkg:maven/io.netty/')]
    manifest_documents = {}
    manifest_records = {}
    package_entries = {}
    source_rows = []
    for row in rows:
        match = PURL.fullmatch(row['purl'])
        if not match:
            raise ValueError('unexpected package URL: ' + row['purl'])
        group, name, version = match.groups()
        coordinate = f'{group}:{name}:{version}'
        report_path = ROOT / row['report']
        report = json.loads(gzip.decompress(report_path.read_bytes()))
        if report.get('source_sha') != row['source_sha']:
            raise ValueError('source report mismatch: ' + row['key'])
        runtime_versions = sorted(scope.split('/', 1)[1] for scope in row['scopes'] if scope.startswith('runtime/'))
        source_rows.append({'advisory': row['advisory'], 'group': row['group'], 'source_sha': row['source_sha'],
                            'purl': row['purl'], 'runtime_versions': runtime_versions,
                            'report': row['report'], 'report_sha256_uncompressed': row['report_sha256_uncompressed']})
        for version_name in runtime_versions:
            manifest_ref = report['runtime_manifests'][version_name]
            key = (version_name, manifest_ref['url'], manifest_ref['sha1'])
            if key not in manifest_documents:
                data = fetch(manifest_ref['url'], 'piston-meta.mojang.com')
                verify_digest(data, 'sha1', manifest_ref['sha1'], version_name + ' Mojang manifest')
                manifest_documents[key] = json.loads(data)
                manifest_records[key] = {'minecraft_version': version_name, 'url': manifest_ref['url'],
                                         'sha1': manifest_ref['sha1'], 'sha256': hashlib.sha256(data).hexdigest()}
            document = manifest_documents[key]
            matches = [item for item in document.get('libraries', []) if item.get('name') == coordinate]
            if len(matches) != 1:
                raise ValueError(f'{version_name}: expected one manifest entry for {coordinate}, found {len(matches)}')
            artifact = matches[0].get('downloads', {}).get('artifact')
            if not artifact:
                raise ValueError(f'{version_name}: no downloadable artifact for {coordinate}')
            # Mojang manifests can pin different artifact bytes for the same
            # Maven coordinate in different game versions. Preserve each
            # distinct published URL/hash tuple rather than assuming identity.
            artifact_key = (coordinate, artifact['url'], artifact['sha1'], artifact['size'])
            entry = package_entries.setdefault(artifact_key, {'coordinate': coordinate, 'minecraft_versions': [],
                'url': artifact['url'], 'sha1': artifact['sha1'], 'size': artifact['size'],
                'source_groups': [], 'classes': []})
            if version_name not in entry['minecraft_versions']:
                entry['minecraft_versions'].append(version_name)
            source_ref = {'group': row['group'], 'source_sha': row['source_sha'], 'source_kind': row['source_kind']}
            if source_ref not in entry['source_groups']:
                entry['source_groups'].append(source_ref)

    for entry in package_entries.values():
        data = fetch(entry['url'], 'libraries.minecraft.net')
        if len(data) != entry['size']:
            raise ValueError('artifact size mismatch: ' + entry['coordinate'])
        verify_digest(data, 'sha1', entry['sha1'], entry['coordinate'])
        entry['sha256'] = hashlib.sha256(data).hexdigest()
        wanted = []
        if entry['coordinate'].split(':')[1] == 'netty-handler':
            wanted = ['io/netty/handler/ssl/SniHandler.class',
                      'io/netty/handler/ssl/AbstractSniHandler.class',
                      'io/netty/handler/ssl/SslClientHelloHandler.class']
        elif entry['coordinate'].split(':')[1] == 'netty-codec-http':
            wanted = ['io/netty/handler/codec/http/HttpObjectDecoder.class',
                      'io/netty/handler/codec/http/HttpRequestDecoder.class']
        with ZipFile(BytesIO(data)) as jar:
            for name in wanted:
                try:
                    class_bytes = jar.read(name)
                except KeyError:
                    continue
                entry['classes'].append({'path': name, 'sha256': hashlib.sha256(class_bytes).hexdigest(),
                                         'size': len(class_bytes)})
        entry['minecraft_versions'].sort()
        entry['source_groups'].sort(key=lambda x: (x['source_kind'], x['group']))
        if not entry['classes']:
            # Preserve the verified artifact even if Mojang's selected JAR
            # does not contain one of the expected class paths; absence is a
            # result to inspect, not a reason to discard the source evidence.
            entry['expected_class_paths_not_found'] = True

    output = {'schema': 1, 'observed_on': '2026-11-21',
        'status': 'complete-hash-verified-artifact-inventory',
        'method': 'Read exact runtime manifest URL and SHA-1 from each finding-index report; verify Mojang metadata SHA-1; select exact Netty Maven coordinate; verify artifact size and SHA-1; record artifact and relevant class SHA-256. Downloaded JARs were inspected as ZIP entries only and not executed.',
        'finding_index': {'path': INDEX.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(INDEX.read_bytes()).hexdigest()},
        'source_occurrences': source_rows,
        'minecraft_manifests': sorted(manifest_records.values(), key=lambda x: x['minecraft_version']),
        'netty_artifacts': sorted(package_entries.values(), key=lambda x: (x['coordinate'], x['sha1']))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'manifests': len(output['minecraft_manifests']), 'artifacts': len(output['netty_artifacts']),
                      'source_occurrences': len(source_rows), 'output': display_output_path(args.output)}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('Netty artifact inspection failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
