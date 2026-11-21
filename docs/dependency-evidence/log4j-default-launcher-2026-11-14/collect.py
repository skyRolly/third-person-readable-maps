from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen
import hashlib,json,time
root=Path('/workspace/tprm-legacy-coordination');source=root/'docs/dependency-evidence/osv-rescan-2026-11-14/final-proposals';versions=set()
for p in source.glob('*-report.json'):
 d=json.loads(p.read_text())
 for m in d.get('matches',[]):
  if m['advisory'] in ('GHSA-jfh8-c2jp-5v3q','GHSA-7rjr-3q55-vv33','GHSA-fxph-q3j8-mv87'):
   versions.update(scope[8:] for scope in m['scopes'] if scope.startswith('runtime/'))
def get(url):
 for attempt in range(3):
  try:
   with urlopen(url,timeout=30) as response:return response.read()
  except OSError:
   if attempt==2:raise
   time.sleep(1)
manifest=json.loads(get('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'))
def check(version):
 x=next(x for x in manifest['versions'] if x['id']==version);raw=get(x['url']);assert hashlib.sha1(raw).hexdigest()==x['sha1'];doc=json.loads(raw);entry=doc.get('logging',{}).get('client');assert entry and entry['type']=='log4j2-xml';spec=entry['file'];data=get(spec['url']);assert len(data)==spec['size'] and hashlib.sha1(data).hexdigest()==spec['sha1'];return version,{'metadata_url':x['url'],'metadata_sha1':x['sha1'],'logging_argument':entry['argument'],'config':spec,'config_sha256':hashlib.sha256(data).hexdigest(),'contains_nolookups':b'%msg{nolookups}' in data,'contains_legacy_xml_layout':b'LegacyXMLLayout' in data}
with ThreadPoolExecutor(max_workers=3) as pool:rows=dict(pool.map(check,sorted(versions)))
Path('/tmp/tprm-log4j-configuration-survey.json').write_text(json.dumps({'groups':'historical Log4j candidate matches','versions':rows},indent=2)+'\n');print('Verified launcher metadata and logging configurations for',len(rows),'versions')
