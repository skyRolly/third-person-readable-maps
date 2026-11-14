from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/tprm-legacy-coordination');workspace=root.parent
worklist=json.loads((root/'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
out=workspace/'.tprm-dryrun/osv-rescan-20261114';out.mkdir(parents=True,exist_ok=True)
jobs=[]
for group,source in worklist['sources'].items():
 branch=source['snapshot_ref'].removeprefix('refs/heads/');sha=source['source_sha']
 remote=subprocess.check_output(['git','rev-parse','refs/remotes/origin/'+branch],cwd=root,text=True).strip();assert remote==sha,(group,remote,sha)
 snapshot=root/source['snapshot_path'];assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==source['snapshot_sha256']
 report=out/(group+'-osv.json');log=out/(group+'-audit.log')
 if source['source_kind']=='candidate':
  repo=workspace/('tprm-legacy-'+('1.14' if group=='1.14-1.14.4' else group));assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==sha
  cmd=['python3','scripts/audit_candidate_dependencies.py','audit','--snapshot',str(snapshot),'--source',str(repo),'--group',group,'--branch',branch,'--source-sha',sha,'--output',str(report)]
 else:cmd=['python3','scripts/audit_dependencies.py','--snapshot',str(snapshot),'--branch',branch,'--source-sha',sha,'--output',str(report)]
 jobs.append((group,source,report,log,cmd))
def run(job):
 group,source,report,log,cmd=job
 with log.open('w') as f:p=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 if not report.exists():print(group,'incomplete exit',p.returncode,flush=True);return group,{'exit_code':p.returncode,'complete':False}
 d=json.loads(report.read_text());assert d['source_sha']==source['source_sha'] and d['scanned_on']=='2026-11-14'
 old=json.loads((root/source['report_path']).read_text());key=lambda m:(m['purl'],m['advisory'],m['fingerprint'],tuple(sorted(m['scopes'])),m['state'],m['failing'])
 same={key(m) for m in d['matches']}=={key(m) for m in old['matches']};counts={}
 for m in d['matches']:counts[m['state']]=counts.get(m['state'],0)+1
 complete=d['status'] in ('complete','complete-unreviewed-candidate-scan');print(group,'exit',p.returncode,'matches',len(d['matches']),'same',same,'complete',complete,flush=True)
 return group,{'exit_code':p.returncode,'complete':complete,'source_sha':source['source_sha'],'source_kind':source['source_kind'],'snapshot_path':source['snapshot_path'],'snapshot_sha256':source['snapshot_sha256'],'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'matches':len(d['matches']),'states':counts,'failing':sum(bool(m['failing']) for m in d['matches']),'same_as_prior':same,'resolved_needing_review':d.get('resolved_needing_review',[])}
with ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(run,jobs))
(out/'index.json').write_text(json.dumps({'scanned_on':'2026-11-14','snapshot_note':'Reused the retained source-bound Gradle snapshots; queried OSV again without re-resolving Gradle dependencies.','groups':results},indent=2)+'\n')
print('Completed',sum(x['complete'] for x in results.values()),'of',len(results),'OSV rescans',flush=True)
