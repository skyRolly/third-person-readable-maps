"""Copy completed clean-build logs without relabelling prior artifacts."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
source = ROOT.parent / '.tprm-dryrun/class-linkage-builds'
refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
results = json.loads((source / 'index.json').read_text())
for group, row in results.items():
    assert group in refs and row['source_commit'] == refs[group]['new_head']
    jar = source / group / row['artifact']
    assert hashlib.sha256(jar.read_bytes()).hexdigest() == row['sha256']
    assert row['same_as_previous'] == (row['sha256'] == refs[group]['artifact_sha256_before_rebuild'])
    log = source / (group + '-build.log')
    assert hashlib.sha256(log.read_bytes()).hexdigest() == row['log_sha256']
    shutil.copyfile(log, HERE / log.name)
    row['runner_variant'] = ('initial runner, exact source not retained' if group in {
        '1.14-1.14.4', '1.15-1.16.5', '1.17-1.19.2', '1.19.3',
        '1.19.4-1.20.4', '1.20.5-1.20.6'} else 'retained resumed runner')
runner = Path('/tmp/tprm-build-class-linkage.py')
shutil.copyfile(runner, HERE / 'run.py')
(HERE / 'index.json').write_text(json.dumps({'schema': 1, 'observed_on': '2026-11-13',
                                            'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
                                            'groups': results}, indent=2) + '\n')
print('Retained', len(results), 'of', len(refs), 'exact-source clean-build records')
