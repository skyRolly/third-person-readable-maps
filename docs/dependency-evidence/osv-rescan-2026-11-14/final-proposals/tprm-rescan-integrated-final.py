from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,hashlib,subprocess
root=Path('/workspace/tprm-legacy-coordination');out=Path('/workspace/.tprm-dryrun/stabilization-security-20261114');old=json.loads((root/'docs/dependency-evidence/osv-rescan-2026-11-14/index.json').read_text())['current_sources']
def run(group):
 s=old[group];snap=root/s['snapshot_path'];sha=s['source_sha'];branch='mc/'+group;assert subprocess.check_output(['git','rev-parse','refs/remotes/origin/'+branch],cwd=root,text=True).strip()==sha;assert hashlib.sha256(snap.read_bytes()).hexdigest()==s['snapshot_sha256']
 cmd=['python3','scripts/audit_dependencies.py','--snapshot',str(snap),'--branch',branch,'--source-sha',sha,'--output',str(out/(group+'-integrated-report.json'))]
 with (out/(group+'-integrated-audit.log')).open('w') as log:p=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT)
 d=json.loads((out/(group+'-integrated-report.json')).read_text());print(group,'exit',p.returncode,'status',d['status'],'matches',len(d.get('matches',[])),'disappeared',len(d.get('resolved_needing_review',[])),flush=True)
 return p.returncode,d['status']
with ThreadPoolExecutor(max_workers=3) as pool:
 r=list(pool.map(run,('1.21.11','26.1-26.2','26.3')))
assert all(code==1 and status=='complete' for code,status in r),r
print('COMPLETE: integrated sources; retained exact-source snapshots, fresh OSV query',flush=True)
