from pathlib import Path
from PIL import Image
from Xlib import X,XK,display
from Xlib.ext import xtest
import hashlib,json,os,shutil,subprocess,time,zipfile
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
install.install_jvm_runtime=lambda *args,**kwargs: None
launcher.install.install_minecraft_version('1.15',str(shared) if 'shared' in globals() else '/workspace/.minecraft-test')
launcher.fabric.install_fabric('1.15','/workspace/.minecraft-test',loader_version='0.20.1',java='/workspace/.toolchains/jre8/bin/java')
shared=Path('/workspace/.minecraft-test');fixture=Path('/workspace/.minecraft-test-114-patches/backups/2026-11-05_06-33-04_New World.zip');probe=Path('/workspace/.minecraft-test-review-mapid115-probe/mapid-probe.jar');java='/workspace/.toolchains/jre8/bin/java'
jars={'old': ('/workspace/tprm-legacy-1.15-1.16.5/build/libs/third-person-readable-maps-0.0.2-mc1.15-1.16.5.jar', 'd30a2a682699e881903275ce373d79374b1475e5dff10e7b3e66d364819b13de'), 'fixed': ('/workspace/tprm-legacy-1.15-1.16.5/build/libs/third-person-readable-maps-1.0.0-mc1.15-1.16.5.jar', '2f8b094db2de01569e42605870ef05a82880ffc72291796ded0a8dd518804eed')}
jars={k:(Path(v[0]),v[1]) for k,v in jars.items()}
env={**os.environ,'DISPLAY':':89','LIBGL_ALWAYS_SOFTWARE':'1','PYTHONPATH':'/workspace/.toolchains/python'}
def wait(p,log,needle,seconds,offset=0):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if needle in log.read_text(errors='replace')[offset:]:return
  if p.poll() is not None:raise RuntimeError('Client exited before '+needle)
  time.sleep(2)
 raise TimeoutError(needle)
def tap(name):
 d=display.Display(':89');r=d.screen().root
 try:
  wins=[w for w in r.query_tree().children if (w.get_wm_name() or '').startswith('Minecraft')];assert len(wins)==1;wins[0].set_input_focus(X.RevertToParent,X.CurrentTime);c=d.keysym_to_keycode(XK.string_to_keysym(name));xtest.fake_input(d,X.KeyPress,c);d.sync();time.sleep(.2);xtest.fake_input(d,X.KeyRelease,c);d.sync()
 finally:d.close()
def hotbar():
 end=time.monotonic()+180
 while time.monotonic()<end:
  d=display.Display(':89');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
  yellow=sum(1 for y in range(660,710) for x in range(368,911) if (lambda c:c[0]>180 and c[1]>180 and c[2]>100 and c[0]>c[2]*1.1)(im.getpixel((x,y))))
  gray=sum(1 for y in range(655,720) for x in range(365,915) if (lambda c:abs(c[0]-c[1])<3 and abs(c[1]-c[2])<3 and 50<c[0]<180)(im.getpixel((x,y))))
  if yellow>500 and gray>2000:return
  time.sleep(2)
 raise TimeoutError('visible hotbar')
for mode,(jar,digest) in jars.items():
 assert hashlib.sha256(jar.read_bytes()).hexdigest()==digest
 root=Path('/workspace/.minecraft-test-review-mapid115-'+mode);assert not root.exists();(root/'saves').mkdir(parents=True);(root/'mods').mkdir()
 with zipfile.ZipFile(fixture) as z:
  for x in z.infolist():
   q=Path(x.filename);assert not q.is_absolute() and '..' not in q.parts and q.parts[0]=='New World'
  z.extractall(root/'saves')
 options=Path('/workspace/.minecraft-test-left-early/options.txt').read_text().replace('mainHand:"left"','mainHand:left');(root/'options.txt').write_text(options)
 shutil.copy2(jar,root/'mods'/jar.name);shutil.copy2(probe,root/'mods'/probe.name)
 opts={'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','token':'0','executablePath':java,'jvmArguments':['-Xmx1300M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'gameDirectory':str(root),'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
 cmd=launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.15',str(shared),opts);log=root/'client.log';print('Launching',mode,'candidate',digest,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT);wait(p,log,'mob_effect',180);time.sleep(8)
  subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:350','sleep:2','click:500:195','sleep:1','click:400:595'],env=env,check=True,stdout=subprocess.DEVNULL);time.sleep(8)
  if 'Starting integrated' not in log.read_text(errors='replace'):subprocess.run(['python3',str(shared/'x11-89.py'),'click:380:410'],env=env,check=True,stdout=subprocess.DEVNULL)
  wait(p,log,'MapSmokeTest joined the game',360);hotbar();tap('2');time.sleep(5);tap('F5');wait(p,log,'TPRM_MAPID_PROBE case=',120);time.sleep(4)
  import re
  import re
  samples=[x for x in log.read_text(errors='replace').splitlines() if 'TPRM_MAPID_PROBE case=' in x];print(mode,'samples',samples[:18],flush=True)
  rows=[dict(re.findall(r'(case|lookup|data)=([a-z]+)',x)) for x in samples]
  assert {x['case'] for x in rows}=={'absent','empty','malformed','zero','nonzero','unavailable'}
  invalid=[x for x in rows if x['case'] in ('absent','empty','malformed')]
  if mode=='old':assert all(x['lookup']=='true' and x['data']=='true' for x in invalid)
  else:assert all(x['lookup']=='false' and x['data']=='false' for x in invalid)
  assert all(x['lookup']=='true' and x['data']=='true' for x in rows if x['case']=='zero')
  assert all(x['lookup']=='true' and x['data']=='false' for x in rows if x['case']=='unavailable')
  d=display.Display(':89');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save(root/'probe-scene.png');d.close()
  off=log.stat().st_size;tap('Escape');time.sleep(1);subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL);wait(p,log,'All chunks are saved',120,off);time.sleep(5);subprocess.run(['python3',str(shared/'x11-89.py'),'click:785:605'],env=env,check=True,stdout=subprocess.DEVNULL);p.wait(timeout=45);assert p.returncode==0
 for f in (root/'.fabric/remappedJars').glob('**/*-intermediary.jar'):f.unlink()
 print('Completed',mode,flush=True)
print('Both map identity probe runs completed',flush=True)
