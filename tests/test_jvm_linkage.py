import shutil
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

    def test_inherited_public_and_cross_package_protected(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); api = root/'parent'; caller = root/'child'; api.mkdir(); caller.mkdir()
        (api/'Base.java').write_text('package parent; public class Base { public void normal() {} protected void guarded() {} }')
        (api/'Api.java').write_text('package parent; public class Api extends Base {}')
        (caller/'Caller.java').write_text('package child; public class Caller extends parent.Api { void call() { normal(); super.guarded(); } }')
        out = root/'classes'; out.mkdir()
        subprocess.run([self.javac, '--release', '8', '-d', str(out), str(api/'Base.java'),
                        str(api/'Api.java'), str(caller/'Caller.java')], check=True, capture_output=True)
        nodes = {}
        for p in out.rglob('*.class'):
            node = linkage.parse(p.read_bytes()); nodes[node['name']] = node
        nodes['java/lang/Object'] = {'name':'java/lang/Object','super':None,'interfaces':[],'access':1,'members':[]}
        uses = [u for u in nodes['child/Caller']['uses'] if u['name'] in ('normal', 'guarded')]
        self.assertEqual({u['name'] for u in uses}, {'normal', 'guarded'})
        for use in uses:
            self.assertEqual(linkage.validate_use(use, 'child/Caller', nodes.get), 'parent/Base')
        with self.assertRaisesRegex(ValueError, 'invalid invokespecial|protected'):
            linkage.validate_use(next(u for u in uses if u['name']=='guarded'), 'outsider/Unrelated', nodes.get)

    def test_descriptor_classes_are_collected(self):
        nodes, uses = self.compile_case('public class Api { public void take(java.util.List<String> x) {} }',
                                        'public class Caller { void call(Api a) { a.take(null); } }')
        self.assertIn('java/util/List', nodes['fixture/Caller']['classes'])

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


if __name__ == '__main__':
    unittest.main()
