from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/tprm-legacy-coordination');workspace=root.parent;old=root/'docs/dependency-evidence/class-linkage-proposals-2026-11-13';sources=json.loads((old/'index.json').read_text())['groups'];out=workspace/'.tprm-dryrun/osv-proposal-rescan-20261114';out.mkdir(parents=True,exist_ok=True);jobs=[]
for group,source in sources.items():
 branch=source['branch'];sha=source['source_sha'];repo=workspace/('tprm-review-'+group)
 assert subprocess.check_output(['git','rev-parse','refs/remotes/origin/'+branch],cwd=root,text=True).strip()==sha
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==sha
 snapshot=root/source['snapshot_path'];assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==source['snapshot_sha256']
 report=out/(group+'-osv.json');log=out/(group+'-audit.log')
 cmd=['python3','scripts/audit_maintenance_proposal.py','--snapshot',str(snapshot),'--source',str(repo),'--group',group,'--branch',branch,'--source-sha',sha,'--output',str(report)]
 jobs.append((group,source,report,log,cmd))
def run(job):
 group,source,report,log,cmd=job
 with log.open('w') as f:p=subprocess.run(cmd,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 if not report.exists():print(group,'incomplete exit',p.returncode,flush=True);return group,{'exit_code':p.returncode,'complete':False}
 d=json.loads(report.read_text());assert d['source_sha']==source['source_sha'] and d['scanned_on']=='2026-11-14';old_report=json.loads((root/source['report_path']).read_text());key=lambda m:(m['purl'],m['advisory'],m['fingerprint'],tuple(sorted(m['scopes'])),m['state'],m['failing']);same={key(m) for m in d['matches']}=={key(m) for m in old_report['matches']};complete=d['status']=='complete-unreviewed-maintenance-proposal';print(group,'exit',p.returncode,'matches',len(d['matches']),'same',same,'complete',complete,flush=True)
 return group,{'exit_code':p.returncode,'complete':complete,'source_sha':source['source_sha'],'branch':source['branch'],'snapshot_path':source['snapshot_path'],'snapshot_sha256':source['snapshot_sha256'],'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'matches':len(d['matches']),'failing':sum(bool(m['failing']) for m in d['matches']),'same_as_prior':same,'resolved_needing_review':d.get('resolved_needing_review',[])}
with ThreadPoolExecutor(max_workers=3) as pool:results=dict(pool.map(run,jobs))
(out/'index.json').write_text(json.dumps({'scanned_on':'2026-11-14','snapshot_note':'Reused the retained exact proposed maintenance snapshots; queried OSV again without re-resolving Gradle dependencies.','groups':results},indent=2)+'\n')
print('Completed',sum(x['complete'] for x in results.values()),'of',len(results),'proposal OSV rescans',flush=True)
