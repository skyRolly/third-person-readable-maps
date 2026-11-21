"""Record 26.3 walking after its save-completion log wording changed."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import nbtlib

root = Path('/workspace/.minecraft-test-v100-final-walk-26.3')
repo = Path('/workspace/tprm-legacy-coordination')
manifest = json.loads((repo / 'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text())
group = next(entry for entry in manifest['groups'] if entry['id'] == '26.3')
digest = hashlib.sha256((root / 'mods' / group['artifact']).read_bytes()).hexdigest()
assert digest == group['sha256']
log = (root / 'client.log').read_text(errors='replace')
for required in ('Using graphics backend OpenGL', 'MapSmokeTest joined the game',
                 'Teleported MapSmokeTest', 'Clock minecraft:overworld is already at time marker minecraft:day',
                 'Saving players', 'Saving worlds', 'Stopping!'):
    assert required in log, required
for error in ('MixinApplyError', 'InvalidInjectionException', 'NoSuchMethodError', 'MixinTransformerError'):
    assert error not in log, error
runner_log = Path('/workspace/.minecraft-test/v100-walking-modern-egl-final.log').read_text(errors='replace')
assert 'Captured walking-1' in runner_log and 'Captured walking-2' in runner_log
assert 'Client exited before All dimensions are saved' in runner_log
for name in ('standing-day.png', 'walking-1.png', 'walking-2.png', 'after-walk.png'):
    assert (root / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), name
player = root / 'saves/New World/players/data/f36d949a-12db-4676-bc41-a7b7fe97fd55.dat'
end = [float(value) for value in nbtlib.load(player)['Pos']]
distance = math.hypot(end[0] - 5.5, end[2] + 62.5)
assert distance > 0.5 and not (root / 'movement.json').exists()
shutil.copy2(player, root / 'ending-player.dat')
(root / 'movement.json').write_text(json.dumps({
    'minecraft': '26.3', 'start': [5.5, 81, -62.5], 'end': end,
    'horizontal_distance': distance, 'renderer': 'Linux Xorg/Mesa software, SDL EGL',
    'candidate_sha256': digest,
    'note': 'One short local walking scene; screenshots require visual inspection and do not establish full acceptance. The world returned to the menu and the client was manually exited. The diagnostic waited for a save-completion log message absent in 26.3; movement was recovered from the saved player data.',
}, indent=2) + '\n')
print('Recovered 26.3 saved movement after manual client exit:', distance)
