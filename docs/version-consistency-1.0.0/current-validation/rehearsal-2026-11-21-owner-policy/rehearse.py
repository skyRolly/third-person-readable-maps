#!/usr/bin/env python3
"""Replay a non-publishing rehearsal from retained exact-head Linux and Windows archives."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile, BadZipFile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import release
import release_github


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def reject(controls, name, operation):
    try:
        operation()
    except (release.Invalid, ValueError, OSError, BadZipFile) as exc:
        controls[name] = str(exc)
    else:
        raise RuntimeError(name + ' was accepted')


def verify_inputs(cfg, plan, builds, hosted, static, heads, input_record):
    if set(builds) != set(cfg['groups']) or set(hosted) != set(cfg['groups']):
        raise release.Invalid('missing build or hosted-check group')
    expected_static = {(g, version) for g, spec in cfg['groups'].items() for version in spec['minecraft']}
    results = static.get('results', [])
    if len(results) != len(expected_static) or {(r['group'], r['version']) for r in results} != expected_static:
        raise release.Invalid('missing or duplicate static verification evidence')
    if set(input_record['groups']) != set(cfg['groups']):
        raise release.Invalid('missing source artifact archive')
    input_blobs = {}
    for group, spec in cfg['groups'].items():
        build = builds[group]
        row = heads[group]
        pr = hosted[group]
        linux, windows = pr['checks']['ubuntu-latest'], pr['checks']['windows-latest']
        recorded = input_record['groups'][group]
        if (build['source_commit'] != row['new_head'] or build['branch'] != row['branch'] or
                build['sha256'] != recorded['artifact_sha256'] or row['new_head'] != pr['head_sha'] or
                pr['head_tree'] != pr['merge_tree'] or recorded['source_commit'] != row['new_head']):
            raise release.Invalid(group + ': current source or artifact identity differs')
        if any(check['conclusion'] != 'SUCCESS' or not check['archive_and_jar_verified'] or
               check['checkout_merge_sha'] != pr['merge_sha'] or check['artifact_sha256'] != build['sha256']
               for check in (linux, windows)):
            raise release.Invalid(group + ': hosted Linux or Windows verification is incomplete')
        if (not linux['archive_created_at'] or not windows['archive_created_at'] or
                int(linux['run_id']) != recorded['run_id'] or linux['archive_artifact_id'] != recorded['artifact_id']):
            raise release.Invalid(group + ': hosted artifact identity differs from retained archive')
        if build.get('wrapper_preflight') != 'coordinator verifier before gradlew':
            raise release.Invalid(group + ': missing Wrapper preflight evidence')
        archive_path = ROOT / recorded['archive_path']
        archive = archive_path.read_bytes()
        archive_sha = hashlib.sha256(archive).hexdigest()
        if archive_sha != linux['archive_sha256'] or archive_sha != recorded['archive_sha256']:
            raise release.Invalid(group + ': retained hosted archive digest mismatch')
        with ZipFile(BytesIO(archive)) as zipped:
            jars = [name for name in zipped.namelist() if name.endswith('.jar')]
            if jars != [build['artifact']]:
                raise release.Invalid(group + ': hosted archive does not contain exactly the expected JAR')
            jar = zipped.read(jars[0])
        if hashlib.sha256(jar).hexdigest() != build['sha256']:
            raise release.Invalid(group + ': hosted JAR digest differs from the clean build')
        windows_path = ROOT / recorded['windows_archive_path']
        windows_archive = windows_path.read_bytes()
        if (hashlib.sha256(windows_archive).hexdigest() != windows['archive_sha256'] or
                hashlib.sha256(windows_archive).hexdigest() != recorded['windows_archive_sha256']):
            raise release.Invalid(group + ': retained Windows hosted archive digest mismatch')
        with ZipFile(BytesIO(windows_archive)) as zipped:
            windows_jars = [name for name in zipped.namelist() if name.endswith('.jar')]
            if windows_jars != [build['artifact']] or hashlib.sha256(zipped.read(windows_jars[0])).hexdigest() != build['sha256']:
                raise release.Invalid(group + ': Windows hosted archive contains a different JAR')
        input_blobs[group] = jar
        for check in static['results']:
            if check['group'] == group and (check['source_commit'] != row['new_head'] or
                    check['artifact_sha256'] != build['sha256'] or check['exit_code'] != 0):
                raise release.Invalid(group + ': static API verification is stale or failed')
    return input_blobs


def main():
    if (OUT / 'bundle').exists():
        raise RuntimeError('refusing to replace retained rehearsal output')
    heads = read('docs/version-consistency-1.0.0/current-heads.json')['groups']
    builds = read('docs/version-consistency-1.0.0/current-validation/builds.json')
    hosted = read('docs/version-consistency-1.0.0/current-validation/hosted-checks.json')['groups']
    static = read('docs/version-consistency-1.0.0/current-validation/static.json')
    input_record = read(str((OUT / 'artifact-inputs.json').relative_to(ROOT)))
    candidate_cfg = (ROOT / 'docs/legacy-dry-run-1.0.0-2026-11-14/hierarchy-2026-11-15/candidate-compatibility.json')
    config_file = OUT / 'candidate-compatibility.json'
    shutil.copyfile(candidate_cfg, config_file)
    cfg_data = json.loads(config_file.read_text())
    if set(heads) != set(cfg_data['groups']):
        raise release.Invalid('candidate configuration does not cover current product heads')
    changes = ['Coordinate the 1.0.0 source heads for a non-publishing owner-policy rehearsal']
    plan = {'schema': 1, 'version': '1.0.0', 'release_date': '2026-11-21', 'changes': changes,
            'known_limitations': ['Non-publishing candidate rehearsal; security, runtime, and publication gates remain open'],
            'groups': {group: {'source_branch': row['branch'], 'commit': row['new_head'],
                               'verified_changes': changes, 'runtime_evidence': {}}
                       for group, row in sorted(heads.items())}}
    plan_file = OUT / 'candidate-plan.json'
    plan_file.write_text(json.dumps(plan, indent=2) + '\n')
    cfg, plan = release.load_plan(plan_file, candidate=True, config_path=config_file)
    (OUT / 'candidate-matrix.json').write_text(json.dumps(release.matrix(cfg, plan), indent=2) + '\n')
    release.verify_sources(cfg, plan)
    jars = verify_inputs(cfg, plan, builds, hosted, static, heads, input_record)
    with tempfile.TemporaryDirectory(prefix='tprm-owner-rehearsal-') as temporary:
        root = Path(temporary)
        artifact_root = root / 'artifacts'
        for group, jar in jars.items():
            destination = artifact_root / group
            destination.mkdir(parents=True)
            destination.joinpath(builds[group]['artifact']).write_bytes(jar)
        cfg, plan = release.load_plan(plan_file, candidate=True, config_path=config_file)
        coordinator_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        output = StringIO()
        with redirect_stdout(output):
            release.aggregate(cfg, plan, artifact_root, OUT / 'bundle', candidate=True,
                              coordinator_sha=coordinator_sha)
        log = ['Verified 13 exact-head hosted Linux and Windows archives against their source, archive, JAR, build, static, and CI records.',
               'Verified candidate source refs against the current remote heads.', output.getvalue().strip()]
        controls = {}
        def check_plan(name, data, candidate=True):
            target = root / (name + '.json')
            target.write_text(json.dumps(data))
            release.load_plan(target, candidate=candidate, config_path=config_file)

        bad = copy.deepcopy(plan); bad['groups'].pop(next(iter(bad['groups'])))
        reject(controls, 'missing-group', lambda: check_plan('missing-group', bad))
        bad = copy.deepcopy(plan); bad['version'] = '0.0.2'
        reject(controls, 'wrong-mod-version', lambda: check_plan('wrong-version', bad))
        bad = copy.deepcopy(plan); bad['groups']['1.14-1.14.4']['source_branch'] = 'candidate/mc-1.21.11'
        reject(controls, 'wrong-candidate-source', lambda: check_plan('wrong-source', bad))
        strict = copy.deepcopy(plan)
        for group in strict['groups']:
            strict['groups'][group]['source_branch'] = cfg['groups'][group]['branch']
        reject(controls, 'missing-strict-runtime-evidence', lambda: check_plan('strict-runtime', strict, False))
        reject(controls, 'candidate-publication',
               lambda: release_github.verified_files(cfg, plan, OUT / 'bundle', plan and
                   json.loads((OUT / 'bundle/release-manifest.json').read_text())['coordinator_sha']))
        duplicate = root / 'duplicate-artifacts'; shutil.copytree(artifact_root, duplicate)
        first_group = next(iter(cfg['groups']))
        first_jar = next((duplicate / first_group).glob('*.jar'))
        shutil.copyfile(first_jar, first_jar.with_name('duplicate.jar'))
        reject(controls, 'duplicate-artifact', lambda: release.aggregate(cfg, plan, duplicate,
               root / 'duplicate-output', candidate=True, coordinator_sha=plan['groups'][first_group]['commit']))
        first_jar = next((artifact_root / first_group).glob('*.jar'))
        wrong = copy.deepcopy(cfg['groups'][first_group]); wrong['minecraft'] = ['1.14.4']
        reject(controls, 'wrong-game-metadata', lambda: release.inspect_jar(first_jar, plan['version'], first_group, wrong))
        wrong = copy.deepcopy(cfg['groups'][first_group]); wrong['namespace'] = 'official'
        reject(controls, 'wrong-namespace', lambda: release.inspect_jar(first_jar, plan['version'], first_group, wrong))
        reject(controls, 'mixed-0.0.2-and-1.0.0-artifacts',
               lambda: release.inspect_jar(first_jar, '0.0.2', first_group, cfg['groups'][first_group]))
        classifier = root / 'third-person-readable-maps-1.0.0-mcWRONG.jar'
        shutil.copyfile(first_jar, classifier)
        reject(controls, 'wrong-artifact-classifier',
               lambda: release.inspect_jar(classifier, plan['version'], first_group, cfg['groups'][first_group]))
        badcfg = copy.deepcopy(cfg); badcfg['groups'][first_group]['minecraft'].append(badcfg['groups'][first_group]['minecraft'][0])
        badcfg_path = root / 'duplicate-version.json'; badcfg_path.write_text(json.dumps(badcfg))
        reject(controls, 'duplicate-game-version', lambda: release.load_plan(plan_file, candidate=True, config_path=badcfg_path))
        badcfg = copy.deepcopy(cfg); badcfg['groups']['1.15-1.16.5']['minecraft'].append('1.14')
        badcfg_path = root / 'overlapping-version.json'; badcfg_path.write_text(json.dumps(badcfg))
        reject(controls, 'overlapping-game-version', lambda: release.load_plan(plan_file, candidate=True, config_path=badcfg_path))
        p = subprocess.run([sys.executable, str(SCRIPTS / 'release.py'), 'validate', '--plan', str(plan_file),
                            '--candidate-config', str(config_file)], capture_output=True, text=True)
        if p.returncode == 0 or '--candidate-config requires --candidate' not in p.stdout + p.stderr:
            raise RuntimeError('strict release CLI accepted candidate configuration')
        controls['strict-rejects-candidate-config'] = 'strict CLI rejected the candidate-only configuration'
        changed = root / 'changed-bundle'; shutil.copytree(OUT / 'bundle', changed)
        target = next(changed.glob('*.jar')); target.write_bytes(target.read_bytes() + b'changed')
        p = subprocess.run(['sha256sum', '--check', 'SHA256SUMS'], cwd=changed, capture_output=True, text=True)
        if p.returncode == 0:
            raise RuntimeError('checksum verification accepted a changed artifact')
        controls['changed-artifact-after-checksum'] = 'sha256sum --check rejected a modified bundle artifact'
        bad = copy.deepcopy(plan); bad['groups'][first_group]['commit'] = 'f' * 40
        reject(controls, 'wrong-remote-source-commit', lambda: release.verify_sources(cfg, bad))
        reject(controls, 'missing-static-evidence',
               lambda: verify_inputs(cfg, plan, builds, hosted, {'results': static['results'][:-1]}, heads, input_record))
        failed = copy.deepcopy(static); failed['results'][0]['exit_code'] = 1
        reject(controls, 'failed-static-evidence',
               lambda: verify_inputs(cfg, plan, builds, hosted, failed, heads, input_record))
        missing_preflight = copy.deepcopy(builds); missing_preflight[first_group]['wrapper_preflight'] = 'not verified'
        reject(controls, 'missing-wrapper-preflight-evidence',
               lambda: verify_inputs(cfg, plan, missing_preflight, hosted, static, heads, input_record))
    expected = {'missing-group', 'wrong-mod-version', 'wrong-candidate-source', 'missing-strict-runtime-evidence',
                'candidate-publication', 'duplicate-artifact', 'wrong-game-metadata', 'wrong-namespace',
                'mixed-0.0.2-and-1.0.0-artifacts', 'wrong-artifact-classifier', 'duplicate-game-version',
                'overlapping-game-version', 'strict-rejects-candidate-config', 'changed-artifact-after-checksum',
                'wrong-remote-source-commit', 'missing-static-evidence', 'failed-static-evidence',
                'missing-wrapper-preflight-evidence'}
    if set(controls) != expected:
        raise RuntimeError('negative-control inventory mismatch')
    (OUT / 'negative-controls.json').write_text(json.dumps(controls, indent=2) + '\n')
    log.append('REJECTED ' + ', '.join(sorted(controls)))
    log.append(f"REHEARSAL COMPLETE {len(cfg['groups'])} groups; {sum(len(x['minecraft']) for x in cfg['groups'].values())} versions; coordinator {coordinator_sha}")
    (OUT / 'rehearsal.log').write_text('\n'.join(log) + '\n')
    print('\n'.join(log))


if __name__ == '__main__':
    main()
