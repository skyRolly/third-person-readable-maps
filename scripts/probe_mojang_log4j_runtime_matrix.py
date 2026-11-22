#!/usr/bin/env python3
"""Probe pinned Minecraft Log4j configurations on exact Mojang JRE components."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import platform as platform_module
import re
import subprocess
import sys
import threading
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
METADATA = EVIDENCE / 'log4j-mojang-runtime-2026-11-22/metadata'
LOG4J_REPORT = EVIDENCE / 'log4j-chat-input-reachability-2026-11-21.json'
LAUNCHER_INDEX = ROOT / 'docs/dependency-evidence/log4j-default-launcher-2026-11-14/metadata-index.json'
ARTIFACTS = ROOT / 'tests/fixtures/critical_reachability/artifacts.json'
ALL_JSON_SHA256 = '7072c6df74f91121e13f01678c8af93be85139cb35c403b03add17717d885b1d'
ALL_JSON_URL = 'https://piston-meta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json'
ALLOWED_HOSTS = {'piston-meta.mojang.com', 'piston-data.mojang.com', 'libraries.minecraft.net'}
_CACHE_LOCKS = {}
_CACHE_LOCKS_GUARD = threading.Lock()
LOG4J_COORDINATES = {
    'com.mojang:patchy:1.3.9',
    'com.mojang:patchy:2.1.6',
    'org.apache.logging.log4j:log4j-api:2.8.1',
    'org.apache.logging.log4j:log4j-core:2.8.1',
    'org.apache.logging.log4j:log4j-api:2.14.1',
    'org.apache.logging.log4j:log4j-core:2.14.1',
}


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS or
            parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError('untrusted upstream URL: ' + url)
    return url


def fetch_bytes(url):
    with urlopen(checked_url(url), timeout=90) as response:
        return response.read()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def expected_java_platform():
    machine = platform_module.machine().lower()
    if sys.platform.startswith('linux') and machine in ('x86_64', 'amd64'):
        return 'linux'
    if sys.platform == 'win32' and machine in ('amd64', 'x86_64'):
        return 'windows-x64'
    raise ValueError('the pinned Mojang runtime matrix supports Linux x86_64 and Windows x64 only')


def safe_target(root, relative):
    pure = PurePosixPath(relative)
    if pure.is_absolute() or '..' in pure.parts or not pure.parts:
        raise ValueError('unsafe Mojang runtime path: ' + relative)
    target = root.joinpath(*pure.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.parent.resolve().is_relative_to(root.resolve()):
        raise ValueError('Mojang runtime path escapes its root: ' + relative)
    return target


def verify_download(url, expected_size, expected_sha1, cache):
    target = cache / expected_sha1
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.setdefault(expected_sha1, threading.Lock())
    with lock:
        if target.exists():
            payload = target.read_bytes()
        else:
            payload = fetch_bytes(url)
            if len(payload) != expected_size or sha1(payload) != expected_sha1:
                raise ValueError('Mojang artifact size or SHA-1 mismatch: ' + url)
            temporary = target.with_suffix('.tmp')
            temporary.write_bytes(payload)
            temporary.replace(target)
        if len(payload) != expected_size or sha1(payload) != expected_sha1:
            raise ValueError('cached Mojang artifact size or SHA-1 mismatch: ' + expected_sha1)
        return payload


def materialize_runtime(runtime_spec, runtime_root, object_cache):
    raw_manifest = runtime_spec['manifest_bytes']
    manifest = runtime_spec['manifest']
    info = runtime_spec['manifest_info']
    if len(raw_manifest) != info['size'] or sha1(raw_manifest) != info['sha1']:
        raise ValueError('runtime manifest identity mismatch')
    runtime_root.mkdir(parents=True, exist_ok=True)
    object_cache.mkdir(parents=True, exist_ok=True)
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('runtime manifest has no files')
    install_root = runtime_root / 'root'
    install_root.mkdir(parents=True, exist_ok=True)
    for relative, item in files.items():
        if item.get('type') == 'directory':
            safe_target(install_root, relative).mkdir(parents=True, exist_ok=True)

    links = []
    file_items = []
    for relative, item in files.items():
        if item.get('type') == 'file':
            file_items.append((relative, item))
        elif item.get('type') == 'link':
            links.append((relative, item.get('target')))
        elif item.get('type') != 'directory':
            raise ValueError('unknown runtime manifest entry type for ' + relative)

    def install_one(row):
        relative, item = row
        downloads = item.get('downloads', {})
        raw_spec = downloads.get('raw')
        if not isinstance(raw_spec, dict):
            raise ValueError('runtime file lacks a raw manifest entry: ' + relative)
        compressed_spec = downloads.get('lzma')
        selected = compressed_spec if isinstance(compressed_spec, dict) else raw_spec
        payload = verify_download(selected['url'], selected['size'], selected['sha1'], object_cache)
        content = lzma.decompress(payload, format=lzma.FORMAT_AUTO) if compressed_spec else payload
        if len(content) != raw_spec['size'] or sha1(content) != raw_spec['sha1']:
            raise ValueError('runtime file raw size or SHA-1 mismatch: ' + relative)
        target = safe_target(install_root, relative)
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_bytes(content)
        temporary.replace(target)
        if item.get('executable') and os.name != 'nt':
            target.chmod(target.stat().st_mode | 0o111)
        return {'path': relative, 'raw_size': len(content), 'raw_sha1': raw_spec['sha1'],
                'download_size': len(payload), 'download_sha1': selected['sha1'],
                'compression': 'lzma' if compressed_spec else 'raw'}

    installed = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(install_one, row) for row in file_items]
        for future in as_completed(futures):
            installed.append(future.result())
    for relative, link_target in links:
        if not isinstance(link_target, str):
            raise ValueError('runtime link has no target: ' + relative)
        link = safe_target(install_root, relative)
        target_path = PurePosixPath(link_target)
        if target_path.is_absolute():
            raise ValueError('absolute symlink target in runtime manifest: ' + relative)
        if link.exists() or link.is_symlink():
            link.unlink()
        if os.name == 'nt':
            raise ValueError('unexpected symlink in Windows Mojang runtime manifest: ' + relative)
        link.symlink_to(str(target_path))
    java_name = 'java.exe' if os.name == 'nt' else 'java'
    java = install_root / 'bin' / java_name
    if not java.is_file():
        raise ValueError('materialized runtime has no java executable')
    return install_root, java, sorted(installed, key=lambda item: item['path'])


def sanitize_env(java_home, home):
    env = {
        'PATH': str(java_home / 'bin') + os.pathsep + os.defpath,
        'LANG': 'C.UTF-8',
        'TZ': 'UTC',
        'HOME': str(home),
        'USERPROFILE': str(home),
        'TMPDIR': str(home),
        'TMP': str(home),
        'TEMP': str(home),
    }
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR'):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def clean_source_paths(text, replacements):
    for path, label in replacements:
        text = text.replace(str(path), label)
    return text


def version_manifest_row(version, index_row, version_refs):
    row = version_refs.get(version)
    if not row:
        raise ValueError('version manifest does not list Minecraft ' + version)
    current_raw = fetch_bytes(row['url'])
    current_doc = json.loads(current_raw)
    current_digest = sha1(current_raw)
    if current_doc.get('id') != version:
        raise ValueError('current Minecraft metadata version ID mismatch: ' + version)

    # Keep the exact metadata indexed by the retained launcher survey as the
    # primary source for classpath order. Mojang occasionally republishes
    # metadata at a new content-addressed URL while leaving the runtime
    # selection and vulnerable artifacts unchanged.
    pinned_raw = fetch_bytes(index_row['metadata_url'])
    pinned_digest = sha1(pinned_raw)
    if pinned_digest != index_row['metadata_sha1']:
        raise ValueError('retained Minecraft metadata SHA-1 mismatch: ' + version)
    pinned_doc = json.loads(pinned_raw)
    if pinned_doc.get('id') != version:
        raise ValueError('retained Minecraft metadata version ID mismatch: ' + version)
    return {
        'url': index_row['metadata_url'], 'sha1': pinned_digest,
        'sha256': sha256(pinned_raw), 'size': len(pinned_raw), 'metadata': pinned_doc,
        'current_url': row['url'], 'current_sha1': current_digest,
        'current_sha256': sha256(current_raw), 'current_size': len(current_raw),
        'current_metadata': current_doc, 'current_raw': current_raw,
        'pinned_url': index_row['metadata_url'], 'pinned_sha1': pinned_digest,
        'pinned_sha256': sha256(pinned_raw), 'pinned_size': len(pinned_raw),
        'pinned_metadata': pinned_doc, 'pinned_raw': pinned_raw,
    }


def relevant_launcher_metadata(metadata):
    log4j_libraries = []
    for library in metadata.get('libraries', []):
        coordinate = library.get('name', '')
        if 'log4j' in coordinate.lower() or 'com.mojang:patchy:' in coordinate.lower():
            artifact = library.get('downloads', {}).get('artifact', {})
            log4j_libraries.append({
                'name': coordinate, 'url': artifact.get('url'),
                'sha1': artifact.get('sha1'), 'size': artifact.get('size'),
            })
    jvm_strings = []
    def collect_strings(value):
        if isinstance(value, str):
            if 'log4j' in value.lower() or 'jndi' in value.lower():
                jvm_strings.append(value)
        elif isinstance(value, list):
            for item in value:
                collect_strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                collect_strings(item)
    collect_strings(metadata.get('arguments', {}).get('jvm', []))
    logging = metadata.get('logging', {}).get('client', {})
    log_config = logging.get('file', {})
    return {
        'java_version': metadata.get('javaVersion'),
        'logging_argument': logging.get('argument'),
        'logging_config': {key: log_config.get(key) for key in ('id', 'sha1', 'size', 'url')},
        'log4j_or_patchy_libraries_in_manifest_order': log4j_libraries,
        'jvm_argument_log4j_or_jndi_mentions': jvm_strings,
    }


def current_commit():
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True,
                                timeout=10, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 'unavailable'


def preserve_snapshot(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('refusing to overwrite an existing evidence snapshot: ' + str(path))
    else:
        path.write_bytes(payload)
    return str(path.relative_to(ROOT))


def run_matrix(cache, compiler_home):
    # The probe changes cwd for isolated JVM invocations, so all cached runtime
    # executable paths must remain absolute across those subprocesses.
    cache = cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    platform_id = expected_java_platform()
    all_raw = (METADATA / 'all.json').read_bytes()
    if sha256(all_raw) != ALL_JSON_SHA256:
        raise ValueError('pinned Mojang Java runtime all.json SHA-256 mismatch')
    all_index = json.loads(all_raw)
    source_report = read_json(LOG4J_REPORT)
    launcher_index = read_json(LAUNCHER_INDEX)
    artifact_spec = read_json(ARTIFACTS)
    sample_by_version = {sample['minecraft_version']: sample
                         for sample in source_report['exact_client_code_path_samples']}
    required_samples = ['1.14.4', '1.17.1', '1.18.1']
    source_group_by_version = {
        version: group
        for group in source_report['source_group_bindings']
        for version in group['minecraft_versions']
    }
    if any(version not in source_group_by_version for version in required_samples):
        raise ValueError('source-bound Log4j report lacks one or more representative source bindings')

    version_manifest_url = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
    version_manifest_raw = fetch_bytes(version_manifest_url)
    version_manifest = json.loads(version_manifest_raw)
    version_manifest_snapshot = preserve_snapshot(
        METADATA / ('current-version-manifest-v2-' + sha256(version_manifest_raw) + '.json'),
        version_manifest_raw)
    version_refs = {entry['id']: entry for entry in version_manifest['versions']}
    metadata_observations = []
    resolved_metadata = {}
    runtime_components = set()
    for version, index_row in launcher_index['versions'].items():
        source = version_manifest_row(version, index_row, version_refs)
        metadata = source['metadata']
        current_metadata = source['current_metadata']
        if relevant_launcher_metadata(metadata) != relevant_launcher_metadata(current_metadata):
            raise ValueError('security-relevant Minecraft launcher metadata changed since retained survey: ' + version)
        current_snapshot = preserve_snapshot(
            METADATA / 'current-version-metadata' /
            (version + '-' + source['current_sha1'] + '.json'),
            source['current_raw'])
        retained_snapshot = preserve_snapshot(
            METADATA / 'retained-version-metadata' /
            (version + '-' + source['pinned_sha1'] + '.json'),
            source['pinned_raw'])
        logging = metadata.get('logging', {}).get('client')
        if not logging or logging.get('argument') != index_row['logging_argument']:
            raise ValueError('Mojang logging launch argument differs from retained index: ' + version)
        config = logging['file']
        expected_config = index_row['config']
        if (config.get('sha1') != expected_config['sha1'] or config.get('size') != expected_config['size'] or
                config.get('url') != expected_config['url']):
            raise ValueError('Mojang logging config identity differs from retained index: ' + version)
        component = metadata.get('javaVersion', {}).get('component')
        major = metadata.get('javaVersion', {}).get('majorVersion')
        if not component or not isinstance(major, int):
            raise ValueError('Minecraft metadata lacks Java runtime selection: ' + version)
        runtime_components.add(component)
        resolved_metadata[version] = source
        jvm_args = metadata.get('arguments', {}).get('jvm', [])
        log4j_arguments = []
        for arg in jvm_args:
            value = arg.get('value') if isinstance(arg, dict) else arg
            values = value if isinstance(value, list) else [value]
            for item in values:
                if isinstance(item, str) and ('log4j' in item.lower() or 'jndi' in item.lower()):
                    log4j_arguments.append(item)
        metadata_observations.append({
            'minecraft_version': version,
            'metadata_url': source['url'],
            'metadata_sha1': source['sha1'],
            'metadata_sha256': source['sha256'],
            'metadata_size': source['size'],
            'retained_metadata_url': source['pinned_url'],
            'retained_metadata_sha1': source['pinned_sha1'],
            'retained_metadata_sha256': source['pinned_sha256'],
            'retained_metadata_size': source['pinned_size'],
            'current_manifest_metadata_url': source['current_url'],
            'current_manifest_metadata_sha1': source['current_sha1'],
            'current_manifest_metadata_sha256': source['current_sha256'],
            'current_manifest_metadata_size': source['current_size'],
            'current_metadata_snapshot_path': current_snapshot,
            'retained_metadata_snapshot_path': retained_snapshot,
            'security_relevant_metadata_equal_to_retained_survey': True,
            'java_component': component,
            'java_major_version': major,
            'logging_argument_template': logging['argument'],
            'logging_config': {k: config[k] for k in ('id', 'sha1', 'size', 'url')},
            'logging_config_sha256': index_row['config_sha256'],
            'jvm_argument_log4j_or_jndi_mentions': log4j_arguments,
        })
    if len(metadata_observations) != 18 or len(runtime_components) != 3:
        raise ValueError('expected the 18-version, three-runtime Log4j metadata set')
    for version in required_samples:
        expected_sha1 = (sample_by_version[version]['version_metadata_sha1']
                         if version in sample_by_version
                         else launcher_index['versions'][version]['metadata_sha1'])
        if resolved_metadata[version]['sha1'] != expected_sha1:
            raise ValueError('source-bound metadata SHA-1 mismatch: ' + version)

    external_xml = ROOT / 'docs/dependency-evidence/log4j-default-launcher-2026-11-14/client-1.12.xml'
    if sha256(external_xml.read_bytes()) != launcher_index['versions']['1.14']['config_sha256']:
        raise ValueError('retained official Log4j XML SHA-256 mismatch')
    configs = {'launcher': external_xml.resolve()}
    for config_name, spec in artifact_spec['configurations'].items():
        path = ROOT / spec['path']
        if sha256(path.read_bytes()) != spec['sha256']:
            raise ValueError('probe configuration hash mismatch: ' + config_name)
        configs[config_name] = path.resolve()

    artifact_cache = cache / 'libraries'
    artifact_cache.mkdir(parents=True, exist_ok=True)
    artifact_paths = {}
    for coordinate in LOG4J_COORDINATES:
        spec = artifact_spec['artifacts'][coordinate]
        path = artifact_cache / spec['sha1']
        if not path.exists():
            payload = fetch_bytes(spec['url'])
            if len(payload) != spec['size'] or sha1(payload) != spec['sha1'] or sha256(payload) != spec['sha256']:
                raise ValueError('Log4j artifact hash mismatch: ' + coordinate)
            path.write_bytes(payload)
        payload = path.read_bytes()
        if len(payload) != spec['size'] or sha1(payload) != spec['sha1'] or sha256(payload) != spec['sha256']:
            raise ValueError('cached Log4j artifact hash mismatch: ' + coordinate)
        artifact_paths[coordinate] = path.resolve()
    classpath_orders = {}
    for version in required_samples:
        metadata = resolved_metadata[version]['metadata']
        core = '2.8.1' if version == '1.14.4' else '2.14.1'
        patchy = '1.3.9' if version == '1.14.4' else '2.1.6'
        expected = {
            'org.apache.logging.log4j:log4j-api:' + core,
            'org.apache.logging.log4j:log4j-core:' + core,
            'com.mojang:patchy:' + patchy,
        }
        found = {}
        ordered = []
        for library in metadata.get('libraries', []):
            coordinate = library.get('name')
            if coordinate in expected:
                item = library.get('downloads', {}).get('artifact')
                if item:
                    found[coordinate] = item
                    ordered.append(coordinate)
        if not expected.issubset(found):
            raise ValueError('sample Minecraft metadata lacks exact Log4j libraries: ' + version)
        for coordinate in expected:
            item = found[coordinate]
            spec = artifact_spec['artifacts'][coordinate]
            if any(item.get(field) != spec.get(field) for field in ('url', 'sha1', 'size')):
                raise ValueError('Log4j library identity mismatch in Minecraft ' + version + ': ' + coordinate)
        classpath_orders[version] = ordered

    java = compiler_home / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
    javac = compiler_home / 'bin' / ('javac.exe' if os.name == 'nt' else 'javac')
    javac_version = subprocess.run([str(javac), '-version'], capture_output=True, text=True, timeout=30)
    if javac_version.returncode:
        raise ValueError('cannot identify Java probe compiler')
    runtimes_root = cache / 'runtimes' / platform_id
    object_cache = cache / 'runtime-objects'
    runtime_rows = {}
    runtime_details = {}
    for component in sorted(runtime_components):
        entries = all_index.get(platform_id, {}).get(component, [])
        if len(entries) != 1:
            raise ValueError('pinned runtime snapshot must have exactly one ' + component)
        row = entries[0]
        runtime_name = row['version']['name']
        manifest_info = row['manifest']
        manifest_path = METADATA / f'{platform_id}-{component}-{runtime_name}.json'
        raw_manifest = manifest_path.read_bytes()
        if len(raw_manifest) != manifest_info['size'] or sha1(raw_manifest) != manifest_info['sha1']:
            raise ValueError('pinned runtime manifest mismatch: ' + component)
        runtime_spec = {'manifest': json.loads(raw_manifest), 'manifest_bytes': raw_manifest,
                        'manifest_info': manifest_info}
        home, runtime_java, installed = materialize_runtime(runtime_spec,
            runtimes_root / component / runtime_name, object_cache)
        home_env = cache / 'runtime-home'
        home_env.mkdir(parents=True, exist_ok=True)
        version_result = subprocess.run([str(runtime_java), '-version'], env=sanitize_env(home, home_env),
                                        capture_output=True, text=True, timeout=30)
        if version_result.returncode:
            raise ValueError('Mojang runtime failed to start: ' + component + '/' + runtime_name)
        java_version_text = version_result.stderr.strip()
        runtime_details[component] = {
            'version_name': runtime_name,
            'released': row['version'].get('released'),
            'manifest_url': manifest_info['url'],
            'manifest_sha1': manifest_info['sha1'],
            'manifest_sha256': sha256(raw_manifest),
            'manifest_size': len(raw_manifest),
            'java_version_output': java_version_text,
            'installed_file_count': len(installed),
            'installed_files': installed,
            'java_executable': str(runtime_java).replace(str(cache.resolve()), '<runtime-cache>'),
        }
        for minecraft_version in required_samples:
            version_info = resolved_metadata[minecraft_version]['metadata']['javaVersion']
            if version_info['component'] == component:
                reported = re.search(r'version "([^"]+)"', java_version_text)
                if not reported:
                    raise ValueError('unrecognized Java version output for ' + component)
                actual_major = 8 if reported.group(1).startswith('1.8') else int(reported.group(1).split('.')[0])
                if version_info['majorVersion'] != actual_major:
                    raise ValueError('Mojang runtime major version mismatch for ' + minecraft_version)
                runtime_details[component]['java_version_property_expected'] = reported.group(1)
                runtime_details[component]['java_specification_version_expected'] = (
                    '1.8' if actual_major == 8 else str(actual_major))
        runtime_rows[component] = {'row': row, 'home': home, 'java': runtime_java}

    with tempfile.TemporaryDirectory(prefix='issue45-mojang-log4j-') as temporary:
        work = Path(temporary)
        classes = work / 'classes'
        classes.mkdir()
        compile_cp = os.pathsep.join(str(artifact_paths[c]) for c in sorted(LOG4J_COORDINATES))
        source_names = ['ChatJndiProbe.java', 'JndiLookupProbe.java', 'LogLookupProbe.java',
                        'NoNetworkContextFactory.java', 'ThreadContextProbe.java',
                        'RuntimeSecurityPropertiesProbe.java',
                        'JndiRemoteCodebasePolicyProbe.java',
                        'LdapSerializedDataProbe.java']
        sources = [ROOT / 'tests/fixtures/critical_reachability' / name for name in source_names]
        compile_run = subprocess.run([str(javac), '--release', '8', '-cp', compile_cp, '-d', str(classes),
                                      *map(str, sources)], cwd=work, capture_output=True, text=True, timeout=90)
        if compile_run.returncode:
            raise ValueError('Java 8-compatible probe compilation failed: ' + compile_run.stderr[:2500])
        cases = []
        for version in required_samples:
            metadata = resolved_metadata[version]['metadata']
            component = metadata['javaVersion']['component']
            runtime = runtime_rows[component]
            runtime_java = runtime['java']
            runtime_home = runtime['home']
            core = '2.8.1' if version == '1.14.4' else '2.14.1'
            patchy = '1.3.9' if core == '2.8.1' else '2.1.6'
            api_coord = 'org.apache.logging.log4j:log4j-api:' + core
            core_coord = 'org.apache.logging.log4j:log4j-core:' + core
            patchy_coord = 'com.mojang:patchy:' + patchy
            launcher_cp = classpath_orders[version]
            if not launcher_cp or launcher_cp.index(patchy_coord) > launcher_cp.index(core_coord):
                raise ValueError('official metadata does not place Patchy before Log4j Core: ' + version)
            embedded = '1.14.4-embedded.xml' if core == '2.8.1' else '1.18.1-embedded.xml'
            runtime_name = runtime['row']['version']['name']

            def execute(name, main_class, coordinates, configuration, expected):
                case_dir = work / re.sub(r'[^A-Za-z0-9._-]+', '-', name)
                case_dir.mkdir()
                classpath = os.pathsep.join([str(classes), *[str(artifact_paths[c]) for c in coordinates]])
                command = [str(runtime_java), '-Djava.io.tmpdir=' + str(case_dir)]
                if main_class in ('JndiRemoteCodebasePolicyProbe', 'LdapSerializedDataProbe') and \
                        metadata['javaVersion']['majorVersion'] >= 9:
                    command.append('--add-opens=java.naming/com.sun.jndi.ldap=ALL-UNNAMED')
                    command.append('--add-opens=java.naming/com.sun.naming.internal=ALL-UNNAMED')
                if configuration:
                    config_path = configs['launcher'] if configuration == 'launcher' else configs[configuration]
                    command.append('-Dlog4j.configurationFile=' + str(config_path))
                command += ['-cp', classpath, main_class]
                run = subprocess.run(command, cwd=case_dir, env=sanitize_env(runtime_home, case_dir),
                                     capture_output=True, text=True, timeout=45)
                observed = {'exit_code': run.returncode}
                token = '$' + '{sys:issue45.safe.marker}'
                if main_class == 'LogLookupProbe':
                    log_path = case_dir / 'logs/latest.log'
                    log_text = log_path.read_text(errors='replace') if log_path.exists() else ''
                    observed.update({'expanded_stdout': 'LOCAL_LOOKUP_EXPANDED' in run.stdout,
                                     'literal_stdout': token in run.stdout,
                                     'expanded_file': 'LOCAL_LOOKUP_EXPANDED' in log_text,
                                     'literal_file': token in log_text})
                if main_class in ('JndiLookupProbe', 'ChatJndiProbe', 'ThreadContextProbe'):
                    match = re.search(r'^NO_NETWORK_CONTEXT_CALLS=(\d+)$', run.stdout, re.MULTILINE)
                    if match:
                        observed['NO_NETWORK_CONTEXT_CALLS'] = int(match.group(1))
                if main_class == 'RuntimeSecurityPropertiesProbe':
                    for key in ('JAVA_VERSION', 'JAVA_SPECIFICATION_VERSION',
                                'LDAP_TRUST_URL_CODEBASE_PROPERTY'):
                        match = re.search(r'^' + re.escape(key) + r'=(.*)$', run.stdout, re.MULTILINE)
                        if match:
                            observed[key] = match.group(1)
                    observed['runtime_security_properties_present'] = all(
                        key in observed for key in ('JAVA_VERSION', 'JAVA_SPECIFICATION_VERSION',
                                                    'LDAP_TRUST_URL_CODEBASE_PROPERTY'))
                if main_class == 'JndiRemoteCodebasePolicyProbe':
                    for key in ('JNDI_HELPER_CLASS', 'JNDI_CODEBASE_TRUST_GATE',
                                'JNDI_CODEBASE_TRUST_GATE_RAW',
                                'JNDI_SERIAL_DATA_TRUST_GATE',
                                'LDAP_TRUST_URL_CODEBASE_PROPERTY', 'JAVA_VERSION'):
                        match = re.search(r'^' + re.escape(key) + r'=(.*)$', run.stdout, re.MULTILINE)
                        if match:
                            observed[key] = match.group(1)
                    observed['codebase_policy_observation_present'] = all(
                        key in observed for key in ('JNDI_HELPER_CLASS', 'JNDI_CODEBASE_TRUST_GATE',
                                                    'JNDI_CODEBASE_TRUST_GATE_RAW',
                                                    'JNDI_SERIAL_DATA_TRUST_GATE', 'JAVA_VERSION'))
                if main_class == 'LdapSerializedDataProbe':
                    for key in ('LDAP_SERIALIZED_DATA_RESULT', 'LDAP_SERIALIZED_DATA_MARKER_MATCH',
                                'LDAP_DECODER_CLASS', 'NETWORK_REQUESTS'):
                        match = re.search(r'^' + re.escape(key) + r'=(.*)$', run.stdout, re.MULTILINE)
                        if match:
                            observed[key] = match.group(1)
                    observed['ldap_serialized_probe_present'] = (
                        observed.get('LDAP_SERIALIZED_DATA_RESULT', '').startswith(('deserialized:', 'blocked:'))
                        and observed.get('LDAP_DECODER_CLASS') == 'com.sun.jndi.ldap.Obj'
                        and observed.get('NETWORK_REQUESTS') == '0')
                observed['lookup_class_source'] = next((line.split('=', 1)[1] for line in run.stdout.splitlines()
                                                       if line.startswith('LOOKUP_CLASS_SOURCE=')), None)
                replacements = [(work, '<probe-work>'), (cache.resolve(), '<runtime-cache>')]
                if observed.get('lookup_class_source'):
                    observed['lookup_class_source'] = clean_source_paths(
                        observed['lookup_class_source'], replacements)
                expected_ok = (run.returncode == 0 and all(observed.get(k) == v for k, v in expected.items())
                               and (main_class != 'RuntimeSecurityPropertiesProbe' or
                                    observed.get('runtime_security_properties_present') is True)
                               and (main_class != 'JndiRemoteCodebasePolicyProbe' or
                                    observed.get('codebase_policy_observation_present') is True)
                               and (main_class != 'LdapSerializedDataProbe' or
                                    observed.get('ldap_serialized_probe_present') is True))
                cases.append({
                    'name': name, 'minecraft_version': version,
                    'source_kind': source_group_by_version[version]['source_kind'],
                    'source_group': source_group_by_version[version]['group'],
                    'source_sha': source_group_by_version[version]['source_sha'],
                    'exact_client_code_path_capture_in_prior_report': version in sample_by_version,
                    'java_component': component, 'java_runtime_name': runtime['row']['version']['name'],
                    'log4j_core_version': core, 'patchy_version': patchy,
                    'coordinates_in_order': coordinates, 'logging_configuration': configuration,
                    'expected': expected, 'observed': observed, 'passed': expected_ok,
                    'stdout': clean_source_paths(run.stdout, replacements),
                    'stderr': clean_source_paths(run.stderr, replacements),
                    'safe_no_network_context_factory': main_class in ('JndiLookupProbe', 'ChatJndiProbe',
                                                                      'ThreadContextProbe'),
                })

            execute(version + '-runtime-properties', 'RuntimeSecurityPropertiesProbe',
                    [patchy_coord, api_coord, core_coord], None,
                    {'JAVA_VERSION': runtime_details[component]['java_version_property_expected'],
                     'JAVA_SPECIFICATION_VERSION': runtime_details[component][
                         'java_specification_version_expected']})
            policy_expectations = {
                '8u202': ('com.sun.jndi.ldap.VersionHelper12', 'false', 'no_runtime_gate_method'),
                '8u51-cacert462b08': ('com.sun.jndi.ldap.VersionHelper12', 'false', 'no_runtime_gate_method'),
                '16.0.1.9.1': ('com.sun.jndi.ldap.VersionHelper', 'false', 'true'),
                '17.0.15': ('com.sun.jndi.ldap.VersionHelper', 'false', 'false'),
            }
            if runtime_name not in policy_expectations:
                raise ValueError('no exact JNDI policy expectations for Mojang runtime ' + runtime_name)
            helper_name, codebase_gate, serial_gate = policy_expectations[runtime_name]
            execute(version + '-jndi-codebase-policy', 'JndiRemoteCodebasePolicyProbe', [], None, {
                'JNDI_HELPER_CLASS': helper_name,
                'JNDI_CODEBASE_TRUST_GATE': codebase_gate,
                'JNDI_SERIAL_DATA_TRUST_GATE': serial_gate,
            })
            serialized_expectations = {
                '8u202': 'deserialized:java.lang.String',
                '8u51-cacert462b08': 'deserialized:java.lang.String',
                '16.0.1.9.1': 'deserialized:java.lang.String',
                '17.0.15': 'blocked:javax.naming.NamingException',
            }
            if runtime_name not in serialized_expectations:
                raise ValueError('no exact LDAP deserialization expectation for Mojang runtime ' + runtime_name)
            execute(version + '-ldap-serialized-data', 'LdapSerializedDataProbe', [], None,
                    {'LDAP_SERIALIZED_DATA_RESULT': serialized_expectations[runtime_name],
                     'LDAP_SERIALIZED_DATA_MARKER_MATCH': 'true' if serialized_expectations[
                         runtime_name].startswith('deserialized:') else 'false',
                     'NETWORK_REQUESTS': '0'})
            execute(version + '-launcher-message', 'LogLookupProbe', launcher_cp, 'launcher',
                    {'expanded_stdout': False, 'literal_stdout': True,
                     'expanded_file': False, 'literal_file': True})
            execute(version + '-launcher-direct-jndi', 'JndiLookupProbe', launcher_cp, 'launcher',
                    {'NO_NETWORK_CONTEXT_CALLS': 0})
            execute(version + '-launcher-chat-jndi', 'ChatJndiProbe', launcher_cp, 'launcher',
                    {'NO_NETWORK_CONTEXT_CALLS': 0})
            execute(version + '-launcher-thread-context', 'ThreadContextProbe', launcher_cp, 'launcher',
                    {'NO_NETWORK_CONTEXT_CALLS': 0})
            embedded_calls = 0 if core == '2.8.1' else 2
            execute(version + '-embedded-chat-jndi', 'ChatJndiProbe', launcher_cp, embedded,
                    {'NO_NETWORK_CONTEXT_CALLS': embedded_calls})
            if core == '2.8.1':
                core_first = [core_coord, api_coord, patchy_coord]
                execute(version + '-embedded-core-first-chat-jndi', 'ChatJndiProbe', core_first, embedded,
                        {'NO_NETWORK_CONTEXT_CALLS': 2})
            if core == '2.14.1':
                execute(version + '-synthetic-context-lookup', 'ThreadContextProbe', launcher_cp,
                        'synthetic-context.xml', {'NO_NETWORK_CONTEXT_CALLS': 1})
        probe_classes = sorted(path.name for path in classes.glob('*.class'))

    return {
        'schema': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
        'platform': platform_id, 'analysis_commit': current_commit(),
        'status': 'complete', 'security_clearance': False, 'risk_accepted': False,
        'release_blocking': True,
        'result_semantics': 'passed means each exact-runtime experiment produced its pinned expected observation, including vulnerable behavior such as accepted LDAP serialized data; it is not a security clearance.',
        'purpose': 'Local Log4j message/JNDI/ThreadContext probes and a harmless javaSerializedData decode check on exact Mojang runtime components. No network JNDI provider is used.',
        'advisory_ids': ['GHSA-jfh8-c2jp-5v3q', 'GHSA-7rjr-3q55-vv33', 'GHSA-fxph-q3j8-mv87'],
        'source_group_bindings': source_report['source_group_bindings'],
        'launcher_metadata_index_path': str(LAUNCHER_INDEX.relative_to(ROOT)),
        'launcher_metadata_index_sha256': sha256(LAUNCHER_INDEX.read_bytes()),
        'verified_affected_version_metadata': metadata_observations,
        'version_manifest_v2': {
            'url': version_manifest_url, 'sha256': sha256(version_manifest_raw), 'size': len(version_manifest_raw),
            'snapshot_path': version_manifest_snapshot,
            'usage': 'Used to locate current version metadata. Current and retained metadata are both hash checked, then security-relevant Java, logging, launcher argument and Log4j/Patchy library fields are compared before probing.',
        },
        'mojang_java_runtime_all': {'url': ALL_JSON_URL, 'sha256': ALL_JSON_SHA256,
                                    'size': len(all_raw), 'snapshot_path': str((METADATA / 'all.json').relative_to(ROOT))},
        'runtime_components': runtime_details,
        'probe_compiler': {'javac_version': javac_version.stderr.strip() or javac_version.stdout.strip(),
                           'compile_release': '8', 'probe_sources': [str(p.relative_to(ROOT)) for p in sources],
                           'probe_classes': probe_classes},
        'configuration_evidence': {
            'official_launcher_xml_path': str(external_xml.relative_to(ROOT)),
            'official_launcher_xml_sha256': sha256(external_xml.read_bytes()),
            'embedded_config_paths': {k: str(v.relative_to(ROOT)) for k, v in configs.items() if k != 'launcher'},
            'jndi_context_factory': 'NoNetworkContextFactory throws locally and performs no network lookup.',
        },
        'cases': cases, 'passed': all(case['passed'] for case in cases),
        'limitations': [
            'The test applies the configurationFile argument specified by exact Mojang version metadata; no running official launcher process was captured, so preservation of that argument and dependency order by each launcher is unverified.',
            'Synthetic inputs use a local JNDI context factory. No LDAP/DNS request, remote code loading, full Minecraft process, custom launcher, third-party mod, Java agent or runtime-generated class was tested.',
            'The javaSerializedData probe directly invokes the JDK LDAP Obj decoder with a harmless local java.lang.String. It makes no network request, uses no executable gadget and does not demonstrate a remote exploit; it records whether the exact decoder accepts or blocks that serialized value.',
            'The JNDI trust-policy probe reads private runtime fields or a public helper method using reflection. On modular Java it uses add-opens only for this read-only probe; no trust value is modified.',
            'This result executed the exact ' + platform_id + ' Mojang runtimes only. macOS and user-selected Java versions remain outside this run; the Windows runtime requires its separate Windows CI result.',
            'Component probes do not establish end-to-end Minecraft exploitability and do not clear or accept any advisory.',
        ],
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--java-home', type=Path, default=os.environ.get('JAVA_HOME'),
                        help='JDK 21 home used only to compile Java 8-compatible probes')
    args = parser.parse_args()
    if not args.java_home:
        parser.error('--java-home or JAVA_HOME is required')
    try:
        result = run_matrix(args.cache, args.java_home.resolve())
        code = 0 if result['passed'] else 1
        print('Mojang Log4j runtime probes:', sum(case['passed'] for case in result['cases']), '/',
              len(result['cases']), 'expected checks passed on', result['platform'])
        print('This verifies component behavior, not a complete launcher process or security clearance.')
    except (OSError, ValueError, KeyError, TypeError, lzma.LZMAError, subprocess.SubprocessError) as exc:
        result = {'schema': 1, 'status': 'incomplete', 'security_clearance': False, 'error': str(exc)}
        code = 2
        print('Mojang Log4j runtime probe incomplete: ' + str(exc), file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return code


if __name__ == '__main__':
    sys.exit(main())
