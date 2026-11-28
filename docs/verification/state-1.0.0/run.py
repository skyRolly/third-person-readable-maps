from pathlib import Path
from PIL import Image
from Xlib import X,XK,display
from Xlib.ext import xtest
import hashlib,json,os,shutil,subprocess,time,zipfile
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
install.install_jvm_runtime=lambda *args,**kwargs: None
launcher.install.install_minecraft_version('1.14',str(shared) if 'shared' in globals() else '/workspace/.minecraft-test')
launcher.fabric.install_fabric('1.14','/workspace/.minecraft-test',loader_version='0.20.1',java='/workspace/.toolchains/jre8/bin/java')
shared=Path('/workspace/.minecraft-test');fixture=Path('/workspace/.minecraft-test-114-patches/backups/2026-11-05_06-33-04_New World.zip');probe=Path('/workspace/.minecraft-test-review-state-probe/state-probe.jar');java='/workspace/.toolchains/jre8/bin/java'
jars={'old': ('/workspace/tprm-legacy-1.14/build/libs/third-person-readable-maps-0.0.2-mc1.14-1.14.4.jar', '839f0982d11c0a0f95199e1486f7ece203acb7fe8f3e2dd309e9edec214ce5a5'), 'fixed': ('/workspace/tprm-legacy-1.14/build/libs/third-person-readable-maps-1.0.0-mc1.14-1.14.4.jar', '5770c22a021f1c2fd74a80444fe759701f70c82a65fa03e9fd5e90154e701423')}
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
 root=Path('/workspace/.minecraft-test-review-state-'+mode);assert not root.exists();(root/'saves').mkdir(parents=True);(root/'mods').mkdir()
 with zipfile.ZipFile(fixture) as z:
  for x in z.infolist():
   q=Path(x.filename);assert not q.is_absolute() and '..' not in q.parts and q.parts[0]=='New World'
  z.extractall(root/'saves')
 options=Path('/workspace/.minecraft-test-left-early/options.txt').read_text().replace('mainHand:"left"','mainHand:left');(root/'options.txt').write_text(options)
 shutil.copy2(jar,root/'mods'/jar.name);shutil.copy2(probe,root/'mods'/probe.name)
 opts={'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','token':'0','executablePath':java,'jvmArguments':['-Xmx1300M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'gameDirectory':str(root),'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
 cmd=launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.14',str(shared),opts);log=root/'client.log';print('Launching',mode,'candidate',digest,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT);wait(p,log,'mob_effect',180);time.sleep(8)
  subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:350','sleep:2','click:500:195','sleep:1','click:400:595'],env=env,check=True,stdout=subprocess.DEVNULL);time.sleep(8)
  if 'Starting integrated' not in log.read_text(errors='replace'):subprocess.run(['python3',str(shared/'x11-89.py'),'click:380:410'],env=env,check=True,stdout=subprocess.DEVNULL)
  wait(p,log,'MapSmokeTest joined the game',360);hotbar();tap('F5');wait(p,log,'TPRM_STATE_PROBE sample=',120);time.sleep(4)
  import re
  samples=[x for x in log.read_text(errors='replace').splitlines() if 'TPRM_STATE_PROBE sample=' in x];print(mode,'samples',samples[:8],flush=True)
  rows=[dict(re.findall(r'(expected_unit|actual_unit|expected_binding|actual_binding|expected_lighting|actual_lighting)=([0-9]+|true|false)',x)) for x in samples]
  assert len(rows)>=2 and all(x['expected_unit']==x['actual_unit'] and x['expected_lighting']==x['actual_lighting'] for x in rows)
  assert {x['expected_lighting'] for x in rows}=={'true','false'}
  if mode=='old':assert any(x['expected_binding']!=x['actual_binding'] for x in rows)
  else:assert all(x['expected_binding']==x['actual_binding'] for x in rows)
  d=display.Display(':89');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save(root/'probe-scene.png');d.close()
  off=log.stat().st_size;tap('Escape');time.sleep(1);subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL);wait(p,log,'All chunks are saved',120,off);time.sleep(5);subprocess.run(['python3',str(shared/'x11-89.py'),'click:785:605'],env=env,check=True,stdout=subprocess.DEVNULL);p.wait(timeout=45);assert p.returncode==0
 for f in (root/'.fabric/remappedJars').glob('**/*-intermediary.jar'):f.unlink()
 print('Completed',mode,flush=True)
print('Both texture and lighting probe runs completed',flush=True)
