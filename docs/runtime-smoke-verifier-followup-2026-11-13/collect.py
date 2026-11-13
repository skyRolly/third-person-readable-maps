"""Retain completed, source-bound client observations from the local sweep."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
builds = json.loads((WORKSPACE / '.tprm-dryrun/class-linkage-builds/index.json').read_text())
manifest = json.loads((ROOT / 'docs/historical-verifier-followup-2026-11-13/release-manifest.json').read_text())
results = {}
for group in manifest['groups']:
    name = group['id']
    for version in group['minecraft']:
        source = WORKSPACE / ('.minecraft-test-class-followup-walk-' + version)
        if not (source / 'movement.json').is_file():
            continue
        row = json.loads((source / 'movement.json').read_text())
        assert row['minecraft'] == version and row['source_commit'] == refs[name]['new_head']
        assert name in builds and builds[name]['source_commit'] == row['source_commit']
        assert row['candidate_sha256'] == builds[name]['sha256'] and row['horizontal_distance'] > 0.5
        log = (source / 'client.log').read_text(errors='replace')
        assert 'MapSmokeTest joined the game' in log
        assert not any(error in log for error in ('MixinApplyError', 'InvalidInjectionException', 'NoSuchMethodError', 'MixinTransformerError'))
        target = HERE / version
        target.mkdir(parents=True, exist_ok=True)
        files = ('movement.json', 'ending-player.dat', 'walking-1.png', 'walking-2.png', 'client.log')
        for file in files:
            shutil.copyfile(source / file, target / file)
        results[version] = {'group': name, 'source_commit': row['source_commit'],
                            'artifact_sha256': row['candidate_sha256'],
                            'observed_on': datetime.fromtimestamp((source / 'movement.json').stat().st_mtime, timezone.utc).date().isoformat(),
                            'files_sha256': {file: hashlib.sha256((target / file).read_bytes()).hexdigest() for file in files}}

harnesses = ['class-followup-walking-early-91.py', 'class-followup-walking-middle-92.py',
             'class-followup-walking-later-93.py', 'class-followup-walking-modern-94.py',
             'class-followup-walking-early-96.py', 'class-followup-walking-middle-97.py',
             'x11-class-followup-91.py', 'x11-class-followup-92.py',
             'x11-class-followup-93.py', 'x11-class-followup-94.py',
             'x11-class-followup-96.py', 'x11-class-followup-97.py']
harness_hashes = {}
for file in harnesses:
    source = WORKSPACE / '.minecraft-test' / file
    if source.is_file():
        target = HERE / 'harness' / file
        shutil.copyfile(source, target)
        harness_hashes[file] = hashlib.sha256(target.read_bytes()).hexdigest()
expected = {v for group in manifest['groups'] for v in group['minecraft']}
(HERE / 'index.json').write_text(json.dumps({'schema': 1, 'status': 'PARTIAL source-bound software-rendered smoke',
                                             'expected_versions': sorted(expected),
                                             'pending_versions': sorted(expected - set(results)),
                                             'harness_sha256': harness_hashes, 'versions': results}, indent=2) + '\n')
print('Retained', len(results), 'of', len(expected), 'new-head source-bound client observations')
