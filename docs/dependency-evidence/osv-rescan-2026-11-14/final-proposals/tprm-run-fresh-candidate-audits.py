from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json,subprocess,time
root=Path('/workspace/tprm-legacy-coordination');out=Path('/workspace/.tprm-dryrun/stabilization-security-20261114');heads=json.loads(Path('/tmp/tprm-stabilization-heads.json').read_text())
def run(item):
 g,h=item
 cmd=['python3',str(root/'scripts/audit_candidate_dependencies.py'),'audit','--snapshot',str(out/(g+'-snapshot.json')),'--source',h['worktree'],'--group',g,'--branch',h['branch'],'--source-sha',h['new_head'],'--output',str(out/(g+'-report.json'))]
 p=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/(g+'-audit.log')).write_text(p.stdout)
 report=json.loads((out/(g+'-report.json')).read_text());result={'exit_code':p.returncode,'status':report['status'],'matches':len(report.get('matches',[])),'disappeared_needing_review':len(report.get('resolved_needing_review',[])),'error':report.get('error')}
 return g,result
items=[(g,h) for g,h in heads.items() if h['branch'].startswith('candidate/')];results={}
with ThreadPoolExecutor(max_workers=3) as pool:
 for future in as_completed([pool.submit(run,item) for item in items]):
  g,r=future.result();results[g]=r;(out/'audit-index.json').write_text(json.dumps(results,indent=2)+'\n');print(g,json.dumps(r),flush=True)
print('Completed',len(results),'candidate audits',flush=True)
