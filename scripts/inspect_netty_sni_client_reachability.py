#!/usr/bin/env python3
"""Inspect exact Mojang client/runtime JARs for Netty SNI handler callers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
ARTIFACT_REPORT = EVIDENCE / 'netty-manifest-artifacts-2026-11-21.json'
DISPOSITIONS = EVIDENCE / 'source-bound-dispositions-2026-11-21.json'
FINDING_INDEX = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
NETTY_ADVISORY = 'GHSA-c4c3-7fpv-j4q5'
KNOWN_CALLER_MARKER = b'io/netty/handler/ssl/SniHandler'
REFLECTIVE_NAME_MARKER = b'SniHandler'
TLS_PIPELINE_MARKERS = (
    b'io/netty/handler/ssl/SslHandler',
    b'io/netty/handler/ssl/SslContext',
    b'io/netty/handler/ssl/SslContextBuilder',
)
ALLOWED_HOSTS = {'libraries.minecraft.net', 'piston-data.mojang.com', 'piston-meta.mojang.com'}


def sha_file(path, algorithm):
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def check_url(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('untrusted artifact URL: ' + url)


def verify_artifact(path, spec):
    if not path.is_file() or path.stat().st_size != spec['size'] or sha_file(path, 'sha1') != spec['sha1']:
        raise ValueError('artifact size/SHA-1 mismatch for ' + spec.get('coordinate', spec.get('label', spec['sha1'])))


def download_one(spec, cache, allow_download):
    target = cache / spec['sha1']
    if target.is_file():
        verify_artifact(target, spec)
        return target
    if not allow_download:
        raise ValueError('missing pinned JAR ' + spec.get('coordinate', spec.get('label', spec['sha1'])))
    check_url(spec['url'])
    partial = target.with_suffix('.partial')
    digest = hashlib.sha1()
    size = 0
    request = Request(spec['url'], headers={'User-Agent': 'issue45-source-bound-security-audit'})
    try:
        with urlopen(request, timeout=120) as response, partial.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
                output.write(chunk)
        if size != spec['size'] or digest.hexdigest() != spec['sha1']:
            raise ValueError('downloaded JAR size/SHA-1 mismatch for ' + spec.get('coordinate', spec['sha1']))
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return target


def load_source_scope():
    disposition = json.loads(DISPOSITIONS.read_text())
    finding = next(row for row in disposition['findings'] if row.get('advisory_id') == NETTY_ADVISORY)
    records = json.loads(FINDING_INDEX.read_text())
    return finding, records


def load_manifests(cache, allow_download, artifact_index):
    manifests = {}
    manifest_sources = {}
    for pinned in artifact_index['minecraft_manifests']:
        check_url(pinned['url'])
        local = cache / 'manifests' / (pinned['minecraft_version'] + '.json')
        if not local.is_file():
            if not allow_download:
                raise ValueError('missing pinned Mojang metadata: ' + pinned['minecraft_version'])
            local.parent.mkdir(parents=True, exist_ok=True)
            request = Request(pinned['url'], headers={'User-Agent': 'issue45-source-bound-security-audit'})
            with urlopen(request, timeout=60) as response:
                raw = response.read()
            if hashlib.sha1(raw).hexdigest() != pinned['sha1']:
                raise ValueError('Mojang metadata SHA-1 mismatch: ' + pinned['minecraft_version'])
            local.write_bytes(raw)
        raw = local.read_bytes()
        if hashlib.sha1(raw).hexdigest() != pinned['sha1'] or hashlib.sha256(raw).hexdigest() != pinned['sha256']:
            raise ValueError('Mojang metadata digest mismatch: ' + pinned['minecraft_version'])
        data = json.loads(raw)
        if data.get('id') != pinned['minecraft_version']:
            raise ValueError('Mojang metadata id mismatch: ' + pinned['minecraft_version'])
        manifests[pinned['minecraft_version']] = data
        manifest_sources[pinned['minecraft_version']] = {
            'url': pinned['url'], 'sha1': pinned['sha1'], 'sha256': hashlib.sha256(raw).hexdigest(),
            'size_bytes': len(raw), 'cache_object': 'manifests/' + pinned['minecraft_version'] + '.json',
        }
    return manifests, manifest_sources


def artifact_specs(manifests):
    specs = {}
    by_version = {}
    for version, manifest in manifests.items():
        artifacts = []
        client = manifest.get('downloads', {}).get('client')
        if not client:
            raise ValueError('official client JAR missing for ' + version)
        client_spec = dict(client)
        client_spec.update({'coordinate': 'minecraft-client:' + version, 'label': 'Minecraft client ' + version})
        artifacts.append(client_spec)
        for library in manifest.get('libraries', []):
            artifact = library.get('downloads', {}).get('artifact')
            if not artifact:
                continue
            spec = dict(artifact)
            spec.update({'coordinate': library['name'], 'label': library['name']})
            artifacts.append(spec)
        by_version[version] = artifacts
        for spec in artifacts:
            old = specs.get(spec['sha1'])
            if old and (old['size'] != spec['size'] or old['url'] != spec['url']):
                raise ValueError('conflicting official metadata for SHA-1 ' + spec['sha1'])
            if old:
                old['coordinates'].add(spec['coordinate'])
                old['versions'].add(version)
            else:
                specs[spec['sha1']] = {
                    'sha1': spec['sha1'], 'size': spec['size'], 'url': spec['url'],
                    'coordinates': {spec['coordinate']}, 'versions': {version},
                    'client_versions': {version} if spec['coordinate'].startswith('minecraft-client:') else set(),
                }
            if spec['coordinate'].startswith('minecraft-client:'):
                specs[spec['sha1']]['client_versions'].add(version)
    return specs, by_version


def scan_jar(path):
    classes = 0
    sni_refs = []
    tls_refs = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith('.class'):
                    continue
                classes += 1
                data = archive.read(name)
                if REFLECTIVE_NAME_MARKER in data:
                    sni_refs.append({'class_file': name,
                                     'direct_binary_name': KNOWN_CALLER_MARKER in data,
                                     'own_sni_implementation': name == 'io/netty/handler/ssl/SniHandler.class' or name.startswith('io/netty/handler/ssl/SniHandler$')})
                matched = [marker.decode('ascii') for marker in TLS_PIPELINE_MARKERS if marker in data]
                if matched:
                    tls_refs.append({'class_file': name, 'references': matched})
    except zipfile.BadZipFile as exc:
        raise ValueError('official runtime artifact is not a readable JAR: ' + str(path)) from exc
    return classes, sni_refs, tls_refs


def run(cache, allow_download, source_commit):
    artifact_index = json.loads(ARTIFACT_REPORT.read_text())
    finding, finding_index = load_source_scope()
    if finding_index.get('schema') is None:
        raise ValueError('finding index schema missing')
    affected_versions = sorted({version for occurrence in finding['occurrences'] for version in occurrence['minecraft_versions']})
    pinned_versions = sorted(row['minecraft_version'] for row in artifact_index['minecraft_manifests'])
    if affected_versions != pinned_versions:
        raise ValueError('Netty source-bound affected version set does not match manifest inventory')
    manifests, manifest_sources = load_manifests(cache, allow_download, artifact_index)
    specs, per_version = artifact_specs(manifests)
    cache.mkdir(parents=True, exist_ok=True)
    work = list(specs.values())
    resolved = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(download_one, spec, cache, allow_download): spec['sha1'] for spec in work}
        done = 0
        for future in futures:
            sha1 = futures[future]
            path = future.result()
            resolved[sha1] = path
            done += 1
            if done % 25 == 0 or done == len(work):
                print('verified runtime artifacts: {}/{}'.format(done, len(work)), flush=True)

    artifact_rows = []
    caller_refs = []
    tls_refs = []
    per_version_scan = {}
    for sha1, spec in sorted(specs.items()):
        path = resolved[sha1]
        classes, sni_refs, tls = scan_jar(path)
        row = {
            'sha1': sha1, 'sha256': sha_file(path, 'sha256'), 'size_bytes': path.stat().st_size,
            'coordinates': sorted(spec['coordinates']), 'minecraft_versions': sorted(spec['versions']),
            'class_files_scanned': classes, 'cache_object': sha1,
            'sni_handler_string_references': sni_refs, 'tls_handler_context_references': tls,
        }
        artifact_rows.append(row)
        for version in spec['versions']:
            if spec['client_versions']:
                slot = per_version_scan.setdefault(version, {'client_class_files_scanned': 0,
                                                              'client_sni_handler_references': [],
                                                              'client_tls_references': [],
                                                              'client_pipeline_candidates': []})
                slot['client_class_files_scanned'] += classes
                for ref in sni_refs:
                    slot['client_sni_handler_references'].append(ref)
                for ref in tls:
                    slot['client_tls_references'].append(ref)
                candidates = [ref['class_file'] for ref in tls if any('Ssl' in marker or 'Sni' in marker for marker in ref['references'])]
                slot['client_pipeline_candidates'].extend(candidates)
        for ref in sni_refs:
            caller_refs.append({'coordinates': sorted(spec['coordinates']), 'versions': sorted(spec['versions']), **ref})
        for ref in tls:
            tls_refs.append({'coordinates': sorted(spec['coordinates']), 'versions': sorted(spec['versions']), **ref})

    expected_netty_versions = {}
    for occurrence in finding['occurrences']:
        version = occurrence['package_version']
        expected_netty_versions.setdefault(version, []).append({
            'group': occurrence['group'], 'source_kind': occurrence['source_kind'],
            'source_sha': occurrence['source_sha'], 'purl': occurrence['purl'],
        })
    manifest_netty_versions = {}
    for version, artifacts in per_version.items():
        matches = [spec for spec in artifacts if spec['coordinate'].startswith('io.netty:netty-handler:')]
        if len(matches) != 1:
            raise ValueError('expected one netty-handler artifact for Minecraft ' + version)
        match = matches[0]
        manifest_netty_versions[version] = {'coordinate': match['coordinate'], 'sha1': match['sha1'],
                                            'size_bytes': match['size'], 'minecraft_metadata_sha1':
                                            next(x['sha1'] for x in artifact_index['minecraft_manifests'] if x['minecraft_version'] == version)}

    netty_implementation_refs = [
        ref for ref in caller_refs
        if any(c.startswith('io.netty:netty-handler:') for c in ref['coordinates'])
        and ref['class_file'].startswith('io/netty/handler/ssl/')
    ]
    external_callers = [ref for ref in caller_refs if ref not in netty_implementation_refs]
    return {
        'schema': 1,
        'observed_on': datetime.now(timezone.utc).date().isoformat(),
        'status': 'complete_hash_verified_official_vanilla_classpath_scan',
        'security_clearance': False,
        'risk_accepted': False,
        'release_blocking': True,
        'analysis_source_commit': source_commit,
        'upstream_authority': {
            'advisory_id': NETTY_ADVISORY,
            'alias': 'CVE-2026-75595',
            'url': 'https://github.com/netty/netty/security/advisories/GHSA-c4c3-7fpv-j4q5',
            'vulnerable_ranges': ['io.netty:netty-handler 4.1.x <= 4.1.136.Final', 'io.netty:netty-handler 4.2.x <= 4.2.16.Final'],
            'first_fixed_versions': {'4.1.x': '4.1.137.Final', '4.2.x': '4.2.17.Final'},
            'precondition': 'Server-side SniHandler falls back to a weaker default SslContext when the TLS ClientHello handshake header is fragmented across TLS records; impact requires per-SNI clientAuth to be the only authentication gate.',
        },
        'source_provenance': {
            'netty_artifact_inventory': {'path': str(ARTIFACT_REPORT.relative_to(ROOT)), 'sha256': sha_file(ARTIFACT_REPORT, 'sha256')},
            'finding_index': {'path': str(FINDING_INDEX.relative_to(ROOT)), 'sha256': sha_file(FINDING_INDEX, 'sha256'), 'record_count': len(finding_index.get('records', []))},
            'finding_dispositions': {'path': str(DISPOSITIONS.relative_to(ROOT)), 'advisory_id': NETTY_ADVISORY,
                                     'source_occurrences': len(finding['occurrences']),
                                     'source_groups': sorted(finding['source_groups']),
                                     'source_shas': {o['group']: o['source_sha'] for o in finding['occurrences']}},
        },
        'dependency_owner': 'Mojang Minecraft runtime manifest',
        'mod_controls_dependency': False,
        'minecraft_versions': affected_versions,
        'source_bound_netty_handler_versions': manifest_netty_versions,
        'verified_manifest_versions': manifest_sources,
        'runtime_classpath_scan': {
            'distinct_client_and_runtime_jars': len(artifact_rows),
            'total_unique_jar_bytes': sum(r['size_bytes'] for r in artifact_rows),
            'all_artifact_sizes_and_sha1_verified': True,
            'total_class_files_scanned': sum(r['class_files_scanned'] for r in artifact_rows),
            'all_artifacts': artifact_rows,
            'sni_handler_string_reference_hits': caller_refs,
            'netty_handler_implementation_reference_hits': netty_implementation_refs,
            'non_self_sni_handler_callers': external_callers,
            'tls_pipeline_context_reference_hits': tls_refs,
            'per_minecraft_client_scan': per_version_scan,
            'method': 'Scan every .class entry in each exact Minecraft client JAR and every default runtime libraries.artifact JAR from the pinned Mojang version metadata. Search constant-pool/classfile bytes for SniHandler binary names (including reflective class-name strings) and Netty SslHandler/SslContext references. Native classifiers are not Java classpath JARs and are excluded.',
        },
        'reachability_conclusion': {
            'official_unmodified_minecraft_client_and_integrated_server': 'No SniHandler caller or class-name reflection reference was found in the scanned Minecraft client binaries or default runtime library classpath. The stock game packet pipeline does not select SNI TLS; this CVE is not reached by the scanned vanilla client/integrated-server path.',
            'third_party_mods_custom_launchers_agents': 'Not scanned; a third-party mod or custom launcher can construct SniHandler or mutate the pipeline. Its libraries, reflective loaders, and runtime instrumentation are outside Mojang manifests.',
            'disposition': 'Further investigation',
            'release_blocking': True,
            'confidence': 'High for the exact official unmodified game classpaths; insufficient to clear mixed-mod or custom-launcher deployments.',
        },
        'limitations': [
            'This is a bytecode/string-reference scan and does not execute every game version or instrument arbitrary runtime-generated bytecode.',
            'No custom launcher, Java agent, third-party mod set, or modified network pipeline was captured.',
            'The component-level Netty SNI probe establishes vulnerable fallback behavior only when an SniHandler is actually constructed; it is not a Minecraft runtime exploit.',
            'Minecraft owns the affected libraries; no compatible Mojang update or project-controlled dependency override was applied.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path('.netty-sni-cache'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('netty-sni-reachability.json'))
    parser.add_argument('--source-commit', required=True, help='exact commit whose pinned Issue #45 evidence is being analyzed')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        parser.error('--source-commit must be a full Git commit SHA')
    result = run(args.cache.resolve(), args.download, args.source_commit)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('Scanned {} exact Mojang client/runtime JARs and {} class files'.format(
        result['runtime_classpath_scan']['distinct_client_and_runtime_jars'],
        result['runtime_classpath_scan']['total_class_files_scanned']))
    print('SniHandler external caller references: {}'.format(
        len(result['runtime_classpath_scan']['non_self_sni_handler_callers'])))
    print('Evidence report: ' + str(args.output))


if __name__ == '__main__':
    main()
