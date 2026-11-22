#!/usr/bin/env python3
"""Validate source hashes and fail-closed results for the Mojang Log4j runtime probe."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
SOURCE_REPORT = EVIDENCE / 'log4j-chat-input-reachability-2026-11-21.json'
DISPOSITION_REPORT = EVIDENCE / 'log4j-runtime-observations-2026-11-22.json'
FINDING_INDEX = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
HOSTED_EVIDENCE = EVIDENCE / 'log4j-runtime-hosted-2026-11-22'
VERSION_SCOPE_REPORT = HOSTED_EVIDENCE / 'minecraft-1.19-log4j-version-check.json'
LOG4J_METADATA_DIR = EVIDENCE / 'log4j-mojang-runtime-2026-11-22/metadata'
TARGETED_LOG4J_ADVISORIES = {
    'GHSA-jfh8-c2jp-5v3q', 'GHSA-7rjr-3q55-vv33', 'GHSA-fxph-q3j8-mv87'
}


def digest_bytes(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def resolve_repo_path(value):
    # Reports produced on Windows contain Windows separators; accept those
    # when validating an artifact on Linux, while retaining the root check.
    value = value.replace('\\', '/')
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('report references a path outside the repository: ' + value)
    return path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def log4j_relevant_metadata(metadata):
    java = metadata.get('javaVersion', {})
    logging = metadata.get('logging', {}).get('client', {})
    logging_file = logging.get('file', {})
    jvm_mentions = []
    for arg in metadata.get('arguments', {}).get('jvm', []):
        value = arg.get('value') if isinstance(arg, dict) else arg
        values = value if isinstance(value, list) else [value]
        jvm_mentions.extend(item for item in values
                            if isinstance(item, str) and ('log4j' in item.lower() or 'jndi' in item.lower()))
    libraries = []
    for library in metadata.get('libraries', []):
        name = library.get('name', '')
        if name.startswith(('org.apache.logging.log4j:', 'com.mojang:patchy:')):
            artifact = library.get('downloads', {}).get('artifact', {})
            libraries.append({'name': name, 'artifact': {
                key: artifact.get(key) for key in ('url', 'sha1', 'size')}})
    return {
        'java': {'component': java.get('component'), 'majorVersion': java.get('majorVersion')},
        'logging_argument': logging.get('argument'),
        'logging_file': {key: logging_file.get(key) for key in ('id', 'sha1', 'size', 'url')},
        'jvm_argument_log4j_or_jndi_mentions': jvm_mentions,
        'logging_libraries_in_order': libraries,
    }


def validate(report_path):
    report_path = Path(report_path).resolve()
    report = read_json(report_path)
    source = read_json(SOURCE_REPORT)
    launcher_index_path = resolve_repo_path(report['launcher_metadata_index_path'])
    require(digest_bytes(launcher_index_path.read_bytes(), 'sha256') == report['launcher_metadata_index_sha256'],
            'retained launcher metadata index SHA-256 mismatch')
    launcher_index = read_json(launcher_index_path)
    require(report.get('schema') == 1, 'unsupported report schema')
    require(report.get('status') == 'complete', 'runtime probe report is incomplete')
    require(report.get('passed') is True, 'one or more runtime experiments failed')
    require(report.get('security_clearance') is False, 'probe report must not grant security clearance')
    require(report.get('risk_accepted') is False, 'probe report must not accept risk')
    require(report.get('release_blocking') is True, 'unresolved Log4j findings must remain release-blocking')
    require('passed means each exact-runtime experiment' in report.get('result_semantics', ''),
            'report does not distinguish probe completion from security clearance')
    require(report.get('source_group_bindings') == source.get('source_group_bindings'),
            'source-group bindings differ from the retained exact-client report')
    require(len(report.get('verified_affected_version_metadata', [])) == 18,
            'expected 18 exact affected Minecraft metadata records')
    require(len(report.get('cases', [])) == 27, 'expected 27 exact-runtime experiment cases')
    require(all(case.get('passed') is True for case in report['cases']),
            'a runtime case is not marked passed')

    groups_by_version = {
        version: group
        for group in source['source_group_bindings']
        for version in group['minecraft_versions']
    }
    case_names = set()
    cases_by_name = {}
    for case in report['cases']:
        name = case.get('name')
        require(name not in case_names, 'duplicate case name: ' + str(name))
        case_names.add(name)
        cases_by_name[name] = case
        binding = groups_by_version.get(case.get('minecraft_version'))
        require(binding is not None, 'case version has no source-group binding')
        for key, expected in (('source_kind', binding['source_kind']),
                              ('source_group', binding['group']),
                              ('source_sha', binding['source_sha'])):
            require(case.get(key) == expected, 'case has incorrect ' + key + ': ' + str(name))
        require(case.get('observed', {}).get('exit_code') == 0,
                'runtime case exited unsuccessfully: ' + str(name))
        for key, expected in case.get('expected', {}).items():
            require(case['observed'].get(key) == expected,
                    'observed result differs from expected ' + key + ': ' + str(name))

    expected_cases = set()
    for version in ('1.14.4', '1.17.1', '1.18.1'):
        names = [version + suffix for suffix in (
            '-runtime-properties', '-jndi-codebase-policy', '-ldap-serialized-data',
            '-launcher-message', '-launcher-direct-jndi', '-launcher-chat-jndi',
            '-launcher-thread-context', '-embedded-chat-jndi')]
        if version == '1.14.4':
            names.append(version + '-embedded-core-first-chat-jndi')
        else:
            names.append(version + '-synthetic-context-lookup')
        expected_cases.update(names)
    require(case_names == expected_cases, 'runtime case set differs from the approved 1.14.4/1.17.1/1.18.1 matrix')

    platform_runtime_names = {
        'linux': {'jre-legacy': '8u202'},
        'windows-x64': {'jre-legacy': '8u51-cacert462b08'},
    }
    require(report.get('platform') in platform_runtime_names, 'unsupported runtime platform')
    policy_by_runtime = {
        '8u202': ('false', 'no_runtime_gate_method', 'deserialized:java.lang.String', 'true'),
        '8u51-cacert462b08': ('false', 'no_runtime_gate_method', 'deserialized:java.lang.String', 'true'),
        '16.0.1.9.1': ('false', 'true', 'deserialized:java.lang.String', 'true'),
        '17.0.15': ('false', 'false', 'blocked:javax.naming.NamingException', 'false'),
    }
    runtime_names = {}
    for component, runtime in report.get('runtime_components', {}).items():
        name = runtime.get('version_name')
        require(name in policy_by_runtime, 'unrecognized exact Mojang runtime: ' + str(name))
        runtime_names[component] = name
    expected_runtime_names = {
        'java-runtime-alpha': '16.0.1.9.1',
        'java-runtime-beta': '17.0.15',
        **platform_runtime_names[report['platform']],
    }
    require(set(runtime_names) == set(expected_runtime_names),
            'report does not contain the complete exact Mojang runtime component set')
    for component, expected_name in expected_runtime_names.items():
        require(runtime_names.get(component) == expected_name,
                'unexpected platform-specific Mojang runtime for ' + component)
    for name in sorted(expected_cases):
        case = cases_by_name[name]
        if not name.endswith(('jndi-codebase-policy', 'ldap-serialized-data')):
            continue
        component = case.get('java_component')
        runtime_name = case.get('java_runtime_name')
        require(runtime_name == runtime_names.get(component),
                'case runtime does not match pinned component: ' + name)
        codebase, serialized_gate, ldap_result, marker_match = policy_by_runtime[runtime_name]
        observed = case['observed']
        if name.endswith('jndi-codebase-policy'):
            require(observed.get('JNDI_CODEBASE_TRUST_GATE') == codebase,
                    'unexpected JNDI codebase gate result: ' + name)
            require(observed.get('JNDI_SERIAL_DATA_TRUST_GATE') == serialized_gate,
                    'unexpected JNDI serialized-data gate result: ' + name)
        else:
            require(observed.get('LDAP_SERIALIZED_DATA_RESULT') == ldap_result,
                    'unexpected local LDAP serialized-data result: ' + name)
            require(observed.get('LDAP_SERIALIZED_DATA_MARKER_MATCH') == marker_match,
                    'local serialized marker result is inconsistent: ' + name)
            require(observed.get('NETWORK_REQUESTS') == '0',
                    'local serialized-data probe must not make network requests')

    metadata_rows = report['verified_affected_version_metadata']
    metadata_by_version = {row['minecraft_version']: row for row in metadata_rows}
    version_set = {row['minecraft_version'] for row in metadata_rows}
    require(len(version_set) == 18, 'metadata versions are duplicated')
    current_manifest_bytes = resolve_repo_path(report['version_manifest_v2']['snapshot_path']).read_bytes()
    current_manifest_index = {entry['id']: entry for entry in json.loads(current_manifest_bytes)['versions']}
    require(set(version_set).issubset(set(launcher_index['versions'])),
            'metadata rows contain a version absent from the retained launcher index')
    for row in metadata_rows:
        require(row.get('security_relevant_metadata_equal_to_retained_survey') is True,
                'current launcher metadata differs in a security-relevant field: ' + row['minecraft_version'])
        for path_field, sha1_field, sha256_field, size_field in (
            ('current_metadata_snapshot_path', 'current_manifest_metadata_sha1',
             'current_manifest_metadata_sha256', 'current_manifest_metadata_size'),
            ('retained_metadata_snapshot_path', 'retained_metadata_sha1',
             'retained_metadata_sha256', 'retained_metadata_size'),
        ):
            snapshot = resolve_repo_path(row[path_field]).read_bytes()
            require(digest_bytes(snapshot, 'sha1') == row[sha1_field],
                    'metadata snapshot SHA-1 mismatch: ' + row['minecraft_version'])
            require(digest_bytes(snapshot, 'sha256') == row[sha256_field],
                    'metadata snapshot SHA-256 mismatch: ' + row['minecraft_version'])
            require(len(snapshot) == row[size_field],
                    'metadata snapshot size mismatch: ' + row['minecraft_version'])
        current_bytes = resolve_repo_path(row['current_metadata_snapshot_path']).read_bytes()
        retained_bytes = resolve_repo_path(row['retained_metadata_snapshot_path']).read_bytes()
        current_metadata = json.loads(current_bytes)
        retained_metadata = json.loads(retained_bytes)
        version = row['minecraft_version']
        require(current_metadata.get('id') == version and retained_metadata.get('id') == version,
                'metadata snapshot version identity mismatch: ' + version)
        require(log4j_relevant_metadata(current_metadata) == log4j_relevant_metadata(retained_metadata),
                'security-relevant launcher fields differ between retained and current metadata: ' + version)
        require(log4j_relevant_metadata(current_metadata)['java'] == {
            'component': row['java_component'], 'majorVersion': row['java_major_version']},
            'reported Java selection differs from current metadata: ' + version)
        require(log4j_relevant_metadata(current_metadata)['logging_argument'] == row['logging_argument_template'],
                'reported Log4j JVM argument differs from current metadata: ' + version)
        require(log4j_relevant_metadata(current_metadata)['logging_file'] == row['logging_config'],
                'reported logging resource differs from current metadata: ' + version)
        require(log4j_relevant_metadata(current_metadata)['jvm_argument_log4j_or_jndi_mentions'] ==
                row['jvm_argument_log4j_or_jndi_mentions'],
                'reported JVM security arguments differ from current metadata: ' + version)
        current_manifest_row = current_manifest_index.get(version)
        require(current_manifest_row is not None and current_manifest_row.get('url') == row['current_manifest_metadata_url']
                and current_manifest_row.get('sha1') == row['current_manifest_metadata_sha1'],
                'current version manifest does not bind to metadata snapshot: ' + version)
        retained_row = launcher_index['versions'][version]
        require(row['retained_metadata_url'] == retained_row['metadata_url']
                and row['retained_metadata_sha1'] == retained_row['metadata_sha1'],
                'retained metadata identity differs from the pinned launcher index: ' + version)
    for case in report['cases']:
        version = case['minecraft_version']
        metadata_row = metadata_by_version[version]
        require(case.get('java_component') == metadata_row['java_component'],
                'case Java component differs from launcher metadata: ' + case['name'])
        require(case.get('java_runtime_name') == runtime_names[metadata_row['java_component']],
                'case Java runtime differs from pinned Mojang component: ' + case['name'])
        current_metadata = json.loads(resolve_repo_path(
            metadata_row['current_metadata_snapshot_path']).read_text(encoding='utf-8'))
        libraries = [library['name'] for library in current_metadata.get('libraries', [])]
        core = next((name.rsplit(':', 1)[1] for name in libraries
                     if name.startswith('org.apache.logging.log4j:log4j-core:')), None)
        patchy = next((name.rsplit(':', 1)[1] for name in libraries
                       if name.startswith('com.mojang:patchy:')), None)
        require(case.get('log4j_core_version') == core and case.get('patchy_version') == patchy,
                'case Log4j/Patchy versions differ from Minecraft metadata: ' + case['name'])

    manifest = report['version_manifest_v2']
    manifest_bytes = resolve_repo_path(manifest['snapshot_path']).read_bytes()
    require(digest_bytes(manifest_bytes, 'sha256') == manifest['sha256'],
            'version_manifest_v2 snapshot hash mismatch')
    runtime_all = report['mojang_java_runtime_all']
    all_bytes = resolve_repo_path(runtime_all['snapshot_path']).read_bytes()
    require(digest_bytes(all_bytes, 'sha256') == runtime_all['sha256'],
            'Mojang runtime all.json snapshot hash mismatch')
    all_index = json.loads(all_bytes)
    for version in report['verified_affected_version_metadata']:
        component = version['java_component']
        expected_major = version['java_major_version']
        runtime = report['runtime_components'][component]
        output = runtime.get('java_version_output', '')
        match = re.search(r'version "([^\"]+)"', output)
        require(match is not None, 'runtime Java version output is not parseable: ' + component)
        actual_major = 8 if match.group(1).startswith('1.8') else int(match.group(1).split('.')[0])
        require(actual_major == expected_major, 'Mojang runtime major version differs from launcher metadata: ' + component)
    for component, runtime in report['runtime_components'].items():
        component_rows = all_index[report['platform']][component]
        require(len(component_rows) == 1, 'pinned runtime component manifest is ambiguous')
        component_row = component_rows[0]
        require(component_row['version']['name'] == runtime.get('version_name'),
                'runtime name differs from pinned Mojang index: ' + component)
        runtime_manifest = json.loads(resolve_repo_path(
            'docs/dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/metadata/' +
            report['platform'] + '-' + component + '-' + runtime['version_name'] + '.json').read_text())
        manifest_info = component_row['manifest']
        runtime_manifest_path = resolve_repo_path(
            'docs/dependency-evidence/critical-reachability-2026-11-21/log4j-mojang-runtime-2026-11-22/metadata/' +
            report['platform'] + '-' + component + '-' + runtime['version_name'] + '.json')
        runtime_manifest_bytes = runtime_manifest_path.read_bytes()
        require(digest_bytes(runtime_manifest_bytes, 'sha1') == manifest_info['sha1'],
                'runtime component manifest SHA-1 mismatch: ' + component)
        require(digest_bytes(runtime_manifest_bytes, 'sha256') == runtime['manifest_sha256'],
                'runtime component manifest SHA-256 mismatch: ' + component)
        require(len(runtime_manifest_bytes) == manifest_info['size'],
                'runtime component manifest size mismatch: ' + component)
        manifest_files = runtime_manifest['files']
        require(len(runtime.get('installed_files', [])) == runtime.get('installed_file_count'),
                'runtime installed file record count mismatch: ' + component)
        for installed in runtime['installed_files']:
            spec = manifest_files.get(installed['path'])
            require(spec is not None and spec.get('type') == 'file',
                    'installed runtime file is absent from Mojang manifest: ' + installed['path'])
            raw = spec['downloads']['raw']
            require(installed['raw_sha1'] == raw['sha1'] and installed['raw_size'] == raw['size'],
                    'installed runtime hash record differs from Mojang manifest: ' + installed['path'])

    return {'platform': report['platform'], 'case_count': len(report['cases']),
            'source_versions': len(metadata_rows), 'runtime_components': len(report['runtime_components']),
            'security_clearance': False, 'release_blocking': True}


def validate_static_dispositions():
    overlay = read_json(DISPOSITION_REPORT)
    require(overlay.get('schema') == 1 and overlay.get('security_clearance') is False and
            overlay.get('risk_accepted') is False and overlay.get('release_blocking') is True,
            'source-bound Log4j overlay must remain incomplete, unaccepted, and release-blocking')
    scope = overlay.get('scope', {})
    require(scope.get('total_occurrences') == 490 and scope.get('candidate_occurrences') == 385 and
            scope.get('integrated_occurrences') == 105 and scope.get('counts_changed') is False,
            'Log4j update must preserve the inventory counts')
    ledger = read_json(ROOT / 'docs/security-advisories.json')
    ledger_pointer = ledger.get('critical_reachability_evidence', {}).get('log4j_runtime_reachability', {})
    require(ledger_pointer.get('path') == DISPOSITION_REPORT.relative_to(ROOT).as_posix() and
            ledger_pointer.get('sha256') == digest_bytes(DISPOSITION_REPORT.read_bytes(), 'sha256') and
            set(ledger_pointer.get('advisory_ids', [])) == TARGETED_LOG4J_ADVISORIES and
            ledger_pointer.get('blocking_finding_index_rows') == 8 and
            ledger_pointer.get('version_scoped_not_applicable_records') == 3 and
            ledger_pointer.get('security_clearance') is False and
            ledger_pointer.get('risk_accepted') is False and
            ledger_pointer.get('release_blocking') is True,
            'structured advisory ledger does not point to the blocking Log4j runtime overlay')
    findings = {row.get('advisory_id'): row for row in overlay.get('findings', [])}
    require(set(findings) == TARGETED_LOG4J_ADVISORIES,
            'source-bound overlay advisory set differs from the three targeted Log4j advisories')
    for advisory, finding in findings.items():
        require(finding.get('disposition') == 'Further investigation' and finding.get('failing') is True and
                finding.get('release_blocking') is True and finding.get('risk_accepted') is False,
                'vulnerable Log4j occurrence was incorrectly cleared: ' + advisory)
    finding_index = read_json(FINDING_INDEX)
    indexed_rows = [row for row in finding_index.get('records', [])
                    if row.get('advisory') in TARGETED_LOG4J_ADVISORIES and
                    row.get('purl', '').startswith('pkg:maven/org.apache.logging.log4j/log4j-core@')]
    expected_rows = {}
    for advisory, finding in findings.items():
        for source in finding.get('source_group_occurrences', []):
            key = (advisory, source.get('source_kind'), source.get('source_group'),
                   source.get('source_sha'), source.get('purl'))
            expected_rows[key] = source
    actual_rows = {}
    for row in indexed_rows:
        key = (row.get('advisory'), row.get('source_kind'), row.get('group'),
               row.get('source_sha'), row.get('purl'))
        actual_rows[key] = row
    require(len(indexed_rows) == 8 and set(actual_rows) == set(expected_rows) and
            all(row.get('failing') is True and row.get('disposition') == 'Further investigation'
                for row in indexed_rows),
            'the eight critical Log4j findings no longer match exact source-bound index rows')

    local_probe = overlay.get('runtime_probe', {})
    local_path = resolve_repo_path(local_probe['path'])
    require(digest_bytes(local_path.read_bytes(), 'sha256') == local_probe['sha256'],
            'local Linux Log4j report checksum differs from the disposition overlay')
    hosted = overlay.get('hosted_runtime_matrix', {})
    workflow = hosted.get('workflow', {})
    require(workflow.get('conclusion') == 'success' and workflow.get('run_id') == 44990273341,
            'hosted Log4j matrix run is not the retained successful run')
    require(hosted.get('related_ci', {}).get('conclusion') == 'success',
            'related source-bound CI run is not successful')
    platform_reports = hosted.get('platform_reports', {})
    require(set(platform_reports) == {'linux', 'windows'}, 'hosted matrix must retain Linux and Windows reports')
    for platform, entry in platform_reports.items():
        report_path = resolve_repo_path(entry['report_path'])
        report_bytes = report_path.read_bytes()
        require(digest_bytes(report_bytes, 'sha256') == entry['report_sha256'],
                'hosted ' + platform + ' report checksum mismatch')
        report = read_json(report_path)
        require(report.get('platform') == entry['platform'] and report.get('status') == 'complete' and
                report.get('passed') is True and len(report.get('cases', [])) == 27 and
                report.get('security_clearance') is False and report.get('risk_accepted') is False and
                report.get('release_blocking') is True,
                'hosted ' + platform + ' report has invalid status or disposition flags')
        require(report.get('analysis_commit') == workflow.get('analysis_commit'),
                'hosted ' + platform + ' report analysis commit differs from the run record')
        require({name: value.get('version_name') for name, value in report.get('runtime_components', {}).items()} ==
                entry.get('runtime_versions'),
                'hosted ' + platform + ' runtime versions differ from the disposition overlay')
        archive_path = resolve_repo_path(entry['artifact_path'])
        archive_bytes = archive_path.read_bytes()
        require(digest_bytes(archive_bytes, 'sha256') == entry['artifact_sha256'] and
                len(archive_bytes) == entry['artifact_size_bytes'],
                'hosted ' + platform + ' artifact checksum or size mismatch')
        with zipfile.ZipFile(archive_path) as archive:
            require(archive.read('mojang-log4j-runtime-probes.json') == report_bytes,
                    'hosted ' + platform + ' archive does not contain the retained JSON report')
            prefix = LOG4J_METADATA_DIR.relative_to(ROOT).as_posix() + '/'
            members = [name for name in archive.namelist() if name.startswith(prefix) and not name.endswith('/')]
            require(bool(members), 'hosted ' + platform + ' archive has no pinned Mojang metadata')
            for member in members:
                require(resolve_repo_path(member).read_bytes() == archive.read(member),
                        'hosted ' + platform + ' archive metadata differs from the committed snapshot: ' + member)
        validate(report_path)

    version_record = overlay.get('minecraft_1_19_version_check', {})
    version_path = resolve_repo_path(version_record['path'])
    version_bytes = version_path.read_bytes()
    require(digest_bytes(version_bytes, 'sha256') == version_record['sha256'],
            '1.19 Log4j version-scope report checksum mismatch')
    version_report = read_json(version_path)
    require(version_report.get('disposition', {}).get('classification') == 'Not applicable' and
            version_report['disposition'].get('risk_accepted') is False and
            version_record.get('advisory_dispositions') == 3,
            '1.19 version exclusion must remain a supported, narrow Not applicable disposition')
    require(version_report.get('source_group_binding', {}).get('source_sha') ==
            '06b350856605011c1549d51d6edd3d351c5021c0',
            '1.19 version-scope report has the wrong candidate source SHA')
    require(digest_bytes(FINDING_INDEX.read_bytes(), 'sha256') ==
            version_report.get('finding_index', {}).get('sha256'),
            '1.19 version-scope report finding-index hash mismatch')
    metadata_manifest_path = resolve_repo_path(version_report['minecraft_version_manifest']['path'])
    manifest_bytes = metadata_manifest_path.read_bytes()
    require(digest_bytes(manifest_bytes, 'sha256') == version_report['minecraft_version_manifest']['sha256'],
            '1.19 metadata manifest hash mismatch')
    version_manifest = {row['id']: row for row in json.loads(manifest_bytes)['versions']}
    expected_versions = {'1.19', '1.19.1', '1.19.2'}
    rows = version_report.get('metadata_observations', [])
    require({row.get('minecraft_version') for row in rows} == expected_versions,
            '1.19 version-scope report does not cover exactly 1.19 through 1.19.2')
    artifact = version_report.get('verified_log4j_core_artifact', {})
    artifact_path = resolve_repo_path(artifact['path'])
    artifact_bytes = artifact_path.read_bytes()
    require(len(artifact_bytes) == artifact['size_bytes'] and
            digest_bytes(artifact_bytes, 'sha1') == artifact['sha1'] and
            digest_bytes(artifact_bytes, 'sha256') == artifact['sha256'],
            'retained Log4j Core 2.17.0 JAR hash or size mismatch')
    for row in rows:
        version = row['minecraft_version']
        version_row = version_manifest.get(version)
        require(version_row is not None and version_row.get('url') == row['metadata_url'] and
                version_row.get('sha1') == row['metadata_sha1'],
                '1.19 metadata row differs from current Mojang manifest: ' + version)
        snapshot_path = resolve_repo_path(row['metadata_snapshot_path'])
        snapshot_bytes = snapshot_path.read_bytes()
        require(digest_bytes(snapshot_bytes, 'sha1') == row['metadata_sha1'] and
                digest_bytes(snapshot_bytes, 'sha256') == row['metadata_sha256'] and
                len(snapshot_bytes) == row['metadata_size_bytes'],
                '1.19 metadata snapshot checksum mismatch: ' + version)
        metadata = json.loads(snapshot_bytes)
        require(metadata.get('id') == version and metadata.get('javaVersion', {}).get('component') == 'java-runtime-gamma' and
                metadata.get('javaVersion', {}).get('majorVersion') == 17,
                '1.19 Java runtime selection differs from exact metadata: ' + version)
        core = [library for library in metadata.get('libraries', [])
                if library.get('name') == 'org.apache.logging.log4j:log4j-core:2.17.0']
        require(len(core) == 1, '1.19 exact metadata lacks a unique Log4j Core 2.17.0: ' + version)
        spec = core[0]['downloads']['artifact']
        require(spec.get('sha1') == artifact['sha1'] and spec.get('size') == artifact['size_bytes'] and
                spec.get('url') == artifact['url'],
                '1.19 Mojang library identity differs from retained Log4j JAR: ' + version)
    purl = 'pkg:maven/org.apache.logging.log4j/log4j-core@2.17.0'
    for item in version_report['advisories']:
        advisory = item['advisory_id']
        require(advisory in TARGETED_LOG4J_ADVISORIES and item.get('purl') == purl and
                item.get('disposition') == 'Not applicable' and item.get('risk_accepted') is False and
                item.get('release_blocking') is False and item.get('review_date') == '2026-11-22' and
                item.get('source_sha') == '06b350856605011c1549d51d6edd3d351c5021c0',
                '1.19 advisory disposition is incomplete or overly broad: ' + advisory)
        require(not any(row.get('purl') == purl and row.get('advisory') == advisory
                        for row in finding_index['records']),
                'finding index contains a targeted advisory occurrence for Log4j 2.17.0: ' + advisory)
        require(item.get('upstream_affected_ranges') == item.get('affected_ranges'),
                '1.19 upstream affected-range evidence is inconsistent: ' + advisory)
    require({item.get('advisory_id') for item in version_report['advisories']} == TARGETED_LOG4J_ADVISORIES,
            '1.19 version-scope advisory set mismatch')
    overlay_exclusions = {item.get('advisory_id'): item for item in overlay.get('version_scope_dispositions', [])}
    require(set(overlay_exclusions) == TARGETED_LOG4J_ADVISORIES,
            'overlay does not retain the three narrow 1.19 version-scope dispositions')
    for advisory, item in overlay_exclusions.items():
        require(item.get('disposition') == 'Not applicable' and item.get('risk_accepted') is False and
                item.get('release_blocking') is False and item.get('purl') == purl and
                item.get('source_sha') == '06b350856605011c1549d51d6edd3d351c5021c0' and
                item.get('minecraft_versions') == ['1.19', '1.19.1', '1.19.2'],
                'overlay 1.19 disposition is too broad or inconsistent: ' + advisory)
    return {'hosted_reports': len(platform_reports), 'version_scope_dispositions': len(overlay_exclusions)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expected-analysis-commit')
    args = parser.parse_args()
    try:
        result = validate(args.report)
        static_result = validate_static_dispositions()
        if args.expected_analysis_commit:
            report = read_json(args.report)
            require(report.get('analysis_commit') == args.expected_analysis_commit,
                    'analysis commit differs from expected checkout commit')
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('Mojang Log4j runtime evidence validation failed: ' + str(exc), file=sys.stderr)
        return 1
    print('Mojang Log4j runtime evidence validated:', result['case_count'], 'cases on', result['platform'],
          'across', result['source_versions'], 'Minecraft metadata versions and',
          result['runtime_components'], 'runtime components; static records include',
          static_result['hosted_reports'], 'verified hosted reports and',
          static_result['version_scope_dispositions'], 'narrow Not applicable version scopes; security remains release-blocking.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
