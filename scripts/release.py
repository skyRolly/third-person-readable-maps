#!/usr/bin/env python3
"""Validate a coordinated release and collect independently built Fabric JARs.

This script does not create tags, contact GitHub or publish anything. In strict
mode the reviewed plan must link to installed-JAR and graphical test evidence;
the links are attestations for human review, not machine proof of gameplay.
"""
import argparse
from datetime import date
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, BadZipFile

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.compile(r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z')
SHA = re.compile(r'[0-9a-f]{40}\Z')
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
ID = 'thirdpersonreadablemaps'
PREFIX = 'third-person-readable-maps'
MIXIN_CLASS = 'tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin.class'


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f'duplicate JSON key: {key}')
        value[key] = item
    return value


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    except (OSError, ValueError) as exc:
        raise Invalid(f'cannot read {path}: {exc}') from exc


def load_plan(path, candidate=False, config_path=ROOT / 'release/compatibility.json'):
    cfg = read_json(config_path)
    plan = read_json(path)
    require(cfg.get('schema') == plan.get('schema') == 1, 'unsupported schema')
    version = plan.get('version')
    require(isinstance(version, str) and VERSION.fullmatch(version), 'version must be X.X.X without a v prefix')
    groups = cfg.get('groups')
    selected = plan.get('groups')
    require(isinstance(groups, dict) and isinstance(selected, dict) and groups, 'missing groups')
    require(set(groups) == set(selected), 'plan must contain every configured group exactly once')
    changes = plan.get('changes')
    require(isinstance(changes, list) and changes and all(isinstance(x, str) and x.strip() for x in changes),
            'plan must list the shared changes')
    require(len(changes) == len(set(changes)), 'duplicate shared change')
    try:
        release_date = plan.get('release_date')
        require(isinstance(release_date, str) and date.fromisoformat(release_date).isoformat() == release_date,
                'release_date must be an ISO date')
    except ValueError as exc:
        raise Invalid('release_date must be an ISO date') from exc
    limitations = plan.get('known_limitations')
    require(isinstance(limitations, list) and all(isinstance(x, str) and x.strip() for x in limitations),
            'known_limitations must be a list of nonempty strings')
    seen_minecraft = set()
    for name, spec in groups.items():
        require(re.fullmatch(r'\d+(?:\.\d+)+(?:-\d+(?:\.\d+)+)?', name) is not None, f'unsafe group id: {name}')
        entry = selected[name]
        require(isinstance(entry, dict), f'{name}: invalid entry')
        commit = entry.get('commit')
        require(isinstance(commit, str) and SHA.fullmatch(commit) and commit != '0' * 40,
                f'{name}: source commit must be a full nonzero SHA')
        require(entry.get('verified_changes') == changes, f'{name}: shared changes are not synchronized')
        require(spec.get('branch') == f'mc/{name}', f'{name}: invalid maintenance branch')
        branch = entry.get('source_branch')
        require(isinstance(branch, str) and re.fullmatch(r'[a-z0-9][a-z0-9./_-]{0,99}', branch) and
                '..' not in branch and '//' not in branch and not branch.endswith(('/', '.', '.lock')),
                f'{name}: invalid source branch')
        require(branch == spec['branch'] or (candidate and branch.startswith('candidate/')),
                f'{name}: source must be the approved maintenance branch')
        minecraft = spec.get('minecraft')
        require(isinstance(minecraft, list) and minecraft and
                all(isinstance(v, str) and re.fullmatch(r'\d+(?:\.\d+)+', v) for v in minecraft) and
                len(set(minecraft)) == len(minecraft) and spec.get('target') in minecraft,
                f'{name}: invalid explicit Minecraft versions or compilation target')
        require(not (seen_minecraft & set(minecraft)), f'{name}: Minecraft versions overlap another group')
        seen_minecraft.update(minecraft)
        require(spec.get('java') in (21, 25) and spec.get('namespace') in ('intermediary', 'official'),
                f'{name}: invalid Java or namespace')
        require(re.fullmatch(r'\d+\.\d+\.\d+', spec.get('loader', '')) is not None, f'{name}: invalid loader')
        evidence = entry.get('runtime_evidence', {})
        require(isinstance(evidence, dict), f'{name}: invalid runtime evidence')
        if not candidate:
            require(set(evidence) == set(spec['minecraft']), f'{name}: missing version-by-version runtime evidence')
            for mc in spec['minecraft']:
                evidence_record(entry, name, mc)
    return cfg, plan


def evidence_record(entry, group, minecraft, root=None):
    """Read a reviewed, repository-owned report; its content is an attestation, not proof."""
    root = root or ROOT
    reference = entry['runtime_evidence'][minecraft]
    require(isinstance(reference, dict) and set(reference) == {'report'},
            f'{group}: evidence for {minecraft} must identify one repository report')
    path = reference['report']
    require(isinstance(path, str) and re.fullmatch(r'release/evidence/[A-Za-z0-9_-]+\.json', path),
            f'{group}: invalid evidence report path for {minecraft}')
    report_path = root / path
    require(not (root / 'release').is_symlink() and not (root / 'release/evidence').is_symlink() and
            not report_path.is_symlink() and report_path.resolve().parent == (root / 'release/evidence').resolve(),
            f'{group}: evidence report must be a repository file')
    raw = report_path.read_bytes()
    require(len(raw) <= 100_000, f'{group}: evidence report is too large')
    report = read_json(report_path)
    require(isinstance(report, dict) and set(report) == {'group', 'minecraft', 'source_commit', 'artifact_sha256',
                                                       'installed_jar', 'graphical'},
            f'{group}: invalid evidence report fields')
    require(report['group'] == group and report['minecraft'] == minecraft and
            report['source_commit'] == entry['commit'], f'{group}: evidence source or version mismatch')
    require(isinstance(report['artifact_sha256'], str) and SHA256.fullmatch(report['artifact_sha256']),
            f'{group}: evidence requires a SHA-256 artifact digest')
    for kind in ('installed_jar', 'graphical'):
        require(isinstance(report[kind], str) and report[kind].strip(), f'{group}: missing {kind} test account')
    return {'report': path, 'report_sha256': hashlib.sha256(raw).hexdigest(),
            'attestation': 'reviewed-report-not-machine-proof',
            'external_references': 'unverified', **report}


def matrix(cfg, plan):
    return [{'group': name, 'commit': plan['groups'][name]['commit'],
             'branch': plan['groups'][name]['source_branch'], 'multi_version': len(spec['minecraft']) > 1}
            for name, spec in sorted(cfg['groups'].items())]


def verify_sources(cfg, plan):
    for entry in matrix(cfg, plan):
        ref = 'refs/heads/' + entry['branch']
        result = subprocess.run(['git', 'ls-remote', '--exit-code', '--heads', 'origin', ref],
                                check=False, capture_output=True, text=True, timeout=60)
        rows = [line.split('\t') for line in result.stdout.splitlines()]
        require(result.returncode == 0 and rows == [[entry['commit'], ref]],
                f"{entry['group']}: source branch is missing or its HEAD differs from the plan")
    print('All pinned commits match their source branch heads.')


def archive_name(version, group):
    return f'{PREFIX}-{version}-mc{group}.jar'


def parse_manifest(raw):
    # JAR manifest continuation lines start with a single space.
    unfolded = re.sub(r'\r?\n ', '', raw.decode('utf-8'))
    result = {}
    for line in unfolded.splitlines():
        if not line:
            break  # only the main section describes the JAR
        key, sep, value = line.partition(': ')
        require(sep and key.lower() not in result, 'invalid or duplicate JAR manifest attribute')
        result[key.lower()] = value
    return result


def inspect_jar(path, version, name, spec):
    require(path.name == archive_name(version, name), f'{name}: unexpected JAR filename: {path.name}')
    try:
        with ZipFile(path) as jar:
            entries = jar.infolist()
            names = [x.filename for x in entries]
            require(len(names) == len(set(names)), f'{name}: duplicate ZIP entries')
            require(len(entries) <= 2000 and sum(x.file_size for x in entries) <= 50_000_000,
                    f'{name}: JAR exceeds verification limits')
            require(jar.testzip() is None, f'{name}: invalid ZIP checksum')
            for required in ('fabric.mod.json', 'META-INF/MANIFEST.MF', 'LICENSE', MIXIN_CLASS):
                require(required in names, f'{name}: missing {required}')
            require(not any(x.endswith('.jar') for x in names), f'{name}: nested JARs are not expected')
            metadata = json.loads(jar.read('fabric.mod.json'), object_pairs_hook=unique_object)
            require(metadata.get('schemaVersion') == 1 and metadata.get('id') == ID and
                    metadata.get('version') == version and metadata.get('environment') == 'client',
                    f'{name}: wrong mod identity, version, or environment')
            depends = metadata.get('depends', {})
            expected_minecraft = spec['minecraft'][0] if len(spec['minecraft']) == 1 else spec['minecraft']
            require(depends.get('minecraft') == expected_minecraft and depends.get('java') == f">={spec['java']}" and
                    depends.get('fabricloader') == f">={spec['loader']}", f'{name}: wrong dependency metadata')
            require(metadata.get('license') == 'MIT' and metadata.get('mixins') == ['thirdpersonreadablemaps.mixins.json'],
                    f'{name}: wrong license or Mixin registration')
            mixin = json.loads(jar.read(metadata['mixins'][0]), object_pairs_hook=unique_object)
            require(mixin.get('required') is True and mixin.get('compatibilityLevel') == f"JAVA_{spec['java']}" and
                    mixin.get('injectors', {}).get('defaultRequire') == 1 and
                    mixin.get('package') == 'tech.rolly.thirdpersonreadablemaps.mixin' and
                    mixin.get('client') == ['ReadableMapLayerMixin'], f'{name}: Mixin is not strictly required')
            manifest = parse_manifest(jar.read('META-INF/MANIFEST.MF'))
            require(manifest.get('fabric-mapping-namespace') == spec['namespace'] and
                    manifest.get('fabric-minecraft-version') == spec['target'], f'{name}: wrong namespace or build target')
            classes = [x for x in names if x.endswith('.class')]
            require(classes, f'{name}: no classes')
            major = spec['java'] + 44
            for cls in classes:
                data = jar.read(cls)
                require(len(data) >= 8 and data[:4] == b'\xca\xfe\xba\xbe', f'{name}: invalid class {cls}')
                require(struct.unpack('>H', data[4:6])[0] != 65535, f'{name}: preview class requires special runtime flags')
                require(struct.unpack('>H', data[6:8])[0] <= major, f'{name}: {cls} needs a newer Java runtime')
            require(struct.unpack('>H', jar.read(MIXIN_CLASS)[6:8])[0] == major,
                    f'{name}: unexpected Mixin bytecode target')
            target = jar.read(MIXIN_CLASS)
            expected = b'net/minecraft/class_' if spec['namespace'] == 'intermediary' else b'net/minecraft/client/renderer/entity/layers/ItemInHandLayer'
            require(expected in target, f'{name}: Mixin target is in the wrong namespace')
    except (KeyError, BadZipFile, json.JSONDecodeError, UnicodeError) as exc:
        raise Invalid(f'{name}: malformed JAR: {exc}') from exc
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(cfg, plan, artifacts, output, candidate=False, coordinator_sha=None):
    require(isinstance(coordinator_sha, str) and SHA.fullmatch(coordinator_sha) and coordinator_sha != '0' * 40,
            'a full nonzero coordinator SHA is required')
    artifacts, output = Path(artifacts), Path(output)
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())), 'output directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    result = {'schema': 1, 'version': plan['version'], 'tag': plan['version'], 'coordinator_sha': coordinator_sha,
              'candidate': candidate, 'release_date': plan['release_date'], 'changes': plan['changes'],
              'known_limitations': plan['known_limitations'], 'groups': []}
    sums = []
    for entry in matrix(cfg, plan):
        name = entry['group']
        directory = artifacts / name
        jars = sorted(directory.glob('*.jar'))
        require(len(jars) == 1, f'{name}: expected exactly one JAR, found {len(jars)}')
        spec = cfg['groups'][name]
        digest = inspect_jar(jars[0], plan['version'], name, spec)
        evidence = {} if candidate else {mc: evidence_record(plan['groups'][name], name, mc) for mc in spec['minecraft']}
        require(candidate or all(r['artifact_sha256'] == digest for r in evidence.values()),
                f'{name}: built artifact differs from runtime-tested artifact')
        shutil.copyfile(jars[0], output / jars[0].name)
        sums.append(f'{digest}  {jars[0].name}')
        result['groups'].append({'id': name, 'branch': entry['branch'], 'source_commit': entry['commit'],
                                 'minecraft': spec['minecraft'], 'compile_target': spec['target'],
                                 'java': spec['java'], 'loader': spec['loader'],
                                 'namespace': spec['namespace'], 'artifact': jars[0].name, 'sha256': digest,
                                 'runtime_evidence': evidence})
    manifest = output / 'release-manifest.json'
    manifest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    sums.append(f"{hashlib.sha256(manifest.read_bytes()).hexdigest()}  {manifest.name}")
    (output / 'SHA256SUMS').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    print(f"Validated {len(result['groups'])} artifacts for {plan['version']} (candidate={candidate})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'matrix', 'verify-sources', 'aggregate'])
    parser.add_argument('--plan', required=True)
    parser.add_argument('--candidate', action='store_true', help='allow missing runtime evidence; never use for release')
    parser.add_argument('--artifacts')
    parser.add_argument('--output')
    parser.add_argument('--coordinator-sha')
    args = parser.parse_args()
    try:
        cfg, plan = load_plan(args.plan, args.candidate)
        if args.command == 'matrix':
            print(json.dumps({'include': matrix(cfg, plan)}, separators=(',', ':')))
        elif args.command == 'verify-sources':
            verify_sources(cfg, plan)
        elif args.command == 'aggregate':
            require(args.artifacts and args.output, 'aggregate requires --artifacts and --output')
            aggregate(cfg, plan, args.artifacts, args.output, args.candidate, args.coordinator_sha)
        else:
            print(f"Validated plan for {plan['version']} (candidate={args.candidate})")
    except (Invalid, OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f'release validation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
