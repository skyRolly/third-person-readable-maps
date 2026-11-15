from pathlib import Path
import hashlib,json,shutil
import nbtlib

source=Path('/workspace/.minecraft-test-mapid-112-26.3-control-retry')
target=Path('/dev/shm/tprm-mapid-113-26.3-native-fixture')
assert not target.exists();target.mkdir()
shutil.copytree(source/'saves'/'New World',target/'saves'/'New World')
shutil.copy2(source/'options.txt',target/'options.txt')
world=target/'saves'/'New World';(world/'session.lock').unlink(missing_ok=True)
level=nbtlib.load(world/'level.dat');assert str(level['Data']['Version']['Name'])=='26.3'
player=world/'players/data/f36d949a-12db-4676-bc41-a7b7fe97fd55.dat';saved=nbtlib.load(player)
items={int(item['Slot']):item for item in saved['Inventory']}
for slot,value in [(1,nbtlib.Int(0)),(2,nbtlib.Int(7)),(3,nbtlib.Double(0.5)),(4,nbtlib.Long(4294967296)),(6,nbtlib.String('not-a-number')),(7,nbtlib.Double(float('nan')))]:
 items[slot]['components']=nbtlib.Compound({'minecraft:map_id':value})
items[8].pop('components',None);saved['SelectedItemSlot']=nbtlib.Int(3);saved.save(player)
mapzero=world/'data/minecraft/maps/0.dat';colors=nbtlib.load(mapzero)['data']['colors'];nonblank=sum(1 for x in colors if int(x)!=0);assert nonblank>0
out=Path('/dev/shm/tprm-mapid-113-26.3-native-evidence');out.mkdir()
for origin,name in [(world/'level.dat','input-level.dat'),(player,'input-player.dat'),(mapzero,'input-map-zero.dat')]:shutil.copyfile(origin,out/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record={'minecraft':'26.3','input_world_version':'26.3','baseline_world':'Previously upgraded no-Mod control world, saved by 26.3; this run loads native-format 26.3 player data without a world upgrade','input_level_sha256':sha(out/'input-level.dat'),'input_player_sha256':sha(out/'input-player.dat'),'input_map_zero_sha256':sha(out/'input-map-zero.dat'),'map_zero_nonblank':nonblank,'selected_slot':3,'slots':{'1':'Int 0','2':'Int 7','3':'Double 0.5','4':'Long 4294967296','6':'String not-a-number','7':'Double NaN','8':'absent component'},'scope':'Controlled copied test world; no production world or item modified.'}
(out/'fixture.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
