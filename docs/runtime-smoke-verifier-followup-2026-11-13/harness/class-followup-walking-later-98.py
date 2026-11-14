from pathlib import Path
from PIL import Image
from Xlib import X, XK, display
from Xlib.ext import xtest
import atexit, hashlib, json, math, os, shutil, subprocess, time
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
import nbtlib
shared=Path('/workspace/.minecraft-test');helper=shared;java8='/workspace/.toolchains/jre8/bin/java';java16='/workspace/.toolchains/jdk16/bin/java';player='f36d949a-12db-4676-bc41-a7b7fe97fd55.dat';install.install_jvm_runtime=lambda *args,**kwargs:None
env={**os.environ,'DISPLAY':':98','LIBGL_ALWAYS_SOFTWARE':'1','PYTHONPATH':'/workspace/.toolchains/python'}
runner_name='class-followup-later'
active=[]
def cleanup():
 for process in active:
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait()
atexit.register(cleanup)
heads=json.loads(Path('/workspace/.minecraft-test-class-linkage-heads.json').read_text())
builds=json.loads(Path('/workspace/.tprm-dryrun/class-linkage-builds/index.json').read_text())
metadata=json.loads(Path('/workspace/tprm-legacy-coordination/docs/legacy-candidate-evidence.json').read_text())
inventory=json.loads(Path('/workspace/tprm-legacy-coordination/docs/legacy-version-inventory.json').read_text())
ordered=list(reversed([r for r in inventory['versions'] if r['minecraft'] in {v for g in metadata['groups'].values() for v in g['versions']}]))
java_paths={8:java8,16:java16,17:'/workspace/.toolchains/jdk17/bin/java',21:'/usr/lib/jvm/java-21-openjdk-amd64/bin/java'}
runs=[]
for row in ordered:
 version=row['minecraft']
 if tuple(map(int,version.split('.'))) < (1,20,5):continue
 group=next(k for k,g in metadata['groups'].items() if version in g['versions']);g=metadata['groups'][group];worktree='1.14' if group=='1.14-1.14.4' else group
 jar=Path('/workspace/.tprm-dryrun/class-linkage-builds')/group/g['artifact'];assert jar.exists(),jar
 if version in ('1.19.3','1.21.4'):
  source_version={'1.19.3':'1.19.2','1.21.4':'1.21.3'}[version];prefix='/workspace/.minecraft-test-left-early-baseline-' if version=='1.19.3' else '/workspace/.minecraft-test-left-baseline-';fixture=Path(prefix+source_version)
 elif tuple(map(int,version.split('.'))) <= (1,19,2):fixture=Path('/workspace/.minecraft-test-left-early-baseline-'+version)
 elif tuple(map(int,version.split('.'))) <= (1,20,4):fixture=Path('/workspace/.minecraft-test-left-java17-baseline-'+version)
 else:fixture=Path('/workspace/.minecraft-test-left-baseline-'+version)
 assert (fixture/'saves/New World').is_dir() and (fixture/'options.txt').exists(),fixture
 java=java_paths[row['java']['majorVersion']];runs.append((version,fixture,jar,builds[group]['sha256'],java,heads[group]['new_head']))

def wait(p,log,needle,seconds,offset=0):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if needle in log.read_text(errors='replace')[offset:]:return
  if p.poll() is not None:raise RuntimeError('Client exited before '+needle)
  time.sleep(2)
 raise TimeoutError(needle)
def send_key(name,pressed):
 d=display.Display(':98');r=d.screen().root
 try:
  wins=[w for w in r.query_tree().children if (w.get_wm_name() or '').startswith('Minecraft')];assert len(wins)==1;wins[0].set_input_focus(X.RevertToParent,X.CurrentTime);code=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress if pressed else X.KeyRelease,code);d.sync()
 finally:d.close()
def tap(name):send_key(name,True);time.sleep(.2);send_key(name,False);time.sleep(.8)
def capture(root,name):
 d=display.Display(':98');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close();im.save(root/(name+'.png'));print('Captured',name,flush=True)

def hotbar():
 end=time.monotonic()+180
 while time.monotonic()<end:
  d=display.Display(':98');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
  yellow=sum(1 for y in range(660,710) for x in range(368,911) if (lambda c:c[0]>180 and c[1]>180 and c[2]>100 and c[0]>c[2]*1.1)(im.getpixel((x,y))))
  gray=sum(1 for y in range(655,720) for x in range(365,915) if (lambda c:abs(c[0]-c[1])<3 and abs(c[1]-c[2])<3 and 50<c[0]<180)(im.getpixel((x,y))))
  if yellow>500 and gray>2000:return
  time.sleep(2)
 raise TimeoutError('visible in-world hotbar')
def command(text,expected,log):
 off=log.stat().st_size;tap('t');subprocess.run(['python3',str(helper/'x11-class-followup-98.py'),'type:'+text],env=env,check=True,stdout=subprocess.DEVNULL);tap('Return')
 end=time.monotonic()+30
 while time.monotonic()<end:
  if expected in log.read_text(errors='replace')[off:]:return
  time.sleep(.5)
 raise RuntimeError('Unconfirmed command '+text)
def prune_assets_for(version):
 import fcntl
 from urllib.request import urlopen
 with urlopen('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json',timeout=90) as response: manifest=json.load(response)
 entry=next(x for x in manifest['versions'] if x['id']==version)
 with urlopen(entry['url'],timeout=90) as response: raw=response.read()
 assert hashlib.sha1(raw).hexdigest()==entry['sha1']
 metadata=json.loads(raw);assert metadata['id']==version
 spec=metadata['assetIndex']
 with urlopen(spec['url'],timeout=90) as response: raw=response.read()
 assert hashlib.sha1(raw).hexdigest()==spec['sha1'] and len(raw)==spec['size']
 hashes=sorted({x['hash'] for x in json.loads(raw)['objects'].values()})
 marker=shared/('active-assets-'+runner_name+'.json');lock=shared/'active-assets.lock'
 with lock.open('a+') as file:
  fcntl.flock(file,fcntl.LOCK_EX)
  temp=marker.with_suffix('.tmp');temp.write_text(json.dumps({'version':version,'hashes':hashes}));temp.replace(marker)
  keep=set(hashes)
  for other in shared.glob('active-assets-*.json'):
   keep.update(json.loads(other.read_text())['hashes'])
  removed=0
  for path in (shared/'assets/objects').glob('*/*'):
   if path.is_file() and path.name not in keep:
    removed+=path.stat().st_size;path.unlink()
  fcntl.flock(file,fcntl.LOCK_UN)
 print('Pruned re-downloadable assets for',runner_name,version,'bytes',removed,flush=True)

for version,fixture,jar,digest,java,source_sha in runs:
 assert hashlib.sha256(jar.read_bytes()).hexdigest()==digest
 root=Path('/workspace/.minecraft-test-class-followup-walk-'+version)
 if (root/'movement.json').exists():
  assert json.loads((root/'movement.json').read_text())['candidate_sha256']==digest
  print('Already completed',version,flush=True);continue
 prune_assets_for(version)
 assert not root.exists();assert shutil.disk_usage('/workspace').free > 180*1024*1024, 'Insufficient free disk for client install';(root/'saves').mkdir(parents=True);(root/'mods').mkdir();shutil.copytree(fixture/'saves/New World',root/'saves/New World');shutil.copy2(fixture/'options.txt',root/'options.txt');shutil.copy2(jar,root/'mods'/jar.name)
 vanilla=shared/'versions'/version;fabric=shared/'versions'/('fabric-loader-0.20.1-'+version);created=[p for p in (vanilla,fabric) if not p.exists()];tracked=[p for p in (vanilla/(version+'.jar'),fabric/('fabric-loader-0.20.1-'+version+'.jar')) if not p.exists()]
 launcher.install.install_minecraft_version(version,str(shared));launcher.fabric.install_fabric(version,str(shared),loader_version='0.20.1',java=java)
 opts={'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','token':'0','executablePath':java,'jvmArguments':['-Xmx1200M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'gameDirectory':str(root),'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
 if tuple(map(int,version.split('.'))) >= (1,20,2):opts['quickPlaySingleplayer']='New World'
 cmd=launcher.command.get_minecraft_command('fabric-loader-0.20.1-'+version,str(shared),opts);log=root/'client.log';captures={};print('Launching',version,digest,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT);active.append(p)
  if tuple(map(int,version.split('.'))) < (1,20,2):
   wait(p,log,'mob_effect',180);time.sleep(8)
   subprocess.run(['python3',str(helper/'x11-class-followup-98.py'),'click:640:350','sleep:2','click:500:195','sleep:1','click:400:595'],env=env,check=True,stdout=subprocess.DEVNULL);time.sleep(8)
   if 'Starting integrated' not in log.read_text(errors='replace'):subprocess.run(['python3',str(helper/'x11-class-followup-98.py'),'click:380:410'],env=env,check=True,stdout=subprocess.DEVNULL)
  wait(p,log,'MapSmokeTest joined the game',360);hotbar()
  command('/fill -5 80 -73 15 80 -33 minecraft:stone','Successfully filled',log);command('/fill -5 81 -73 15 85 -33 minecraft:air','Successfully filled',log)
  command('/tp @s 5.5 81 -62.5','Teleported',log);command('/time set day','Set the time to 1000',log);tap('F5');time.sleep(3)
  capture(root,'standing-day')
  d=display.Display(':98');r=d.screen().root;wins=[w for w in r.query_tree().children if (w.get_wm_name() or '').startswith('Minecraft')];assert len(wins)==1;wins[0].set_input_focus(X.RevertToParent,X.CurrentTime);code=d.keysym_to_keycode(XK.string_to_keysym('w'));xtest.fake_input(d,X.KeyPress,code);d.sync()
  try:
   for i in range(1,3):time.sleep(.9);capture(root,'walking-'+str(i))
  finally:xtest.fake_input(d,X.KeyRelease,code);d.sync();d.close()
  time.sleep(1);capture(root,'after-walk')
  offset=log.stat().st_size;tap('Escape');subprocess.run(['python3',str(helper/'x11-class-followup-98.py'),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL);wait(p,log,'All dimensions are saved' if tuple(map(int,version.split('.'))) >= (1,21,5) else 'All chunks are saved',120,offset);time.sleep(5);subprocess.run(['python3',str(helper/'x11-class-followup-98.py'),'click:785:605'],env=env,check=True,stdout=subprocess.DEVNULL);p.wait(timeout=45);assert p.returncode==0
 end=[float(x) for x in nbtlib.load(root/'saves/New World/playerdata'/player)['Pos']];horizontal=math.hypot(end[0]-5.5,end[2]+62.5);print(version,'ending position',end,'horizontal distance',horizontal,flush=True);assert horizontal>.5
 assert not any(x in log.read_text(errors='replace') for x in ('MixinApplyError','InvalidInjectionException','NoSuchMethodError','MixinTransformerError'))
 (root/'movement.json').write_text(json.dumps({'minecraft':version,'start':[5.5,81,-62.5],'end':end,'horizontal_distance':horizontal,'renderer':'Linux Xorg/Mesa software','candidate_sha256':digest,'source_commit':source_sha,'note':'One short local walking scene; screenshots require visual inspection and do not establish full acceptance.'},indent=2)+'\n')
 shutil.copy2(root/'saves/New World/playerdata'/player,root/'ending-player.dat')
 shutil.rmtree(root/'saves')
 for f in (root/'.fabric/remappedJars').glob('**/*-intermediary.jar'):f.unlink()
 for path in created:
  if path.exists() and path.parent==shared/'versions':shutil.rmtree(path)
 for path in tracked:
  if path.exists():path.unlink()
 print('Completed',version,flush=True)
print('All remaining short movement checks completed',flush=True)
