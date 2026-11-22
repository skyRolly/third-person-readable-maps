#!/usr/bin/env python3
"""Verify source-bound Commons Compress TAR reachability and compare fixed parser behavior."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21'
PROBE_DIR = EVIDENCE / 'commons-compress-probes-2026-11-22'
FIXTURE = PROBE_DIR / 'pax-oversize-length.tar.gz'
JAVA_SOURCE = ROOT / 'tests/fixtures/critical_reachability/CommonsTarGzipPipelineProbe.java'
LEGACY_REPORT = EVIDENCE / 'commons-compress-reachability-2026-11-21.json'
DISPOSITIONS = EVIDENCE / 'source-bound-dispositions-2026-11-21.json'
FOLLOWUP = EVIDENCE / 'commons-compress-runtime-followup-2026-11-22.json'

MANIFEST = {
    'url': 'https://piston-meta.mojang.com/v1/packages/be146d5f66a3627ed0a87c234c4d8dde8ab35098/1.14.4.json',
    'sha1': 'be146d5f66a3627ed0a87c234c4d8dde8ab35098',
}
ARTIFACTS = {
    'commons-compress-1.8.1': {
        'coordinate': 'org.apache.commons:commons-compress:1.8.1',
        'url': 'https://libraries.minecraft.net/org/apache/commons/commons-compress/1.8.1/commons-compress-1.8.1.jar',
        'sha1': 'a698750c16740fd5b3871425f4cb3bbaa87f529d',
        'sha256': '5fca136503f86ecc6cb61fbd17b137d59e56b45c7a5494e6b8fd3cabd4697fbd',
        'size': 365552,
        'minecraft_manifest': True,
    },
    'commons-io-2.5': {
        'coordinate': 'commons-io:commons-io:2.5',
        'url': 'https://libraries.minecraft.net/commons-io/commons-io/2.5/commons-io-2.5.jar',
        'sha1': '2852e6e05fbb95076fc091f6d1780f1f8fe35e0f',
        'sha256': 'a10418348d234968600ccb1d988efcbbd08716e1d96936ccc1880e7d22513474',
        'size': 208700,
        'minecraft_manifest': True,
    },
    'commons-compress-1.21': {
        'coordinate': 'org.apache.commons:commons-compress:1.21',
        'url': 'https://repo.maven.apache.org/maven2/org/apache/commons/commons-compress/1.21/commons-compress-1.21.jar',
        'sha1': '4ec95b60d4e86b5c95a0e919cb172a0af98011ef',
        'sha256': '6aecfd5459728a595601cfa07258d131972ffc39b492eb48bdd596577a2f244a',
        'size': 1018316,
        'sha1_sidecar': 'https://repo.maven.apache.org/maven2/org/apache/commons/commons-compress/1.21/commons-compress-1.21.jar.sha1',
    },
}
EXPECTED_BASE_REPORT_SHA256 = 'bec556dc9aae4440a41f37432f5e1b4e4c4d5dfbbc471857a5cb38139a740095'
EXPECTED_FOLLOWUP_SHA256 = '6fcf266f703b3a34536977fe00aac21e714de32a2010276b89ca4d214545d065'
EXPECTED_FIXTURE_SHA256 = 'd96b8f41faf3710f1707e69e15783f2c44df6d334ff6ddc98b5547b0f972a957'
EXPECTED_PROBE_SHA256 = '96d131c1e78557aa63bfb28c2309a6698246c172c004d0d5ab1c6ec98feb54cf'
EXPECTED_SOURCES = {
    '1.14-1.14.4': 'b6f7632af554a0e51c7d8c421c17adc893cc1379',
    '1.15-1.16.5': '4231b420749db2bbab3cf3e3a7825fc2516511d9',
    '1.17-1.19.2': '06b350856605011c1549d51d6edd3d351c5021c0',
}
EXPECTED_ADVISORIES = {
    'GHSA-xqfj-vm6h-2x34', 'GHSA-7hfm-57qf-j43q',
    'GHSA-crv7-7245-f45f', 'GHSA-mc84-pj99-q6hh',
}


def sha(data, algorithm):
    return hashlib.new(algorithm, data).hexdigest()


def validate_evidence():
    if sha(LEGACY_REPORT.read_bytes(), 'sha256') != EXPECTED_BASE_REPORT_SHA256:
        raise ValueError('historical Commons Compress report digest mismatch')
    if sha(FIXTURE.read_bytes(), 'sha256') != EXPECTED_FIXTURE_SHA256:
        raise ValueError('pinned malformed TAR fixture digest mismatch')
    if sha(JAVA_SOURCE.read_bytes(), 'sha256') != EXPECTED_PROBE_SHA256:
        raise ValueError('pinned Java probe digest mismatch')
    if sha(FOLLOWUP.read_bytes(), 'sha256') != EXPECTED_FOLLOWUP_SHA256:
        raise ValueError('Commons Compress follow-up evidence digest mismatch')

    old = json.loads(LEGACY_REPORT.read_text())
    sources = {}
    found = set()
    for finding in old.get('findings', []):
        advisory = finding.get('advisory_id')
        if advisory not in EXPECTED_ADVISORIES:
            continue
        found.add(advisory)
        if finding.get('occurrence_count') != 3:
            raise ValueError('unexpected historical occurrence count for ' + advisory)
        for occurrence in finding.get('occurrences', []):
            if occurrence.get('group') in EXPECTED_SOURCES:
                sources[occurrence['group']] = occurrence.get('source_sha')
    if found != EXPECTED_ADVISORIES or sources != EXPECTED_SOURCES:
        raise ValueError('historical advisory IDs or exact source SHAs changed')

    disposition = json.loads(DISPOSITIONS.read_text())
    if disposition.get('risk_accepted') or disposition.get('security_clearance'):
        raise ValueError('Commons Compress evidence cannot claim accepted risk or clearance')
    findings = {item['advisory_id']: item for item in disposition.get('findings', [])
                if item.get('advisory_id') in EXPECTED_ADVISORIES}
    if set(findings) != EXPECTED_ADVISORIES:
        raise ValueError('source-bound Commons Compress dispositions are incomplete')
    for advisory, finding in findings.items():
        if finding.get('occurrence_count') != 3 or finding.get('release_blocking') is not True:
            raise ValueError('Commons Compress advisory lost its blocker state: ' + advisory)
        if finding.get('risk_accepted') is not False:
            raise ValueError('Commons Compress risk acceptance must remain false: ' + advisory)
    if findings['GHSA-xqfj-vm6h-2x34'].get('disposition') != 'Further investigation':
        raise ValueError('TAR attacker-control question remains open; do not downgrade the blocker')
    latest = disposition.get('commons_compress_tar_reachability', {}).get('latest_followup', {})
    expected_path = 'docs/dependency-evidence/critical-reachability-2026-11-21/commons-compress-runtime-followup-2026-11-22.json'
    if latest.get('path') != expected_path or latest.get('sha256') != EXPECTED_FOLLOWUP_SHA256 or \
            latest.get('occurrences') != 12 or latest.get('source_groups') != 3 or \
            latest.get('security_clearance') is not False or latest.get('risk_accepted') is not False or \
            latest.get('release_blocking') is not True:
        raise ValueError('source-bound latest Commons Compress observation is missing or inconsistent')
    return old, findings


def validate_url(url, allowed):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or
            parsed.password or parsed.port not in (None, 443)):
        raise ValueError('untrusted evidence URL: ' + url)


def download_verified(spec, cache, download):
    target = cache / spec['sha1']
    if not target.exists():
        if not download:
            raise ValueError('missing pinned artifact ' + spec['coordinate'])
        validate_url(spec['url'], {'libraries.minecraft.net', 'repo.maven.apache.org'})
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = urlopen(spec['url'], timeout=60).read()
        verify_bytes(raw, spec)
        target.write_bytes(raw)
    raw = target.read_bytes()
    verify_bytes(raw, spec)
    if spec.get('sha1_sidecar'):
        validate_url(spec['sha1_sidecar'], {'repo.maven.apache.org'})
        declared = urlopen(spec['sha1_sidecar'], timeout=30).read().decode('ascii').strip().split()[0]
        if declared != spec['sha1']:
            raise ValueError('upstream Maven SHA-1 sidecar mismatch for ' + spec['coordinate'])
    return target.resolve()


def verify_bytes(raw, spec):
    if (len(raw) != spec['size'] or sha(raw, 'sha1') != spec['sha1'] or
            sha(raw, 'sha256') != spec['sha256']):
        raise ValueError('pinned artifact digest or size mismatch for ' + spec['coordinate'])


def verify_minecraft_manifest(cache, download):
    validate_url(MANIFEST['url'], {'piston-meta.mojang.com'})
    path = cache / MANIFEST['sha1']
    if not path.exists():
        if not download:
            raise ValueError('missing exact Mojang 1.14.4 metadata')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urlopen(MANIFEST['url'], timeout=60).read())
    raw = path.read_bytes()
    if sha(raw, 'sha1') != MANIFEST['sha1']:
        raise ValueError('exact Mojang metadata SHA-1 mismatch')
    metadata = json.loads(raw)
    if metadata.get('id') != '1.14.4':
        raise ValueError('Mojang metadata version ID mismatch')
    for name in ('commons-compress-1.8.1', 'commons-io-2.5'):
        spec = ARTIFACTS[name]
        matches = [lib.get('downloads', {}).get('artifact') for lib in metadata.get('libraries', [])
                   if lib.get('name') == spec['coordinate']]
        matches = [entry for entry in matches if entry]
        if len(matches) != 1:
            raise ValueError('expected one manifest artifact for ' + spec['coordinate'])
        actual = matches[0]
        if any(actual.get(key) != spec[key] for key in ('url', 'sha1', 'size')):
            raise ValueError('Mojang manifest artifact mismatch for ' + spec['coordinate'])


def experiment_environment(home, java_bin):
    env = {'PATH': str(java_bin.parent) + os.pathsep + os.defpath,
           'LANG': 'C.UTF-8', 'TZ': 'UTC', 'HOME': str(home),
           'USERPROFILE': str(home), 'TMPDIR': str(home), 'TMP': str(home), 'TEMP': str(home)}
    for name in ('SYSTEMROOT', 'WINDIR'):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def run_probe(cache, java_home, download):
    validate_evidence()
    verify_minecraft_manifest(cache, download)
    paths = {name: download_verified(spec, cache, download)
             for name, spec in ARTIFACTS.items()}
    java_name = 'java.exe' if os.name == 'nt' else 'java'
    javac_name = 'javac.exe' if os.name == 'nt' else 'javac'
    java = java_home / 'bin' / java_name
    javac = java_home / 'bin' / javac_name
    if not java.is_file() or not javac.is_file():
        raise ValueError('JAVA_HOME does not contain java and javac')
    results = []
    with tempfile.TemporaryDirectory(prefix='issue45-commons-compress-') as name:
        work = Path(name)
        home = work / 'private-home'
        home.mkdir(mode=0o700)
        classes = work / 'classes'
        classes.mkdir()
        env = experiment_environment(home, java)
        baseline_cp = os.pathsep.join(str(paths[key]) for key in
                                      ('commons-compress-1.8.1', 'commons-io-2.5'))
        compile_result = subprocess.run([str(javac), '-cp', baseline_cp, '-d', str(classes), str(JAVA_SOURCE)],
                                        cwd=work, env=env, capture_output=True, text=True, timeout=60)
        if compile_result.returncode:
            raise ValueError('source-bound probe compilation failed: ' + compile_result.stderr[:2000])
        version = subprocess.run([str(java), '-version'], cwd=work, env=env,
                                 capture_output=True, text=True, timeout=20)
        version_text = (version.stderr or version.stdout).strip()
        if version.returncode or '21.' not in version_text:
            raise ValueError('probe requires the configured Java 21 runtime')
        for name, compress in (('vulnerable_1.8.1', 'commons-compress-1.8.1'),
                               ('fixed_1.21', 'commons-compress-1.21')):
            cp = os.pathsep.join([str(classes), str(paths[compress]), str(paths['commons-io-2.5'])])
            completed = subprocess.run([str(java), '-Xmx32m', '-cp', cp,
                                        'CommonsTarGzipPipelineProbe', str(FIXTURE.resolve())],
                                       cwd=work, env=env, capture_output=True, text=True, timeout=30)
            stdout = completed.stdout.strip()
            if completed.returncode != 0:
                raise ValueError(name + ' probe exited ' + str(completed.returncode) + ': ' + completed.stderr[:2000])
            if name == 'vulnerable_1.8.1' and 'RESULT=OUT_OF_MEMORY' not in stdout:
                raise ValueError('exact 1.8.1 parser did not reproduce bounded-heap OOM')
            if name == 'fixed_1.21' and not stdout.startswith('RESULT=java.io.IOException:Paxheader value size'):
                raise ValueError('fixed 1.21 parser did not reject the inconsistent PAX record')
            results.append({'name': name, 'commons_compress': ARTIFACTS[compress]['coordinate'],
                            'commons_io': ARTIFACTS['commons-io-2.5']['coordinate'],
                            'max_heap': '32m', 'fixture_sha256': EXPECTED_FIXTURE_SHA256,
                            'exit_code': completed.returncode, 'stdout': stdout,
                            'stderr': completed.stderr.strip(), 'passed': True})
    return {'schema': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'java_version': version_text, 'network_used_by_probe': False,
            'fixture': {'path': str(FIXTURE.relative_to(ROOT)), 'size': FIXTURE.stat().st_size,
                        'sha256': EXPECTED_FIXTURE_SHA256},
            'artifacts': {name: {'coordinate': spec['coordinate'], 'url': spec['url'],
                                 'sha1': spec['sha1'], 'sha256': spec['sha256'], 'size': spec['size']}
                          for name, spec in ARTIFACTS.items()},
            'results': results, 'passed': all(result['passed'] for result in results)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, default=Path('.probe-cache'))
    parser.add_argument('--java-home', type=Path, default=Path(os.environ.get('JAVA_HOME', '')))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('commons-compress-reachability-probes.json'))
    args = parser.parse_args()
    java_home = args.java_home
    if not str(java_home) or str(java_home) == '.':
        java_path = shutil.which('java')
        if not java_path:
            raise SystemExit('Java 21 is required')
        java_home = Path(java_path).resolve().parent.parent
    cache = args.cache.resolve()
    result = run_probe(cache, java_home.resolve(), args.download)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('Commons Compress TAR probes: 2/2 passed; vulnerable 1.8.1 OOM reproduced and fixed 1.21 rejected the same fixture')
    print('Evidence report: ' + str(args.output))


if __name__ == '__main__':
    main()
