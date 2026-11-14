from pathlib import Path
import hashlib, json, shutil
import nbtlib

source=Path('/workspace/.minecraft-test-foreground-1214-candidate')
target=Path('/workspace/.minecraft-test-mapid-112-1.21.4-fixture')
assert not target.exists()
target.mkdir()
shutil.copytree(source/'saves'/'New World',target/'saves'/'New World')
shutil.copy2(source/'options.txt',target/'options.txt')
world=target/'saves'/'New World'
(world/'session.lock').unlink(missing_ok=True)
player=world/'playerdata'/'f36d949a-12db-4676-bc41-a7b7fe97fd55.dat'
level=nbtlib.load(world/'level.dat');saved=nbtlib.load(player)
def amend(obj):
    inventory=obj['Inventory']
    byslot={int(item['Slot']):item for item in inventory}
    byslot[1]['components']['minecraft:map_id']=nbtlib.Int(0)
    byslot[2]['components']['minecraft:map_id']=nbtlib.Int(7)
    byslot[3]['components']['minecraft:map_id']=nbtlib.Double(0.5)
    byslot[4]['components']['minecraft:map_id']=nbtlib.Long(4294967296)
    inventory.append(nbtlib.Compound({'count':nbtlib.Int(1),'Slot':nbtlib.Byte(6),'id':nbtlib.String('minecraft:filled_map'),'components':nbtlib.Compound({'minecraft:map_id':nbtlib.String('not-a-number')})}))
    inventory.append(nbtlib.Compound({'count':nbtlib.Int(1),'Slot':nbtlib.Byte(7),'id':nbtlib.String('minecraft:filled_map'),'components':nbtlib.Compound({'minecraft:map_id':nbtlib.Double(float('nan'))})}))
    obj['SelectedItemSlot']=nbtlib.Int(3)
amend(level['Data']['Player']);amend(saved)
level.save(world/'level.dat');saved.save(player)
shutil.copyfile(world/'data'/'map_1.dat',world/'data'/'map_0.dat')
out=Path('/workspace/.minecraft-test-mapid-112-evidence');out.mkdir(exist_ok=True)
for origin,name in [(world/'level.dat','input-level.dat'),(player,'input-player.dat'),(world/'data'/'map_0.dat','input-map-zero.dat')]:shutil.copyfile(origin,out/name)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
raw=nbtlib.load(world/'data'/'map_0.dat');colors=raw['data']['colors'];nonblank=sum(1 for x in colors if int(x)!=0)
assert nonblank>0
fixture={'minecraft':'1.21.4','baseline_world':'foreground-1214-candidate, copied before mutation','input_level_sha256':sha(out/'input-level.dat'),'input_player_sha256':sha(out/'input-player.dat'),'input_map_zero_sha256':sha(out/'input-map-zero.dat'),'map_zero_nonblank':nonblank,'selected_slot':3,'slots':{'1':'Int 0','2':'Int 7','3':'Double 0.5','4':'Long 4294967296','6':'String not-a-number','7':'Double NaN','8':'absent component'},'scope':'Controlled copied test world; no production world or item modified.'}
(out/'fixture.json').write_text(json.dumps(fixture,indent=2)+'\n')
print(json.dumps(fixture,indent=2))
