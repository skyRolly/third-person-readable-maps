from pathlib import Path
from PIL import Image
from Xlib import X, XK, display
from Xlib.ext import xtest
import atexit, hashlib, json, math, os, shutil, subprocess, time
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
import nbtlib
shared=Path('/workspace/.minecraft-test');helper=shared;java8='/workspace/.toolchains/jre8/bin/java';java16='/workspace/.toolchains/jdk16/bin/java';player='f36d949a-12db-4676-bc41-a7b7fe97fd55.dat';install.install_jvm_runtime=lambda *args,**kwargs:None
env={**os.environ,'DISPLAY':':102','LIBGL_ALWAYS_SOFTWARE':'1','PYTHONPATH':'/workspace/.toolchains/python'}
runner_name='class-followup-modern'
active=[]
def cleanup():
 for process in active:
  if process.poll() is None:
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait()
atexit.register(cleanup)
heads=json.loads(Path('/workspace/tprm-legacy-coordination/docs/source-head-transition-2026-11-13.json').read_text())['groups']
builds=json.loads(Path('/workspace/.tprm-dryrun/class-linkage-builds/index.json').read_text())
versions=['1.21.11','26.1','26.1.1','26.1.2','26.2','26.3']
runs=[]
for version in versions:
 group='1.21.11' if version=='1.21.11' else ('26.3' if version=='26.3' else '26.1-26.2')
 repo=Path('/workspace/tprm-review-'+group)
 jar=Path('/workspace/.tprm-dryrun/class-linkage-builds')/group/builds[group]['artifact']
 assert builds[group]['source_commit']==heads[group]['new_head'] and hashlib.sha256(jar.read_bytes()).hexdigest()==builds[group]['sha256']
 fixture=Path('/workspace/.minecraft-test-left-baseline-1.21.10')
 assert jar.exists() and (fixture/'saves/New World').is_dir() and (fixture/'options.txt').exists()
 java='/usr/lib/jvm/java-21-openjdk-amd64/bin/java' if version=='1.21.11' else '/workspace/.toolchains/jdk25/bin/java'
 runs.append((version,fixture,jar,builds[group]['sha256'],java,heads[group]['new_head']))

def wait(p,log,needle,seconds,offset=0):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if needle in log.read_text(errors='replace')[offset:]:return
  if p.poll() is not None:raise RuntimeError('Client exited before '+needle)
  time.sleep(2)
 raise TimeoutError(needle)
def game_windows(d):
 matches=[]
 for w in d.screen().root.query_tree().children:
  name=w.get_wm_name()
  if not name:
   prop=w.get_full_property(d.intern_atom('_NET_WM_NAME'),0)
   name=prop.value if prop else ''
  if isinstance(name,bytes):name=name.decode('utf-8','replace')
  g=w.get_geometry()
  if name.startswith('Minecraft') and g.width>=640 and g.height>=480:matches.append(w)
 return matches
def send_key(name,pressed):
 d=display.Display(':102');r=d.screen().root
 try:
  wins=game_windows(d);assert len(wins)==1;wins[0].set_input_focus(X.RevertToParent,X.CurrentTime);code=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress if pressed else X.KeyRelease,code);d.sync()
 finally:d.close()
def tap(name):send_key(name,True);time.sleep(.2);send_key(name,False);time.sleep(.8)
def capture(root,name):
 d=display.Display(':102');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close();im.save(root/(name+'.png'));print('Captured',name,flush=True)

def request_close():
 from Xlib.protocol import event
 d=display.Display(':102');r=d.screen().root
 wins=game_windows(d);assert len(wins)==1
 message=event.ClientMessage(window=wins[0],client_type=d.intern_atom('WM_PROTOCOLS'),data=(32,[d.intern_atom('WM_DELETE_WINDOW'),X.CurrentTime,0,0,0]))
 wins[0].send_event(message,event_mask=0);d.sync();d.close()

def hotbar():
 end=time.monotonic()+180
 while time.monotonic()<end:
  d=display.Display(':102');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
  yellow=sum(1 for y in range(660,710) for x in range(368,911) if (lambda c:c[0]>180 and c[1]>180 and c[2]>100 and c[0]>c[2]*1.1)(im.getpixel((x,y))))
  gray=sum(1 for y in range(655,720) for x in range(365,915) if (lambda c:abs(c[0]-c[1])<3 and abs(c[1]-c[2])<3 and 50<c[0]<180)(im.getpixel((x,y))))
  if yellow>500 and gray>2000:return
  time.sleep(2)
 raise TimeoutError('visible in-world hotbar')
def command(text,expected,log):
 off=log.stat().st_size;tap('t');subprocess.run(['python3',str(helper/'x11-class-followup-102.py'),'type:'+text],env=env,check=True,stdout=subprocess.DEVNULL);tap('Return')
 end=time.monotonic()+30
 while time.monotonic()<end:
  values=(expected,) if isinstance(expected,str) else expected
  if any(value in log.read_text(errors='replace')[off:] for value in values):return
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
  assert json.loads((root/'movement.json').read_text())['source_commit']==source_sha
  print('Already completed',version,flush=True);continue
 prune_assets_for(version)
 assert not root.exists();assert shutil.disk_usage('/workspace').free > 180*1024*1024, 'Insufficient free disk for client install';(root/'saves').mkdir(parents=True);(root/'mods').mkdir();shutil.copytree(fixture/'saves/New World',root/'saves/New World');shutil.copy2(fixture/'options.txt',root/'options.txt');shutil.copy2(jar,root/'mods'/jar.name)
 vanilla=shared/'versions'/version;fabric=shared/'versions'/('fabric-loader-0.20.1-'+version);created=[p for p in (vanilla,fabric) if not p.exists()];tracked=[p for p in (vanilla/(version+'.jar'),fabric/('fabric-loader-0.20.1-'+version+'.jar')) if not p.exists()]
 launcher.install.install_minecraft_version(version,str(shared));launcher.fabric.install_fabric(version,str(shared),loader_version='0.20.1',java=java)
 opts={'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','token':'0','executablePath':java,'jvmArguments':['-Xmx1200M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'gameDirectory':str(root),'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
 if tuple(map(int,version.split('.'))) >= (1,20,2):opts['quickPlaySingleplayer']='New World'
 cmd=launcher.command.get_minecraft_command('fabric-loader-0.20.1-'+version,str(shared),opts)
 # Give each client immutable copies of Fabric's classpath inputs so another
 # local installation cannot replace a JAR while this process is starting.
 from urllib.request import urlopen
 from zipfile import ZipFile
 profile=json.loads((fabric/('fabric-loader-0.20.1-'+version+'.json')).read_text());pins=[];replacements={}
 private=root/'launcher-pins';private.mkdir()
 for item in profile['libraries']:
  coord=item['name'].split(':')
  if len(coord)!=3 or coord[0] not in ('net.fabricmc','org.ow2.asm'):continue
  group,name,ver=coord;rel=Path(group.replace('.','/'))/name/ver/(name+'-'+ver+'.jar');source=shared/'libraries'/rel
  raw=source.read_bytes();actual=hashlib.sha1(raw).hexdigest()
  url=item.get('url','https://maven.fabricmc.net/').rstrip('/')+'/'+rel.as_posix()
  if item.get('sha1'):
   expected=item['sha1'];assert len(raw)==item['size']
  else:
   with urlopen(url+'.sha1',timeout=60) as response:expected=response.read().decode().strip().split()[0]
  assert actual==expected,(item['name'],actual,expected)
  dest=private/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  with ZipFile(dest) as archive:assert archive.testzip() is None
  replacements[str(source)]=str(dest);pins.append({'coordinate':item['name'],'url':url,'sha1':actual,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)})
 cp=cmd.index('-cp')+1;parts=cmd[cp].split(os.pathsep);cmd[cp]=os.pathsep.join(replacements.get(part,part) for part in parts)
 assert all(path in parts for path in replacements)
 (root/'launcher-pins.json').write_text(json.dumps({'source':'Fabric loader profile and Maven SHA-1 files','libraries':pins},indent=2)+'\n')
 log=root/'client.log';captures={};print('Launching',version,digest,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT);active.append(p)
  if tuple(map(int,version.split('.'))) < (1,20,2):
   wait(p,log,'mob_effect',180);time.sleep(8)
   subprocess.run(['python3',str(helper/'x11-class-followup-102.py'),'click:640:350','sleep:2','click:500:195','sleep:1','click:400:595'],env=env,check=True,stdout=subprocess.DEVNULL);time.sleep(8)
   if 'Starting integrated' not in log.read_text(errors='replace'):subprocess.run(['python3',str(helper/'x11-class-followup-102.py'),'click:380:410'],env=env,check=True,stdout=subprocess.DEVNULL)
  # 26.x can ask to upgrade this copied fixture before opening it.
  # Record the prompt and use OCR on its fixed header before accepting it;
  # never apply this to an unrecognized screen or to a non-test world.
  if tuple(map(int,version.split('.'))) >= (26,1):
   end=time.monotonic()+600;last_probe=0;handled=False
   while 'MapSmokeTest joined the game' not in log.read_text(errors='replace'):
    if p.poll() is not None:raise RuntimeError('Client exited before local-world join')
    if time.monotonic()>=end:raise TimeoutError('MapSmokeTest joined the game')
    if not handled and time.monotonic()-last_probe>12:
     last_probe=time.monotonic();d=display.Display(':102');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);screen=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
     header=root/'upgrade-header.png';screen.crop((150,125,1130,195)).save(header)
     ocr=subprocess.run(['tesseract',str(header),'stdout','--psm','7'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=20).stdout.lower();header.unlink()
     if 'backup' in ocr and 'before upgrading this world' in ocr:
      screen.save(root/'world-upgrade-prompt.png');(root/'world-upgrade-ocr.txt').write_text(ocr)
      (root/'operator-note.txt').write_text('Automated OCR recognized the world-upgrade prompt on a copied local test world and selected the continue button; the original fixture was untouched. The screenshot and OCR output were retained before the click.\n')
      subprocess.run(['python3',str(helper/'x11-class-followup-102.py'),'click:860:438'],env=env,check=True,stdout=subprocess.DEVNULL);handled=True;print('Accepted recognized copied-world upgrade prompt for',version,flush=True)
    time.sleep(2)
  else:wait(p,log,'MapSmokeTest joined the game',360)
  hotbar()
  command('/fill -5 80 -73 15 80 -33 minecraft:stone','Successfully filled',log);command('/fill -5 81 -73 15 85 -33 minecraft:air','Successfully filled',log)
  command('/tp @s 5.5 81 -62.5','Teleported',log);command('/time set day',('Set minecraft:overworld to time marker minecraft:day','Clock minecraft:overworld is already at time marker minecraft:day') if tuple(map(int,version.split('.'))) >= (26,1) else 'Set the time to 1000',log);tap('F5');time.sleep(3)
  capture(root,'standing-day')
  d=display.Display(':102');r=d.screen().root;wins=game_windows(d);assert len(wins)==1;wins[0].set_input_focus(X.RevertToParent,X.CurrentTime);code=d.keysym_to_keycode(XK.string_to_keysym('w'));xtest.fake_input(d,X.KeyPress,code);d.sync()
  try:
   for i in range(1,3):time.sleep(.9);capture(root,'walking-'+str(i))
  finally:xtest.fake_input(d,X.KeyRelease,code);d.sync();d.close()
  time.sleep(1);capture(root,'after-walk')
  offset=log.stat().st_size;tap('Escape');subprocess.run(['python3',str(helper/'x11-class-followup-102.py'),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL)
  if version=='26.3':
   wait(p,log,'Saving worlds',120,offset);saved_worlds=log.read_text(errors='replace').index('Saving worlds',offset)
   wait(p,log,"Saving chunks for level 'ServerLevel[New World]'/minecraft:the_nether",120,saved_worlds)
  else:wait(p,log,'All dimensions are saved' if tuple(map(int,version.split('.'))) >= (1,21,5) else 'All chunks are saved',120,offset)
  time.sleep(5);request_close();p.wait(timeout=45);assert p.returncode==0
 playerdata=root/'saves/New World'/('players/data' if tuple(map(int,version.split('.'))) >= (26,1) else 'playerdata')/player
 end=[float(x) for x in nbtlib.load(playerdata)['Pos']];horizontal=math.hypot(end[0]-5.5,end[2]+62.5);print(version,'ending position',end,'horizontal distance',horizontal,flush=True);assert horizontal>.5
 assert not any(x in log.read_text(errors='replace') for x in ('MixinApplyError','InvalidInjectionException','NoSuchMethodError','MixinTransformerError'))
 (root/'movement.json').write_text(json.dumps({'minecraft':version,'start':[5.5,81,-62.5],'end':end,'horizontal_distance':horizontal,'renderer':'Linux Xorg/Mesa software','candidate_sha256':digest,'source_commit':source_sha,'note':'One short local walking scene; screenshots require visual inspection and do not establish full acceptance.'},indent=2)+'\n')
 shutil.copy2(playerdata,root/'ending-player.dat')
 shutil.rmtree(root/'saves');shutil.rmtree(private)
 for f in (root/'.fabric/remappedJars').glob('**/*-intermediary.jar'):f.unlink()
 for path in created:
  if path.exists() and path.parent==shared/'versions':shutil.rmtree(path)
 for path in tracked:
  if path.exists():path.unlink()
 print('Completed',version,flush=True)
print('All remaining short movement checks completed',flush=True)
