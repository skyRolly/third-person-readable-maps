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
    if evidence.get('targeted_high_occurrences') != 23:
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
    if set(TARGET_COUNTS) - set(upstream['advisories']):
        fail('upstream advisory responses missing for focused findings')
    for finding in evidence['findings']:
        authoritative = upstream['advisories'][finding['advisory_id']]
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
