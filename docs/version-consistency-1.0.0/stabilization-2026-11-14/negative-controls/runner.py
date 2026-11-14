from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib,json,subprocess
workspace=Path('/workspace');heads=json.loads((Path('/tmp/tprm-stabilization-heads.json')).read_text());builds=json.loads((workspace/'.tprm-dryrun/stabilization-final-builds-20261114/index.json').read_text())
cases={'1.14-1.14.4':['1.15'],'1.15-1.16.5':['1.14.4','1.17'],'1.17-1.19.2':['1.19.3'],'1.19.3':['1.19.2','1.19.4'],'1.21.4-1.21.8':['1.21.9'],'1.21.9-1.21.10':['1.21.8','1.21.11']}
out=workspace/'.tprm-dryrun/stabilization-final-negatives-20261114';out.mkdir(parents=True,exist_ok=True)
def run(group,version):
 root=workspace/('tprm-legacy-'+('1.14' if group=='1.14-1.14.4' else group));sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert sha==heads[group]['new_head']
 jar=workspace/'.tprm-dryrun/stabilization-final-builds-20261114'/group/builds[group]['artifact'];digest=hashlib.sha256(jar.read_bytes()).hexdigest();assert digest==builds[group]['sha256']
 p=subprocess.run(['python3','scripts/verify_supported_apis.py','--jar',str(jar),'--versions',version],cwd=root,capture_output=True,text=True)
 output=(p.stdout+'\n'+p.stderr).strip()+'\n';log=out/(group+'-on-'+version+'.log');log.write_text(output)
 valid=p.returncode!=0 and any(x in output for x in ('missing Mixin target','missing classes','missing game members','missing game or descriptor classes'))
 return {'group':group,'unsupported_version':version,'source_commit':sha,'artifact_sha256':digest,'exit_code':p.returncode,'discriminating_rejection':valid,'log':log.name,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'tail':output.splitlines()[-3:]}
with ThreadPoolExecutor(max_workers=2) as pool:
 results={}
 for f in as_completed([pool.submit(run,g,v) for g,vs in cases.items() for v in vs]):
  row=f.result();results[row['group']+' on '+row['unsupported_version']]=row;print(row['group'],'on',row['unsupported_version'],'REJECTED' if row['discriminating_rejection'] else 'FAIL',flush=True)
  (out/'index.json').write_text(json.dumps(results,indent=2)+'\n')
if len(results)!=9 or any(not row['discriminating_rejection'] for row in results.values()):raise SystemExit('Some adjacent-version negative controls failed')
