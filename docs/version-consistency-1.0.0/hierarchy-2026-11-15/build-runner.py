from pathlib import Path
from zipfile import ZipFile
import hashlib, json, os, shutil, subprocess, tempfile

w = Path('/workspace')
heads = json.loads(Path('/tmp/tprm-hierarchy-final-heads.json').read_text())
previous = json.loads((w/'.tprm-dryrun/wrapper-hardening-final-builds-20261114/index.json').read_text())
out = w/'.tprm-dryrun/hierarchy-final-builds-20261115'
out.mkdir(parents=True, exist_ok=True)
index = out/'index.json'
results = json.loads(index.read_text()) if index.exists() else {}
env = {**os.environ, 'JAVA_HOME': '/workspace/.toolchains/jdk25', 'JAVA_HOME_25_X64': '/workspace/.toolchains/jdk25',
       'JAVA_TOOL_OPTIONS': '-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts -Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080'}
requested = os.environ.get('TPRM_GROUP')
groups = [requested] if requested else sorted(heads)
for group in groups:
 info = heads[group]; repo = Path(info['worktree']); sha = info['new_head']
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip() == sha
 if group in results:
  item = results[group]; artifact = out/group/item['artifact']
  assert item['source_commit'] == sha and hashlib.sha256(artifact.read_bytes()).hexdigest() == item['sha256']
  print('REUSE VERIFIED',group,flush=True);continue
 if shutil.disk_usage(w).free < 120*1024*1024: raise RuntimeError('Insufficient free workspace space before '+group)
 if shutil.disk_usage('/dev/shm').free < 1024*1024*1024: raise RuntimeError('Insufficient free temporary storage before '+group)
 print('BUILD',group,sha,flush=True)
 with tempfile.TemporaryDirectory(prefix='tprm-hierarchy-build-',dir='/dev/shm') as temp:
  temp=Path(temp);src=temp/'source';src.mkdir();archive=temp/'source.tar'
  names=subprocess.check_output(['git','ls-tree','--name-only',sha],cwd=repo,text=True).splitlines()
  names=[n for n in names if n not in ('docs','.github')]
  subprocess.run(['git','archive','--format=tar','--output',str(archive),sha,'--',*names],cwd=repo,check=True)
  subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True);archive.unlink()
  log=out/(group+'-build.log')
  with log.open('w') as f:
   preflight=subprocess.run(['python3',str(w/'tprm-legacy-coordination/scripts/verify_gradle_wrapper.py'),'--root',str(src)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
  if preflight.returncode: raise RuntimeError('Wrapper preflight failed for '+group)
  with log.open('a') as f:
   p=subprocess.run(['./gradlew','--no-daemon','--console=plain','clean','build'],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
  if p.returncode:
   print('BUILD FAILED',group,log.read_text(errors='replace')[-4000:],flush=True);raise SystemExit(p.returncode)
  name=previous[group]['artifact'];jar=src/'build/libs'/name;assert jar.is_file(),name
  with ZipFile(jar) as z:
   metadata=json.loads(z.read('fabric.mod.json'));assert metadata['version']=='1.0.0' and metadata['id']=='thirdpersonreadablemaps'
  digest=hashlib.sha256(jar.read_bytes()).hexdigest();target=out/group;target.mkdir(exist_ok=True);shutil.copyfile(jar,target/name)
  results[group]={'source_commit':sha,'branch':info['branch'],'artifact':name,'sha256':digest,
                  'previous_source':previous[group]['source_commit'],'previous_sha256':previous[group]['sha256'],
                  'same_as_previous':digest==previous[group]['sha256'], 'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                  'build_storage':'task-owned /dev/shm; no cache deletion', 'wrapper_preflight':'coordinator verifier before gradlew'}
  index.write_text(json.dumps(results,indent=2)+'\n')
  print('BUILT',group,digest,'same',results[group]['same_as_previous'],flush=True)
print('COMPLETE',len(results),'groups',flush=True)
