from pathlib import Path
import atexit, hashlib, json, os, shutil, subprocess, time
import minecraft_launcher_lib as launcher
import minecraft_launcher_lib.install as install
from Xlib import X, XK, display
from Xlib.ext import xtest
from PIL import Image

workspace = Path('/workspace')
root = workspace / '.minecraft-test-foreground-1214-candidate'
fixture = workspace / '.minecraft-test-left-baseline-1.21.3'
shared = workspace / '.minecraft-test-control-shared'
helper = workspace / '.minecraft-test/x11.py'
java = '/usr/lib/jvm/java-21-openjdk-amd64/bin/java'
env = {**os.environ, 'DISPLAY': ':88', 'LIBGL_ALWAYS_SOFTWARE': '1',
       'PYTHONPATH': '/workspace/.toolchains/python'}
install.install_jvm_runtime = lambda *args, **kwargs: None
assert not root.exists()
(root / 'saves').mkdir(parents=True)
(root / 'mods').mkdir()
shutil.copytree(fixture / 'saves/New World', root / 'saves/New World')
shutil.copy2(fixture / 'options.txt', root / 'options.txt')
jar=workspace/'tprm-legacy-1.21.4-1.21.8/build/libs/third-person-readable-maps-0.0.2-mc1.21.4-1.21.8.jar'
digest='26a28fb550132d07af415c41ccb82982937906ab991ad810406d2937b5e4e776'
assert hashlib.sha256(jar.read_bytes()).hexdigest()==digest
shutil.copy2(jar,root/'mods'/jar.name)
launcher.install.install_minecraft_version('1.21.4', str(shared))
launcher.fabric.install_fabric('1.21.4', str(shared), loader_version='0.20.1', java=java)
opts = {'username': 'MapSmokeTest', 'uuid': 'f36d949a12db4676bc41a7b7fe97fd55',
        'token': '0', 'executablePath': java, 'jvmArguments': ['-Xmx1200M',
        '-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts'],
        'gameDirectory': str(root), 'customResolution': True,
        'resolutionWidth': '1280', 'resolutionHeight': '720',
        'quickPlaySingleplayer': 'New World'}
cmd = launcher.command.get_minecraft_command('fabric-loader-0.20.1-1.21.4', str(shared), opts)
log = root / 'client.log'
process = None
def cleanup():
    if process and process.poll() is None:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
atexit.register(cleanup)
def wait(needle, seconds=180, offset=0):
    end = time.monotonic()+seconds
    while time.monotonic() < end:
        if needle in log.read_text(errors='replace')[offset:]: return
        if process.poll() is not None: raise RuntimeError('Client exited before '+needle)
        time.sleep(1)
    raise TimeoutError(needle)
def key(name, down):
    d=display.Display(':88'); windows=[w for w in d.screen().root.query_tree().children if (w.get_wm_name() or '').startswith('Minecraft')]
    assert len(windows)==1
    windows[0].set_input_focus(X.RevertToParent,X.CurrentTime)
    xtest.fake_input(d, X.KeyPress if down else X.KeyRelease, d.keysym_to_keycode(XK.string_to_keysym(name)))
    d.sync(); d.close()
def tap(name):
    key(name,True); time.sleep(.2); key(name,False); time.sleep(.8)
def capture(name):
    d=display.Display(':88'); r=d.screen().root; g=r.get_geometry(); raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff)
    Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX').save(root/(name+'.png')); d.close()
    print('Captured',name,flush=True)
def command(text,expected):
    off=log.stat().st_size; tap('t')
    subprocess.run(['python3',str(helper),'type:'+text],env=env,check=True,stdout=subprocess.DEVNULL); tap('Return')
    wait(expected,30,off)
def walking(prefix):
    time.sleep(3); capture(prefix+'-standing'); key('w',True)
    try:
        for i in (1,2): time.sleep(.9); capture(prefix+'-walking-'+str(i))
    finally: key('w',False)
with log.open('w') as out:
    process=subprocess.Popen(cmd,env=env,stdout=out,stderr=subprocess.STDOUT)
    wait('MapSmokeTest joined the game',360); time.sleep(15)
    command('/fill -5 80 -73 15 80 -33 minecraft:stone','Successfully filled')
    command('/fill -5 81 -73 15 85 -33 minecraft:air','Successfully filled')
    command('/tp @s 5.5 81 -62.5','Teleported')
    command('/time set day','Set the time to 1000')
    tap('F5'); walking('original-clearance')
    command('/fill -5 86 -73 15 95 -33 minecraft:air','Successfully filled')
    command('/tp @s 5.5 81 -62.5','Teleported')
    walking('extra-clearance')
    off=log.stat().st_size; tap('Escape')
    subprocess.run(['python3',str(helper),'click:640:520'],env=env,check=True,stdout=subprocess.DEVNULL)
    wait('All chunks are saved',120,off); time.sleep(5)
    subprocess.run(['python3',str(helper),'click:785:605'],env=env,check=True,stdout=subprocess.DEVNULL)
    process.wait(timeout=45); assert process.returncode==0
assert len(list((root/'mods').glob('*.jar')))==1
assert 'thirdpersonreadablemaps' in log.read_text(errors='replace')
(root/'result.json').write_text(json.dumps({'version':'1.21.4','fabric_loader':'0.20.1','candidate_sha256':digest,
    'source_fixture':str(fixture),'renderer':'Linux Xorg/Mesa software',
    'original_clearance':'y 81-85','extra_clearance':'y 81-95','exit_code':process.returncode},indent=2)+'\n')
print('Candidate repeat completed',flush=True)
