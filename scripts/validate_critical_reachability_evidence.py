#!/usr/bin/env python3
"""Validate source-bound Issue #45 reachability observations and hashes."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
EVIDENCE = BASE / 'source-bound-dispositions-2026-11-21.json'
LEDGER = ROOT / 'docs/security-advisories.json'
DIGEST = re.compile(r'^[0-9a-f]{64}$')
TARGET_COUNTS = {
    'GHSA-c4c3-7fpv-j4q5': 14,
    'GHSA-jfh8-c2jp-5v3q': 3,
    'GHSA-7rjr-3q55-vv33': 3,
    'GHSA-fxph-q3j8-mv87': 2,
    'GHSA-pwqr-wmgm-9rr8': 3,
    'GHSA-mcr4-qmvw-px4g': 8,
    'GHSA-xqfj-vm6h-2x34': 3,
    'GHSA-7hfm-57qf-j43q': 3,
    'GHSA-crv7-7245-f45f': 3,
    'GHSA-mc84-pj99-q6hh': 3,
    'GHSA-7hhh-6rmp-j9qf': 3,
    'GHSA-cxp5-3px4-pw24': 3,
    'GHSA-h46c-h94j-95f3': 3,
    'GHSA-j3rv-43j4-c7qm': 3,
    'GHSA-r7wm-3cxj-wff9': 3,
    'GHSA-rmj7-2vxq-3g9f': 3,
    'GHSA-wv8q-qhhj-9h54': 3,
    'GHSA-xxph-c9ww-hj94': 16,
    'GHSA-cmp6-m4wj-q63q': 6,
    'GHSA-vqf4-7m7x-wgfc': 5,
}


def fail(message):
    raise ValueError(message)


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def validate():
    evidence = load(EVIDENCE)
    archive_index = load(ARCHIVE / 'archive-index.json')
    finding_index = load(ARCHIVE / 'finding-index.json')
    if evidence.get('schema') != 1 or evidence.get('security_clearance') is not False:
        fail('invalid evidence schema or clearance claim')
    if evidence.get('risk_accepted') is not False:
        fail('risk acceptance must remain false')
    if evidence['source_provenance']['archive_report_hashes_verified'] != len(archive_index['files']):
        fail('archive verification count mismatch')
    if evidence['source_provenance']['finding_records_hashes_and_source_identities_verified'] != len(finding_index['records']):
        fail('finding verification count mismatch')
    if evidence['source_provenance']['finding_index']['sha256'] != raw_hash(ARCHIVE / 'finding-index.json'):
        fail('finding-index hash mismatch')
    if evidence['source_provenance']['archive_index']['sha256'] != raw_hash(ARCHIVE / 'archive-index.json'):
        fail('archive-index hash mismatch')

    for item in archive_index['files']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ARCHIVE.resolve()) or not path.is_file():
            fail('missing or out-of-archive report: ' + item['path'])
        packed = path.read_bytes()
        raw = gzip.decompress(packed)
        if hashlib.sha256(packed).hexdigest() != item['sha256_gzip']:
            fail('compressed archive checksum mismatch: ' + item['path'])
        if hashlib.sha256(raw).hexdigest() != item['sha256_uncompressed']:
            fail('uncompressed archive checksum mismatch: ' + item['path'])
        document = json.loads(raw)
        if '/dependency-graph-reports/' in item['path']:
            source = document.get('sha')
        else:
            source = document.get('source_sha')
        if source != item['source_sha']:
            fail('archive source identity mismatch: ' + item['path'])

    indexed = {(row['advisory'], row['group'], row['source_kind'], row['purl']): row
               for row in finding_index['records']}
    reports = {}
    for row in finding_index['records']:
        report_path = ROOT / row['report']
        if row['report'] not in reports:
            report_bytes = gzip.decompress(report_path.read_bytes())
            reports[row['report']] = (hashlib.sha256(report_bytes).hexdigest(), json.loads(report_bytes))
        digest, report = reports[row['report']]
        if digest != row['report_sha256_uncompressed'] or report.get('source_sha') != row['source_sha']:
            fail('finding index report checksum or source mismatch: ' + row['report'])
    seen = {}
    for finding in evidence.get('findings', []):
        advisory = finding['advisory_id']
        if advisory in seen:
            fail('duplicate advisory evidence: ' + advisory)
        seen[advisory] = finding
        occurrences = finding['occurrences']
        if len(occurrences) != TARGET_COUNTS.get(advisory):
            fail('wrong occurrence count for ' + advisory)
        if finding.get('release_blocking') is not True or finding.get('risk_accepted') is not False:
            fail('targeted advisory must remain blocking: ' + advisory)
        for row in occurrences:
            key = (advisory, row['group'], row['source_kind'], row['purl'])
            match = indexed.get(key)
            if match is None:
                fail('source occurrence not found in exact-source index: ' + str(key))
            for field in ('source_sha', 'scopes', 'fingerprint', 'severity', 'disposition'):
                actual = row['source_sha'] if field == 'source_sha' else (
                    row['dependency_scopes'] if field == 'scopes' else row[field])
                if actual != match[field]:
                    fail(f'{field} mismatch for {row["group"]} {advisory}')
            if row.get('failing') is not True or row.get('release_blocking') is not True or row.get('risk_accepted') is not False:
                fail('target occurrence is not retained as a blocking failure')
            report_path = ROOT / row['source_report']['path']
            report_bytes = gzip.decompress(report_path.read_bytes())
            if hashlib.sha256(report_bytes).hexdigest() != row['source_report']['sha256_uncompressed']:
                fail('source report checksum mismatch')
            if json.loads(report_bytes).get('source_sha') != row['source_sha']:
                fail('source report SHA mismatch')
    if set(seen) != set(TARGET_COUNTS):
        fail('targeted advisory set mismatch')

    expected_counts = {'candidate': {}, 'integrated': {}}
    for kind in expected_counts:
        rows = [row for row in finding_index['records'] if row['source_kind'] == kind]
        expected_counts[kind] = {
            'occurrences': len(rows),
            'severity_occurrences': {severity: sum(row['severity'] == severity for row in rows)
                                     for severity in ('CRITICAL', 'HIGH', 'MODERATE', 'LOW')},
            'distinct_package_version_advisory_pairs': len({(row['purl'], row['advisory']) for row in rows}),
            'distinct_advisory_ids': len({row['advisory'] for row in rows}),
        }
    if evidence['current_counts'] != expected_counts:
        fail('candidate or integrated advisory counts changed')
    if evidence['occurrences_total'] != len(finding_index['records']):
        fail('total finding count changed')

    for item in evidence['supporting_evidence']:
        path = (ROOT / item['path']).resolve()
        if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
            fail('missing or out-of-repository evidence: ' + item['path'])
        if raw_hash(path) != item['sha256']:
            fail('supporting evidence hash mismatch: ' + item['path'])
        if item.get('sha256_uncompressed'):
            if hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() != item['sha256_uncompressed']:
                fail('uncompressed evidence hash mismatch: ' + item['path'])
    commons_path = BASE / 'commons-compress-reachability-2026-11-21.json'
    commons = load(commons_path)
    if commons['source_provenance']['finding_index']['sha256'] != raw_hash(ARCHIVE / 'finding-index.json'):
        fail('Commons Compress reachability record is not bound to the finding index')
    high_family_path = BASE / 'high-family-inspection.json.gz'
    if commons['source_provenance']['high_family_inspection']['sha256'] != raw_hash(high_family_path):
        fail('Commons Compress record has stale high-family evidence')
    high_family = json.loads(gzip.decompress(high_family_path.read_bytes()))
    compress = [row for row in high_family['libraries']
                if 'org.apache.commons:commons-compress:1.8.1' in row.get('coordinates', [])]
    if len(compress) != 1 or commons['package']['sha256'] != compress[0]['sha256'] or \
            commons['package']['sha1'] != compress[0]['artifact']['sha1']:
        fail('Commons Compress artifact identity mismatch')
    expected_sources = {(row['source_kind'], row['group'], row['source_sha'])
                        for row in finding_index['records']}
    build_sources = commons['build_gradle_control_assessment']['sources']
    actual_build_sources = {(row['source_kind'], row['group'], row['source_sha'])
                            for row in build_sources}
    if actual_build_sources != expected_sources or any(
            not re.fullmatch(r'[0-9a-f]{40}', row.get('build_gradle_blob_sha', ''))
            for row in build_sources):
        fail('Commons Compress build.gradle source bindings mismatch')
    for row in build_sources:
        declarations = ' '.join(row['dependency_declarations']).lower()
        if any(token in declarations for token in ('commons-compress', 'netty', 'log4j', 'jackson', 'guava', 'lz4')):
            fail('source build.gradle declares a focused game-managed library')
    if set(row['advisory_id'] for row in commons['findings']) != {
            'GHSA-xqfj-vm6h-2x34', 'GHSA-7hfm-57qf-j43q',
            'GHSA-crv7-7245-f45f', 'GHSA-mc84-pj99-q6hh'}:
        fail('Commons Compress focused advisory set mismatch')
    if any(seen.get(row['advisory_id']) != row for row in commons['findings']):
        fail('Commons Compress record differs from source-bound dispositions')
    for finding in commons['findings']:
        target = finding['vulnerable_api_or_class']
        for occurrence in finding['occurrences']:
            for observation in occurrence['client_vulnerable_api_reference_observations']:
                game = high_family['games'].get(observation['minecraft_version'])
                if game is None or observation['classes'] != game['literal_reference_matches'].get(target, []):
                    fail('Commons Compress client reference evidence mismatch for ' + target)
            if occurrence.get('dependency_owner') != 'Minecraft runtime manifest':
                fail('Commons Compress dependency owner is not source-bound to Minecraft')
    expected_realms = {
        '1.14': '1.14.14', '1.14.1': '1.14.15',
        '1.14.2': '1.14.16', '1.14.3': '1.14.17',
    }
    runtime_rows = commons.get('additional_runtime_library_callers', [])
    if {row['minecraft_version'] for row in runtime_rows} != set(expected_realms):
        fail('Mojang Realms TAR caller observations do not cover Minecraft 1.14.0-1.14.3')
    for observation in runtime_rows:
        version = observation['minecraft_version']
        coordinate = 'com.mojang:realms:' + expected_realms[version]
        matches = [row for row in high_family['libraries']
                   if coordinate in row.get('coordinates', []) and version in row.get('versions', [])]
        if len(matches) != 1:
            fail('Mojang Realms runtime artifact missing for Minecraft ' + version)
        library = matches[0]
        artifact = library['artifact']
        if observation['coordinate'] != coordinate or observation['artifact'] != artifact or \
                observation['artifact_sha256'] != library['sha256'] or \
                observation['literal_reference_matches'] != library['literal_reference_matches'].get(
                    'org/apache/commons/compress/archivers/tar/TarArchiveInputStream', []):
            fail('Mojang Realms caller artifact/reference mismatch for Minecraft ' + version)
        if observation['literal_reference_matches'] != ['realms/c.class'] or \
                observation['class_sha256'] != 'f3eb2f48eb3b81b43f84cb8e67961f7f52ea9f39a3bbe9ebf4dd3fd516d50ee0':
            fail('Mojang Realms TAR class identity mismatch for Minecraft ' + version)
        if not DIGEST.fullmatch(observation.get('artifact_sha256', '')) or \
                not all(DIGEST.fullmatch(row.get('sha256', ''))
                        for row in observation.get('related_call_path_classes', [])):
            fail('Mojang Realms artifact or caller class hash is incomplete for Minecraft ' + version)
    tar_finding = next(row for row in commons['findings']
                       if row['advisory_id'] == 'GHSA-xqfj-vm6h-2x34')
    for occurrence in tar_finding['occurrences']:
        expected_versions = set(occurrence['minecraft_versions']) & set(expected_realms)
        actual_observations = occurrence.get('runtime_library_vulnerable_api_reference_observations', [])
        if {row['minecraft_version'] for row in actual_observations} != expected_versions:
            fail('Mojang Realms callsite coverage mismatch for ' + occurrence['group'])
        for observation in actual_observations:
            runtime = next(row for row in runtime_rows
                           if row['minecraft_version'] == observation['minecraft_version'])
            for field in ('coordinate', 'artifact', 'artifact_sha256', 'literal_reference_matches',
                          'class_sha256', 'class_path'):
                if observation.get(field) != runtime.get(field):
                    fail('Mojang Realms source-bound observation mismatch for ' + field)
    if set(commons['reachability_scope']['tar_parser_reference_versions']) != \
            set(commons['package']['runtime_minecraft_versions']):
        fail('combined client and Mojang Realms TAR reference version list mismatch')
    client_versions = set(commons['reachability_scope']['game_client_tar_parser_reference_versions'])
    runtime_versions = set(commons['reachability_scope']['realms_runtime_library_tar_parser_reference_versions'])
    expected_runtime_versions = set(expected_realms)
    expected_client_versions = set(commons['package']['runtime_minecraft_versions']) - expected_runtime_versions
    if runtime_versions != expected_runtime_versions or client_versions != expected_client_versions or \
            set(commons['reachability_scope']['game_client_versions_without_direct_tar_parser_reference']) != expected_runtime_versions:
        fail('client versus Mojang Realms TAR caller scope mismatch')
    tar_api = 'org/apache/commons/compress/archivers/tar/TarArchiveInputStream'
    for version in expected_client_versions:
        game = high_family['games'].get(version)
        if game is None or not game['literal_reference_matches'].get(tar_api):
            fail('expected game-client TAR parser caller missing for Minecraft ' + version)
    for version in expected_runtime_versions:
        game = high_family['games'].get(version)
        if game is None or game['literal_reference_matches'].get(tar_api):
            fail('unexpected game-client TAR parser literal for Minecraft ' + version)
    log4j_path = BASE / 'log4j-chat-input-reachability-2026-11-21.json'
    log4j = load(log4j_path)
    if log4j.get('security_clearance') is not False or log4j.get('risk_accepted') is not False or \
            log4j.get('release_blocking') is not True:
        fail('Log4j chat-path evidence must remain unresolved and blocking')
    if set(log4j.get('advisory_ids', [])) != {
            'GHSA-jfh8-c2jp-5v3q', 'GHSA-7rjr-3q55-vv33', 'GHSA-fxph-q3j8-mv87'}:
        fail('Log4j chat-path advisory scope mismatch')
    if log4j['source_provenance']['finding_index']['sha256'] != raw_hash(ARCHIVE / 'finding-index.json') or \
            log4j['source_provenance']['high_family_inspection']['sha256'] != raw_hash(high_family_path):
        fail('Log4j chat-path observation is not bound to exact source/artifact indexes')
    chat_probe_path = BASE / 'log4j-chat-parameter-probes-2026-11-21.json'
    chat_probe = load(chat_probe_path)
    if log4j['source_provenance']['new_parameterized_chat_probe_report']['sha256'] != raw_hash(chat_probe_path) or \
            chat_probe.get('passed') is not True or len(chat_probe.get('cases', [])) != 34:
        fail('parameterized Log4j chat probe report is missing or incomplete')
    expected_chat_cases = {
        '2.8.1-launcher-chat-jndi': 0,
        '2.8.1-launcher-chat-jndi-core-first': 0,
        '2.8.1-1.14.4-embedded.xml-chat-jndi': 0,
        '2.8.1-1.14.4-embedded.xml-chat-jndi-core-first': 2,
        '2.14.1-launcher-chat-jndi': 0,
        '2.14.1-1.18.1-embedded.xml-chat-jndi': 2,
    }
    actual_chat_cases = {row['name']: row for row in chat_probe['cases'] if 'chat-jndi' in row['name']}
    if set(actual_chat_cases) != set(expected_chat_cases):
        fail('parameterized chat JNDI probe case set mismatch')
    for name, calls in expected_chat_cases.items():
        row = actual_chat_cases[name]
        if row.get('passed') is not True or row.get('observed', {}).get('NO_NETWORK_CONTEXT_CALLS') != calls:
            fail('parameterized chat JNDI probe result mismatch for ' + name)
    if log4j.get('parameterized_chat_probe', {}).get('all_expected_results_passed') is not True:
        fail('Log4j chat-path summary does not retain its blocking local probe results')
    expected_log4j_groups = {(row['group'], row['source_sha']) for row in finding_index['records']
                             if row['advisory'] == 'GHSA-jfh8-c2jp-5v3q' and row['source_kind'] == 'candidate'}
    actual_log4j_groups = {(row['group'], row['source_sha']) for row in log4j['source_group_bindings']}
    if actual_log4j_groups != expected_log4j_groups:
        fail('Log4j chat-path source group/SHA coverage mismatch')
    for row in log4j['source_group_bindings']:
        binding = indexed.get(('GHSA-jfh8-c2jp-5v3q', row['group'], 'candidate', row['purl']))
        if binding is None or row['source_sha'] != binding['source_sha'] or \
                row['package_version'] != row['purl'].rsplit('@', 1)[1] or \
                row['dependency_artifact_sha256'] != next(
                    occurrence['dependency_artifact_sha256']
                    for occurrence in seen['GHSA-jfh8-c2jp-5v3q']['occurrences']
                    if occurrence['group'] == row['group']):
            fail('Log4j chat-path dependency owner/version evidence mismatch')
        expected_advisories = sorted(record['advisory'] for record in finding_index['records']
                                     if record['source_kind'] == 'candidate' and
                                     record['group'] == row['group'] and record['source_sha'] == row['source_sha'] and
                                     record['advisory'] in ('GHSA-jfh8-c2jp-5v3q',
                                                            'GHSA-7rjr-3q55-vv33',
                                                            'GHSA-fxph-q3j8-mv87'))
        if row['advisory_occurrences'] != expected_advisories:
            fail('Log4j chat-path advisory binding mismatch for ' + row['group'])
    for sample in log4j['exact_client_code_path_samples']:
        version = sample['minecraft_version']
        game = high_family['games'].get(version)
        if game is None or sample['client_sha256'] != game['client_sha256'] or \
                sample['version_metadata_sha1'] != game['metadata_sha1'] or \
                sample['official_version_metadata_logging'] != game['logging']['client'] or \
                sample['embedded_log4j2_xml_sha256'] != game['embedded_log4j2_sha256']:
            fail('Log4j client/version metadata binding mismatch for Minecraft ' + version)
        group = sample['source_group']
        source_row = next((row for row in log4j['source_group_bindings'] if row['group'] == group), None)
        if source_row is None or sample['source_sha'] != source_row['source_sha'] or \
                sample['source_kind'] != source_row['source_kind']:
            fail('Log4j client observation source binding mismatch for Minecraft ' + version)
        coordinate = sample['log4j_core_coordinate']
        library = [row for row in high_family['libraries']
                   if coordinate in row.get('coordinates', []) and version in row.get('versions', [])]
        if len(library) != 1 or sample['log4j_core_artifact'] != library[0]['artifact'] or \
                sample['log4j_core_sha256'] != library[0]['sha256']:
            fail('Log4j Core manifest artifact binding mismatch for Minecraft ' + version)
        patchy = [row for row in high_family['libraries']
                  if sample['patchy_coordinate'] in row.get('coordinates', []) and
                  version in row.get('versions', [])]
        if len(patchy) != 1 or sample['patchy_artifact'] != patchy[0]['artifact'] or \
                sample['patchy_sha256'] != patchy[0]['sha256'] or \
                sample['manifest_runtime_library_order'] != game['relevant_library_order']:
            fail('Log4j Patchy/classpath evidence mismatch for Minecraft ' + version)
        if {row['role'] for row in sample['class_observations']} != {'packet', 'listener', 'chat_component'} or \
                any(not DIGEST.fullmatch(row.get('class_sha256', '')) for row in sample['class_observations']):
            fail('Log4j chat caller class hashes are incomplete for Minecraft ' + version)
    for advisory in ('GHSA-jfh8-c2jp-5v3q', 'GHSA-7rjr-3q55-vv33', 'GHSA-fxph-q3j8-mv87'):
        finding = seen[advisory]
        references = finding.get('supplemental_source_bound_evidence', [])
        if references != [{'path': log4j_path.relative_to(ROOT).as_posix(), 'sha256': raw_hash(log4j_path)}]:
            fail('Log4j finding lacks current supplemental chat-path evidence for ' + advisory)

    upstream_path = BASE / 'upstream-critical-high.json.gz'
    jackson_path = BASE / 'jackson-msal-runtime-reachability-2026-11-22.json'
    jackson = load(jackson_path)
    jackson_ids = {
        'GHSA-7hhh-6rmp-j9qf', 'GHSA-cxp5-3px4-pw24', 'GHSA-h46c-h94j-95f3',
        'GHSA-j3rv-43j4-c7qm', 'GHSA-r7wm-3cxj-wff9', 'GHSA-rmj7-2vxq-3g9f',
        'GHSA-wv8q-qhhj-9h54',
    }
    if jackson.get('security_clearance') is not False or jackson.get('risk_accepted') is not False or \
            jackson.get('release_blocking') is not True or jackson.get('findings_remain_blocking') is not True:
        fail('Jackson/MSAL reachability evidence must remain unresolved and blocking')
    if set(jackson.get('advisories', {})) != jackson_ids or \
            jackson.get('source_provenance', {}).get('finding_index', {}).get('sha256') != raw_hash(ARCHIVE / 'finding-index.json') or \
            jackson.get('source_provenance', {}).get('high_family_inspection', {}).get('sha256') != raw_hash(high_family_path) or \
            jackson.get('source_provenance', {}).get('upstream_advisory_archive', {}).get('sha256') != raw_hash(BASE / 'upstream-critical-high.json.gz'):
        fail('Jackson/MSAL evidence is stale or has the wrong advisory/index scope')
    logging_capture = jackson.get('source_provenance', {}).get('official_minecraft_logging_configuration', {})
    logging_path = ROOT / logging_capture.get('path', '')
    if not logging_path.is_file() or raw_hash(logging_path) != logging_capture.get('sha256') or \
            hashlib.sha1(logging_path.read_bytes()).hexdigest() != logging_capture.get('sha1') or \
            len(logging_path.read_bytes()) != logging_capture.get('size'):
        fail('Jackson/Log4j external logging configuration source hash mismatch')
    logging_text = logging_path.read_text()
    if '<LegacyXMLLayout' not in logging_text or '<PatternLayout' not in logging_text or \
            '<JsonLayout' in logging_text or '<YamlLayout' in logging_text or 'SocketServer' in logging_text:
        fail('Mojang default logging configuration no longer matches the recorded XML/pattern layouts')
    if len(jackson.get('source_occurrences', [])) != 21 or jackson['scope'].get('occurrences') != 21 or \
            set(jackson['scope'].get('source_groups', [])) != {'1.21.2-1.21.3', '1.21.4-1.21.8', '1.21.9-1.21.10'}:
        fail('Jackson/MSAL source occurrence coverage mismatch')
    jackson_source_rows = [row for row in finding_index['records'] if row['advisory'] in jackson_ids]
    if len(jackson_source_rows) != 21:
        fail('Jackson findings are not represented by 21 exact-source index rows')
    jackson_bindings = {(row['advisory_id'], row['source_kind'], row['group'], row['purl']): row
                        for row in jackson.get('source_occurrences', [])}
    if len(jackson_bindings) != 21:
        fail('duplicate Jackson source occurrence binding')
    for row in jackson_source_rows:
        key = (row['advisory'], row['source_kind'], row['group'], row['purl'])
        binding = jackson_bindings.get(key)
        runtime_versions = sorted(scope.removeprefix('runtime/') for scope in row['scopes']
                                  if scope.startswith('runtime/'))
        if binding is None or row['source_kind'] != 'candidate' or \
                binding.get('source_sha') != row['source_sha'] or \
                binding.get('runtime_versions') != runtime_versions or \
                binding.get('source_report_sha256_uncompressed') != row['report_sha256_uncompressed'] or \
                binding.get('finding_fingerprint') != row['fingerprint'] or \
                binding.get('purl') != row['purl']:
            fail('Jackson occurrence is not bound to its exact candidate source/report: ' + str(key))
    version_rows = {row['minecraft_version']: row for row in jackson.get('minecraft_versions', [])}
    jackson_versions = ['1.21.2', '1.21.3', '1.21.4', '1.21.5', '1.21.6',
                        '1.21.7', '1.21.8', '1.21.9', '1.21.10']
    if set(version_rows) != set(jackson_versions):
        fail('Jackson Minecraft artifact coverage does not cover 1.21.2-1.21.10')
    official_versions_path = BASE / 'upstream-minecraft-metadata/version_manifest_v2.json'
    official_versions = load(official_versions_path)
    manifest_reference = jackson.get('source_provenance', {}).get('official_minecraft_version_manifest', {})
    if manifest_reference.get('sha256') != raw_hash(official_versions_path) or \
            manifest_reference.get('path') != official_versions_path.relative_to(ROOT).as_posix():
        fail('Jackson source report is not bound to the captured official version manifest')
    manifest_versions = {row['id']: row for row in official_versions['versions']}
    jackson_high_family = json.loads(gzip.decompress(high_family_path.read_bytes()))
    jackson_libraries = {coordinate: row for row in jackson_high_family['libraries']
                         for coordinate in row.get('coordinates', [])}
    expected_groups = {
        '1.21.2': '1.21.2-1.21.3', '1.21.3': '1.21.2-1.21.3',
        '1.21.4': '1.21.4-1.21.8', '1.21.5': '1.21.4-1.21.8',
        '1.21.6': '1.21.4-1.21.8', '1.21.7': '1.21.4-1.21.8',
        '1.21.8': '1.21.4-1.21.8', '1.21.9': '1.21.9-1.21.10',
        '1.21.10': '1.21.9-1.21.10',
    }
    for version, observation in version_rows.items():
        metadata_path = ROOT / observation['version_metadata']['path']
        metadata = load(metadata_path)
        manifest = manifest_versions.get(version)
        group = expected_groups[version]
        source_sha = next(row['source_sha'] for row in jackson_source_rows
                          if row['source_kind'] == 'candidate' and row['group'] == group)
        game = jackson_high_family['games'].get(version)
        if manifest is None or hashlib.sha1(metadata_path.read_bytes()).hexdigest() != manifest['sha1'] or \
                observation['version_metadata'].get('sha256') != raw_hash(metadata_path) or \
                observation['version_metadata'].get('url') != manifest['url'] or \
                observation['version_metadata'].get('id') != version or \
                observation.get('source_group') != group or observation.get('source_sha') != source_sha or \
                observation.get('source_kind') != 'candidate' or game is None or \
                observation.get('metadata_sha1_in_high_family') != manifest['sha1']:
            fail('Jackson version metadata/source binding mismatch for Minecraft ' + version)
        client = metadata['downloads']['client']
        mappings = metadata['downloads']['client_mappings']
        client_observation = observation['client_artifact']
        mappings_observation = observation['client_mappings']
        if any(client_observation.get(field) != client.get(field) for field in ('url', 'sha1', 'size')) or \
                client_observation.get('sha256') != game['client_sha256'] or \
                game.get('client', {}).get('sha1') != client['sha1'] or \
                game.get('client', {}).get('size') != client['size'] or \
                client_observation.get('sha1_and_size_verified') is not True:
            fail('Jackson client binary is not bound to Mojang metadata/high-family hash for ' + version)
        if any(mappings_observation.get(field) != mappings.get(field) for field in ('url', 'sha1', 'size')) or \
                not DIGEST.fullmatch(mappings_observation.get('sha256', '')) or \
                mappings_observation.get('sha1_and_size_verified') is not True:
            fail('Jackson official mapping artifact identity mismatch for ' + version)
        if set(observation.get('class_observations', {})) != {
                'player_safety_filter', 'server_text_filter', 'dedicated_server',
                'dedicated_server_properties', 'minecraft_server', 'integrated_server',
                'text_filter_interface'}:
            fail('Jackson client class observations incomplete for ' + version)
        for class_observation in observation['class_observations'].values():
            if not DIGEST.fullmatch(class_observation.get('sha256', '')):
                fail('Jackson client class hash missing for Minecraft ' + version)
        relationships = observation['constant_pool_relationships']
        if relationships.get('player_safety_superclass_is_server_text_filter') is not True or \
                relationships.get('dedicated_server_constant_pool_references_server_text_filter') is not True or \
                relationships.get('integrated_server_constant_pool_references_server_text_filter') is not False or \
                relationships.get('integrated_server_constant_pool_references_player_safety_filter') is not False or \
                relationships.get('player_safety_class_references_jackson') is not False:
            fail('Jackson first-party client call-graph observations changed for Minecraft ' + version)
        for label, coordinate in (
                ('jackson_core', 'com.fasterxml.jackson.core:jackson-core:2.13.4'),
                ('jackson_databind', 'com.fasterxml.jackson.core:jackson-databind:2.13.4.2')):
            manifest_matches = [library for library in metadata['libraries'] if library['name'] == coordinate]
            package_observation = observation['runtime_dependencies'].get(label, {})
            artifact = manifest_matches[0]['downloads']['artifact'] if len(manifest_matches) == 1 else None
            inspected = jackson_libraries.get(coordinate)
            if artifact is None or inspected is None or \
                    package_observation.get('manifest_artifact') != artifact or \
                    package_observation.get('observed_sha256') != inspected['sha256'] or \
                    inspected['artifact']['sha1'] != artifact['sha1'] or inspected['artifact']['size'] != artifact['size']:
                fail('Jackson runtime library artifact mismatch for ' + coordinate + ' Minecraft ' + version)
        msal_version = '1.15.0' if version in ('1.21.2', '1.21.3') else '1.17.2'
        msal_coordinate = 'com.microsoft.azure:msal4j:' + msal_version
        msal_observation = observation['runtime_dependencies'].get('msal4j', {})
        msal_manifest = [library for library in metadata['libraries'] if library['name'] == msal_coordinate]
        if len(msal_manifest) != 1 or msal_observation.get('coordinate') != msal_coordinate or \
                msal_observation.get('manifest_artifact') != msal_manifest[0]['downloads']['artifact']:
            fail('MSAL runtime library does not match the official manifest for Minecraft ' + version)
        logging_metadata = metadata['logging']['client']
        logging_observation = observation.get('logging_configuration', {})
        if logging_observation.get('jvm_argument_from_official_metadata') != logging_metadata['argument'] or \
                logging_observation.get('default_client_config_file') != logging_metadata['file'] or \
                logging_metadata['file'].get('sha1') != logging_capture.get('sha1') or \
                logging_observation.get('production_launcher_arguments_verified') is not False:
            fail('Jackson/Log4j launcher metadata mismatch for Minecraft ' + version)
        log4j_core = observation.get('runtime_dependencies', {}).get('log4j_core', {})
        log4j_coordinate = log4j_core.get('coordinate')
        manifest_log4j = [library for library in metadata['libraries'] if library['name'] == log4j_coordinate]
        inspected_log4j = jackson_libraries.get(log4j_coordinate)
        if len(manifest_log4j) != 1 or inspected_log4j is None or \
                log4j_core.get('manifest_artifact') != manifest_log4j[0]['downloads']['artifact'] or \
                log4j_core.get('observed_sha256') != inspected_log4j['sha256']:
            fail('Log4j Core is not source-bound to the official manifest for Minecraft ' + version)
    for msal in jackson.get('msal_artifacts_and_bytecode', []):
        coordinate = msal['coordinate']
        inspected = jackson_libraries.get(coordinate)
        expected_class_count = {'com.microsoft.azure:msal4j:1.15.0': 241,
                                'com.microsoft.azure:msal4j:1.17.2': 247}.get(coordinate)
        if inspected is None or msal.get('sha256') != inspected['sha256'] or \
                msal.get('sha1') != inspected['artifact']['sha1'] or msal.get('size') != inspected['artifact']['size'] or \
                msal.get('class_files_scanned') != expected_class_count or \
                msal.get('url') != inspected['artifact']['url']:
            fail('MSAL artifact identity or bytecode scan count mismatch for ' + coordinate)
        scan = msal.get('reference_scan', {})
        if scan.get('JsonHelper') != ['com/microsoft/aad/msal4j/JsonHelper.class'] or \
                not DIGEST.fullmatch(msal.get('json_helper_class_sha256', '')) or any(scan.get(key) for key in (
                'JsonIdentityInfo_uses', 'JsonTypeInfo_uses', 'PolymorphicTypeValidator_uses',
                'default_typing_activation_uses', 'async_parser_creation_uses',
                'data_input_parser_uses', 'classloader_reflection_uses')):
            fail('MSAL bytecode scan unexpectedly includes a Jackson advisory trigger for ' + coordinate)
    expected_log4j_versions = {
        'org.apache.logging.log4j:log4j-core:2.22.1': {'1.21.2', '1.21.3'},
        'org.apache.logging.log4j:log4j-core:2.24.1':
            {'1.21.4', '1.21.5', '1.21.6', '1.21.7', '1.21.8', '1.21.9', '1.21.10'},
    }
    log4j_rows = {row['coordinate']: row for row in jackson.get('log4j_core_runtime_analysis', [])}
    if set(log4j_rows) != set(expected_log4j_versions):
        fail('Jackson evidence is missing exact Log4j Core parser versions')
    for coordinate, expected_versions in expected_log4j_versions.items():
        observation = log4j_rows[coordinate]
        inspected = jackson_libraries.get(coordinate)
        if inspected is None or set(observation.get('versions', [])) != expected_versions or \
                observation.get('sha256') != inspected['sha256'] or \
                observation.get('manifest_artifact') != inspected['artifact'] or \
                observation.get('class_files') != inspected['class_files'] or \
                observation.get('jackson_object_mapper_reference_classes') != \
                inspected['literal_reference_matches'].get('com/fasterxml/jackson/databind/ObjectMapper'):
            fail('Log4j Core Jackson class references are not bound to the inspected artifact: ' + coordinate)
        if any(not DIGEST.fullmatch(value) for value in observation.get('class_hashes', {}).values()) or \
                any(observation.get('advisory_precondition_bytecode_scan', {}).values()) or \
                observation.get('built_in_socket_server_or_input_stream_bridge_classes_present'):
            fail('Log4j parser precondition or socket-server findings changed for ' + coordinate)
    expected_caller_inventory = []
    for version in jackson_versions:
        callers = []
        for library in jackson_high_family['libraries']:
            if version not in library.get('versions', []):
                continue
            references = library.get('literal_reference_matches', {}).get(
                'com/fasterxml/jackson/databind/ObjectMapper', [])
            if references and not any(c.startswith('com.fasterxml.jackson.core:jackson-databind:')
                                      for c in library.get('coordinates', [])):
                callers.append({'coordinates': library['coordinates'], 'class_files': references})
        expected_caller_inventory.append({'minecraft_version': version, 'manifest_library_callers': callers})
    if jackson.get('runtime_manifest_object_mapper_caller_inventory') != expected_caller_inventory:
        fail('Jackson runtime manifest ObjectMapper caller inventory mismatch')
    probe = jackson['first_party_call_path']['isolated_dynamic_probe']
    probe_result_path = ROOT / probe['result_report']['path']
    probe_result = load(probe_result_path)
    if raw_hash(probe_result_path) != probe['result_report']['sha256'] or \
            jackson.get('source_provenance', {}).get('dynamic_probe_results', {}).get('sha256') != raw_hash(probe_result_path) or \
            len(probe_result.get('cases', [])) != 16:
        fail('Jackson depth probe result/source hash mismatch')
    for source in probe['probe_sources']:
        path = ROOT / source['path']
        if not path.is_file() or raw_hash(path) != source['sha256'] or path.stat().st_size != source['size_bytes']:
            fail('Jackson local probe source checksum mismatch: ' + source['path'])
    old_depth_cases = [row for row in probe_result['cases']
                       if row['probe_class'] in ('JacksonDepthProbe', 'JacksonObjectDepthProbe')]
    fixed_depth_cases = [row for row in probe_result['cases'] if row['probe_class'] == 'JacksonFixedDepthProbe']
    if len(old_depth_cases) != 15 or any(row['exit_code'] != 0 or 'parsed depth=' not in row['stdout']
                                         for row in old_depth_cases) or \
            len(fixed_depth_cases) != 1 or fixed_depth_cases[0]['exit_code'] != 0 or \
            'StreamConstraintsException' not in fixed_depth_cases[0]['stdout'] or \
            'Depth (1001) exceeds the maximum allowed nesting depth (1000)' not in fixed_depth_cases[0]['stdout']:
        fail('Jackson fixed-version depth-limit observation mismatch')
    if probe_result.get('fixed_artifact_sha1_verified_from_maven_checksum_files') != {
            'jackson-core': '12f334a1dc9c6d2854c43ae314024dde8b3ad572',
            'jackson-databind': '0d41caa3a4e9f85382702a059a65c512f85ac230',
            'jackson-annotations': '89b0fd554928425a776a6e97ed010034312af21d'}:
        fail('Jackson upstream fixed artifact checksum comparison mismatch')
    if probe_result.get('fixed_artifacts') != {
            'jackson-core-2.15.0.jar': '5b483f68fa9dd6aa37da37d1f79dd5c4b9464238f4f0660a242cb6b5c724950c',
            'jackson-databind-2.15.0.jar': '00c5a5d5ae71ac8e8d5b8da606841e2251c806355939cb5d51c4cdc6b644a0dc',
            'jackson-annotations-2.15.0.jar': '91adcd3dcf5fd9a16499934e7536a23d456692a0093e3d4fd52f138c3936348c'}:
        fail('Jackson fixed dependency artifact hash comparison mismatch')
    upstream_advisories = json.loads(gzip.decompress(upstream_path.read_bytes()))['advisories']
    for advisory in jackson_ids:
        source_finding = seen[advisory]
        supplemental = source_finding.get('supplemental_source_bound_evidence', [])
        if source_finding.get('severity') != 'HIGH' or supplemental != [
                {'path': jackson_path.relative_to(ROOT).as_posix(), 'sha256': raw_hash(jackson_path)}]:
            fail('Jackson finding lacks current source-bound reachability evidence for ' + advisory)
        if any(occurrence.get('dependency_owner') !=
               'Minecraft version manifest (game-managed runtime; Gradle scope is the resolved game-library development graph)'
               for occurrence in source_finding['occurrences']):
            fail('Jackson dependency ownership is not recorded as Minecraft-managed for ' + advisory)
        source_advisory = upstream_advisories[advisory]
        if jackson['advisories'][advisory]['upstream_authority'] != source_advisory['url']:
            fail('Jackson advisory authority mismatch for ' + advisory)
    jackson_pointer = evidence.get('jackson_msal_runtime_reachability', {})
    if jackson_pointer.get('path') != jackson_path.relative_to(ROOT).as_posix() or \
            jackson_pointer.get('sha256') != raw_hash(jackson_path) or jackson_pointer.get('occurrences') != 21 or \
            jackson_pointer.get('security_clearance') is not False or jackson_pointer.get('release_blocking') is not True:
        fail('source-bound Jackson/MASL report pointer mismatch')

    guava_id = 'GHSA-xxph-c9ww-hj94'
    guava_path = BASE / 'guava-deserialization-reachability-2026-11-22.json'
    guava = load(guava_path)
    guava_pointer = evidence.get('guava_deserialization_reachability', {})
    if guava.get('advisory', {}).get('advisory_id') != guava_id or \
            guava.get('security_clearance') is not False or guava.get('risk_accepted') is not False or \
            guava.get('release_blocking') is not True or guava.get('findings_remain_blocking') is not True:
        fail('Guava deserialization finding must remain unresolved and release-blocking')
    if guava.get('source_provenance', {}).get('finding_index', {}).get('sha256') != raw_hash(ARCHIVE / 'finding-index.json') or \
            guava_pointer.get('path') != guava_path.relative_to(ROOT).as_posix() or \
            guava_pointer.get('sha256') != raw_hash(guava_path) or guava_pointer.get('occurrences') != 16 or \
            guava_pointer.get('security_clearance') is not False or guava_pointer.get('release_blocking') is not True:
        fail('Guava reachability report/source pointer mismatch')

    guava_index_rows = [row for row in finding_index['records'] if row['advisory'] == guava_id]
    guava_source_rows = [row for row in evidence['findings'] if row['advisory_id'] == guava_id]
    if len(guava_index_rows) != 16 or len(guava_source_rows) != 1:
        fail('Guava exact-source occurrence coverage mismatch')
    guava_finding = guava_source_rows[0]
    if guava_finding.get('disposition') != 'Further investigation' or \
            guava_finding.get('release_blocking') is not True or guava_finding.get('risk_accepted') is not False or \
            guava_finding.get('occurrence_count') != 16:
        fail('Guava occurrence disposition unexpectedly cleared')
    guava_bindings = {(row['source_kind'], row['group'], row['source_sha'], row['purl']): row
                      for row in guava.get('source_occurrences', [])}
    if len(guava_bindings) != 16 or len(guava_finding['occurrences']) != 16:
        fail('Guava duplicate or missing source occurrence bindings')
    for row in guava_index_rows:
        key = (row['source_kind'], row['group'], row['source_sha'], row['purl'])
        binding = guava_bindings.get(key)
        occurrence = next((item for item in guava_finding['occurrences']
                           if (item['source_kind'], item['group'], item['source_sha'], item['purl']) == key), None)
        versions = sorted(scope.removeprefix('runtime/') for scope in row['scopes']
                          if scope.startswith('runtime/'))
        if binding is None or occurrence is None or binding.get('minecraft_versions') != versions or \
                binding.get('dependency_scopes') != row['scopes'] or binding.get('fingerprint') != row['fingerprint'] or \
                binding.get('source_report') != {'path': row['report'],
                                                  'sha256_uncompressed': row['report_sha256_uncompressed']} or \
                occurrence.get('minecraft_versions') != versions or occurrence.get('dependency_scopes') != row['scopes'] or \
                occurrence.get('fingerprint') != row['fingerprint'] or occurrence.get('severity') != 'HIGH' or \
                occurrence.get('disposition') != row['disposition'] or occurrence.get('failing') is not True or \
                occurrence.get('risk_accepted') is not False or occurrence.get('release_blocking') is not True:
            fail('Guava finding is not bound to its exact indexed source/report: ' + str(key))

    guava_advisory_path = BASE / 'guava-probes-2026-11-22/guava-upstream-advisory.json'
    guava_advisory = load(guava_advisory_path)
    if guava.get('source_provenance', {}).get('upstream_advisory_snapshot', {}).get('sha256') != raw_hash(guava_advisory_path) or \
            guava_advisory.get('ghsa_id') != guava_id or guava_advisory.get('cve_id') != 'CVE-2026-102554':
        fail('Guava authoritative advisory response mismatch')
    expected_guava_range = [{'package': 'com.google.guava:guava',
                             'vulnerable_version_range': '>= 4.0, <= 33.7.1',
                             'first_patched_version': '33.7.2'}]
    if guava_finding.get('upstream_affected_ranges') != expected_guava_range or \
            guava_advisory['vulnerabilities'][0].get('vulnerable_version_range') != '>= 4.0, <= 33.7.1' or \
            guava_advisory['vulnerabilities'][0].get('first_patched_version') != '33.7.2':
        fail('Guava upstream affected/fixed range mismatch')
    patch_path = BASE / 'guava-probes-2026-11-22/upstream-fix.patch'
    patch_text = patch_path.read_text()
    if guava.get('source_provenance', {}).get('upstream_fix', {}).get('patch_sha256') != raw_hash(patch_path) or \
            'b931fe9d6d5cf00bc55714ad3308d086f71850fe' not in patch_text or \
            patch_text.count('min(elementCount, 256)') < 4 or patch_text.count('min(size, 256)') < 2:
        fail('Guava upstream fix patch identity or capacity caps mismatch')
    release_path = BASE / 'guava-probes-2026-11-22/guava-release.json'
    release = load(release_path)
    if guava.get('source_provenance', {}).get('upstream_release_snapshot', {}).get('sha256') != raw_hash(release_path) or \
            release.get('tag_name') != 'v33.7.2':
        fail('Guava fixed release snapshot mismatch')

    guava_scan_ref = guava['source_provenance']['minecraft_runtime_scan']
    guava_scan_path = ROOT / guava_scan_ref['result_path']
    guava_scan_raw = gzip.decompress(guava_scan_path.read_bytes())
    guava_scan = json.loads(guava_scan_raw)
    if raw_hash(guava_scan_path) != guava_scan_ref.get('result_sha256') or \
            hashlib.sha256(guava_scan_raw).hexdigest() != guava_scan_ref.get('result_sha256_uncompressed') or \
            guava_scan.get('finding_index_sha256') != raw_hash(ARCHIVE / 'finding-index.json') or \
            guava_scan.get('high_family_inspection_sha256') != raw_hash(high_family_path):
        fail('Guava runtime scan source hashes mismatch')
    if guava_scan['counts'] != {
            'minecraft_clients': 48, 'runtime_artifacts': 655,
            'game_clients_with_literal_target_references': 0,
            'runtime_artifacts_with_literal_target_references': 86} or \
            len(guava_scan.get('minecraft_versions', [])) != 48 or \
            len(guava_scan.get('runtime_artifacts_scanned', [])) != 655:
        fail('Guava runtime scan coverage/count mismatch')
    scan_versions = {row['minecraft_version']: row for row in guava_scan['minecraft_versions']}
    if set(scan_versions) != {scope.removeprefix('runtime/') for row in guava_index_rows
                             for scope in row['scopes'] if scope.startswith('runtime/')}:
        fail('Guava exact runtime version set mismatch')
    for version, game in scan_versions.items():
        expected_bindings = {(row['source_kind'], row['group'], row['source_sha'], row['purl'])
                             for row in guava_index_rows if 'runtime/' + version in row['scopes']}
        actual_bindings = {(row['source_kind'], row['group'], row['source_sha'], row['purl'])
                           for row in game['source_bindings']}
        official = high_family['games'].get(version)
        if actual_bindings != expected_bindings or game['client_artifact'].get('constant_pool_matches') or \
                official is None or game['version_metadata'].get('sha1') != official.get('metadata_sha1') or \
                game['client_artifact'].get('sha1') != official.get('client', {}).get('sha1') or \
                game['client_artifact'].get('sha256') != official.get('client_sha256'):
            fail('Guava Minecraft client/source artifact binding mismatch for ' + version)
    scan_libraries = guava_scan['runtime_artifacts_scanned']
    if len({row['artifact']['sha1'] for row in scan_libraries}) != 655:
        fail('Guava scan runtime artifacts are not uniquely hash identified')
    guava_runtime_artifacts = {}
    for artifact in scan_libraries:
        for coordinate in artifact.get('coordinates', []):
            if coordinate.startswith('com.google.guava:guava:'):
                guava_runtime_artifacts[coordinate.rsplit(':', 1)[-1]] = artifact
    expected_guava_versions = {row['purl'].rsplit('@', 1)[-1] for row in guava_index_rows}
    if set(guava_runtime_artifacts) != expected_guava_versions or \
            {row['version'] for row in guava.get('package_versions', [])} != expected_guava_versions:
        fail('Guava exact package-version artifact set mismatch')
    for occurrence in guava_finding['occurrences']:
        artifact = guava_runtime_artifacts.get(occurrence['package_version'])
        if artifact is None or occurrence.get('dependency_artifact_sha1') != artifact['artifact']['sha1'] or \
                occurrence.get('dependency_artifact_sha256') != artifact['artifact']['sha256'] or \
                occurrence.get('dependency_manifest_artifact_url') != artifact['artifact']['url']:
            fail('Guava runtime artifact identity mismatch for ' + occurrence['package_version'])

    probe_source_path = BASE / 'guava-probes-2026-11-22/GuavaDeserializationProbe.java'
    probe_result_path = BASE / 'guava-probes-2026-11-22/probe-results.json'
    probe_results = load(probe_result_path)
    probe_ref = guava['source_provenance']['deserialization_probe']
    if raw_hash(probe_source_path) != probe_ref.get('source_sha256') or \
            raw_hash(probe_result_path) != probe_ref.get('results_sha256') or \
            len(probe_results.get('cases', [])) != 3:
        fail('Guava bounded probe source/result hash mismatch')
    by_artifact = {row['artifact']: row for row in probe_results['cases']}
    vulnerable_probe = by_artifact.get('guava-33.6.0-jre.jar', {})
    fixed_probe = by_artifact.get('guava-33.7.2-jre.jar', {})
    if vulnerable_probe.get('exit_code') != 0 or sum('OutOfMemoryError' in line for line in vulnerable_probe.get('stdout', [])) != 3 or \
            fixed_probe.get('exit_code') != 0 or \
            not any('OptionalDataException' in line for line in fixed_probe.get('stdout', [])) or \
            not any('MapMakerInternalMap: unexpected object returned' in line for line in fixed_probe.get('stdout', [])):
        fail('Guava vulnerable/fixed component probe result mismatch')
    sha1_sidecar = (BASE / 'guava-probes-2026-11-22/guava-33.7.2-jre.jar.sha1').read_text().strip()
    sha256_sidecar = (BASE / 'guava-probes-2026-11-22/guava-33.7.2-jre.jar.sha256').read_text().strip()
    fixed_case = by_artifact['guava-33.7.2-jre.jar']
    if sha1_sidecar != fixed_case.get('sha1') or sha256_sidecar != fixed_case.get('sha256'):
        fail('Guava fixed artifact Maven sidecar mismatch')

    packet_index_path = BASE / 'guava-probes-2026-11-22/vanilla-packet-paths/capture-index.json'
    packet_index = load(packet_index_path)
    if raw_hash(packet_index_path) != guava['source_provenance']['vanilla_packet_path_capture'].get('capture_index_sha256') or \
            {row['minecraft_version'] for row in packet_index.get('observations', [])} != {'1.14.4', '1.21.10', '26.3'}:
        fail('Guava vanilla packet path evidence identity mismatch')
    for observation in packet_index['observations']:
        if scan_versions[observation['minecraft_version']]['client_artifact'].get('sha256') != observation['client_sha256']:
            fail('Guava packet capture is bound to a different Minecraft client')
        class_texts = []
        for class_observation in observation['classes']:
            if not DIGEST.fullmatch(class_observation.get('class_sha256', '')):
                fail('Minecraft packet path class hash missing')
            capture = ROOT / class_observation['javap_path']
            if raw_hash(capture) != class_observation['javap_sha256']:
                fail('Minecraft javap capture checksum mismatch')
            class_texts.append(capture.read_text())
        joined = '\n'.join(class_texts)
        connection_text = '\n'.join(text for item, text in zip(observation['classes'], class_texts)
                                     if item['class'].endswith('Connection') or item['class'] in ('jc$1', 'wk'))
        expected_decoder = {'1.14.4': 'jf', '1.21.10': 'wy', '26.3': 'net/minecraft/network/PacketDecoder'}[
            observation['minecraft_version']]
        if 'ByteToMessageDecoder' not in joined or 'ObjectInputStream' in joined or \
                expected_decoder not in connection_text:
            fail('Minecraft packet path does not match the recorded typed-decoder observation')

    lz4_path = BASE / 'lz4-reachability-2026-11-22.json'
    lz4 = load(lz4_path)
    lz4_pointer = evidence.get('lz4_runtime_reachability', {})
    lz4_ids = {'GHSA-cmp6-m4wj-q63q', 'GHSA-vqf4-7m7x-wgfc'}
    if lz4.get('security_clearance') is not False or lz4.get('risk_accepted') is not False or \
            lz4.get('release_blocking') is not True or lz4.get('scope', {}).get('full_inventory_changed') is not False:
        fail('LZ4 report must preserve the failing inventory and withhold clearance')
    if lz4.get('source_provenance', {}).get('finding_index', {}).get('sha256') != raw_hash(ARCHIVE / 'finding-index.json') or \
            lz4.get('source_provenance', {}).get('archive_index', {}).get('sha256') != raw_hash(ARCHIVE / 'archive-index.json') or \
            lz4_pointer.get('path') != lz4_path.relative_to(ROOT).as_posix() or \
            lz4_pointer.get('sha256') != raw_hash(lz4_path) or lz4_pointer.get('occurrences') != 19 or \
            lz4_pointer.get('minecraft_versions') != 19 or lz4_pointer.get('source_groups') != 8 or \
            lz4_pointer.get('security_clearance') is not False or lz4_pointer.get('release_blocking') is not True:
        fail('LZ4 report/source-bound pointer mismatch')
    if lz4['scope'].get('focused_critical_occurrences') != 22 or \
            lz4['scope'].get('focused_high_occurrences') != 71 or \
            lz4['scope'].get('focused_critical_high_occurrences') != 93 or \
            lz4['scope'].get('finding_index_records') != len(finding_index['records']):
        fail('LZ4 focused or full source counts mismatch')
    hosted_ci_path = BASE / 'lz4-hosted-ci-verification-2026-11-22.json'
    hosted_ci = load(hosted_ci_path)
    hosted_ref = lz4.get('source_provenance', {}).get('hosted_ci_verification', {})
    expected_hosted_jobs = {
        'Verify reachability experiments (ubuntu-latest)',
        'Verify reachability experiments (windows-latest)',
        'Validate coordination',
        'Validate live release prerequisites',
    }
    if raw_hash(hosted_ci_path) != hosted_ref.get('sha256') or \
            hosted_ref.get('path') != hosted_ci_path.relative_to(ROOT).as_posix() or \
            hosted_ref.get('run_id') != 44977010612 or lz4_pointer.get('hosted_ci_run') != 44977010612 or \
            hosted_ci.get('workflow_run_id') != 44977010612 or \
            hosted_ci.get('head_sha') != 'a800917f9fa111df3bf9a0720fbd976e67ecbeb3' or \
            hosted_ci.get('status') != 'completed' or hosted_ci.get('conclusion') != 'success' or \
            {row['name'] for row in hosted_ci.get('jobs', []) if row.get('conclusion') == 'success'} != expected_hosted_jobs or \
            lz4.get('component_tests', {}).get('hosted_cross_platform_verification') != hosted_ref:
        fail('LZ4 hosted Linux/Windows verification is not source-bound or did not pass')
    if {row['name'] for row in hosted_ci.get('artifacts', [])} != {
            'reachability-probes-ubuntu-latest', 'reachability-probes-windows-latest'} or \
            any(not DIGEST.fullmatch(row.get('sha256', '')) for row in hosted_ci.get('artifacts', [])) or \
            hosted_ci.get('security_clearance') is not False or hosted_ci.get('risk_accepted') is not False:
        fail('LZ4 hosted probe artifacts or clearance status mismatch')

    lz4_by_id = {row['advisory_id']: row for row in lz4.get('findings', [])}
    lz4_source_by_id = {row['advisory_id']: row for row in evidence['findings']
                        if row['advisory_id'] in lz4_ids}
    if set(lz4_by_id) != lz4_ids or set(lz4_source_by_id) != lz4_ids:
        fail('LZ4 supplemental advisory set mismatch')
    for advisory in lz4_ids:
        exact_rows = [row for row in finding_index['records'] if row['advisory'] == advisory]
        finding = lz4_source_by_id[advisory]
        report_finding = lz4_by_id[advisory]
        if len(exact_rows) != TARGET_COUNTS[advisory] or finding.get('occurrence_count') != len(exact_rows) or \
                report_finding.get('occurrence_count') != len(exact_rows) or \
                finding.get('disposition') != 'Further investigation' or \
                report_finding.get('disposition') != 'Further investigation' or \
                finding.get('release_blocking') is not True or report_finding.get('release_blocking') is not True or \
                finding.get('risk_accepted') is not False or report_finding.get('risk_accepted') is not False:
            fail('LZ4 advisory remains blocking with exact occurrence count: ' + advisory)
        source_occurrences = {(row['source_kind'], row['group'], row['source_sha'], row['purl']): row
                              for row in finding['occurrences']}
        report_occurrences = {(row['source_kind'], row['group'], row['source_sha'], row['purl']): row
                              for row in report_finding['occurrences']}
        if len(source_occurrences) != len(exact_rows) or len(report_occurrences) != len(exact_rows):
            fail('LZ4 occurrence bindings contain duplicates or omissions: ' + advisory)
        for row in exact_rows:
            key = (row['source_kind'], row['group'], row['source_sha'], row['purl'])
            occurrence = source_occurrences.get(key)
            report_occurrence = report_occurrences.get(key)
            expected_versions = sorted(scope.removeprefix('runtime/') for scope in row['scopes']
                                       if scope.startswith('runtime/'))
            for candidate in (occurrence, report_occurrence):
                if candidate is None or candidate.get('source_sha') != row['source_sha'] or \
                        candidate.get('dependency_scopes') != row['scopes'] or \
                        candidate.get('fingerprint') != row['fingerprint'] or \
                        candidate.get('severity') != 'HIGH' or candidate.get('disposition') != row['disposition'] or \
                        candidate.get('failing') is not True or candidate.get('risk_accepted') is not False or \
                        candidate.get('release_blocking') is not True or \
                        candidate.get('source_report') != {'path': row['report'],
                                                           'sha256_uncompressed': row['report_sha256_uncompressed']} or \
                        candidate.get('minecraft_versions') != expected_versions:
                    fail('LZ4 occurrence is not exact-source bound: ' + advisory + ' ' + str(key))

    mcr4_rows = [row for row in finding_index['records'] if row['advisory'] == 'GHSA-mcr4-qmvw-px4g']
    mcr4_evidence = next(row for row in evidence['findings'] if row['advisory_id'] == 'GHSA-mcr4-qmvw-px4g')
    shared_mcr4 = lz4.get('shared_mcr4_context', {})
    if len(mcr4_rows) != 8 or shared_mcr4.get('occurrences') != 8 or \
            len(shared_mcr4.get('source_occurrences', [])) != 8 or \
            shared_mcr4.get('disposition') != 'Further investigation' or \
            shared_mcr4.get('release_blocking') is not True or shared_mcr4.get('risk_accepted') is not False:
        fail('LZ4 native extraction finding source coverage/disposition mismatch')
    exact_mcr4 = {(row['source_kind'], row['group'], row['source_sha'], row['purl']): row for row in mcr4_rows}
    supplemental_mcr4 = {(row['source_kind'], row['group'], row['source_sha'], row['purl']): row
                         for row in shared_mcr4['source_occurrences']}
    if set(supplemental_mcr4) != set(exact_mcr4):
        fail('LZ4 native extraction source group bindings mismatch')
    for key, row in exact_mcr4.items():
        supplemental = supplemental_mcr4[key]
        if supplemental.get('source_report') != {'path': row['report'],
                                                  'sha256_uncompressed': row['report_sha256_uncompressed']} or \
                supplemental.get('fingerprint') != row['fingerprint'] or \
                supplemental.get('dependency_scopes') != row['scopes'] or \
                supplemental.get('release_blocking') is not True or supplemental.get('risk_accepted') is not False:
            fail('LZ4 native extraction occurrence not bound to exact report: ' + str(key))

    lz4_dir = BASE / 'lz4-probes-2026-11-22'
    runtime_scan_path = lz4_dir / 'runtime-scan.json'
    runtime_scan = load(runtime_scan_path)
    if raw_hash(runtime_scan_path) != next(x['sha256'] for x in evidence['supporting_evidence']
                                          if x['path'] == runtime_scan_path.relative_to(ROOT).as_posix()) or \
            runtime_scan.get('finding_index', {}).get('sha256') != raw_hash(ARCHIVE / 'finding-index.json') or \
            runtime_scan.get('high_family_inspection', {}).get('sha256') != raw_hash(high_family_path) or \
            runtime_scan.get('minecraft_version_count') != 19 or runtime_scan.get('occurrence_count') != 8 or \
            runtime_scan.get('security_clearance') is not False:
        fail('LZ4 exact client runtime scan provenance/count mismatch')
    expected_lz4_versions = {scope.removeprefix('runtime/') for row in mcr4_rows for scope in row['scopes']
                             if scope.startswith('runtime/')}
    runtime_observations = runtime_scan.get('observations', [])
    if {row['minecraft_version'] for row in runtime_observations} != expected_lz4_versions or \
            len(runtime_observations) != 19 or \
            {row['source_group'] for row in runtime_observations} != {row['group'] for row in mcr4_rows}:
        fail('LZ4 exact-client coverage does not match source-bound version scopes')
    for observation in runtime_observations:
        game = high_family['games'].get(observation['minecraft_version'])
        source_row = next(row for row in mcr4_rows if row['group'] == observation['source_group'])
        if game is None or observation.get('source_sha') != source_row['source_sha'] or \
                observation.get('source_kind') != source_row['source_kind'] or \
                observation.get('literal_reference_verified') is not True or \
                observation.get('client_sha1') != game.get('client', {}).get('sha1') or \
                observation.get('client_sha256') != game.get('client_sha256') or \
                not DIGEST.fullmatch(observation.get('direct_caller_class_sha256', '')):
            fail('LZ4 client artifact/source binding mismatch for ' + observation['minecraft_version'])

    capture_index_path = lz4_dir / 'capture-index.json'
    capture_index = load(capture_index_path)
    if raw_hash(capture_index_path) != next(x['sha256'] for x in evidence['supporting_evidence']
                                           if x['path'] == capture_index_path.relative_to(ROOT).as_posix()):
        fail('LZ4 caller/bytecode capture index hash mismatch')
    group_captures = capture_index.get('group_caller_captures', [])
    if {row['source_group'] for row in group_captures} != {row['group'] for row in mcr4_rows} or \
            len(group_captures) != 8:
        fail('LZ4 per-source-group bytecode caller coverage mismatch')
    for capture in group_captures:
        path = ROOT / capture['javap_path']
        contents = path.read_text()
        source_row = next(row for row in mcr4_rows if row['group'] == capture['source_group'])
        if raw_hash(path) != capture.get('javap_sha256') or capture.get('source_sha') != source_row['source_sha'] or \
                capture.get('constructor_reference_verified') is not True or \
                'LZ4BlockInputStream' not in contents:
            fail('LZ4 region-file stream constructor capture mismatch for ' + capture['source_group'])
    library_captures = capture_index.get('library_bytecode_captures', [])
    if {row['version'] for row in library_captures} != {'1.8.0', '1.8.1', '1.10.1', '1.11.4'}:
        fail('LZ4 library bytecode comparison version set mismatch')
    for artifact in library_captures:
        for capture in artifact['classes']:
            path = ROOT / capture['javap_path']
            if raw_hash(path) != capture.get('javap_sha256'):
                fail('LZ4 library bytecode capture checksum mismatch: ' + capture['javap_path'])
        block = next(row for row in artifact['classes'] if row['class'] == 'net.jpountz.lz4.LZ4BlockInputStream')
        text = (ROOT / block['javap_path']).read_text()
        if 'LZ4BlockInputStream(java.io.InputStream)' not in text or 'fastDecompressor' not in text:
            fail('LZ4 fixed/vulnerable artifact does not contain the compared stream API')

    packet_path = lz4_dir / 'packet-and-region-paths/capture-index.json'
    packet_index = load(packet_path)
    if raw_hash(packet_path) != next(x['sha256'] for x in evidence['supporting_evidence']
                                    if x['path'] == packet_path.relative_to(ROOT).as_posix()) or \
            {row['minecraft_version'] for row in packet_index['observations']} != {'1.20.5', '1.21.10', '1.21.11', '26.3'}:
        fail('LZ4 region/packet representative capture identity mismatch')
    for observation in packet_index['observations']:
        for capture in observation['all_captures']:
            path = ROOT / capture['javap_path']
            if raw_hash(path) != capture.get('javap_sha256'):
                fail('LZ4 region/packet javap capture checksum mismatch: ' + capture['javap_path'])
        if observation.get('minecraft_version') == '26.3':
            if observation.get('chunk_packet_classes') or observation.get('client_packet_listener_classes'):
                fail('26.3 packet path is marked captured without mapped classes')
            continue
        for role in ('chunk_packet_classes', 'client_packet_listener_classes'):
            if not observation.get(role):
                fail('representative vanilla packet path missing class captures: ' + observation['minecraft_version'])
            for capture in observation[role]:
                path = ROOT / capture['javap_path']
                contents = path.read_text()
                if raw_hash(path) != capture.get('javap_sha256') or 'LZ4BlockInputStream' in contents:
                    fail('vanilla packet capture unexpectedly references LZ4 stream: ' + capture['javap_path'])
    probe_path = lz4_dir / 'probe-results.json'
    probe_results = load(probe_path)
    if raw_hash(probe_path) != next(x['sha256'] for x in evidence['supporting_evidence']
                                   if x['path'] == probe_path.relative_to(ROOT).as_posix()) or \
            probe_results.get('all_passed') is not True or probe_results.get('observed_case_count') != 8 or \
            probe_results.get('passed_case_count') != 8:
        fail('LZ4 bounded component probe result mismatch')
    probe_by_name = {row['name']: row for row in probe_results['cases']}
    expected_probe_values = {
        'lz4-advisory-1.8.0': ('net.jpountz.lz4.LZ4JNIFastDecompressor', 0, 923, 923),
        'lz4-advisory-1.8.1': ('net.jpountz.lz4.LZ4JavaSafeFastDecompressor', 923, 923, 923),
        'lz4-advisory-1.10.1': ('net.jpountz.lz4.LZ4JavaSafeFastDecompressor', 0, 0, 0),
        'lz4-advisory-1.11.4': ('net.jpountz.lz4.LZ4JavaSafeFastDecompressor', 0, 0, 0),
    }
    for name, expected in expected_probe_values.items():
        observed = probe_by_name.get(name, {}).get('observed', {})
        actual = (observed.get('FASTEST_FAST_CLASS'), observed.get('FASTEST_FAST_NONZERO_OUTPUT_BYTES'),
                  observed.get('SAFE_FAST_NONZERO_OUTPUT_BYTES'), observed.get('JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES'))
        if actual != expected or observed.get('STREAM_BUFFERS_DISTINCT') != 1:
            fail('LZ4 CMP6 test vector output/class mismatch: ' + name)

    host_temp = load(lz4_dir / 'host-temp-observation.json')
    if host_temp.get('tmp_directory', {}).get('mode_octal') != '0o1777' or \
            host_temp.get('sysctls', {}).get('protected_regular') != '0' or \
            host_temp.get('java_default_tmpdir') != '/tmp' or host_temp.get('security_clearance') is not False:
        fail('LZ4 local temp-directory observation changed or overclaims')

    cmp6_advisory = load(lz4_dir / 'GHSA-cmp6-m4wj-q63q.json')
    vqf4_advisory = load(lz4_dir / 'GHSA-vqf4-7m7x-wgfc.json')
    expected_ranges = {
        'GHSA-cmp6-m4wj-q63q': [
            {'package': 'at.yawk.lz4:lz4-java', 'vulnerable_version_range': '<= 1.10.0', 'first_patched_version': '1.10.1'},
            {'package': 'org.lz4:lz4-java', 'vulnerable_version_range': '<= 1.8.1', 'first_patched_version': None}],
        'GHSA-vqf4-7m7x-wgfc': [
            {'package': 'at.yawk.lz4:lz4-java', 'vulnerable_version_range': '< 1.8.1', 'first_patched_version': '1.8.1'},
            {'package': 'org.lz4:lz4-java', 'vulnerable_version_range': '< 1.8.1', 'first_patched_version': '1.8.1'}],
    }
    for advisory, snapshot in (("GHSA-cmp6-m4wj-q63q", cmp6_advisory), ("GHSA-vqf4-7m7x-wgfc", vqf4_advisory)):
        ranges = [{'package': row['package']['name'], 'vulnerable_version_range': row.get('vulnerable_version_range'),
                   'first_patched_version': row.get('first_patched_version')}
                  for row in snapshot.get('vulnerabilities', [])
                  if row.get('package', {}).get('name') in {'at.yawk.lz4:lz4-java', 'org.lz4:lz4-java'}]
        if snapshot.get('ghsa_id') != advisory or sorted(ranges, key=lambda x: x['package']) != \
                sorted(expected_ranges[advisory], key=lambda x: x['package']) or \
                sorted(lz4_by_id[advisory]['upstream_affected_ranges'], key=lambda x: x['package']) != \
                sorted(expected_ranges[advisory], key=lambda x: x['package']):
            fail('LZ4 authoritative affected/fixed version range mismatch: ' + advisory)
    cmp6_patch = lz4_dir / 'cmp6-fix.patch.gz'
    mcr4_patch = lz4_dir / 'mcr4-fix.patch.gz'
    cmp6_patch_raw = gzip.decompress(cmp6_patch.read_bytes())
    mcr4_patch_raw = gzip.decompress(mcr4_patch.read_bytes())
    patch_refs = lz4.get('source_provenance', {}).get('upstream_patches', {})
    if hashlib.sha256(cmp6_patch_raw).hexdigest() != patch_refs.get('cmp6-fix.patch', {}).get('sha256_uncompressed') or \
            hashlib.sha256(mcr4_patch_raw).hexdigest() != patch_refs.get('mcr4-fix.patch', {}).get('sha256_uncompressed') or \
            raw_hash(cmp6_patch) != patch_refs.get('cmp6-fix.patch', {}).get('sha256_gzip') or \
            raw_hash(mcr4_patch) != patch_refs.get('mcr4-fix.patch', {}).get('sha256_gzip') or \
            '33d180cb70c4d93c80fb0dc3ab3002f457e93840' not in cmp6_patch_raw.decode() or \
            '7a48b7f6b8099b9dab6541e4ac2ee0979dc55aa3' not in mcr4_patch_raw.decode():
        fail('LZ4 upstream fix evidence commit references mismatch')
    for release_name, expected_tag in (('v1.8.1-release.json', 'v1.8.1'),
                                       ('v1.10.1-release.json', 'v1.10.1'),
                                       ('v1.11.4-release.json', 'v1.11.4')):
        release = load(lz4_dir / release_name)
        if release.get('tag_name') != expected_tag:
            fail('LZ4 upstream release snapshot mismatch: ' + expected_tag)

    run_reference = evidence.get('log4j_chat_input_probe_run', {})
    if run_reference.get('path') != chat_probe_path.relative_to(ROOT).as_posix() or \
            run_reference.get('sha256') != raw_hash(chat_probe_path) or \
            run_reference.get('observations') != 34 or run_reference.get('parameterized_chat_cases') != 6 or \
            run_reference.get('all_passed') is not True or run_reference.get('security_clearance') is not False:
        fail('source-bound Log4j chat probe reference mismatch')
    if evidence.get('targeted_high_occurrences') != 71:
        fail('targeted High occurrence count mismatch')
    if evidence['component_probe_run']['sha256'] != raw_hash(BASE / 'reachability-probes-2026-11-21-rerun.json'):
        fail('component probe report hash mismatch')

    probe = load(BASE / 'reachability-probes-2026-11-21-rerun.json')
    if probe.get('passed') is not True or len(probe.get('cases', [])) != 28:
        fail('component probe run is missing expected observations')
    netty_path = BASE / 'netty-manifest-artifacts-2026-11-21.json'
    netty = load(netty_path)
    expected_netty = {(row['advisory'], row['group'], row['source_sha'], row['purl'])
                      for row in finding_index['records']
                      if row['advisory'] in ('GHSA-c4c3-7fpv-j4q5', 'GHSA-pwqr-wmgm-9rr8')}
    actual_netty = {(row['advisory'], row['group'], row['source_sha'], row['purl'])
                    for row in netty['source_occurrences']}
    if actual_netty != expected_netty or len(netty['netty_artifacts']) != 10:
        fail('Netty manifest-artifact source coverage mismatch')
    if netty.get('finding_index', {}).get('sha256') != raw_hash(ARCHIVE / 'finding-index.json'):
        fail('Netty manifest inspection is not bound to the finding index')
    for artifact in netty['netty_artifacts']:
        if not DIGEST.fullmatch(artifact.get('sha256', '')) or not re.fullmatch(r'[0-9a-f]{40}', artifact.get('sha1', '')):
            fail('Netty artifact hashes are incomplete')
        if ':netty-handler:' in artifact['coordinate'] and not any(
                row['path'] == 'io/netty/handler/ssl/SniHandler.class' for row in artifact['classes']):
            fail('SniHandler class hash missing from exact Netty handler artifact')
    for finding in evidence['findings']:
        for occurrence in finding['occurrences']:
            if not DIGEST.fullmatch(occurrence.get('dependency_artifact_sha256', '')):
                fail('dependency artifact hash missing for ' + occurrence['purl'])
            if occurrence['purl'].startswith('pkg:maven/io.netty/'):
                group, tail = occurrence['purl'].removeprefix('pkg:maven/').split('/', 1)
                name, version = tail.rsplit('@', 1)
                coordinate = f'{group}:{name}:{version}'
                matches = [artifact for artifact in netty['netty_artifacts']
                           if artifact['coordinate'] == coordinate and
                           set(occurrence['minecraft_versions']) & set(artifact['minecraft_versions'])]
                if len(matches) != 1 or occurrence['dependency_artifact_sha256'] != matches[0]['sha256'] or \
                        occurrence.get('dependency_artifact_sha1') != matches[0]['sha1']:
                    fail('Netty artifact SHA mismatch for ' + coordinate)

    upstream_path = BASE / 'upstream-critical-high.json.gz'
    upstream = json.loads(gzip.decompress(upstream_path.read_bytes()))
    archived_target_ids = set(TARGET_COUNTS) - {guava_id}
    if archived_target_ids - set(upstream['advisories']):
        fail('upstream advisory responses missing for focused findings')
    for finding in evidence['findings']:
        authoritative = guava_advisory if finding['advisory_id'] == guava_id else upstream['advisories'][finding['advisory_id']]
        packages = set(finding['component'].split('; '))
        ranges = [{'package': item['package']['name'],
                   'vulnerable_version_range': item.get('vulnerable_version_range'),
                   'first_patched_version': item.get('first_patched_version')}
                  for item in authoritative.get('vulnerabilities', [])
                  if item.get('package', {}).get('name') in packages]
        if sorted(ranges, key=lambda x: (x['package'], x['vulnerable_version_range'] or '')) != \
                sorted(finding['upstream_affected_ranges'], key=lambda x: (x['package'], x['vulnerable_version_range'] or '')):
            fail('upstream affected ranges/fixed versions mismatch for ' + finding['advisory_id'])

    wrapper = load(BASE / 'wrapper-source-verification-2026-11-21.json')
    if wrapper.get('verified_sources') != 13 or len(wrapper.get('sources', [])) != 13:
        fail('Gradle Wrapper verification does not cover all 13 source groups')
    source_sha_by_branch = {}
    for key, row in finding_index['reports'].items():
        kind, group = key.split('|', 1)
        branch = 'candidate/mc-' + group if kind == 'candidate' else 'mc/' + group
        source_sha_by_branch[branch] = row['source_sha']
    if {row['branch']: row['source_sha'] for row in wrapper['sources']} != source_sha_by_branch:
        fail('Wrapper observations do not match current archived source SHAs')
    if any(row['gradle_version'] != '9.9.2' or row['remote_head_sha'] != row['source_sha'] for row in wrapper['sources']):
        fail('Wrapper source head or version mismatch')
    if evidence['source_bound_wrapper_verification']['sha256'] != raw_hash(BASE / 'wrapper-source-verification-2026-11-21.json'):
        fail('Wrapper evidence hash mismatch')

    ledger = load(LEDGER)
    reference = ledger.get('critical_reachability_evidence', {})
    if reference.get('path') != EVIDENCE.relative_to(ROOT).as_posix() or reference.get('sha256') != raw_hash(EVIDENCE):
        fail('structured advisory ledger does not reference this evidence')
    commons_pointer = evidence.get('commons_compress_tar_reachability', {}).get('latest_followup', {})
    commons_path = ROOT / commons_pointer.get('path', '')
    commons = load(commons_path) if commons_path.is_file() else {}
    if commons_pointer.get('path') != (BASE / 'commons-compress-runtime-followup-2026-11-22.json').relative_to(ROOT).as_posix() or \
            commons_pointer.get('sha256') != raw_hash(commons_path) or \
            commons_pointer.get('occurrences') != 12 or commons_pointer.get('source_groups') != 3 or \
            commons_pointer.get('risk_accepted') is not False or commons_pointer.get('security_clearance') is not False or \
            commons_pointer.get('release_blocking') is not True or commons.get('security_clearance') is not False or \
            commons.get('risk_accepted') is not False or commons.get('release_blocking') is not True:
        fail('Commons Compress source-bound TAR follow-up is missing, cleared, or inconsistent')
    hosted_pointer = commons_pointer.get('hosted_ci_verification', {})
    hosted_path = ROOT / hosted_pointer.get('path', '')
    hosted = load(hosted_path) if hosted_path.is_file() else {}
    expected_hosted_path = (BASE / 'commons-compress-hosted-verification-2026-11-22.json').relative_to(ROOT).as_posix()
    if hosted_pointer.get('path') != expected_hosted_path or hosted_pointer.get('sha256') != raw_hash(hosted_path) or \
            hosted_pointer.get('run_id') != 44980595788 or hosted_pointer.get('source_commit') != '51ec66fb9ace4506dcb43c738ba3ae407fafbdc3' or \
            hosted.get('status') != 'hosted_matrix_passed_and_artifacts_hash_verified' or hosted.get('security_clearance') is not False or \
            hosted.get('risk_accepted') is not False or hosted.get('release_blocking') is not True or \
            hosted.get('workflow', {}).get('conclusion') != 'success' or hosted.get('source_commit') != hosted_pointer.get('source_commit'):
        fail('Commons Compress hosted verification is missing, changed, or cleared')
    artifact_rows = hosted.get('hosted_artifacts', [])
    if {row.get('os') for row in artifact_rows} != {'ubuntu-latest', 'windows-latest'} or len(artifact_rows) != 2 or \
            any(row.get('passed') is not True or not row.get('artifact_zip_sha256') for row in artifact_rows):
        fail('Commons Compress hosted matrix does not contain two verified passing artifacts')
    for artifact in artifact_rows:
        payload = ROOT / artifact.get('payload_path', '')
        results = artifact.get('results', [])
        if not payload.is_file() or raw_hash(payload) != artifact.get('payload_sha256') or \
                len(results) != 2 or any(result.get('passed') is not True for result in results):
            fail('Commons Compress hosted payload is missing or does not record two passing cases')
    if reference.get('commons_compress_tar_reachability') != commons_pointer:
        fail('structured advisory ledger Commons Compress pointer mismatch')
    if reference.get('targeted_high_occurrences') != 71 or reference.get('targeted_critical_occurrences') != 22 or \
            reference.get('targeted_occurrences') != 93 or \
            reference.get('guava_deserialization_reachability') != guava_pointer or \
            reference.get('lz4_runtime_reachability') != lz4_pointer or \
            reference.get('commons_compress_tar_reachability', {}).get('hosted_ci_verification') != hosted_pointer:
        fail('structured advisory ledger focused counts or Guava/LZ4/Commons pointer mismatch')
    updated = [row for row in ledger['records'] if 'latest_source_observation' in row]
    if len(updated) != reference.get('updated_integrated_occurrence_records'):
        fail('structured ledger source-observation count mismatch')
    for row in updated:
        observation = row['latest_source_observation']
        exact = indexed.get((row['advisory'], row['group'], 'integrated', row['purl']))
        if exact is None or observation['source_sha'] != exact['source_sha'] or observation['failing'] is not True:
            fail('structured ledger observation is not bound to an integrated finding')
    return len(finding_index['records']), sum(TARGET_COUNTS.values())


if __name__ == '__main__':
    try:
        total, targeted = validate()
        print(f'Validated {total} source-bound finding records; {targeted} focused critical/high occurrences remain blocking.')
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, gzip.BadGzipFile) as exc:
        print('Critical reachability evidence validation failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
