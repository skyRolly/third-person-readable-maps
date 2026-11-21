from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib, json, re, urllib.request

root=Path(__file__).resolve().parents[3]
out=root/'docs/dependency-evidence/log4j-config-2026-11-12'
out.mkdir(exist_ok=True)
def get(url):
    with urllib.request.urlopen(url,timeout=60) as response: return response.read()
manifest=json.loads(get('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
entries={x['id']:x for x in manifest['versions'] if x['type']=='release'}
inventory=json.loads((root/'docs/legacy-version-inventory.json').read_text())
versions=[x['minecraft'] for x in inventory['versions']]+['1.21.11','26.1','26.1.1','26.1.2','26.2','26.3']
assert len(versions)==len(set(versions))==48
def metadata(v):
    e=entries[v];data=get(e['url']);assert hashlib.sha1(data).hexdigest()==e['sha1']
    m=json.loads(data); libs=[x['name'] for x in m['libraries'] if x['name'].split(':')[:2]==['org.apache.logging.log4j','log4j-core']]
    return v,{'metadata_url':e['url'],'metadata_sha1':e['sha1'],'log4j_core_coordinates':libs,'logging':m.get('logging',{}).get('client')}
with ThreadPoolExecutor(max_workers=8) as pool: records=dict(pool.map(metadata,versions))
configs={}
for v in versions:
    log=records[v]['logging']
    if not log: continue
    f=log['file'];sha=f['sha1']
    if sha not in configs:
        raw=get(f['url']);assert hashlib.sha1(raw).hexdigest()==sha and len(raw)==f['size']
        text=raw.decode('utf-8');(out/(sha+'.xml')).write_bytes(raw)
        configs[sha]={'id':f['id'],'url':f['url'],'sha1':sha,'sha256':hashlib.sha256(raw).hexdigest(),
                      'size':len(raw),'path':'log4j-config-2026-11-12/'+sha+'.xml',
                      'mentions_nolookups':'nolookups' in text.lower(),
                      'mentions_context_lookup':bool(re.search(r'\$\$?\{ctx:',text,re.I)),
                      'mentions_context_pattern':bool(re.search(r'%(?:X|mdc|MDC)(?:\{|\b)',text))}
    else: assert configs[sha]['size']==f['size'] and configs[sha]['url']==f['url']
    records[v]['logging']={'argument':log['argument'],'config_sha1':sha}
result={'schema':1,'checked_on':'2026-11-12','source':'Mojang version manifest and SHA-1-verified version metadata',
        'scope':'default client logging configuration only; launchers, other mods and execution paths may differ',
        'versions':records,'configs':configs}
(root/'docs/dependency-evidence/log4j-default-config-2026-11-12.json').write_text(json.dumps(result,indent=2)+'\n')
print('Verified',len(records),'version manifests and',len(configs),'distinct client logging configurations')
for sha,c in configs.items():print(c['id'],sha,'nolookups',c['mentions_nolookups'],'context-lookup',c['mentions_context_lookup'],'context-pattern',c['mentions_context_pattern'])
