#!/usr/bin/env python3
"""Bind the Netty SNI High advisory to retained exact-source observations.

This records static evidence only. It does not exercise vulnerable network
behavior, test arbitrary modpacks, accept risk, or authorize release.
"""
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

import reconcile_issue45_live_audits as audits
from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
DIR = 'docs/dependency-evidence/issue45-netty-sni-high-2026-11-22'
PRIORITY = 'docs/dependency-evidence/issue45-live-source-2026-11-22/priority-register.json'
MOD_REPORT = 'docs/dependency-evidence/issue45-live-source-2026-11-22/mod-jar-literal-inspection-v2.json'
MOD_SHA = '5814bc1a2e6f0bc3bce5ec1059aa830b689e892a3743fa73f8d05bdf29e985e1'
UPSTREAM = DIR + '/upstream-advisory.json'
UPSTREAM_SHA = 'daf24ba7ef8ed9e5131ff8264cd8c8554d789b841dbd1c0f286554d456b07bae'
ARTIFACTS = DIR + '/local-artifact-verification.json'
BASE_SCAN = DIR + '/clienthello-classpath-scan.json'
KNOWN_HITS = DIR + '/known-clienthello-class-hits-2026-11-22.json'
KNOWN_HITS_SHA = 'c818c5c955642f351866bbf248ba1e5f46b4cbbc33b12c75a3f2ac6fcb817355'
REVIEW = DIR + '/source-bound-review.json'
CURRENT = DIR + '/priority-register-v2.json'
HIGH = 'GHSA-x4gw-5cx5-pgmh'
CRITICAL = 'GHSA-c4c3-7fpv-j4q5'
KNOWN_HIT_PATHS = frozenset({
    'io/netty/handler/ssl/AbstractSniHandler.class',
    'io/netty/handler/ssl/SslClientHelloHandler$1.class',
    'io/netty/handler/ssl/SslClientHelloHandler.class',
})
CATALOG_HIT_PATHS = KNOWN_HIT_PATHS - {'io/netty/handler/ssl/SslClientHelloHandler$1.class'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, path, expected=None):
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root.resolve()), 'evidence path escapes repository')
    raw = resolved.read_bytes()
    if expected is not None:
        require(sha(raw) == expected, 'evidence checksum mismatch: ' + path)
    return raw


def load_inputs(root=ROOT):
    ledger = json.loads(read(root, 'docs/security-advisories.json'), object_pairs_hook=unique_object)
    prior = ledger['latest_live_source_audit']['priority_register']
    require(prior['path'] == PRIORITY, 'unexpected historical priority register')
    priority_raw = read(root, PRIORITY, prior['sha256'])
    priority = json.loads(priority_raw, object_pairs_hook=unique_object)
    regenerated = audits.priority_register(root / audits.LIVE.relative_to(audits.ROOT), root)
    require(type(priority.get('schema')) is int and priority['schema'] == 1 and
            type(regenerated.get('schema')) is int and regenerated['schema'] == 1 and regenerated == priority,
            'historical priority register does not match verified reports')
    ref = ledger['critical_reachability_evidence']
    critical_raw = read(root, ref['path'], ref['sha256'])
    critical = json.loads(critical_raw, object_pairs_hook=unique_object)
    finding = next(row for row in critical['findings'] if row['advisory_id'] == CRITICAL)
    scan_ref = finding['supplemental_source_bound_evidence']['vanilla_classpath_scan']
    scan = json.loads(read(root, scan_ref['path'], scan_ref['sha256']), object_pairs_hook=unique_object)
    mod = json.loads(read(root, MOD_REPORT, MOD_SHA), object_pairs_hook=unique_object)
    upstream = json.loads(read(root, UPSTREAM, UPSTREAM_SHA), object_pairs_hook=unique_object)
    require(upstream.get('ghsa_id') == HIGH and upstream.get('cve_id') == 'CVE-2026-45416' and
            upstream.get('severity') == 'high' and upstream.get('withdrawn_at') is None and
            {(row['package'], row['range'], row['patched']) for row in upstream['vulnerabilities']} == {
                ('io.netty:netty-handler', '<=4.1.134.Final', '4.1.135.Final'),
                ('io.netty:netty-handler', '>=4.2.0.Final, <=4.2.14.Final', '4.2.15.Final')},
            'upstream advisory ranges differ from this investigation')
    return ledger, priority, finding, scan, mod


def identity(row):
    return row['source_kind'], row['group'], row['source_sha'], row['purl']


def affected_version(version):
    match = re.fullmatch(r'4\.(1|2)\.(\d+)\.Final', version)
    require(match is not None, 'unsupported Netty version for this scoped review')
    return int(match[2]) <= (134 if match[1] == '1' else 14)


def library_catalog(high, critical):
    reviewed = {identity(row): row for row in critical['occurrences']}
    require(len(reviewed) == len(critical['occurrences']), 'duplicate prior critical occurrence')
    catalog, seen = {}, set()
    for row in high['occurrences']:
        key = identity(row)
        require(key not in seen and key in reviewed, 'missing or duplicate SNI occurrence')
        seen.add(key)
        previous = reviewed[key]
        require(row['scopes'] == previous['dependency_scopes'] and row['release_blocking'] is True and
                row['risk_accepted'] is False and row['disposition'] == 'Further investigation',
                'SNI occurrence scope or disposition differs')
        version = row['purl'].rsplit('@', 1)[1]
        require(affected_version(version), 'Netty version is outside the reviewed upstream range')
        entry = {'version': version, 'sha1': previous['dependency_artifact_sha1'],
                 'sha256': previous['dependency_artifact_sha256'],
                 'classes': previous['dependency_artifact_classes']}
        require(version not in catalog or catalog[version] == entry, 'inconsistent Netty library evidence')
        catalog[version] = entry
    require(len(seen) == 12 and len(catalog) == 6, 'incomplete High SNI coverage')
    return [catalog[key] for key in sorted(catalog)]


def inspect_library(raw, expected):
    require(hashlib.sha1(raw).hexdigest() == expected['sha1'] and sha(raw) == expected['sha256'],
            'cached Netty library checksum mismatch: ' + expected['version'])
    with ZipFile(BytesIO(raw)) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'duplicate Netty archive member')
        for cls in expected['classes']:
            require(sha(archive.read(cls['path'])) == cls['sha256'],
                    'Netty class checksum mismatch: ' + expected['version'])
    return expected


def inspect_cached_classpath_jar(cache, artifact, versions):
    path = (cache / artifact['cache_object']).resolve()
    require(path.is_relative_to(cache.resolve()), 'classpath cache path escapes cache root')
    raw = path.read_bytes()
    require(len(raw) == artifact['size_bytes'] and hashlib.sha1(raw).hexdigest() == artifact['sha1'] and
            sha(raw) == artifact['sha256'], 'cached classpath artifact checksum mismatch')
    hits, classes = [], 0
    with ZipFile(BytesIO(raw)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate classpath archive member')
        for name in sorted(name for name in names if name.endswith('.class')):
            classes += 1
            contents = archive.read(name)
            if b'SslClientHelloHandler' in contents:
                internal = name.startswith('io/netty/handler/ssl/') and any(
                    coordinate.startswith('io.netty:netty-handler:') for coordinate in artifact['coordinates'])
                hits.append({'class_file': name, 'sha256': sha(contents), 'netty_handler_internal': internal})
    require(classes == artifact['class_files_scanned'], 'classpath class count differs from prior inspection')
    return {'sha1': artifact['sha1'], 'sha256': artifact['sha256'], 'size_bytes': len(raw),
            'coordinates': artifact['coordinates'],
            'minecraft_versions': sorted(set(artifact['minecraft_versions']) & set(versions)),
            'class_files_scanned': classes, 'clienthello_name_references': hits}


def known_hit_inventory(catalog, root=ROOT):
    """Bind independently observed literal hits to the reviewed JAR catalog."""
    known = json.loads(read(root, KNOWN_HITS, KNOWN_HITS_SHA), object_pairs_hook=unique_object)
    require(known.get('schema') == 1 and known.get('security_clearance') is False and
            isinstance(known.get('libraries'), list), 'invalid known ClientHello inventory')
    libraries = {row['sha1']: row for row in catalog}
    require(len(libraries) == len(catalog) == len(known['libraries']) == 6,
            'known Netty library coverage differs')
    result = {}
    for row in known['libraries']:
        prior = libraries.get(row['sha1'])
        require(prior is not None and row['sha1'] not in result and
                row['version'] == prior['version'] and row['sha256'] == prior['sha256'],
                'known Netty library identity differs')
        recorded = {item['path']: item['sha256'] for item in prior['classes']}
        require(len(recorded) == len(prior['classes']), 'duplicate Netty catalog class')
        hits = {item['path']: item['sha256'] for item in row['literal_hits']}
        require(len(hits) == len(row['literal_hits']) and set(hits) == KNOWN_HIT_PATHS and
                all(re.fullmatch(r'[a-f0-9]{64}', value) for value in hits.values()),
                'known Netty ClientHello class inventory differs')
        require(CATALOG_HIT_PATHS <= set(recorded) and
                all(hits[path] == recorded[path] for path in CATALOG_HIT_PATHS),
                'known Netty ClientHello class digest differs from library catalog')
        result[row['sha1']] = {'version': row['version'], 'sha256': row['sha256'], 'hits': hits}
    return result


def verify_known_cached_library(raw, library, known):
    inspect_library(raw, library)
    with ZipFile(BytesIO(raw)) as archive:
        for path, expected in known['hits'].items():
            contents = archive.read(path)
            require(b'SslClientHelloHandler' in contents and sha(contents) == expected,
                    'known cached ClientHello literal or class digest differs')


def validate_base_scan(base_scan, scan, critical, versions, catalog):
    prior = critical['supplemental_source_bound_evidence']['vanilla_classpath_scan']
    require(base_scan.get('schema') == 1 and base_scan.get('security_clearance') is False and
            base_scan.get('prior_vanilla_scan') == {'path': prior['path'], 'sha256': prior['sha256']} and
            base_scan.get('minecraft_versions') == versions, 'ClientHello scan provenance differs')
    selected = [item for item in scan['runtime_classpath_scan']['all_artifacts']
                if set(item['minecraft_versions']) & set(versions)]
    expected = {item['sha1']: item for item in selected}
    rows = base_scan['artifacts']
    require(len(expected) == len(selected) == len(rows) == 471 and
            len({row['sha1'] for row in rows}) == len(rows), 'ClientHello scan coverage differs')
    known = known_hit_inventory(catalog)
    required = {(jar, path, digest) for jar, item in known.items() for path, digest in item['hits'].items()}
    internal, external, observed_known = [], [], set()
    for row in rows:
        previous = expected.get(row['sha1'])
        require(previous is not None and row['sha256'] == previous['sha256'] and
                row['size_bytes'] == previous['size_bytes'] and row['coordinates'] == previous['coordinates'] and
                row['class_files_scanned'] == previous['class_files_scanned'] and
                row['minecraft_versions'] == sorted(set(previous['minecraft_versions']) & set(versions)),
                'ClientHello artifact identity differs')
        seen_paths = set()
        for hit in row['clienthello_name_references']:
            require(hit['class_file'] not in seen_paths, 'duplicate ClientHello class observation')
            seen_paths.add(hit['class_file'])
            is_internal = hit['class_file'].startswith('io/netty/handler/ssl/') and any(
                coordinate.startswith('io.netty:netty-handler:') for coordinate in row['coordinates'])
            require(hit['netty_handler_internal'] == is_internal and
                    re.fullmatch(r'[a-f0-9]{64}', hit['sha256']), 'ClientHello reference classification differs')
            if is_internal:
                library = known.get(row['sha1'])
                require(library is not None and row['sha256'] == library['sha256'] and
                        'io.netty:netty-handler:' + library['version'] in row['coordinates'],
                        'known Netty library identity differs')
                require(hit['class_file'] in library['hits'], 'unexpected Netty ClientHello class observation')
                require(hit['sha256'] == library['hits'][hit['class_file']],
                        'known Netty ClientHello class digest differs')
                observed_known.add((row['sha1'], hit['class_file'], hit['sha256']))
            (internal if is_internal else external).append((row['sha1'], hit['class_file']))
    require(observed_known == required, 'known Netty ClientHello class missing from scan')
    require(base_scan['class_files_scanned'] == sum(row['class_files_scanned'] for row in rows) and
            base_scan['netty_handler_reference_count'] == len(internal) and
            base_scan['external_references'] == [{'artifact_sha1': jar, 'class_file': name}
                                                  for jar, name in external] and not external,
            'ClientHello scan has uncovered callers or inconsistent counts')


def bind_occurrences(high, critical, scan, mod):
    require(high['advisory_id'] == HIGH and high['severity'] == 'HIGH' and
            high['aliases'] == ['CVE-2026-45416'] and high['focused_evidence'] is None,
            'unexpected High advisory baseline')
    ranges = high['affected_ranges']['pkg:maven/io.netty/netty-handler']
    events = {(event['events'][0]['introduced'], event['events'][1]['fixed'])
              for group in ranges for event in group if event.get('type') == 'ECOSYSTEM'}
    require(events == {('0', '4.1.135.Final'), ('4.2.0.Final', '4.2.15.Final')},
            'OSV affected ranges differ from the upstream advisory')
    catalog = library_catalog(high, critical)
    old = {identity(row): row for row in critical['occurrences']}
    classpath = scan['runtime_classpath_scan']
    require(scan.get('security_clearance') is False and scan.get('risk_accepted') is False and
            scan.get('release_blocking') is True and classpath['all_artifact_sizes_and_sha1_verified'] is True and
            classpath['non_self_sni_handler_callers'] == [] and
            classpath['distinct_client_and_runtime_jars'] == len(classpath['all_artifacts']) == 612,
            'prior vanilla SNI scan does not support the stated conclusion')
    require(mod.get('security_clearance') is False, 'mod inspection claims security clearance')
    occurrences, versions = [], set()
    for row in high['occurrences']:
        previous = old[identity(row)]
        minecraft = sorted(scope.split('/', 1)[1] for scope in row['scopes'] if scope.startswith('runtime/'))
        require(minecraft == sorted(previous['minecraft_versions']) and minecraft, 'runtime version scopes differ')
        product = mod['groups'][row['group']]
        require(product['source_sha'] == row['source_sha'] and not product['nested_jar_entries'] and
                all(not cls['matches'] for cls in product['classes']), 'mod JAR evidence differs')
        clients = {item['minecraft_version']: item for item in previous['minecraft_artifacts']}
        require(set(clients) == set(minecraft), 'Minecraft client artifact coverage differs')
        for version in minecraft:
            spec = scan['source_bound_netty_handler_versions'][version]
            require(spec['coordinate'] == 'io.netty:netty-handler:' + previous['package_version'] and
                    spec['sha1'] == previous['dependency_artifact_sha1'] and
                    scan['runtime_classpath_scan']['per_minecraft_client_scan'][version]
                        ['client_sni_handler_references'] == [],
                    'Minecraft runtime or SNI scan differs: ' + version)
            client = [item for item in classpath['all_artifacts']
                      if 'minecraft-client:' + version in item['coordinates']]
            require(len(client) == 1 and client[0]['sha256'] == clients[version]['client_sha256'] and
                    client[0]['sha1'] == clients[version]['client_sha1'], 'client hash mismatch: ' + version)
        versions.update(minecraft)
        occurrences.append({**row, 'minecraft_artifacts': [clients[v] for v in minecraft],
                            'dependency_sha1': previous['dependency_artifact_sha1'],
                            'dependency_sha256': previous['dependency_artifact_sha256'],
                            'product_jar_sha256': product['jar_sha256']})
    require(len(versions) == 27 and len({(row['source_kind'], row['group']) for row in occurrences}) == 10,
            'unexpected Minecraft version or source-group coverage')
    return catalog, occurrences, sorted(versions)


def write_new(path, value):
    require(not path.exists(), 'refusing to overwrite existing evidence')
    path.parent.mkdir(parents=True, exist_ok=True)
    # Hash exactly the LF-terminated UTF-8 bytes Git retains on every platform.
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(raw)


def make_review(ledger, critical, scan, catalog, occurrences, versions, artifact_raw, base_scan_raw):
    artifact = json.loads(artifact_raw, object_pairs_hook=unique_object)
    require(artifact.get('schema') == 1 and artifact.get('observed_on') == '2026-11-22' and
            artifact.get('method') == 'Local hash verification of six cached upstream Netty JARs and their SNI class entries.' and
            artifact.get('prior_evidence_sha256') == ledger['critical_reachability_evidence']['sha256'] and
            artifact.get('libraries') == catalog and artifact.get('security_clearance') is False,
            'local artifact verification differs from prior source-bound evidence')
    base_scan = json.loads(base_scan_raw, object_pairs_hook=unique_object)
    validate_base_scan(base_scan, scan, critical, versions, catalog)
    scan_ref = critical['supplemental_source_bound_evidence']['vanilla_classpath_scan']
    review = {'schema': 1, 'advisory_id': HIGH, 'aliases': ['CVE-2026-45416'], 'severity': 'HIGH',
        'observed_on': '2026-11-22', 'analysis_base_commit': 'cf7f850a618a02321c9b3d27b3e9ba13c03b2792',
        'upstream_advisory': {'path': UPSTREAM, 'sha256': UPSTREAM_SHA},
        'baseline_priority_register': ledger['latest_live_source_audit']['priority_register'],
        'prior_critical_evidence': {'path': ledger['critical_reachability_evidence']['path'],
            'sha256': ledger['critical_reachability_evidence']['sha256']},
        'prior_vanilla_classpath_scan': {'path': scan_ref['path'], 'sha256': scan_ref['sha256']},
        'clienthello_classpath_scan': {'path': BASE_SCAN, 'sha256': sha(base_scan_raw)},
        'product_jar_inspection': {'path': MOD_REPORT, 'sha256': MOD_SHA},
        'local_artifact_verification': {'path': ARTIFACTS, 'sha256': sha(artifact_raw)},
        'affected_component': 'Minecraft-managed io.netty:netty-handler SNI and ClientHello processing',
        'upstream_fixed_versions': {'4.1.x': '4.1.135.Final', '4.2.x': '4.2.15.Final'},
        'occurrence_count': len(occurrences),
        'source_group_count': len({(row['source_kind'], row['group']) for row in occurrences}),
        'minecraft_version_count': len(versions), 'minecraft_versions': versions,
        'occurrences': occurrences,
        'reachability': 'The retained exact vanilla client and default Java runtime classpaths contain '
            'no non-Netty SniHandler name references. The new hash-verified scan of the affected classpaths '
            'found no external SslClientHelloHandler name references. The mod JAR scan found no selected direct literal '
            'references. Selected dedicated-management bytecode uses SslHandler directly. These are '
            'bounded static observations, not proof about launchers, mods, agents, generated names or all server distributions.',
        'input_boundary': 'Exposure requires a component to install an affected SNI/ClientHello handler or subclass and accept '
            'untrusted TLS handshake input. That path is not established in the inspected vanilla client classpaths.',
        'remediation': 'Request a compatible Minecraft-managed Netty update; do not replace game libraries '
            'from this mod. The higher-severity SNI advisory requires later fixed versions in each line.',
        'upstream_examples': {'26.2': scan['source_bound_netty_handler_versions']['26.2']['coordinate'],
                              '26.3': scan['source_bound_netty_handler_versions']['26.3']['coordinate']},
        'limitations': ['No supported launcher, Fabric runtime, third-party mod set or agent was observed.',
            'The prior classpath scan is static and does not exclude generated or indirect behavior.',
            'No remote test or reproduction of this High advisory was performed.',
            'A compatible update for affected older Minecraft versions is not verified.'],
        'reviewer': 'Codex automated static investigation; human security review pending',
        'responsible_owner': 'Project maintainer and upstream Minecraft/library owners',
        'review_date': '2026-11-22', 'disposition': 'Further investigation',
        'follow_up_requirements': ['Observe supported launcher, Fabric and representative modded pipelines.',
            'Verify a compatible upstream game update covering this and the Critical SNI advisory.'],
        'release_blocking': True, 'risk_accepted': False, 'security_clearance': False}
    require(review['upstream_examples'] == {'26.2': 'io.netty:netty-handler:4.2.15.Final',
            '26.3': 'io.netty:netty-handler:4.2.16.Final'}, 'unexpected later game versions')
    return review


def make_current_register(priority, review, review_raw):
    require(type(priority.get('schema')) is int and priority['schema'] == 1,
            'unsupported priority schema for retained SNI evidence')
    updated = copy.deepcopy(priority)
    entry = next(row for row in updated['advisories'] if row['advisory_id'] == HIGH)
    require(entry['focused_evidence'] is None and len(entry['occurrences']) == review['occurrence_count'] == 12,
            'High SNI baseline is already focused or has changed')
    entry.update(focused_evidence=REVIEW, reviewer=review['reviewer'], review_date=review['review_date'],
                 responsible_owner=review['responsible_owner'], follow_up=review['follow_up_requirements'])
    updated['supplementary_focused_evidence'] = {'path': REVIEW, 'sha256': sha(review_raw),
        'new_advisory_ids': 1, 'new_high_occurrences': 12}
    updated['review_status'] = 'Adds a bounded High SNI investigation; no finding is cleared or risk accepted.'
    focused = [row for row in updated['advisories'] if row['focused_evidence']]
    critical = sum(len(row['occurrences']) for row in focused if row['severity'] == 'CRITICAL')
    high = sum(len(row['occurrences']) for row in focused if row['severity'] == 'HIGH')
    all_high = sum(len(row['occurrences']) for row in updated['advisories'] if row['severity'] == 'HIGH')
    updated['focused_coverage'] = {'advisory_ids': len(focused), 'critical_occurrences': critical,
        'high_occurrences': high, 'total_occurrences': critical + high,
        'high_occurrences_without_focused_evidence': all_high - high}
    require(updated['focused_coverage'] == {'advisory_ids': 21, 'critical_occurrences': 22,
        'high_occurrences': 83, 'total_occurrences': 105, 'high_occurrences_without_focused_evidence': 94},
        'unexpected focused advisory coverage')
    return updated


def validate_outputs(priority, review_raw, current_raw, expected_review):
    review = json.loads(review_raw, object_pairs_hook=unique_object)
    require(review == expected_review, 'High SNI review does not match source-bound evidence')
    current = json.loads(current_raw, object_pairs_hook=unique_object)
    require(current == make_current_register(priority, review, review_raw),
            'current priority register does not match source-bound review')


def validate_ledger_reference(ledger, current_raw):
    ref = ledger.get('latest_focused_priority_register')
    coverage = json.loads(current_raw, object_pairs_hook=unique_object)['focused_coverage']
    require(isinstance(ref, dict) and ref.get('path') == CURRENT and ref.get('sha256') == sha(current_raw) and
            ref.get('advisory_ids') == coverage['advisory_ids'] and
            ref.get('focused_occurrences') == coverage['total_occurrences'] and
            ref.get('remaining_unfocused_high_occurrences') == coverage['high_occurrences_without_focused_evidence'] and
            ref.get('security_clearance') is False, 'current priority ledger reference differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--inspect-cache', type=Path, help='verify SHA-1-keyed Netty library cache')
    mode.add_argument('--verify-known-hits-cache', type=Path, help='recheck known ClientHello literal hits in cached JARs')
    mode.add_argument('--scan-clienthello-cache', type=Path, help='scan hash-verified cached client/runtime JARs')
    mode.add_argument('--write-review', action='store_true')
    args = parser.parse_args()
    try:
        ledger, priority, critical, scan, mod = load_inputs()
        high = next(row for row in priority['advisories'] if row['advisory_id'] == HIGH)
        catalog, occurrences, versions = bind_occurrences(high, critical, scan, mod)
        if args.inspect_cache:
            for row in catalog:
                inspect_library((args.inspect_cache / row['sha1']).read_bytes(), row)
            write_new(ROOT / ARTIFACTS, {'schema': 1, 'observed_on': '2026-11-22',
                'method': 'Local hash verification of six cached upstream Netty JARs and their SNI class entries.',
                'prior_evidence_sha256': ledger['critical_reachability_evidence']['sha256'],
                'libraries': catalog, 'security_clearance': False})
            print('Verified six Netty JARs and their SNI class hashes locally')
        elif args.verify_known_hits_cache:
            known = known_hit_inventory(catalog)
            for row in catalog:
                verify_known_cached_library((args.verify_known_hits_cache / row['sha1']).read_bytes(), row,
                                            known[row['sha1']])
            print('Verified 18 known literal-bearing class entries in six Netty JARs; no reachability is implied')
        elif args.scan_clienthello_cache:
            selected = [item for item in scan['runtime_classpath_scan']['all_artifacts']
                        if set(item['minecraft_versions']) & set(versions)]
            with ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(lambda item: inspect_cached_classpath_jar(args.scan_clienthello_cache, item, versions),
                                     selected))
            external = [{'artifact_sha1': row['sha1'], 'class_file': hit['class_file']}
                        for row in rows for hit in row['clienthello_name_references']
                        if not hit['netty_handler_internal']]
            prior = critical['supplemental_source_bound_evidence']['vanilla_classpath_scan']
            result = {'schema': 1, 'observed_on': '2026-11-22',
                      'prior_vanilla_scan': {'path': prior['path'], 'sha256': prior['sha256']},
                      'minecraft_versions': versions, 'artifacts': rows,
                      'class_files_scanned': sum(row['class_files_scanned'] for row in rows),
                      'netty_handler_reference_count': sum(hit['netty_handler_internal'] for row in rows
                                                            for hit in row['clienthello_name_references']),
                      'external_references': external, 'security_clearance': False}
            validate_base_scan(result, scan, critical, versions, catalog)
            write_new(ROOT / BASE_SCAN, result)
            print('Scanned ' + str(len(rows)) + ' hash-verified JARs; external ClientHello name references: ' + str(len(external)))
        elif args.write_review:
            artifact_raw = read(ROOT, ARTIFACTS)
            base_scan_raw = read(ROOT, BASE_SCAN)
            review = make_review(ledger, critical, scan, catalog, occurrences, versions, artifact_raw, base_scan_raw)
            write_new(ROOT / REVIEW, review)
            review_raw = read(ROOT, REVIEW)
            updated = make_current_register(priority, review, review_raw)
            write_new(ROOT / CURRENT, updated)
            print('Recorded 12 blocking High occurrences and updated focused coverage')
        else:
            artifact_raw = read(ROOT, ARTIFACTS)
            base_scan_raw = read(ROOT, BASE_SCAN)
            review_raw = read(ROOT, REVIEW)
            current_raw = read(ROOT, CURRENT)
            expected = make_review(ledger, critical, scan, catalog, occurrences, versions, artifact_raw, base_scan_raw)
            validate_outputs(priority, review_raw, current_raw, expected)
            validate_ledger_reference(ledger, current_raw)
            print('Validated source and artifact bindings for 12 blocking High occurrences')
        return 0
    except (OSError, ValueError, KeyError, StopIteration, TypeError, BadZipFile) as exc:
        print('High SNI investigation incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
