"""Retain candidate/no-Mod dropped-item control and source identities."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent
SHARED = WORKSPACE / '.minecraft-test'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    build = json.loads((ROOT / 'docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups']['1.21.11']
    fixture = WORKSPACE / '.minecraft-test-left-baseline-1.21.10'
    world = fixture / 'saves/New World'
    index = {'minecraft': '1.21.11', 'observed_on': '2026-11-13',
             'fixture_note': 'Hashes recorded after the two runs; each runner copied this local fixture before modifying the test world.',
             'fixture_files_sha256': {str(p.relative_to(fixture)): digest(p) for p in sorted(world.rglob('*')) if p.is_file()},
             'variants': {}}
    index['fixture_files_sha256']['options.txt'] = digest(fixture / 'options.txt')
    for variant in ('candidate', 'control'):
        src = WORKSPACE / ('.minecraft-test-foreground-items-' + variant + '-1.21.11')
        dest = HERE / variant
        dest.mkdir(exist_ok=True)
        movement = json.loads((src / 'movement.json').read_text())
        assert movement['variant'] == variant and movement['source_commit'] == build['source_commit']
        assert movement['paired_candidate_sha256'] == build['sha256']
        log = (src / 'client.log').read_text(errors='replace')
        assert 'MapSmokeTest joined the game' in log
        assert 'Wheat Seeds has the following entity data' in log and 'Killed 8 entities' in log
        if variant == 'candidate':
            assert 'thirdpersonreadablemaps 1.0.0' in log
        else:
            assert 'thirdpersonreadablemaps' not in log and 'Loading 4 mods:' in log
        files = ((src / 'before-clear.png', 'before-clear.png'),
                 (src / 'after-clear.png', 'after-clear.png'),
                 (src / 'client.log', 'client.log'), (src / 'movement.json', 'movement.json'),
                 (src / 'ending-player.dat', 'ending-player.dat'),
                 (src / 'launcher-pins.json', 'launcher-pins.json'),
                 (SHARED / ('foreground-items-' + variant + '-retry.log'), 'runner.log'))
        for source, name in files:
            shutil.copyfile(source, dest / name)
        index['variants'][variant] = {'source_commit': build['source_commit'],
                                       'paired_candidate_sha256': build['sha256'],
                                       'mod_installed': variant == 'candidate',
                                       'nearest_item': 'minecraft:wheat_seeds', 'item_entities_cleared': 8,
                                       'files_sha256': {name: digest(dest / name) for _, name in files}}
    for name in ('foreground-items-104.py', 'x11-foreground-items-104.py'):
        shutil.copyfile(SHARED / name, HERE / name)
        index[name + '_sha256'] = digest(HERE / name)
    (HERE / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Recorded candidate and no-Mod dropped-item controls')


if __name__ == '__main__':
    main()
