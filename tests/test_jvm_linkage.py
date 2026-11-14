import shutil
import struct
import hashlib
import io
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import jvm_linkage as linkage
import game_linkage


class ClassFileFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javac = shutil.which('javac')
        if not cls.javac:
            raise unittest.SkipTest('javac is required for bytecode fixtures')

    def compile_case(self, original_api, caller, replacement_api=None, release='8'):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); src = root/'src'/'fixture'; src.mkdir(parents=True)
        (src/'Api.java').write_text('package fixture; ' + original_api)
        (src/'Caller.java').write_text('package fixture; ' + caller)
        initial = root/'initial'; initial.mkdir()
        subprocess.run([self.javac, '--release', release, '-d', str(initial),
                        str(src/'Api.java'), str(src/'Caller.java')], check=True, capture_output=True)
        if replacement_api is not None:
            (src/'Api.java').write_text('package fixture; ' + replacement_api)
            subprocess.run([self.javac, '--release', release, '-d', str(initial),
                            str(src/'Api.java')], check=True, capture_output=True)
        nodes = {}
        for p in initial.rglob('*.class'):
            node = linkage.parse(p.read_bytes()); nodes[node['name']] = node
        nodes['java/lang/Object'] = {'name': 'java/lang/Object', 'super': None, 'interfaces': [],
                                     'access': 1, 'members': [{'kind':'method','name':'<init>',
                                                               'descriptor':'()V','access':1}]}
        caller_node = nodes['fixture/Caller']
        uses = [u for u in caller_node['uses'] if u['owner'] == 'fixture/Api']
        self.assertTrue(uses)
        return nodes, uses

    def test_static_instance_method_changes_are_rejected(self):
        cases = [
            ('public class Api { public static void run() {} }',
             'public class Caller { void call() { Api.run(); } }',
             'public class Api { public void run() {} }'),
            ('public class Api { public void run() {} }',
             'public class Caller { void call(Api a) { a.run(); } }',
             'public class Api { public static void run() {} }')]
        for before, caller, after in cases:
            with self.subTest(before=before):
                nodes, uses = self.compile_case(before, caller, after)
                # The previous name/descriptor-only check would accept this.
                self.assertIsNotNone(linkage.resolve_member('fixture/Api', 'method', 'run', '()V', nodes.get))
                with self.assertRaisesRegex(ValueError, 'static/instance mismatch'):
                    linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)

    def test_field_staticness_and_accessibility(self):
        nodes, uses = self.compile_case('public class Api { public static int value; }',
                                        'public class Caller { int call() { return Api.value; } }',
                                        'public class Api { public int value; }')
        with self.assertRaisesRegex(ValueError, 'static/instance mismatch'):
            linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)
        nodes, uses = self.compile_case('public class Api { public void run() {} }',
                                        'public class Caller { void call(Api a) { a.run(); } }',
                                        'public class Api { private void run() {} }')
        with self.assertRaisesRegex(ValueError, 'private'):
            linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)

    def test_final_field_changes_fail_in_verifier_and_jvm(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); src = root/'fixture'; src.mkdir()
        api, caller = src/'Api.java', src/'Caller.java'
        api.write_text('package fixture; public class Api { public int value; public static int global; }')
        caller.write_text('package fixture; public class Caller { public static void main(String[] a) { '
                          'if (a[0].equals("instance")) new Api().value = 3; else Api.global = 4; } }')
        subprocess.run([self.javac, '--release', '8', '-d', str(root), str(api), str(caller)],
                       check=True, capture_output=True)
        api.write_text('package fixture; public class Api { public final int value = 1; '
                       'public static final int global = Integer.parseInt("2"); }')
        subprocess.run([self.javac, '--release', '8', '-d', str(root), str(api)],
                       check=True, capture_output=True)
        nodes = {}
        for p in root.rglob('*.class'):
            node = linkage.parse(p.read_bytes()); nodes[node['name']] = node
        uses = [u for u in nodes['fixture/Caller']['uses'] if u['owner'] == 'fixture/Api'
                and u['operation'] in ('putfield', 'putstatic')]
        self.assertEqual({u['operation'] for u in uses}, {'putfield', 'putstatic'})
        for use in uses:
            self.assertIsNotNone(linkage.resolve_member(use['owner'], 'field', use['name'],
                                                        use['descriptor'], nodes.get))
            self.assertEqual(use['source_kind'], 'instruction')
            self.assertEqual(use['enclosing_method'], 'main')
            with self.assertRaisesRegex(ValueError, 'final field write outside declaring class'):
                linkage.validate_use(use, 'fixture/Caller', nodes.get)
        java = shutil.which('java')
        if java:
            for arg in ('instance', 'static'):
                run = subprocess.run([java, '-cp', str(root), 'fixture.Caller', arg], capture_output=True, text=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertIn('IllegalAccessError', run.stderr)

    def test_final_initializers_reads_and_mixin_caller_context(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); src = root/'Api.java'
        src.write_text('package fixture; public class Api { public final int value; '
                       'public static final int global; public Api() { value = 1; } '
                       'static { global = Integer.parseInt("2"); } '
                       'int read() { return value + global; } }')
        subprocess.run([self.javac, '--release', '8', '-d', str(root), str(src)],
                       check=True, capture_output=True)
        node = linkage.parse((root/'fixture/Api.class').read_bytes())
        nodes = {'fixture/Api': node}
        writes = [u for u in node['uses'] if u['owner'] == 'fixture/Api'
                  and u['operation'] in ('putfield', 'putstatic')]
        reads = [u for u in node['uses'] if u['owner'] == 'fixture/Api'
                 and u['operation'] in ('getfield', 'getstatic')]
        self.assertEqual({u['enclosing_method'] for u in writes}, {'<init>', '<clinit>'})
        self.assertEqual(len(reads), 2)
        for use in writes + reads:
            linkage.validate_use(use, 'fixture/Api', nodes.get)
        for use in writes:
            bad = dict(use, enclosing_method='ordinary')
            with self.assertRaisesRegex(ValueError, 'outside (constructor|class initializer)'):
                linkage.validate_use(bad, 'fixture/Api', nodes.get)
            target = dict(node, name='game/Target')
            transformed = dict(use, owner='game/Target')
            linkage.validate_use(transformed, 'game/Target', {'game/Target': target}.get)
            with self.assertRaisesRegex(ValueError, 'outside declaring class'):
                linkage.validate_use(transformed, 'other/Caller', {'game/Target': target}.get)

    def test_changed_final_fields_fail_game_and_library_verification_paths(self):
        for package, prefix in (('com.mojang.math', 'com/mojang/math/'), ('org.joml', 'org/joml/')):
            for static in (False, True):
                with self.subTest(package=package, static=static), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory); src = root/'src'; api = src/Path(package.replace('.', '/'))/'Api.java'
                    caller = src/'app/Caller.java'; api.parent.mkdir(parents=True); caller.parent.mkdir(parents=True)
                    out = root/'classes'; out.mkdir()
                    field = 'public static int value;' if static else 'public int value;'
                    target = package+'.Api.value' if static else '(new '+package+'.Api()).value'
                    api.write_text('package '+package+'; public class Api { '+field+' }')
                    caller.write_text('package app; public class Caller { void call() { '+target+' = 3; } }')
                    subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api), str(caller)],
                                   check=True, capture_output=True)
                    final = ('public static final int value = Integer.parseInt("1");' if static
                             else 'public final int value = 1;')
                    api.write_text('package '+package+'; public class Api { '+final+' }')
                    subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api)],
                                   check=True, capture_output=True)
                    mod = linkage.parse((out/'app/Caller.class').read_bytes()); archive = root/'runtime.jar'
                    with ZipFile(archive, 'w') as z:
                        z.write(out/(prefix+'Api.class'), prefix+'Api.class')
                    with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'final field write'):
                        if package == 'org.joml':
                            game_linkage.verify_library_instructions({mod['name']:mod}, {}, z, prefix, 'fixture')
                        else:
                            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')

    def test_final_setter_method_handle_is_not_an_initializer_write(self):
        def u1(x): return struct.pack('>B', x)
        def u2(x): return struct.pack('>H', x)
        def u4(x): return struct.pack('>I', x)
        def utf(s):
            raw = s.encode(); return b'\x01' + u2(len(raw)) + raw
        def handle_class(kind, final):
            cp = [utf('fixture/Handle'), b'\x07'+u2(1), utf('java/lang/Object'), b'\x07'+u2(3),
                  utf('<init>'), utf('()V'), b'\x0c'+u2(5)+u2(6), b'\x0a'+u2(4)+u2(7),
                  utf('field'), utf('I'), b'\x0c'+u2(9)+u2(10), b'\x09'+u2(2)+u2(11),
                  b'\x0f'+u1(kind)+u2(12), utf('Code'), utf('main'), utf('([Ljava/lang/String;)V')]
            def method(access, name, desc, code, stack, locals_):
                body = u2(stack)+u2(locals_)+u4(len(code))+code+u2(0)+u2(0)
                return u2(access)+u2(name)+u2(desc)+u2(1)+u2(14)+u4(len(body))+body
            field_flags = 1 | (8 if kind == 4 else 0) | (16 if final else 0)
            fields = u2(1)+u2(field_flags)+u2(9)+u2(10)+u2(0)
            init = method(1, 5, 6, b'\x2a\xb7\x00\x08\xb1', 1, 1)
            main = method(9, 15, 16, b'\x12\x0d\x57\xb1', 1, 1)
            return (b'\xca\xfe\xba\xbe'+u2(0)+u2(52)+u2(len(cp)+1)+b''.join(cp)+
                    u2(0x21)+u2(2)+u2(4)+u2(0)+fields+u2(2)+init+main+u2(0))
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root/'fixture').mkdir()
        java = shutil.which('java')
        for kind in (3, 4):
            for final in (False, True):
                raw = handle_class(kind, final)
                (root/'fixture/Handle.class').write_bytes(raw)
                node = linkage.parse(raw); use = next(u for u in node['uses'] if u['owner'] == 'fixture/Handle')
                self.assertEqual(use['source_kind'], 'method_handle')
                self.assertEqual(use['enclosing_method'], 'main')
                if final:
                    with self.assertRaisesRegex(ValueError, 'final field setter handle'):
                        linkage.validate_use(use, 'fixture/Handle', {'fixture/Handle': node}.get)
                else:
                    linkage.validate_use(use, 'fixture/Handle', {'fixture/Handle': node}.get)
                empty = io.BytesIO()
                with ZipFile(empty, 'w'): pass
                with ZipFile(io.BytesIO(empty.getvalue())) as game:
                    if final:
                        with self.assertRaisesRegex(ValueError, 'final field setter handle'):
                            game_linkage.verify_game_instructions({node['name']:node}, {}, game, {}, {}, {}, 'fixture')
                    else:
                        game_linkage.verify_game_instructions({node['name']:node}, {}, game, {}, {}, {}, 'fixture')
                if java:
                    run = subprocess.run([java, '-cp', str(root), 'fixture.Handle'], capture_output=True, text=True)
                    self.assertEqual(run.returncode == 0, not final, run.stderr)
                    if final: self.assertIn('IllegalAccessError', run.stderr)

    def test_interface_and_constructor_mismatches(self):
        nodes, uses = self.compile_case('public interface Api { void run(); }',
                                        'public class Caller { void call(Api a) { a.run(); } }',
                                        'public class Api { public void run() {} }')
        with self.assertRaisesRegex(ValueError, 'class/interface'):
            linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)
        nodes, uses = self.compile_case('public class Api { public Api() {} }',
                                        'public class Caller { Api call() { return new Api(); } }',
                                        'public class Api { public Api(int x) {} }')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)

    def test_method_handle_bootstrap_is_checked(self):
        nodes, uses = self.compile_case('public class Api { public static String text() { return "x"; } }',
                                        'public class Caller { java.util.function.Supplier<String> call() { return Api::text; } }',
                                        'public class Api { public String text() { return "x"; } }')
        handle = next(u for u in uses if u['name'] == 'text')
        self.assertEqual(handle['operation'], 'invokestatic')
        with self.assertRaisesRegex(ValueError, 'static/instance mismatch'):
            linkage.validate_use(handle, 'fixture/Caller', nodes.get)

    def test_dynamic_bootstrap_subset_rejects_unverified_sites(self):
        nodes, _ = self.compile_case('public class Api { public static String text() { return "x"; } }',
                                     'public class Caller { java.util.function.Supplier<String> call() { return Api::text; } }')
        node = nodes['fixture/Caller']
        self.assertEqual([(site['owner'], site['name']) for site in node['dynamic_sites']],
                         [('java/lang/invoke/LambdaMetafactory', 'metafactory')])
        empty = io.BytesIO()
        with ZipFile(empty, 'w'): pass
        with ZipFile(io.BytesIO(empty.getvalue())) as game:
            game_linkage.verify_game_instructions({'fixture/Caller':node, 'fixture/Api':nodes['fixture/Api']},
                                                  {}, game, {}, {}, {}, 'fixture')
            unsupported = dict(node, dynamic_sites=[dict(node['dynamic_sites'][0], name='other')])
            # The preceding verifier did not classify bootstrap kinds.
            legacy = dict(unsupported, dynamic_sites=[])
            game_linkage.verify_game_instructions({'fixture/Caller':legacy, 'fixture/Api':nodes['fixture/Api']},
                                                  {}, game, {}, {}, {}, 'fixture')
            with self.assertRaisesRegex(ValueError, 'unsupported dynamic bootstrap'):
                game_linkage.verify_game_instructions({'fixture/Caller':unsupported, 'fixture/Api':nodes['fixture/Api']},
                                                      {}, game, {}, {}, {}, 'fixture')
            constant = dict(node, dynamic_sites=[dict(node['dynamic_sites'][0], kind='constant')])
            with self.assertRaisesRegex(ValueError, 'unsupported dynamic bootstrap'):
                game_linkage.verify_game_instructions({'fixture/Caller':constant, 'fixture/Api':nodes['fixture/Api']},
                                                      {}, game, {}, {}, {}, 'fixture')

    def test_valid_and_missing_classes(self):
        nodes, uses = self.compile_case('public class Api { public static void run() {} }',
                                        'public class Caller { void call() { Api.run(); } }')
        linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)
        del nodes['fixture/Api']
        with self.assertRaisesRegex(ValueError, 'missing class'):
            linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)

    def test_constructor_method_handle(self):
        nodes, uses = self.compile_case('public class Api { public Api() {} }',
                                        'public class Caller { java.util.function.Supplier<Api> call() { return Api::new; } }')
        handle = next(u for u in uses if u['name'] == '<init>')
        self.assertEqual(handle['operation'], 'newinvokespecial')
        linkage.validate_use(handle, 'fixture/Caller', nodes.get)
        nodes, uses = self.compile_case('public class Api { public Api() {} }',
                                        'public class Caller { java.util.function.Supplier<Api> call() { return Api::new; } }',
                                        'public abstract class Api { public Api() {} }')
        handle = next(u for u in uses if u['name'] == '<init>')
        self.assertIsNotNone(linkage.resolve_member('fixture/Api', 'method', '<init>', '()V', nodes.get))
        with self.assertRaisesRegex(ValueError, 'cannot instantiate'):
            linkage.validate_use(handle, 'fixture/Caller', nodes.get)

    def test_inherited_public_and_bounded_protected_and_special_access(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); api = root/'parent'; caller = root/'child'; api.mkdir(); caller.mkdir()
        (api/'Base.java').write_text('package parent; public class Base { public void normal() {} protected void guarded() {} }')
        (api/'Api.java').write_text('package parent; public class Api extends Base {}')
        (caller/'Caller.java').write_text('package child; public class Caller extends parent.Api { '
                                         'void call() { normal(); super.guarded(); } '
                                         'void other(Caller receiver) { receiver.guarded(); } }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api/'Base.java'),
                        str(api/'Api.java'), str(caller/'Caller.java')], check=True, capture_output=True)
        nodes = {}
        for p in out.rglob('*.class'):
            node = linkage.parse(p.read_bytes()); nodes[node['name']] = node
        nodes['java/lang/Object'] = {'name':'java/lang/Object','super':None,'interfaces':[],'access':1,'members':[]}
        uses = [u for u in nodes['child/Caller']['uses'] if u['name'] in ('normal', 'guarded')]
        self.assertEqual({u['name'] for u in uses}, {'normal', 'guarded'})
        normal = next(u for u in uses if u['name'] == 'normal')
        self.assertEqual(linkage.validate_use(normal, 'child/Caller', nodes.get), 'parent/Base')
        special = next(u for u in uses if u['name'] == 'guarded' and u['operation'] == 'invokespecial')
        virtual = next(u for u in uses if u['name'] == 'guarded' and u['operation'] == 'invokevirtual')
        with self.assertRaisesRegex(ValueError, 'unsupported non-constructor invokespecial'):
            linkage.validate_use(special, 'child/Caller', nodes.get)
        with self.assertRaisesRegex(ValueError, 'unsupported non-constructor invokespecial'):
            linkage.validate_use(special, 'outsider/Unrelated', nodes.get)
        with self.assertRaisesRegex(ValueError, 'unsupported cross-package protected receiver'):
            linkage.validate_use(virtual, 'child/Caller', nodes.get)
        self.assertEqual(linkage.validate_use(dict(virtual, source_kind='method_handle'),
                                              'child/Caller', nodes.get), 'parent/Base')
        with self.assertRaisesRegex(ValueError, 'unsupported cross-package protected receiver'):
            linkage.validate_use(dict(virtual, source_kind='method_handle', owner='parent/Api'),
                                 'child/Caller', nodes.get)
        nodes, uses = self.compile_case('public class Api { protected void guarded() {} }',
                                        'public class Caller { void call(Api a) { a.guarded(); } }')
        self.assertEqual(linkage.validate_use(uses[0], 'fixture/Caller', nodes.get), 'fixture/Api')

    def test_descriptor_classes_are_collected(self):
        nodes, uses = self.compile_case('public class Api { public void take(java.util.List<String> x) {} }',
                                        'public class Caller { void call(Api a) { a.take(null); } }')
        self.assertIn('java/util/List', nodes['fixture/Caller']['classes'])

    def test_method_handle_descriptor_access_is_checked_without_overrejecting_direct_calls(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); game = root/'src/com/mojang/math'; app = root/'src/app'
        game.mkdir(parents=True); app.mkdir(parents=True); out = root/'classes'; out.mkdir()
        hidden, api = game/'Hidden.java', game/'Api.java'
        hidden.write_text('package com.mojang.math; public class Hidden {}')
        api.write_text('package com.mojang.math; public class Api { public static Hidden value() { return null; } }')
        direct, handle = app/'Direct.java', app/'Handle.java'
        direct.write_text('package app; public class Direct { public static void main(String[] a) { '
                          'Object x = com.mojang.math.Api.value(); System.out.println(x); } }')
        handle.write_text('package app; public class Handle { public static void main(String[] a) { '
                          'java.util.function.Supplier<Object> x = com.mojang.math.Api::value; '
                          'System.out.println(x.get()); } }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(hidden), str(api),
                        str(direct), str(handle)], check=True, capture_output=True)
        hidden.write_text('package com.mojang.math; class Hidden {}')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(hidden)],
                       check=True, capture_output=True)
        direct_node = linkage.parse((out/'app/Direct.class').read_bytes())
        handle_node = linkage.parse((out/'app/Handle.class').read_bytes())
        self.assertIn({'name':'com/mojang/math/Hidden', 'operation':'method_handle_descriptor'},
                      handle_node['class_uses'])
        archive = root/'game.jar'
        with ZipFile(archive, 'w') as z:
            for name in ('Hidden', 'Api'):
                z.write(out/('com/mojang/math/'+name+'.class'), 'com/mojang/math/'+name+'.class')
        with ZipFile(archive) as z:
            game_linkage.verify_game_instructions({direct_node['name']:direct_node}, {}, z, {}, {}, {}, 'fixture')
            old = dict(handle_node, class_uses=[])
            game_linkage.verify_game_instructions({old['name']:old}, {}, z, {}, {}, {}, 'fixture')
            with self.assertRaisesRegex(ValueError, 'inaccessible referenced class'):
                game_linkage.verify_game_instructions({handle_node['name']:handle_node}, {}, z, {}, {}, {}, 'fixture')
        java = shutil.which('java')
        if java:
            direct_run = subprocess.run([java, '-cp', str(out), 'app.Direct'], capture_output=True, text=True)
            self.assertEqual(direct_run.returncode, 0, direct_run.stderr)
            handle_run = subprocess.run([java, '-cp', str(out), 'app.Handle'], capture_output=True, text=True)
            self.assertNotEqual(handle_run.returncode, 0)
            self.assertIn('IllegalAccessError', handle_run.stderr)

    def test_consumed_method_type_checks_descriptor_class_access(self):
        def u2(x): return struct.pack('>H', x)
        def u4(x): return struct.pack('>I', x)
        def utf(s):
            raw = s.encode(); return b'\x01'+u2(len(raw))+raw
        cp = [utf('app/TypeCaller'), b'\x07'+u2(1), utf('java/lang/Object'), b'\x07'+u2(3),
              utf('main'), utf('([Ljava/lang/String;)V'), utf('Code'),
              utf('()Lcom/mojang/math/Hidden;'), b'\x10'+u2(8)]
        code = b'\x12\x09\x57\xb1'
        body = u2(1)+u2(1)+u4(len(code))+code+u2(0)+u2(0)
        main = u2(9)+u2(5)+u2(6)+u2(1)+u2(7)+u4(len(body))+body
        raw = (b'\xca\xfe\xba\xbe'+u2(0)+u2(52)+u2(len(cp)+1)+b''.join(cp)+
               u2(0x21)+u2(2)+u2(4)+u2(0)+u2(0)+u2(1)+main+u2(0))
        node = linkage.parse(raw)
        self.assertIn({'name':'com/mojang/math/Hidden', 'operation':'method_type_descriptor'}, node['class_uses'])
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root/'app').mkdir(); (root/'app/TypeCaller.class').write_bytes(raw)
        source = root/'Hidden.java'; archive = root/'game.jar'
        java = shutil.which('java')
        for public in (True, False):
            source.write_text('package com.mojang.math; '+('public ' if public else '')+'class Hidden {}')
            subprocess.run([self.javac, '--release', '8', '-d', str(root), str(source)],
                           check=True, capture_output=True)
            with ZipFile(archive, 'w') as z:
                z.write(root/'com/mojang/math/Hidden.class', 'com/mojang/math/Hidden.class')
            with ZipFile(archive) as z:
                old = dict(node, class_uses=[])
                game_linkage.verify_game_instructions({old['name']:old}, {}, z, {}, {}, {}, 'fixture')
                if public:
                    game_linkage.verify_game_instructions({node['name']:node}, {}, z, {}, {}, {}, 'fixture')
                else:
                    with self.assertRaisesRegex(ValueError, 'inaccessible referenced class'):
                        game_linkage.verify_game_instructions({node['name']:node}, {}, z, {}, {}, {}, 'fixture')
            if java:
                result = subprocess.run([java, '-cp', str(root), 'app.TypeCaller'], capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, public, result.stderr)
                if not public: self.assertIn('IllegalAccessError', result.stderr)

    def test_supported_classfile_levels(self):
        help_text = subprocess.check_output([self.javac, '--help'], text=True)
        for release in ('8', '16', '17', '21', '25'):
            if release not in help_text:
                continue
            with self.subTest(release=release):
                nodes, uses = self.compile_case('public class Api { public static void run() {} }',
                                                'public class Caller { void call() { Api.run(); } }', release=release)
                self.assertEqual(nodes['fixture/Caller']['major'], int(release) + 44)
                linkage.validate_use(uses[0], 'fixture/Caller', nodes.get)

    def test_mixin_target_staticness(self):
        nodes, _ = self.compile_case('public class Api { public static void run() {} }',
                                     'public class Caller { void call() { Api.run(); } }')
        linkage.validate_mixin_target(nodes['fixture/Api'], 'run', '()V', 8)
        with self.assertRaisesRegex(ValueError, 'staticness'):
            linkage.validate_mixin_target(nodes['fixture/Api'], 'run', '()V', 0)
        with self.assertRaisesRegex(ValueError, 'missing Mixin'):
            linkage.validate_mixin_target(nodes['fixture/Api'], 'missing', '()V', 8)

    def test_unmodeled_mixin_and_unique_options_fail_closed(self):
        mixin_type = 'Lorg/spongepowered/asm/mixin/Mixin;'
        unique_type = 'Lorg/spongepowered/asm/mixin/Unique;'
        node = {'annotations':{mixin_type:{'value':['Lgame/Target;']}}, 'members':[]}
        game_linkage.validate_mixin_semantics({'fixture/Mixin':node}, {'fixture/Mixin':'game/Target'})
        node['annotations'][mixin_type]['remap'] = 0
        with self.assertRaisesRegex(ValueError, 'unsupported Mixin options'):
            game_linkage.validate_mixin_semantics({'fixture/Mixin':node}, {'fixture/Mixin':'game/Target'})
        del node['annotations'][mixin_type]['remap']
        node['members'] = [{'annotations':{unique_type:{'silent':1}}}]
        with self.assertRaisesRegex(ValueError, 'unsupported Unique options'):
            game_linkage.validate_mixin_semantics({'fixture/Mixin':node}, {'fixture/Mixin':'game/Target'})

    def test_tail_injection_requires_a_real_void_return(self):
        nodes, _ = self.compile_case('public class Api { public void run() { throw new RuntimeException(); } }',
                                     'public class Caller { void call(Api a) { a.run(); } }')
        linkage.validate_injection_point(nodes['fixture/Api'], 'run', '()V', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'no void return'):
            linkage.validate_injection_point(nodes['fixture/Api'], 'run', '()V', 'TAIL')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            linkage.validate_injection_point(nodes['fixture/Api'], 'run', '()V', 'INVOKE')

    def test_static_interface_methods_are_not_inherited(self):
        method = {'kind':'method', 'name':'run', 'descriptor':'()V', 'access':9}
        nodes = {
            'p/Base': {'super':None, 'interfaces':[], 'access':0x201, 'members':[method]},
            'p/Child': {'super':None, 'interfaces':['p/Base'], 'access':0x201, 'members':[]},
        }
        self.assertIsNone(linkage.resolve_member('p/Child', 'method', 'run', '()V', nodes.get))
        self.assertEqual(linkage.resolve_member('p/Base', 'method', 'run', '()V', nodes.get)[0], 'p/Base')

    def test_game_math_classes_and_member_staticness(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); math = root/'src/com/mojang/math'; app = root/'src/app'
        math.mkdir(parents=True); app.mkdir(parents=True)
        vector = math/'Vector.java'; caller = app/'Caller.java'
        vector.write_text('package com.mojang.math; public class Vector { public static void rotate() {} }')
        caller.write_text('package app; public class Caller { void run() { com.mojang.math.Vector.rotate(); } }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector), str(caller)],
                       check=True, capture_output=True)
        mod = linkage.parse((out/'app/Caller.class').read_bytes())
        archive = root/'game.jar'
        def write_game(include):
            with ZipFile(archive, 'w') as z:
                if include: z.write(out/'com/mojang/math/Vector.class', 'com/mojang/math/Vector.class')
        write_game(True)
        with ZipFile(archive) as z:
            self.assertEqual(game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture'), 1)
        write_game(False)
        with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'missing game or descriptor'):
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')
        vector.write_text('package com.mojang.math; public class Vector { public void rotate() {} }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector)], check=True, capture_output=True)
        write_game(True)
        with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'static/instance mismatch'):
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')

    def test_instruction_only_class_access_and_new_abstract(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); math = root/'src/com/mojang/math'; app = root/'src/app'
        math.mkdir(parents=True); app.mkdir(parents=True)
        vector = math/'Vector.java'; caller = app/'Caller.java'
        vector.write_text('package com.mojang.math; public class Vector { public Vector() {} }')
        caller.write_text('package app; public class Caller { '
                          'Class<?> literal() { return com.mojang.math.Vector.class; } '
                          'boolean test(Object x) { return x instanceof com.mojang.math.Vector; } '
                          'Object cast(Object x) { return (com.mojang.math.Vector)x; } '
                          'Object array() { return new com.mojang.math.Vector[1]; } '
                          'Object matrix() { return new com.mojang.math.Vector[1][1]; } }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector), str(caller)],
                       check=True, capture_output=True)
        mod = linkage.parse((out/'app/Caller.class').read_bytes()); archive = root/'game.jar'
        self.assertEqual({u['operation'] for u in mod['class_uses']},
                         {'class_constant', 'instanceof', 'checkcast', 'anewarray', 'multianewarray'})
        def write_game():
            with ZipFile(archive, 'w') as z:
                z.write(out/'com/mojang/math/Vector.class', 'com/mojang/math/Vector.class')
        write_game()
        with ZipFile(archive) as z:
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')
        vector.write_text('package com.mojang.math; class Vector { public Vector() {} }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector)], check=True, capture_output=True)
        write_game()
        legacy = dict(mod); legacy.pop('class_uses')
        with ZipFile(archive) as z:
            # The previous class-presence/member-only check accepted these invalid class operations.
            self.assertEqual(game_linkage.verify_game_instructions({legacy['name']:legacy}, {}, z, {}, {}, {}, 'fixture'), 0)
        with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'inaccessible referenced class'):
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')
        with ZipFile(archive) as z:
            game_linkage.verify_game_instructions({mod['name']:mod}, {'app/Caller':'com/mojang/math/Target'},
                                                  z, {}, {}, {}, 'fixture')
        vector.write_text('package com.mojang.math; public class Vector { public Vector() {} }')
        caller.write_text('package app; public class Caller { Object make() { return new com.mojang.math.Vector(); } }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector), str(caller)],
                       check=True, capture_output=True)
        mod = linkage.parse((out/'app/Caller.class').read_bytes())
        vector.write_text('package com.mojang.math; public abstract class Vector { public Vector() {} }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(vector)], check=True, capture_output=True)
        write_game()
        legacy = dict(mod); legacy.pop('class_uses')
        with ZipFile(archive) as z:
            self.assertEqual(game_linkage.verify_game_instructions({legacy['name']:legacy}, {}, z, {}, {}, {}, 'fixture'), 1)
        with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'cannot instantiate'):
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, z, {}, {}, {}, 'fixture')

    def test_library_descriptor_only_class_is_required(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); lib = root/'src/org/joml'; app = root/'src/app'
        lib.mkdir(parents=True); app.mkdir(parents=True)
        (lib/'Quaternionfc.java').write_text('package org.joml; public interface Quaternionfc {}')
        (app/'Caller.java').write_text('package app; public class Caller { void use(org.joml.Quaternionfc q) {} }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(lib/'Quaternionfc.java'),
                        str(app/'Caller.java')], check=True, capture_output=True)
        mod = linkage.parse((out/'app/Caller.class').read_bytes()); archive = root/'library.jar'
        with ZipFile(archive, 'w') as z:
            z.write(out/'org/joml/Quaternionfc.class', 'org/joml/Quaternionfc.class')
        with ZipFile(archive) as z:
            self.assertEqual(game_linkage.verify_library_instructions({mod['name']:mod}, {}, z, 'org/joml/', 'fixture'), 0)
        with ZipFile(archive, 'w'): pass
        with ZipFile(archive) as z, self.assertRaisesRegex(ValueError, 'missing dependency class'):
            game_linkage.verify_library_instructions({mod['name']:mod}, {}, z, 'org/joml/', 'fixture')

    def test_unclassified_and_undeclared_libraries_fail_closed(self):
        mod = {'fixture/Caller': {'classes': {'other/Unknown'}, 'uses': []}}
        with self.assertRaisesRegex(ValueError, 'unclassified'):
            game_linkage.verify_declared_libraries({'libraries': []}, mod, {}, lambda x: b'', 'fixture')
        mod['fixture/Caller']['classes'] = {'org/joml/Quaternionfc'}
        with self.assertRaisesRegex(ValueError, 'no declared library'):
            game_linkage.verify_declared_libraries({'libraries': []}, mod, {}, lambda x: b'', 'fixture')
        metadata = {'libraries':[{'name':'org.joml:joml:1.0', 'downloads':{'artifact':{
            'url':'https://example.invalid/joml.jar','sha1':'a'*40,'size':10}}}]}
        def bad_hash(_): raise ValueError('SHA-1 mismatch')
        with self.assertRaisesRegex(ValueError, 'SHA-1 mismatch'):
            game_linkage.verify_declared_libraries(metadata, mod, {}, bad_hash, 'fixture')

    def test_inherited_library_fields_and_defaults_use_composite_classpath(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); lib = root/'src/org/joml'; app = root/'src/app'
        lib.mkdir(parents=True); app.mkdir(parents=True)
        interface, api, target, caller = lib/'I.java', lib/'Api.java', lib/'Target.java', app/'Caller.java'
        interface.write_text('package org.joml; public interface I { default void run() {} }')
        target.write_text('package org.joml; public class Target extends Api {}')
        caller.write_text('package app; public class Caller extends org.joml.Target { '
                          'public void call() { run(); value = 3; } }')
        api.write_text('package org.joml; public class Api implements I { public int value; }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(interface), str(api),
                        str(target), str(caller)], check=True, capture_output=True)
        mod = linkage.parse((out/'app/Caller.class').read_bytes())
        inherited = [u for u in mod['uses'] if u['owner'] == 'app/Caller'
                     and u['name'] in ('run', 'value')]
        self.assertEqual({u['name'] for u in inherited}, {'run', 'value'})
        game_bytes = io.BytesIO()
        with ZipFile(game_bytes, 'w'): pass

        def archive_bytes(include=('I', 'Api', 'Target')):
            data = io.BytesIO()
            with ZipFile(data, 'w') as z:
                for name in include:
                    z.write(out/('org/joml/'+name+'.class'), 'org/joml/'+name+'.class')
            return data.getvalue()

        def run(data, mixins=None):
            artifact = {'url':'fixture:library', 'sha1':hashlib.sha1(data).hexdigest(), 'size':len(data)}
            metadata = {'libraries':[{'name':'org.joml:joml:1.0', 'downloads':{'artifact':artifact}}]}
            def fetch(item):
                self.assertEqual(item['sha1'], hashlib.sha1(data).hexdigest())
                self.assertEqual(item['size'], len(data))
                return data
            runtime = game_linkage.RuntimeLibraries(metadata, fetch, 'fixture')
            with ZipFile(io.BytesIO(game_bytes.getvalue())) as game:
                lookup = game_linkage.make_class_lookup({mod['name']:mod}, game, {}, {}, {},
                                                       'fixture', runtime.lookup)
                count = game_linkage.verify_game_instructions({mod['name']:mod}, mixins or {}, game,
                                                               {}, {}, {}, 'fixture', class_lookup=lookup)
                game_linkage.verify_declared_libraries(metadata, {mod['name']:mod}, mixins or {}, fetch,
                                                       'fixture', runtime_libraries=runtime, class_lookup=lookup)
                return count

        original = archive_bytes()
        with ZipFile(io.BytesIO(game_bytes.getvalue())) as game, self.assertRaisesRegex(ValueError, 'missing member|missing superclass'):
            game_linkage.verify_game_instructions({mod['name']:mod}, {}, game, {}, {}, {}, 'fixture')
        self.assertGreaterEqual(run(original), 2)
        self.assertGreaterEqual(run(original, {'app/Caller':'org/joml/Target'}), 2)
        with self.assertRaisesRegex(ValueError, 'missing superclass or interface'):
            run(archive_bytes(('I', 'Target')))
        with self.assertRaisesRegex(ValueError, 'missing superclass or interface'):
            run(archive_bytes(('Api', 'Target')))
        interface.write_text('package org.joml; public interface I {}')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(interface)],
                       check=True, capture_output=True)
        with self.assertRaisesRegex(ValueError, 'missing member'):
            run(archive_bytes())
        interface.write_text('package org.joml; public interface I { default void run() {} }')
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(interface)],
                       check=True, capture_output=True)
        for replacement, error in (
                ('public static int value;', 'static/instance mismatch'),
                ('int value;', 'package-private'),
                ('public final int value = 1;', 'final field write outside declaring class')):
            api.write_text('package org.joml; public class Api implements I { '+replacement+' }')
            subprocess.run([self.javac, '--release', '8', '-classpath', str(out), '-d', str(out), str(api)],
                           check=True, capture_output=True)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, error):
                run(archive_bytes())

    def test_conflicting_declared_library_origins_are_rejected(self):
        artifacts = [{'url':'fixture:'+str(i), 'sha1':str(i)*40, 'size':1} for i in (1, 2)]
        metadata = {'libraries':[{'name':'org.joml:joml:'+str(i), 'downloads':{'artifact':artifact}}
                                 for i, artifact in enumerate(artifacts)]}
        runtime = game_linkage.RuntimeLibraries(metadata, lambda item: b'', 'fixture')
        with self.assertRaisesRegex(ValueError, 'ambiguous declared libraries'):
            runtime.lookup('org/joml/Api')

    def test_inherited_game_member_and_effective_mixin_field(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); game = root/'src/net/minecraft'; app = root/'src/app'
            game.mkdir(parents=True); app.mkdir(parents=True); out = root/'classes'; out.mkdir()
            api, target, caller, mixin = game/'Api.java', game/'Target.java', app/'Caller.java', app/'Mixin.java'
            api.write_text('package net.minecraft; public class Api { public void run() {} }')
            target.write_text('package net.minecraft; public class Target {}')
            caller.write_text('package app; public class Caller extends net.minecraft.Api { void call() { run(); } }')
            mixin.write_text('package app; public class Mixin { private final int value; '
                             'public Mixin() { value = 1; } }')
            subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api), str(target),
                            str(caller), str(mixin)], check=True, capture_output=True)
            caller_node = linkage.parse((out/'app/Caller.class').read_bytes())
            mixin_node = linkage.parse((out/'app/Mixin.class').read_bytes())
            archive = root/'game.jar'
            def write_game():
                with ZipFile(archive, 'w') as z:
                    for name in ('Api', 'Target'):
                        z.write(out/('net/minecraft/'+name+'.class'), 'net/minecraft/'+name+'.class')
            write_game()
            with ZipFile(archive) as z:
                self.assertGreater(game_linkage.verify_game_instructions({caller_node['name']:caller_node}, {}, z,
                                                                          {}, {}, {}, 'fixture'), 0)
                self.assertGreater(game_linkage.verify_game_instructions({mixin_node['name']:mixin_node},
                                  {'app/Mixin':'net/minecraft/Target'}, z, {}, {}, {}, 'fixture'), 0)
                changed = dict(mixin_node, uses=[dict(u, enclosing_method='handler') if u['name']=='value' else u
                                                  for u in mixin_node['uses']])
                with self.assertRaisesRegex(ValueError, 'final instance field write outside constructor'):
                    game_linkage.verify_game_instructions({changed['name']:changed},
                        {'app/Mixin':'net/minecraft/Target'}, z, {}, {}, {}, 'fixture')
            api.write_text('package net.minecraft; public class Api {}')
            target.write_text('package net.minecraft; public class Target { private int value; }')
            subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api), str(target)],
                           check=True, capture_output=True)
            write_game()
            with ZipFile(archive) as z:
                with self.assertRaisesRegex(ValueError, 'missing member'):
                    game_linkage.verify_game_instructions({caller_node['name']:caller_node}, {}, z, {}, {}, {}, 'fixture')
                with self.assertRaisesRegex(ValueError, 'unsupported Mixin member collision'):
                    game_linkage.verify_game_instructions({mixin_node['name']:mixin_node},
                        {'app/Mixin':'net/minecraft/Target'}, z, {}, {}, {}, 'fixture')


if __name__ == '__main__':
    unittest.main()
