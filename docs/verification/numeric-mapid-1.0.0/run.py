from pathlib import Path
from PIL import Image
from Xlib import X,XK,display
from Xlib.ext import xtest
import hashlib,json,os,shutil,subprocess,time,zipfile
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
install.install_jvm_runtime=lambda *args,**kwargs: None
launcher.install.install_minecraft_version('1.19.4',str(shared) if 'shared' in globals() else '/workspace/.minecraft-test')
launcher.fabric.install_fabric('1.19.4','/workspace/.minecraft-test',loader_version='0.20.1',java='/workspace/.toolchains/jdk17/bin/java')
shared=Path('/workspace/.minecraft-test');fixture=Path('/workspace/.minecraft-test-left-java17-baseline-1.19.4');probe=Path('/workspace/.minecraft-test-numeric-probe-1.19.4/mapid-probe.jar');java='/workspace/.toolchains/jdk17/bin/java'
jars={'old': ('/workspace/.tprm-dryrun/100/rehearsal/artifacts/1.19.4-1.20.4/third-person-readable-maps-1.0.0-mc1.19.4-1.20.4.jar', 'dfe2940c28a80b051856efbd1c86eec99ff7c1031426ab62ebcfc7f26efdd29a'), 'fixed': ('/workspace/tprm-legacy-1.19.4-1.20.4/build/libs/third-person-readable-maps-1.0.0-mc1.19.4-1.20.4.jar', 'c2fc1583487f5e1d4e6e82494582951aee055e45664583fbe1c6c88605601a2c')}
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
 root=Path('/workspace/.minecraft-test-numeric-1.19.4-'+mode);assert not root.exists();(root/'saves').mkdir(parents=True);(root/'mods').mkdir()
 shutil.copytree(fixture/'saves/New World',root/'saves/New World')
 shutil.copy2(fixture/'options.txt',root/'options.txt')
 shutil.copy2(jar,root/'mods'/jar.name);shutil.copy2(probe,root/'mods'/probe.name)
 opts={'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','token':'0','executablePath':java,'jvmArguments':['-Xmx1300M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'gameDirectory':str(root),'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
 cmd=launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.19.4',str(shared),opts);log=root/'client.log';print('Launching',mode,'candidate',digest,flush=True)
 with log.open('w') as out:
  p=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT);wait(p,log,'mob_effect',180);time.sleep(8)
  subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:350','sleep:2','click:500:195','sleep:1','click:400:595'],env=env,check=True,stdout=subprocess.DEVNULL);time.sleep(8)
  if 'Starting integrated' not in log.read_text(errors='replace'):subprocess.run(['python3',str(shared/'x11-89.py'),'click:380:410'],env=env,check=True,stdout=subprocess.DEVNULL)
  wait(p,log,'MapSmokeTest joined the game',360);hotbar();tap('2');time.sleep(5);tap('F5');wait(p,log,'TPRM_MAPID_PROBE case=',120);time.sleep(4)
  import re
  import re
  end=time.monotonic()+90
  while time.monotonic()<end:
   samples=[x for x in log.read_text(errors='replace').splitlines() if 'TPRM_MAPID_PROBE case=' in x]
   if len(samples)>=30:break
   time.sleep(1)
  print(mode,'samples',samples[:30],flush=True)
  rows=[dict(re.findall(r'(case|lookup|data)=([a-z]+)',x)) for x in samples[:30]]
  assert len(rows)==30 and {x['case'] for x in rows}=={'absent','empty','text','fraction','overflow','nan','zero','shortzero','nonzero','unavailable'}
  for case in ('absent','empty','text'):
   assert all(x['lookup']==('true' if mode=='old' else 'false') and x['data']=='false' for x in rows if x['case']==case)
  for case in ('fraction','overflow','nan'):
   assert all(x['lookup']==('true' if mode=='old' else 'false') and x['data']==('true' if mode=='old' else 'false') for x in rows if x['case']==case)
  for case in ('zero','shortzero','nonzero'):
   assert all(x['lookup']=='true' and x['data']=='true' for x in rows if x['case']==case)
  assert all(x['lookup']=='true' and x['data']=='false' for x in rows if x['case']=='unavailable')
  d=display.Display(':89');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save(root/'probe-scene.png');d.close()
  off=log.stat().st_size;tap('Escape');time.sleep(1);subprocess.run(['python3',str(shared/'x11-89.py'),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL);wait(p,log,'All chunks are saved',120,off);time.sleep(5);subprocess.run(['python3',str(shared/'x11-89.py'),'click:785:605'],env=env,check=True,stdout=subprocess.DEVNULL);p.wait(timeout=45);assert p.returncode==0
 shutil.rmtree(root/'saves')
 for f in (root/'.fabric/remappedJars').glob('**/*-intermediary.jar'):f.unlink()
 print('Completed',mode,flush=True)
print('Both map identity probe runs completed',flush=True)
