#!/usr/bin/env python3
"""Run local-only Log4j and Netty experiments using pinned Minecraft libraries."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/critical_reachability'


class RejectRedirects(HTTPRedirectHandler):
    """Pinned artifact URLs have no authorized redirect targets."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('unexpected redirect while fetching pinned evidence')


def validate_source_url(url, allowed_hosts):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in allowed_hosts or
            parsed.username or parsed.password or parsed.port not in (None, 443) or
            parsed.query or parsed.fragment):
        raise ValueError('untrusted source URL')


def fetch_https(url, allowed_hosts, max_bytes):
    validate_source_url(url, allowed_hosts)
    with build_opener(RejectRedirects()).open(url, timeout=60) as response:
        if response.geturl() != url:
            raise ValueError('unexpected redirect while fetching pinned evidence')
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError('source exceeds expected maximum size')
    return data


def verified_artifact(spec, cache, download, verification=None):
    sha1 = spec['sha1']
    if not re.fullmatch(r'[a-f0-9]{40}', sha1):
        raise ValueError('invalid artifact identity')
    if download:
        validate_source_url(spec['url'], {'libraries.minecraft.net', 'repo.maven.apache.org'})
    path = cache / sha1
    source = 'cache'
    if not path.exists():
        if not download:
            raise ValueError('missing cached artifact ' + sha1)
        raw = fetch_https(spec['url'], {'libraries.minecraft.net', 'repo.maven.apache.org'}, spec['size'])
        # Validate before publishing a cache entry.
        validate_bytes(raw, spec)
        path.write_bytes(raw)
        source = 'download'
    validate_bytes(path.read_bytes(), spec)
    checksum_url = spec.get('checksum_url')
    sidecar = 'not_applicable' if not checksum_url else 'not_retrieved_offline'
    if checksum_url and download:
        raw_checksum = fetch_https(checksum_url, {'repo.maven.apache.org'}, 1024)
        fields = raw_checksum.decode('ascii').strip().split()
        if not fields:
            raise ValueError('empty upstream checksum sidecar')
        declared = fields[0]
        if declared != spec['sha256']:
            raise ValueError('upstream SHA-256 sidecar mismatch for ' + sha1)
        sidecar = 'retrieved_and_verified'
    if verification is not None:
        verification.update({'artifact_source': source, 'size_sha1_sha256_verified': True,
                             'upstream_checksum': sidecar, 'checksum_url': checksum_url,
                             'previously_recorded_provenance': spec.get('verified_against')})
    return path.resolve()


def verified_minecraft_manifest(version, spec, cache, download):
    sha1 = spec['sha1']
    if not re.fullmatch(r'[a-f0-9]{40}', sha1):
        raise ValueError('invalid Minecraft manifest identity')
    url = urlsplit(spec['url'])
    if (url.scheme != 'https' or url.hostname != 'piston-meta.mojang.com' or
            url.username or url.password or url.port not in (None, 443)):
        raise ValueError('untrusted Minecraft manifest URL')
    path = cache / sha1
    if not path.exists():
        if not download:
            raise ValueError('missing cached Minecraft manifest ' + sha1)
        raw = fetch_https(spec['url'], {'piston-meta.mojang.com'}, 8 * 1024 * 1024)
        if hashlib.sha1(raw).hexdigest() != sha1:
            raise ValueError('Minecraft manifest digest mismatch for ' + version)
        path.write_bytes(raw)
    raw = path.read_bytes()
    if hashlib.sha1(raw).hexdigest() != sha1:
        raise ValueError('Minecraft manifest digest mismatch for ' + version)
    manifest = json.loads(raw)
    if manifest.get('id') != version:
        raise ValueError('Minecraft manifest version mismatch for ' + version)
    return manifest


def validate_bytes(raw, spec):
    if (len(raw) != spec['size'] or hashlib.sha1(raw).hexdigest() != spec['sha1'] or
            hashlib.sha256(raw).hexdigest() != spec['sha256']):
        raise ValueError('artifact size or digest mismatch for ' + spec['sha1'])


def experiment_environment(java_home, home):
    env = {'PATH': str(java_home / 'bin') + os.pathsep + os.defpath,
           'LANG': 'C.UTF-8', 'TZ': 'UTC', 'HOME': str(home), 'USERPROFILE': str(home),
           'TMPDIR': str(home), 'TMP': str(home), 'TEMP': str(home)}
    # Windows JVM startup needs the operating-system directory.
    for name in ('SYSTEMROOT', 'WINDIR'):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def run_experiments(cache, java_home, download):
    specification = json.loads((FIXTURES / 'artifacts.json').read_text())
    manifests = {version: verified_minecraft_manifest(version, spec, cache, download)
                 for version, spec in specification['minecraft_metadata'].items()}
    for coordinate, spec in specification['artifacts'].items():
        source_version = spec.get('minecraft')
        if source_version is None and 'minecraft_metadata_sha1' in spec:
            source_version = next((version for version, meta in specification['minecraft_metadata'].items()
                                   if meta['sha1'] == spec['minecraft_metadata_sha1']), None)
        if source_version is None:
            continue
        if source_version not in manifests:
            raise ValueError('artifact references an unverified Minecraft manifest: ' + coordinate)
        declared = [library.get('downloads', {}).get('artifact')
                    for library in manifests[source_version].get('libraries', [])
                    if library.get('name') == coordinate]
        declared = [item for item in declared if item]
        if len(declared) != 1:
            raise ValueError('artifact coordinate missing or ambiguous in Minecraft manifest: ' + coordinate)
        item = declared[0]
        if any(spec.get(field) != item.get(field) for field in ('url', 'sha1', 'size')):
            raise ValueError('artifact does not match Minecraft manifest: ' + coordinate)
    artifact_verification = {}
    paths = {}
    for name, spec in specification['artifacts'].items():
        artifact_verification[name] = {}
        paths[name] = verified_artifact(spec, cache, download, artifact_verification[name])
    configs = {}
    for name, spec in specification['configurations'].items():
        path = ROOT / spec['path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec['sha256']:
            raise ValueError('configuration digest mismatch for ' + name)
        configs[name] = path.resolve()
    java = java_home / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
    javac = java_home / 'bin' / ('javac.exe' if os.name == 'nt' else 'javac')
    cases = []
    with tempfile.TemporaryDirectory(prefix='issue45-probes-') as temporary:
        work = Path(temporary)
        classes = work / 'classes'
        classes.mkdir()
        env = experiment_environment(java_home, work)
        compile_classpath = os.pathsep.join(str(path) for name, path in paths.items()
                                           if name.endswith((':2.8.1', ':4.2.7.Final',
                                                             ':1.8.0', ':1.8.1', ':1.10.1', ':1.11.4')))
        sources = sorted(FIXTURES.glob('*.java'))
        compilation = subprocess.run([str(javac), '-cp', compile_classpath, '-d', str(classes),
                                      *map(str, sources)], cwd=work, env=env, capture_output=True,
                                     text=True, timeout=60)
        if compilation.returncode:
            raise ValueError('probe compilation failed: ' + compilation.stderr[:2000])
        java_version_result = subprocess.run([str(java), '-version'], env=env, capture_output=True,
                                             text=True, timeout=30)
        if java_version_result.returncode:
            raise ValueError('Java version check failed')

        def execute(name, main, coordinates, expected, config=None, no_lookups=False):
            directory = work / name
            directory.mkdir()
            classpath = os.pathsep.join([str(classes), *[str(paths[c]) for c in coordinates]])
            command = [str(java)]
            private_tmp = None
            if main in ('Lz4NativeProbe', 'Lz4AdvisoryProbe'):
                empty_native_path = directory / 'empty-native-path'
                empty_native_path.mkdir()
                private_tmp = directory / 'private-tmp'
                private_tmp.mkdir(mode=0o700)
                command.append('-Djava.io.tmpdir=' + str(private_tmp))
                command.append('-Djava.library.path=' + str(empty_native_path))
                if main == 'Lz4AdvisoryProbe':
                    command.append('-Xmx128m')
            if config:
                command.append('-Dlog4j.configurationFile=' + str(configs[config]))
            if no_lookups:
                command.append('-Dlog4j2.formatMsgNoLookups=true')
            command += ['-cp', classpath, main]
            if private_tmp is not None:
                command.append(str(private_tmp))
            completed = subprocess.run(command, cwd=directory, env=env, capture_output=True,
                                       text=True, timeout=30)
            observations = {}
            for field in ('NO_NETWORK_CONTEXT_CALLS', 'ACCEPTED_REQUESTS', 'FAILED_REQUESTS',
                          'SMUGGLED_REQUESTS', 'CREDENTIAL_NAMES_PRESENT',
                          'NATIVE_LOADED_BEFORE', 'NATIVE_LOADED_AFTER', 'TEMP_LOCK_FILES',
                          'TEMP_PREFIX_FILES', 'JAVA_TMPDIR_PRIVATE', 'NATIVE_LIBRARY_PATH_ISOLATED',
                          'FIRST_FRAGMENT_FALLBACKS', 'FINAL_FALLBACKS', 'HOST_SELECTIONS',
                          'FASTEST_FAST_NONZERO_OUTPUT_BYTES', 'SAFE_FAST_NONZERO_OUTPUT_BYTES',
                          'JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES', 'STREAM_BUFFERS_DISTINCT'):
                match = re.search(r'^' + field + r'=(\d+)$', completed.stdout, re.MULTILINE)
                if match:
                    observations[field] = int(match.group(1))
            for field in ('FASTEST_FAST_CLASS', 'SAFE_FAST_CLASS', 'JAVA_ONLY_FAST_CLASS',
                          'STREAM_DECOMPRESSOR_CLASS'):
                match = re.search(r'^' + field + r'=([A-Za-z0-9_.$]+)$', completed.stdout, re.MULTILINE)
                if match:
                    observations[field] = match.group(1)
            if main == 'LogLookupProbe':
                observations['expanded_stdout'] = 'LOCAL_LOOKUP_EXPANDED' in completed.stdout
                observations['literal_stdout'] = '${sys:issue45.safe.marker}' in completed.stdout
                logfile = directory / 'logs/latest.log'
                observations['expanded_file'] = logfile.exists() and 'LOCAL_LOOKUP_EXPANDED' in logfile.read_text()
                observations['literal_file'] = logfile.exists() and '${sys:issue45.safe.marker}' in logfile.read_text()
            def normalize(text):
                return text.replace(str(cache.resolve()), '<artifact-cache>').replace(str(work), '<experiment>')
            cases.append({'name': name, 'main': main, 'coordinates_in_order': coordinates,
                          'configuration': config, 'formatMsgNoLookups': no_lookups,
                          'expected': expected, 'observed': observations,
                          'exit_code': completed.returncode,
                          'passed': completed.returncode == 0 and all(observations.get(k) == v for k, v in expected.items()),
                          'stdout': normalize(completed.stdout), 'stderr': normalize(completed.stderr)})

        execute('credential-environment', 'EnvironmentProbe', [], {'CREDENTIAL_NAMES_PRESENT': 0})
        for core, patchy in (('2.8.1', '1.3.9'), ('2.14.1', '2.1.6')):
            normal = ['com.mojang:patchy:' + patchy, 'org.apache.logging.log4j:log4j-api:' + core,
                      'org.apache.logging.log4j:log4j-core:' + core]
            embedded = '1.14.4-embedded.xml' if core == '2.8.1' else '1.18.1-embedded.xml'
            for configuration in ('launcher', embedded):
                prefix = core + '-' + configuration
                literal = configuration == 'launcher'
                execute(prefix + '-message', 'LogLookupProbe', normal,
                        {'expanded_stdout': not literal, 'literal_stdout': literal,
                         'expanded_file': not literal, 'literal_file': literal}, configuration)
                expected_calls = 2 if core == '2.14.1' and not literal else 0
                execute(prefix + '-jndi', 'JndiLookupProbe', normal,
                        {'NO_NETWORK_CONTEXT_CALLS': expected_calls}, configuration)
                execute(prefix + '-chat-jndi', 'ChatJndiProbe', normal,
                        {'NO_NETWORK_CONTEXT_CALLS': expected_calls}, configuration)
                if core == '2.8.1':
                    execute(prefix + '-core-first', 'JndiLookupProbe', list(reversed(normal)),
                            {'NO_NETWORK_CONTEXT_CALLS': 0 if literal else 2}, configuration)
                    execute(prefix + '-chat-jndi-core-first', 'ChatJndiProbe', list(reversed(normal)),
                            {'NO_NETWORK_CONTEXT_CALLS': 0 if literal else 2}, configuration)
            if core == '2.14.1':
                # The 1.17.1 client embeds the same XML bytes as the 1.14.4
                # fixture; the 1.18.1 fixture is a distinct configuration.
                execute('2.14.1-1.17.1-exact-embedded-chat-jndi', 'ChatJndiProbe', normal,
                        {'NO_NETWORK_CONTEXT_CALLS': 2}, '1.14.4-embedded.xml')
        context_coordinates = ['com.mojang:patchy:2.1.6', 'org.apache.logging.log4j:log4j-api:2.14.1',
                               'org.apache.logging.log4j:log4j-core:2.14.1']
        for configuration in ('launcher', 'synthetic-context.xml'):
            for flag in (False, True):
                execute('context-' + configuration + '-' + str(flag), 'ThreadContextProbe',
                        context_coordinates, {'NO_NETWORK_CONTEXT_CALLS': 0 if configuration == 'launcher' else 1},
                        configuration, flag)
        for netty, accepted, failed, smuggled in (
                ('4.1.118.Final', 2, 0, 1), ('4.1.137.Final', 0, 1, 0),
                ('4.2.7.Final', 2, 0, 1), ('4.2.15.Final', 0, 1, 0)):
            coordinates = sorted(name for name in paths if name.startswith('io.netty:') and name.endswith(':' + netty))
            execute('netty-chunk-' + netty, 'NettyChunkProbe', coordinates,
                    {'ACCEPTED_REQUESTS': accepted, 'FAILED_REQUESTS': failed,
                     'SMUGGLED_REQUESTS': smuggled})
        for netty, first_fallback, final_fallback, host_selection in (
                ('4.1.118.Final', 1, 1, 0), ('4.1.137.Final', 0, 0, 1),
                ('4.2.7.Final', 1, 1, 0), ('4.2.15.Final', 1, 1, 0),
                ('4.2.17.Final', 0, 0, 1)):
            coordinates = sorted(name for name in paths if name.startswith('io.netty:') and name.endswith(':' + netty))
            execute('netty-sni-' + netty, 'NettySniProbe', coordinates,
                    {'FIRST_FRAGMENT_FALLBACKS': first_fallback,
                     'FINAL_FALLBACKS': final_fallback,
                     'HOST_SELECTIONS': host_selection})
        for coordinate, lz4_version in (
                ('org.lz4:lz4-java:1.8.0', '1.8.0'),
                ('at.yawk.lz4:lz4-java:1.8.1', '1.8.1'),
                ('at.yawk.lz4:lz4-java:1.10.1', '1.10.1'),
                ('at.yawk.lz4:lz4-java:1.11.4', '1.11.4')):
            execute('lz4-native-' + lz4_version, 'Lz4NativeProbe', [coordinate],
                    {'NATIVE_LOADED_BEFORE': 0, 'NATIVE_LOADED_AFTER': 1,
                     'JAVA_TMPDIR_PRIVATE': 1, 'NATIVE_LIBRARY_PATH_ISOLATED': 1,
                     **({'TEMP_LOCK_FILES': 0, 'TEMP_PREFIX_FILES': 1}
                        if lz4_version == '1.11.4' else {})})
            expected_fast = {
                '1.8.0': {
                    'FASTEST_FAST_CLASS': 'net.jpountz.lz4.LZ4JNIFastDecompressor',
                    'FASTEST_FAST_NONZERO_OUTPUT_BYTES': 0,
                    'SAFE_FAST_NONZERO_OUTPUT_BYTES': 923,
                    'JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES': 923,
                },
                '1.8.1': {
                    'FASTEST_FAST_CLASS': 'net.jpountz.lz4.LZ4JavaSafeFastDecompressor',
                    'FASTEST_FAST_NONZERO_OUTPUT_BYTES': 923,
                    'SAFE_FAST_NONZERO_OUTPUT_BYTES': 923,
                    'JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES': 923,
                },
                '1.10.1': {
                    'FASTEST_FAST_CLASS': 'net.jpountz.lz4.LZ4JavaSafeFastDecompressor',
                    'FASTEST_FAST_NONZERO_OUTPUT_BYTES': 0,
                    'SAFE_FAST_NONZERO_OUTPUT_BYTES': 0,
                    'JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES': 0,
                },
                '1.11.4': {
                    'FASTEST_FAST_CLASS': 'net.jpountz.lz4.LZ4JavaSafeFastDecompressor',
                    'FASTEST_FAST_NONZERO_OUTPUT_BYTES': 0,
                    'SAFE_FAST_NONZERO_OUTPUT_BYTES': 0,
                    'JAVA_ONLY_FAST_NONZERO_OUTPUT_BYTES': 0,
                },
            }[lz4_version]
            expected_fast.update({'NATIVE_LOADED_AFTER': 1, 'STREAM_BUFFERS_DISTINCT': 1,
                                  'STREAM_DECOMPRESSOR_CLASS': expected_fast['FASTEST_FAST_CLASS']})
            execute('lz4-advisory-' + lz4_version, 'Lz4AdvisoryProbe', [coordinate], expected_fast)
    return {'schema': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'status': 'complete', 'security_clearance': False,
            'purpose': 'Component-level reachability experiments with local synthetic inputs. Advisory gates remain separate.',
            'java_version': java_version_result.stderr.strip(), 'specification': specification,
            'artifact_verification_mode': 'download_and_verify_upstream_sidecars' if download else 'offline_pinned_hashes',
            'artifact_verification': artifact_verification,
            'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'harness_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(FIXTURES.glob('*.java'))},
            'cases': cases, 'passed': all(case['passed'] for case in cases)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--java-home', type=Path, default=os.environ.get('JAVA_HOME'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.java_home is None:
        parser.error('--java-home or JAVA_HOME is required')
    args.cache.mkdir(parents=True, exist_ok=True)
    try:
        result = run_experiments(args.cache, args.java_home.resolve(), args.download)
        code = 0 if result['passed'] else 1
        print(f"Reachability experiments: {sum(c['passed'] for c in result['cases'])}/{len(result['cases'])} expected results")
        print('Existing advisory findings continue to require security disposition.')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result = {'schema': 1, 'status': 'incomplete', 'security_clearance': False, 'error': str(exc)}
        code = 2
        print('Reachability experiment incomplete: ' + str(exc), file=sys.stderr)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
