from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,subprocess,time
w=Path('/workspace');heads=json.loads(Path('/tmp/tprm-stabilization-heads.json').read_text());old=json.loads((w/'tprm-legacy-coordination/docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups'];manifest=json.loads((w/'tprm-legacy-coordination/docs/legacy-dry-run-1.0.0-2026-11-14/release-manifest.json').read_text());out=w/'.tprm-dryrun/stabilization-final-api-20261114';out.mkdir(exist_ok=True);jobs=[]
for spec in manifest['groups']:
 group=spec['id'];repo=Path(heads[group]['worktree']);sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();assert sha==heads[group]['new_head']
 for name in ('scripts/jvm_linkage.py','scripts/game_linkage.py','scripts/verify_supported_apis.py'):
  actual=(repo/name).read_bytes();committed=subprocess.check_output(['git','show',sha+':'+name],cwd=repo);assert actual==committed
 jar=w/'.tprm-dryrun/class-linkage-builds'/group/old[group]['artifact'];assert hashlib.sha256(jar.read_bytes()).hexdigest()==old[group]['sha256']
 for version in spec['minecraft']:jobs.append((group,repo,sha,jar,version))
def run(job):
 group,repo,sha,jar,version=job;log=out/(version+'.log');start=time.monotonic()
 for attempt in (1,2):
  with log.open('w' if attempt==1 else 'a') as f:
   if attempt>1:f.write('\nRETRY AFTER PRIOR FAILED ATTEMPT\n')
   p=subprocess.run(['python3','scripts/verify_supported_apis.py','--jar',str(jar),'--versions',version],cwd=repo,stdout=f,stderr=subprocess.STDOUT)
  if p.returncode==0:break
 result={'group':group,'version':version,'source_commit':sha,'artifact_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),'exit_code':p.returncode,'attempts':attempt,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
 print(group,version,'exit',p.returncode,'attempts',attempt,'seconds',round(time.monotonic()-start,1),flush=True)
 return result
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,jobs))
(out/'index.json').write_text(json.dumps({'results':results,'status':'local verifier sweep against retained prior JAR bytes; final clean-build identity must be checked separately'},indent=2)+'\n')
print('Completed',sum(r['exit_code']==0 for r in results),'of',len(results),'versions',flush=True)
