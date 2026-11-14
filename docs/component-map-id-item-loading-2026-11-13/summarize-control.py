"""Summarize the no-Mod local-world control; requires nbtlib."""
from pathlib import Path
import hashlib
import json
import nbtlib
from summarize import inventory

HERE = Path(__file__).resolve().parent
CASE = HERE / 'no-mod-control'


def main():
    candidate = json.loads((HERE / 'host-inventory-attempt/index.json').read_text())
    movement = json.loads((CASE / 'movement.json').read_text())
    player = nbtlib.load(CASE / 'ending-player.dat')
    saved = inventory(player)
    assert int(player['SelectedItemSlot']) == candidate['selected_slot'] == 3
    assert saved == candidate['saved_inventory']
    assert movement['paired_candidate_source_commit'] == candidate['source_commit']
    assert movement['paired_candidate_sha256'] == candidate['artifact_sha256']
    log = (CASE / 'client.log').read_text(errors='replace')
    assert 'Loading 4 mods:' in log and 'thirdpersonreadablemaps' not in log
    assert 'MapSmokeTest joined the game' in log
    fixture = json.loads((CASE / 'fixture.json').read_text())
    assert fixture['input_level_sha256'] == candidate['files_sha256']['input-level.dat']
    assert fixture['input_player_sha256'] == candidate['files_sha256']['input-player.dat']
    assert fixture['input_map_zero_sha256'] == candidate['files_sha256']['input-map-zero.dat']
    files = sorted(p for p in CASE.iterdir() if p.is_file() and p.name not in ('index.json', 'README.md'))
    result = {'minecraft': '1.21.11', 'status': 'OBSERVED no-Mod local-world control',
              'paired_candidate_source_commit': candidate['source_commit'],
              'paired_candidate_artifact_sha256': candidate['artifact_sha256'],
              'input_level_sha256': fixture['input_level_sha256'],
              'input_player_sha256': fixture['input_player_sha256'],
              'input_map_zero_sha256': fixture['input_map_zero_sha256'],
              'selected_slot': 3, 'saved_inventory': saved,
              'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (CASE / 'index.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Recorded no-Mod control against the same input fixture')


if __name__ == '__main__':
    main()
