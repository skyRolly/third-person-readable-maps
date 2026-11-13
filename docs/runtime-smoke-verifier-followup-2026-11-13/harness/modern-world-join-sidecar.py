"""Confirm a recognized post-upgrade join prompt in disposable test worlds."""
from pathlib import Path
from PIL import Image
from Xlib import X, display
from difflib import SequenceMatcher
import os,re,subprocess,time
shared=Path('/workspace/.minecraft-test');runner=shared/'class-followup-walking-modern-prompt-retry.log'
while True:
    text=runner.read_text(errors='replace') if runner.exists() else ''
    if 'All remaining short movement checks completed' in text or 'Traceback (most recent call last)' in text:
        print('Main runner ended',flush=True);break
    launches=re.findall(r'^Launching (26\.[0-9.]+) ',text,re.M)
    if not launches:
        time.sleep(5);continue
    version=launches[-1];root=Path('/workspace/.minecraft-test-class-followup-walk-'+version);log=root/'client.log';s=log.read_text(errors='replace') if log.exists() else ''
    capture=root/'world-upgrade-completed-prompt.png'
    if 'Upgrade done for world' not in s or 'MapSmokeTest joined the game' in s or capture.exists():
        time.sleep(5);continue
    d=display.Display(':102');r=d.screen().root;g=r.get_geometry();raw=r.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff);screen=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX');d.close()
    header=root/'completed-prompt-header.png';screen.crop((250,235,1030,340)).save(header)
    try:ocr=subprocess.run(['tesseract',str(header),'stdout','--psm','6'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,timeout=20).stdout.lower()
    finally:header.unlink(missing_ok=True)
    lines=[''.join(c for c in line if c.isalpha()) for line in ocr.splitlines()]
    score=lambda target:max((SequenceMatcher(None,target,line).ratio() for line in lines),default=0)
    if score('upgradingworldcompleted') >= .8 and score('doyouwanttojointheworldnow') >= .8:
        screen.save(capture);(root/'world-upgrade-completed-ocr.txt').write_text(ocr)
        with (root/'operator-note.txt').open('a') as note:note.write('An OCR sidecar recognized the completed-upgrade join prompt on the copied test world and selected Yes; the screenshot and OCR output were retained.\n')
        env={**os.environ,'DISPLAY':':102','PYTHONPATH':'/workspace/.toolchains/python'}
        subprocess.run(['python3',str(shared/'x11-class-followup-102.py'),'click:408:435'],env=env,check=True,stdout=subprocess.DEVNULL)
        print('Confirmed recognized completed-upgrade prompt for',version,flush=True)
    time.sleep(5)
