"""Compiled/JVM regression cases for candidate nests and descriptor class use."""
import copy
import io
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import game_linkage as game
import jvm_linkage as jvm


def duplicate_class_attribute(data, desired):
    r=jvm.Reader(data);r.u4();r.u2();r.u2();count=r.u2();names={};i=1
    while i<count:
        tag=r.u1()
        if tag==1:names[i]=r.read(r.u2()).decode('utf-8')
        elif tag in (3,4):r.read(4)
        elif tag in (5,6):r.read(8);i+=1
        elif tag in (7,8,16,19,20):r.read(2)
        elif tag in (9,10,11,12,17,18):r.read(4)
        elif tag==15:r.read(3)
        else:raise AssertionError(tag)
        i+=1
    r.read(6);r.read(r.u2()*2)
    for _ in range(2):
        for _ in range(r.u2()):
            r.read(6)
            for _ in range(r.u2()):r.u2();r.read(r.u4())
    offset=r.buf.tell();number=r.u2();match=None
    for _ in range(number):
        start=r.buf.tell();index=r.u2();r.read(r.u4())
        if names[index]==desired:match=data[start:r.buf.tell()]
    assert match is not None and r.buf.tell()==len(data)
    return data[:offset]+struct.pack('>H',number+1)+data[offset+2:]+match


class NestAndDescriptorFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javac = shutil.which('javac'); cls.java = shutil.which('java')
        if not cls.javac or not cls.java: raise unittest.SkipTest('JDK required')

    def fixture(self, release='21'):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); src = root/'src/fixture'; src.mkdir(parents=True); out = root/'classes'; out.mkdir()
        java = src/'Nest.java'
        java.write_text('package fixture; public class Nest { private int value = 1; private static int global = 2; '
                        'private int secret() { return value; } '
                        'private int fromMember(B b) { return b.other; } '
                        'static class A { int run(Nest n, B b) { java.util.function.IntSupplier f=n::secret; '
                        'return n.value + global + f.getAsInt() + b.other; } } '
                        'static class B { private int other=3; } '
                        'public static void main(String[] a) { Nest n=new Nest(); '
                        'if (n.fromMember(new B()) + new A().run(n,new B()) != 10) throw new Error(); } }')
        subprocess.run([self.javac,'--release',release,'-d',str(out),str(java)],check=True,capture_output=True)
        nodes = {n['name']:n for n in (jvm.parse(p.read_bytes()) for p in out.rglob('*.class'))}
        return root, out, nodes

    @staticmethod
    def empty_game():
        buf=io.BytesIO()
        with ZipFile(buf,'w'): pass
        return ZipFile(io.BytesIO(buf.getvalue()))

    def test_compiled_nest_access_and_method_handle_execute(self):
        root,out,nodes=self.fixture()
        self.assertEqual(nodes['fixture/Nest$A']['nest_host'], 'fixture/Nest')
        self.assertEqual(set(nodes['fixture/Nest']['nest_members']), {'fixture/Nest$A','fixture/Nest$B'})
        private_uses=[(name,u) for name,node in nodes.items() for u in node['uses']
                      if u['owner'].startswith('fixture/Nest') and u['name'] in ('value','global','secret','other')]
        self.assertTrue(any(u['source_kind']=='method_handle' for _,u in private_uses))
        self.assertTrue(any(name=='fixture/Nest' and u['owner']=='fixture/Nest$B' for name,u in private_uses))
        self.assertTrue(any(name=='fixture/Nest$A' and u['owner']=='fixture/Nest$B' for name,u in private_uses))
        self.assertTrue(any(name=='fixture/Nest$A' and u['operation']=='getstatic' for name,u in private_uses))
        # The former caller==declaring-class rule rejected these legal accesses.
        self.assertTrue(any(name!=u['owner'] for name,u in private_uses))
        with self.empty_game() as archive: game.verify_game_instructions(nodes,{},archive,{},{},{},'fixture')
        run=subprocess.run([self.java,'-cp',str(out),'fixture.Nest'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_unrelated_missing_nonreciprocal_wrong_package_or_origin_rejected(self):
        _,_,nodes=self.fixture(); name='fixture/Nest$A'; caller=nodes[name]
        use=next(u for u in caller['uses'] if u['owner']=='fixture/Nest' and u['name']=='value')
        def tagged(items): return {n:dict(v,origin='candidate') for n,v in items.items()}
        good=tagged(nodes); self.assertEqual(jvm.validate_use(use,name,good.get),'fixture/Nest')
        unrelated=copy.deepcopy(good); unrelated[name]['nest_host']=None
        with self.assertRaisesRegex(ValueError,'private'): jvm.validate_use(use,name,unrelated.get)
        missing=copy.deepcopy(good); del missing['fixture/Nest']
        with self.assertRaisesRegex(ValueError,'missing class|nest'): jvm.validate_use(use,name,missing.get)
        nonreciprocal=copy.deepcopy(good);nonreciprocal['fixture/Nest']['nest_members'].remove(name)
        with self.assertRaisesRegex(ValueError,'nonreciprocal'): jvm.validate_use(use,name,nonreciprocal.get)
        wrong_package=copy.deepcopy(good);wrong_package[name]['nest_host']='other/Host'
        with self.assertRaisesRegex(ValueError,'different runtime package'): jvm.validate_use(use,name,wrong_package.get)
        wrong_origin=copy.deepcopy(good);wrong_origin[name]['origin']='game'
        with self.assertRaisesRegex(ValueError,'origin'): jvm.validate_use(use,name,wrong_origin.get)
        old=copy.deepcopy(good);old[name]['major']=52
        with self.assertRaisesRegex(ValueError,'private'): jvm.validate_use(use,name,old.get)

    def test_missing_attributes_and_duplicated_attribute_are_rejected(self):
        _,out,nodes=self.fixture();p=out/'fixture/Nest$A.class';raw=p.read_bytes()
        self.assertIn(b'NestHost',raw)
        changed=jvm.parse(raw.replace(b'NestHost',b'NestH0st',1));self.assertIsNone(changed['nest_host'])
        nodes[changed['name']]=changed
        with self.empty_game() as archive, self.assertRaisesRegex(ValueError,'private'):
            game.verify_game_instructions(nodes,{},archive,{},{},{},'fixture')
        # Replacing a host's attribute name leaves no reciprocal membership.
        host=(out/'fixture/Nest.class').read_bytes();self.assertIn(b'NestMembers',host)
        with self.assertRaisesRegex(ValueError,'duplicate'):
            jvm.parse(duplicate_class_attribute(host,'NestMembers'))
        with self.assertRaisesRegex(ValueError,'unsupported NestMembers'):
            jvm.parse(host[:6]+struct.pack('>H',52)+host[8:])
        parsed=jvm.parse(host.replace(b'NestMembers',b'NestMemberX',1));self.assertIsNone(parsed['nest_members'])
        nodes['fixture/Nest']=parsed;nodes['fixture/Nest$A']=jvm.parse(raw)
        with self.empty_game() as archive, self.assertRaisesRegex(ValueError,'nonreciprocal'):
            game.verify_game_instructions(nodes,{},archive,{},{},{},'fixture')

    def test_java8_compiler_accessors_do_not_use_nest_metadata(self):
        _,out,nodes=self.fixture('8')
        self.assertTrue(all(n['major']==52 and n['nest_host'] is None and n['nest_members'] is None for n in nodes.values()))
        with self.empty_game() as archive: game.verify_game_instructions(nodes,{},archive,{},{},{},'fixture')
        run=subprocess.run([self.java,'-cp',str(out),'fixture.Nest'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_nestmate_final_write_is_not_legal(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);src=root/'Nest.java';out=root/'out';out.mkdir()
        src.write_text('package fixture; public class Nest { private int value; static class Inner { '
                       'static void write(Nest n) { n.value=4; } } '
                       'public static void main(String[] a) { Inner.write(new Nest()); } }')
        subprocess.run([self.javac,'--release','21','-d',str(out),str(src)],check=True,capture_output=True)
        inner=(out/'fixture/Nest$Inner.class').read_bytes()
        src.write_text('package fixture; public class Nest { private final int value=1; static class Inner {} '
                       'public static void main(String[] a) { Inner.write(new Nest()); } }'.replace('Inner.write(new Nest());',''))
        subprocess.run([self.javac,'--release','21','-d',str(out),str(src)],check=True,capture_output=True)
        (out/'fixture/Nest$Inner.class').write_bytes(inner)
        nodes={n['name']:n for n in (jvm.parse(p.read_bytes()) for p in out.rglob('*.class'))}
        use=next(u for u in nodes['fixture/Nest$Inner']['uses'] if u['name']=='value')
        lookup={n:dict(v,origin='candidate') for n,v in nodes.items()}.get
        with self.assertRaisesRegex(ValueError,'final field write outside declaring class'):
            jvm.validate_use(use,'fixture/Nest$Inner',lookup)
        # A separately compiled driver exercises the old inner against the new final owner.
        driver=root/'Driver.java';driver.write_text('package fixture; public class Driver { '
              'public static void main(String[] a) throws Exception { Class<?> c=Class.forName("fixture.Nest$Inner"); '
              'java.lang.reflect.Method m=c.getDeclaredMethod("write",Nest.class); m.setAccessible(true); m.invoke(null,new Nest()); } }')
        subprocess.run([self.javac,'--release','21','-cp',str(out),'-d',str(out),str(driver)],check=True,capture_output=True)
        result=subprocess.run([self.java,'-cp',str(out),'fixture.Driver'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('IllegalAccessError',result.stderr)

    def test_mapped_mixin_uses_target_nest_not_original_nest(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        source=root/'Target.java';out=root/'classes';out.mkdir()
        source.write_text('package game; public class Target { static class Nested { private int value=7; } '
                          'int read(Nested n) { return n.value; } }')
        subprocess.run([self.javac,'--release','21','-d',str(out),str(source)],check=True,capture_output=True)
        target=jvm.parse((out/'game/Target.class').read_bytes())
        use=next(u for u in target['uses'] if u['owner']=='game/Target$Nested' and u['name']=='value')
        mixin=dict(target,name='fixture/Mixin',annotations={},uses=[dict(use,owner='net/minecraft/class_2')],
                   class_uses=[],classes=set(),dynamic_sites=[])
        mixin['members']=[]
        forward={'game/Target':'net/minecraft/class_1','game/Target$Nested':'net/minecraft/class_2'}
        reverse={v:k for k,v in forward.items()}
        jar=root/'game.jar'
        with ZipFile(jar,'w') as z:
            for p in (out/'game').glob('*.class'):z.write(p,'game/'+p.name)
        with ZipFile(jar) as archive:
            lookup=game.make_class_lookup({'fixture/Mixin':mixin},archive,forward,reverse,{},'fixture')
            self.assertEqual(lookup('net/minecraft/class_2')['nest_host'],'net/minecraft/class_1')
            game.verify_game_instructions({'fixture/Mixin':mixin},{'fixture/Mixin':'net/minecraft/class_1'},
                                          archive,forward,reverse,{},'fixture',class_lookup=lookup)
        _,_,original=self.fixture();one=original['fixture/Nest$A']
        private=next(u for u in one['uses'] if u['owner']=='fixture/Nest' and u['name']=='value')
        transformed=dict(one,uses=[private],class_uses=[],dynamic_sites=[])
        with ZipFile(jar) as archive, self.assertRaisesRegex(ValueError,'private'):
            game.verify_game_instructions({'fixture/Nest$A':transformed,'fixture/Nest':original['fixture/Nest']},
                {'fixture/Nest$A':'net/minecraft/class_1'},archive,forward,reverse,{},'fixture')

    def test_library_hidden_descriptor_and_real_class_access(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);lib=root/'src/org/joml';app=root/'src/app';lib.mkdir(parents=True);app.mkdir();out=root/'classes';out.mkdir()
        hidden=lib/'Hidden.java';api=lib/'Api.java';direct=app/'Direct.java';handle=app/'Handle.java';literal=app/'Literal.java';methodtype=app/'MethodTypeUse.java'
        hidden.write_text('package org.joml; public class Hidden {}')
        api.write_text('package org.joml; public class Api { public static Hidden value() { return null; } }')
        direct.write_text('package app; public class Direct { public static void main(String[] x) { Object a=org.joml.Api.value(); System.out.println(a); } }')
        handle.write_text('package app; public class Handle { public static void main(String[] x) { java.util.function.Supplier<Object> s=org.joml.Api::value; System.out.println(s.get()); } }')
        literal.write_text('package app; public class Literal { public static void main(String[] x) { System.out.println(org.joml.Hidden.class); } }')
        methodtype.write_text('package app; public class MethodTypeUse { public static void main(String[] x) { '
                              'java.util.function.Supplier<org.joml.Hidden> s=org.joml.Api::value; System.out.println(s.get()); } }')
        subprocess.run([self.javac,'--release','8','-d',str(out),str(hidden),str(api),str(direct),str(handle),str(literal),str(methodtype)],check=True,capture_output=True)
        hidden.write_text('package org.joml; class Hidden {}');subprocess.run([self.javac,'--release','8','-d',str(out),str(hidden)],check=True,capture_output=True)
        path=root/'library.jar'
        def archive(include_hidden):
            with ZipFile(path,'w') as z:
                z.write(out/'org/joml/Api.class','org/joml/Api.class')
                if include_hidden:z.write(out/'org/joml/Hidden.class','org/joml/Hidden.class')
        nodes={name:jvm.parse((out/('app/'+name+'.class')).read_bytes()) for name in ('Direct','Handle','Literal','MethodTypeUse')}
        self.assertIn({'name':'org/joml/Hidden','operation':'method_type_descriptor'},nodes['MethodTypeUse']['class_uses'])
        self.assertFalse(jvm.parse((out/'org/joml/Hidden.class').read_bytes())['access'] & 1)
        archive(True)
        with ZipFile(path) as libzip:
            game.verify_library_instructions({'app/Direct':nodes['Direct']},{},libzip,'org/joml/','fixture')
            for name in ('Handle','Literal','MethodTypeUse'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError,'inaccessible referenced class'):
                    game.verify_library_instructions({'app/'+name:nodes[name]},{},libzip,'org/joml/','fixture')
        for name,success in [('Direct',True),('Handle',False),('Literal',False),('MethodTypeUse',False)]:
            run=subprocess.run([self.java,'-cp',str(out),'app.'+name],capture_output=True,text=True)
            self.assertEqual(run.returncode==0,success,run.stderr)
            if not success:self.assertIn('IllegalAccessError',run.stderr)
        archive(False)
        with ZipFile(path) as libzip, self.assertRaisesRegex(ValueError,'missing dependency class'):
            game.verify_library_instructions({'app/Direct':nodes['Direct']},{},libzip,'org/joml/','fixture')

    def test_candidate_owned_class_literal_access_is_checked(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);a=root/'src/app';b=root/'src/other';a.mkdir(parents=True);b.mkdir();out=root/'classes';out.mkdir()
        hidden=a/'Hidden.java';caller=b/'Caller.java';hidden.write_text('package app; public class Hidden {}')
        caller.write_text('package other; public class Caller { public static void main(String[] a) { System.out.println(app.Hidden.class); } }')
        subprocess.run([self.javac,'--release','8','-d',str(out),str(hidden),str(caller)],check=True,capture_output=True)
        hidden.write_text('package app; class Hidden {}');subprocess.run([self.javac,'--release','8','-d',str(out),str(hidden)],check=True,capture_output=True)
        nodes={n['name']:n for n in (jvm.parse(p.read_bytes()) for p in out.rglob('*.class'))}
        with self.empty_game() as archive, self.assertRaisesRegex(ValueError,'inaccessible referenced class'):
            game.verify_game_instructions(nodes,{},archive,{},{},{},'fixture')
        run=subprocess.run([self.java,'-cp',str(out),'other.Caller'],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0);self.assertIn('IllegalAccessError',run.stderr)


if __name__=='__main__': unittest.main()
