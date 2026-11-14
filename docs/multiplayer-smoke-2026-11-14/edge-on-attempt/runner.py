"""Controlled two-client LAN smoke of the exact proposed 1.21.11 JAR."""
from pathlib import Path
from PIL import Image
from Xlib import X,display
import atexit,hashlib,json,os,re,shutil,subprocess,time,uuid
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install

shared=Path('/workspace/.minecraft-test');workspace=Path('/workspace');root=workspace/'.minecraft-test-multiplayer-1.21.11-20261114';fixture=workspace/'.minecraft-test-left-baseline-1.21.10';builds=json.loads((workspace/'tprm-legacy-coordination/docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups'];build=builds['1.21.11'];jar=workspace/'.tprm-dryrun/class-linkage-builds/1.21.11'/build['artifact'];java='/usr/lib/jvm/java-21-openjdk-amd64/bin/java';assert hashlib.sha256(jar.read_bytes()).hexdigest()==build['sha256'];assert not root.exists();root.mkdir();active=[]
install.install_jvm_runtime=lambda *args,**kwargs:None
baseenv={**os.environ,'LIBGL_ALWAYS_SOFTWARE':'1','PYTHONPATH':'/workspace/.toolchains/python'}

def cleanup():
 for proc in active:
  if proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
atexit.register(cleanup)

def env(display_name):return {**baseenv,'DISPLAY':display_name}
def wait_for(path,needle,seconds,proc=None,offset=0):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  text=path.read_text(errors='replace')[offset:] if path.exists() else ''
  if needle in text:return text
  if proc and proc.poll() is not None:raise RuntimeError('Client exited before '+needle)
  time.sleep(2)
 raise TimeoutError(needle)
def helper(display_number,*args):
 subprocess.run(['python3',str(shared/('x11-multiplayer-'+str(display_number)+'.py')),*args],env=env(':'+str(display_number)),check=True,stdout=subprocess.DEVNULL)
def tap(display_number,key):helper(display_number,'key:'+key);time.sleep(.9)
def chat(display_number,log,text,expect,timeout=60):
 offset=log.stat().st_size;tap(display_number,'t');helper(display_number,'type:'+text);tap(display_number,'Return');wait_for(log,expect,timeout,offset=offset);print('Confirmed command',text,flush=True)
def hotbar(display_number):
 end=time.monotonic()+180
 while time.monotonic()<end:
  d=display.Display(':'+str(display_number));r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
  gray=sum(1 for y in range(655,720) for x in range(365,915) if (lambda c:abs(c[0]-c[1])<3 and abs(c[1]-c[2])<3 and 50<c[0]<180)(im.getpixel((x,y))))
  if gray>1800:return
  time.sleep(3)
 raise TimeoutError('visible in-world hotbar')
def capture(display_number,name):
 d=display.Display(':'+str(display_number));r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save(root/(name+'.png'));d.close();print('Captured',name,flush=True)

print('Installing cached launcher inputs',flush=True);launcher.install.install_minecraft_version('1.21.11',str(shared));launcher.fabric.install_fabric('1.21.11',str(shared),loader_version='0.20.1',java=java)
for role in ('host','observer'):
 d=root/role;(d/'mods').mkdir(parents=True);shutil.copy2(jar,d/'mods'/jar.name);shutil.copy2(fixture/'options.txt',d/'options.txt')
(root/'host/saves').mkdir();shutil.copytree(fixture/'saves/New World',root/'host/saves/New World')
common={'token':'0','executablePath':java,'jvmArguments':['-Xmx1000M','-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],'customResolution':True,'resolutionWidth':'1280','resolutionHeight':'720'}
hostopts={**common,'username':'MapSmokeTest','uuid':'f36d949a12db4676bc41a7b7fe97fd55','gameDirectory':str(root/'host'),'quickPlaySingleplayer':'New World'}
hostlog=root/'host.log';hf=hostlog.open('w');host=subprocess.Popen(launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.21.11',str(shared),hostopts),env=env(':110'),stdout=hf,stderr=subprocess.STDOUT);active.append(host);print('Started host',flush=True)
wait_for(hostlog,'MapSmokeTest joined the game',420,host);hotbar(110)
chat(110,hostlog,'/fill -5 80 -73 15 80 -33 minecraft:stone','Successfully filled')
chat(110,hostlog,'/fill -5 81 -73 15 85 -33 minecraft:air','Successfully filled')
chat(110,hostlog,'/time set day','Set the time to 1000')
offset=hostlog.stat().st_size;tap(110,'t');helper(110,'type:/publish');tap(110,'Return')
end=time.monotonic()+120;port=None
while time.monotonic()<end:
 text=hostlog.read_text(errors='replace')[offset:]
 match=re.search(r'(?i)(?:hosted on port|port)\s+\[?(\d{4,5})\]?',text)
 if match:port=int(match.group(1));break
 if host.poll() is not None:raise RuntimeError('Host exited while publishing LAN')
 time.sleep(2)
if port is None:raise TimeoutError('LAN port confirmation')
print('Published local test LAN port',port,flush=True)
obsopts={**common,'username':'MapObserver','uuid':uuid.uuid5(uuid.NAMESPACE_DNS,'tprm-local-map-observer').hex,'gameDirectory':str(root/'observer'),'server':'127.0.0.1','port':str(port)}
obslog=root/'observer.log';of=obslog.open('w');observer=subprocess.Popen(launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.21.11',str(shared),obsopts),env=env(':111'),stdout=of,stderr=subprocess.STDOUT);active.append(observer);print('Started observer',flush=True)
wait_for(hostlog,'MapObserver joined the game',420,host);hotbar(111)
chat(110,hostlog,'/tp MapSmokeTest 5.5 81 -62.5 180 0','Teleported')
chat(110,hostlog,'/tp MapObserver 5.5 81 -67.5 0 0','Teleported')
time.sleep(12);capture(111,'observer-before-map');capture(110,'host-held-map')
chat(110,hostlog,'/give MapObserver minecraft:filled_map[minecraft:map_id=2]','Gave')
time.sleep(18);tap(111,'2');time.sleep(5);capture(111,'observer-after-map')
for name,path in (('host',hostlog),('observer',obslog)):
 text=path.read_text(errors='replace');assert 'thirdpersonreadablemaps 1.0.0' in text,(name,'mod missing')
 assert not any(e in text for e in ('MixinApplyError','InvalidInjectionException','NoSuchMethodError','MixinTransformerError'))
result={'minecraft':'1.21.11','mode':'local two-client LAN, integrated server','source_commit':build['source_commit'],'artifact_sha256':build['sha256'],'host':'MapSmokeTest','observer':'MapObserver','local_port':port,'renderer':'Linux Xorg/Mesa software','events':['host joined copied world','observer joined LAN','observer photographed remote map before and after receiving map ID 2'],'limitation':'The observer client map-data cache was not instrumented; screenshots alone do not establish natural data absence or full multiplayer acceptance. Clients were terminated after capture.'}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('MULTIPLAYER CAPTURE COMPLETE',flush=True)
