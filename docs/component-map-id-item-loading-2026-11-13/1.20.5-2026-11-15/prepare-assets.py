"""Prepare hash-checked 1.20.5 assets in task-owned tmpfs without pruning shared assets."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib, json, os, time, urllib.request

version='1.20.5';root=Path('/dev/shm/tprm-mapid-1205-assets');assets=root/'assets'
shared=Path('/workspace/.minecraft-test/assets/objects')
for name in ('objects','indexes'):(assets/name).mkdir(parents=True,exist_ok=True)
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ThirdPersonReadableMaps-validation/1.0'})
    with urllib.request.urlopen(req,timeout=90) as response:return response.read()
manifest=json.loads(fetch('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
entry=next(e for e in manifest['versions'] if e['id']==version)
raw=fetch(entry['url']);assert hashlib.sha1(raw).hexdigest()==entry['sha1']
metadata=json.loads(raw);assert metadata['id']==version
spec=metadata['assetIndex'];index=fetch(spec['url'])
assert len(index)==spec['size'] and hashlib.sha1(index).hexdigest()==spec['sha1']
(assets/'indexes'/(spec['id']+'.json')).write_bytes(index)
objects={item['hash']:item['size'] for item in json.loads(index)['objects'].values()}
def obtain(item):
    digest,size=item;dest=assets/'objects'/digest[:2]/digest;dest.parent.mkdir(exist_ok=True)
    existing=shared/digest[:2]/digest
    if existing.exists() and existing.stat().st_size==size and hashlib.sha1(existing.read_bytes()).hexdigest()==digest:
        if not dest.exists():dest.symlink_to(existing)
        return 'reused',size
    if dest.is_file() and not dest.is_symlink() and dest.stat().st_size==size and hashlib.sha1(dest.read_bytes()).hexdigest()==digest:
        return 'downloaded',size
    last=None
    for attempt in range(3):
        try:
            data=fetch('https://resources.download.minecraft.net/'+digest[:2]+'/'+digest)
            if len(data)!=size or hashlib.sha1(data).hexdigest()!=digest:raise ValueError('asset digest or size mismatch')
            dest.write_bytes(data);return 'downloaded',size
        except Exception as exc:last=type(exc).__name__;time.sleep(.2*(attempt+1))
    raise RuntimeError('asset '+digest+' failed: '+str(last))
counts={'reused':0,'downloaded':0};sizes={'reused':0,'downloaded':0};errors=[]
with ThreadPoolExecutor(max_workers=12) as pool:
    futures={pool.submit(obtain,item):item[0] for item in objects.items()}
    for done,future in enumerate(as_completed(futures),1):
        try:kind,size=future.result();counts[kind]+=1;sizes[kind]+=size
        except Exception as exc:errors.append(str(exc))
        if done%250==0:print('assets',done,'of',len(objects),'errors',len(errors),flush=True)
report={'minecraft':version,'manifest_metadata_sha1':entry['sha1'],'asset_index_id':spec['id'],
        'asset_index_sha1':spec['sha1'],'asset_index_size':spec['size'],'unique_objects':len(objects),
        'counts':counts,'bytes':sizes,'errors':errors,'storage':'task-owned /dev/shm; verified shared assets linked read-only'}
(root/'asset-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
if errors:raise SystemExit(1)
