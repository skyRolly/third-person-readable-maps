"""Retain instruction-resolver traces from archived proposed source commits."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent
SOURCE = WORKSPACE / '.tprm-dryrun/protected-trace-archived-20261114'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    builds = json.loads((ROOT / 'docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups']
    manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0-2026-11-14/release-manifest.json').read_text())
    index = {'schema': 1, 'observed_on': '2026-11-14', 'versions': {}}
    checked_scripts = set()
    for group in manifest['groups']:
        name = group['id']
        repo = WORKSPACE / (('tprm-review-' + name) if name in ('1.21.11', '26.1-26.2', '26.3')
                            else ('tprm-legacy-' + ('1.14' if name == '1.14-1.14.4' else name)))
        for version in group['minecraft']:
            result = SOURCE / (version + '.json')
            log = SOURCE / (version + '.log')
            row = json.loads(result.read_text())
            assert row['version'] == version and row['group'] == name and row['exit_code'] == 0
            assert row['source_commit'] == refs[name]['new_head'] == builds[name]['source_commit']
            assert row['artifact_sha256'] == builds[name]['sha256'] and row['validated_uses'] > 0
            assert not row['protected_uses']
            for script, expected in row['archived_script_sha256'].items():
                key = (name, script)
                if key not in checked_scripts:
                    raw = subprocess.check_output(['git', 'show', row['source_commit'] + ':scripts/' + script], cwd=repo)
                    assert hashlib.sha256(raw).hexdigest() == expected
                    checked_scripts.add(key)
            for path in (result, log):
                shutil.copyfile(path, HERE / path.name)
            index['versions'][version] = {'group': name, 'source_commit': row['source_commit'],
                                           'artifact_sha256': row['artifact_sha256'],
                                           'validated_uses': row['validated_uses'],
                                           'protected_uses': len(row['protected_uses']),
                                           'result_sha256': digest(HERE / result.name),
                                           'log_sha256': digest(HERE / log.name)}
    for src, name in ((Path('/tmp/tprm-protected-worker.py'), 'worker.py'),
                      (Path('/tmp/tprm-protected-archived-sweep.py'), 'run.py'),
                      (Path('/tmp/tprm-protected-archived-sweep.log'), 'run.log')):
        shutil.copyfile(src, HERE / name)
        index[name + '_sha256'] = digest(HERE / name)
    assert len(index['versions']) == 48
    (HERE / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Retained archived-source protected-access traces for', len(index['versions']), 'versions')


if __name__ == '__main__':
    main()
