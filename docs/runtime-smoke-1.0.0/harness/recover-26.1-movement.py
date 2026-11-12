"""Finish the retained 26.1 observation after the player-data path changed.

The original runner reached its captures and a clean client shutdown, then
looked in the old playerdata directory. This checks the saved, new-format file
and original log before producing the same movement record as the runner.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import nbtlib

root = Path('/workspace/.minecraft-test-v100-final-walk-26.1')
repo = Path('/workspace/tprm-legacy-coordination')
manifest = json.loads((repo / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
group = next(entry for entry in manifest['groups'] if entry['id'] == '26.1-26.2')
jar = root / 'mods' / group['artifact']
digest = hashlib.sha256(jar.read_bytes()).hexdigest()
assert digest == group['sha256']
log = (root / 'client.log').read_text(errors='replace')
for required in ('MapSmokeTest joined the game', 'Teleported MapSmokeTest',
                 'Set minecraft:overworld to time marker minecraft:day',
                 'All dimensions are saved', 'Stopping!'):
    assert required in log, required
for error in ('MixinApplyError', 'InvalidInjectionException', 'NoSuchMethodError', 'MixinTransformerError'):
    assert error not in log, error
for name in ('standing-day.png', 'walking-1.png', 'walking-2.png', 'after-walk.png'):
    assert (root / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), name
player = root / 'saves/New World/players/data/f36d949a-12db-4676-bc41-a7b7fe97fd55.dat'
end = [float(value) for value in nbtlib.load(player)['Pos']]
distance = math.hypot(end[0] - 5.5, end[2] + 62.5)
assert distance > 0.5
assert not (root / 'movement.json').exists()
shutil.copy2(player, root / 'ending-player.dat')
(root / 'movement.json').write_text(json.dumps({
    'minecraft': '26.1', 'start': [5.5, 81, -62.5], 'end': end,
    'horizontal_distance': distance, 'renderer': 'Linux Xorg/Mesa software',
    'candidate_sha256': digest,
    'note': 'One short local walking scene; screenshots require visual inspection and do not establish full acceptance. The game completed and exited; this record was recovered from the new players/data path after the original runner looked for the old playerdata path.',
}, indent=2) + '\n')
print('Recovered 26.1 saved movement:', distance)
