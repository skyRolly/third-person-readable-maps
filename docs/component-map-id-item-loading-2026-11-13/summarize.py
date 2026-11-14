"""Summarize retained NBT inputs and output from the controlled host-world probe.

Requires nbtlib; this is a diagnostic collector, not a production dependency.
"""
from pathlib import Path
import hashlib
import json
import nbtlib

HERE = Path(__file__).resolve().parent
CASE = HERE / 'host-inventory-attempt'


def inventory(player):
    result = {}
    for item in player['Inventory']:
        slot = str(int(item['Slot']))
        value = item.get('components', {}).get('minecraft:map_id')
        result[slot] = {'item': str(item['id']), 'tag': type(value).__name__ if value is not None else None,
                        'value': float(value) if isinstance(value, nbtlib.Double)
                        else int(value) if value is not None else None}
    return result


def main():
    host = nbtlib.load(CASE / 'input-level.dat')['Data']['Player']
    player = nbtlib.load(CASE / 'input-player.dat')
    saved = nbtlib.load(CASE / 'ending-player.dat')
    assert int(host['SelectedItemSlot']) == int(player['SelectedItemSlot']) == int(saved['SelectedItemSlot']) == 3
    before = inventory(host)
    assert before == inventory(player)
    after = inventory(saved)
    assert before['1']['value'] == after['1']['value'] == 0
    assert before['2']['value'] == after['2']['value'] == 7
    assert before['3']['tag'] == 'Double' and before['3']['value'] == 0.5
    assert before['4']['tag'] == 'Long' and before['4']['value'] == 4294967296
    assert after['3']['tag'] == after['4']['tag'] == 'Int'
    assert after['3']['value'] == after['4']['value'] == 0
    assert before['8']['value'] is None and after['8']['value'] is None
    colors = nbtlib.load(CASE / 'input-map-zero.dat')['data']['colors']
    nonblank = sum(int(color) != 0 for color in colors)
    assert len(colors) == 16384 and nonblank > 1000
    movement = json.loads((CASE / 'movement.json').read_text())
    files = sorted(p for p in CASE.iterdir() if p.is_file() and p.name not in ('index.json', 'README.md'))
    result = {'minecraft': '1.21.11', 'status': 'OBSERVED in one local integrated-server world with mod installed',
              'source_commit': movement['source_commit'], 'artifact_sha256': movement['candidate_sha256'],
              'selected_slot': 3, 'map_zero_nonblank_color_count': nonblank,
              'input_inventory': before, 'saved_inventory': after,
              'limitation': 'One controlled single-player world; other versions, network paths and independent visual acceptance remain untested.',
              'files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (CASE / 'index.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Recorded host inventory normalization with', nonblank, 'nonblank map-zero pixels')


if __name__ == '__main__':
    main()
