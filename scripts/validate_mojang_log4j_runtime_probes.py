#!/usr/bin/env python3
"""Validate source hashes and fail-closed results for the Mojang Log4j runtime probe."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
SOURCE_REPORT = EVIDENCE / 'log4j-chat-input-reachability-2026-11-21.json'


def digest_bytes(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def resolve_repo_path(value):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expected-analysis-commit')
    args = parser.parse_args()
    try:
        result = validate(args.report)
        if args.expected_analysis_commit:
            report = read_json(args.report)
            require(report.get('analysis_commit') == args.expected_analysis_commit,
                    'analysis commit differs from expected checkout commit')
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print('Mojang Log4j runtime evidence validation failed: ' + str(exc), file=sys.stderr)
        return 1
    print('Mojang Log4j runtime evidence validated:', result['case_count'], 'cases on', result['platform'],
          'across', result['source_versions'], 'Minecraft metadata versions and',
          result['runtime_components'], 'runtime components; security remains release-blocking.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
