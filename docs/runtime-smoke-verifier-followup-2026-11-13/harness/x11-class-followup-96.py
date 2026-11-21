from Xlib import X, XK, display
from Xlib.ext import xtest
from PIL import Image
import sys,time

d=display.Display(':96');root=d.screen().root
for win in root.query_tree().children:
    name=win.get_wm_name()
    if not name:
        prop=win.get_full_property(d.intern_atom('_NET_WM_NAME'),0)
        name=prop.value if prop else ''
    if isinstance(name,bytes):name=name.decode('utf-8','replace')
    geometry=win.get_geometry()
    if name.startswith('Minecraft') and geometry.width>=640 and geometry.height>=480:
        win.set_input_focus(X.RevertToParent, X.CurrentTime)
d.sync()
for arg in sys.argv[1:]:
    if arg.startswith('click:'):
        x,y=map(int,arg.split(':')[1:]);xtest.fake_input(d,X.MotionNotify,x=x,y=y);xtest.fake_input(d,X.ButtonPress,1);xtest.fake_input(d,X.ButtonRelease,1)
    elif arg.startswith('move:'):
        x,y=map(int,arg.split(':')[1:]);xtest.fake_input(d,X.MotionNotify,x=x,y=y)
    elif arg == 'right':
        xtest.fake_input(d,X.ButtonPress,3);d.sync();time.sleep(0.3);xtest.fake_input(d,X.ButtonRelease,3)
    elif arg.startswith('key:'):
        key=arg[4:];code=d.keysym_to_keycode(XK.string_to_keysym(key));xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code)
    elif arg.startswith('type:'):
        for char in arg[5:]:
            shift=char.isupper() or char in '_:+{}[]!@#$%^&*()<>?"'
            keys={'_':'minus',':':'semicolon','+':'equal','{':'bracketleft','}':'bracketright','[':'bracketleft',']':'bracketright',' ':'space','/':'slash','.':'period','-':'minus','=':'equal',',':'comma','@':'2'}
            name=keys.get(char,char.lower());code=d.keysym_to_keycode(XK.string_to_keysym(name));sc=d.keysym_to_keycode(XK.string_to_keysym('Shift_L'))
            if shift:xtest.fake_input(d,X.KeyPress,sc)
            xtest.fake_input(d,X.KeyPress,code);xtest.fake_input(d,X.KeyRelease,code)
            if shift:xtest.fake_input(d,X.KeyRelease,sc)
            d.sync();time.sleep(0.035)
    elif arg.startswith('sleep:'):
        d.sync();time.sleep(float(arg[6:]))
    elif arg.startswith('screen:'):
        d.sync();w=root.get_geometry().width;h=root.get_geometry().height
        im=root.get_image(0,0,w,h,X.ZPixmap,0xffffffff)
        Image.frombytes('RGB',(w,h),im.data,'raw','BGRX').save(arg[7:])
    d.sync()
