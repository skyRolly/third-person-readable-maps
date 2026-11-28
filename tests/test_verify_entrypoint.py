"""Exercise the intermediary packaged-JAR verifier, including Mixin injection points."""
import hashlib
import io
import os
import json
import re
import shutil
import java_toolchain
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT/'tests'))
import verify_supported_apis as verifier
import hierarchy_entrypoint_fixtures as hierarchy_fixtures


class IntermediaryEntrypointFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javac = java_toolchain.which('javac')
        if not cls.javac:
            raise unittest.SkipTest('javac is required for packaged verifier fixtures')

    def fixture(self, point, body, extra='', target_signature='()', inherited=None, candidate_case=None, self_cast=False,
                hierarchy=None, mixin_helper=False, target_hierarchy='object', game_inherited=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); support = root/'support'; support.mkdir()
            config = json.loads((ROOT/'src/main/resources/thirdpersonreadablemaps.mixins.json').read_text())
            advertised = json.loads((ROOT/'src/main/resources/fabric.mod.json').read_text())['depends']['minecraft']
            properties = dict(line.split('=', 1) for line in (ROOT/'gradle.properties').read_text().splitlines()
                              if '=' in line and not line.lstrip().startswith('#'))
            if isinstance(advertised, str):
                advertised = re.sub(r'\$\{([^}]+)\}', lambda m: properties[m.group(1)], advertised)
            sources = {
                'org/spongepowered/asm/mixin/Mixin.java':
                    'package org.spongepowered.asm.mixin; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface Mixin { Class<?>[] value(); }',
                'org/spongepowered/asm/mixin/injection/At.java':
                    'package org.spongepowered.asm.mixin.injection; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface At { String value(); }',
                'org/spongepowered/asm/mixin/injection/Inject.java':
                    'package org.spongepowered.asm.mixin.injection; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface Inject { '
                    'String[] method(); At[] at(); boolean cancellable() default false; int require() default -1; }',
                'org/spongepowered/asm/mixin/injection/callback/CallbackInfo.java':
                    'package org.spongepowered.asm.mixin.injection.callback; public class CallbackInfo {}',
                'net/minecraft/class_1.java':'package net.minecraft; public class class_1 {}',
                'net/minecraft/class_2.java':'package net.minecraft; public class class_2 {}',
                'game/Target1.java':'package game; public class Target1 { public void a'+target_signature+' { '+body+' } }',
                'game/Target2.java':'package game; public class Target2 { public void b() {} }',
            }
            declaration = {
                'object': 'class Target1',
                'runtime': 'class Target1 extends RuntimeException',
                'indirect': 'class Target1 extends Base',
                'enum': 'enum Target1',
                'record': 'record Target1()',
                'missing': 'class Target1',
                'missing-parent': 'class Target1 extends Base',
                'interface': 'interface Target1',
            }[target_hierarchy]
            prefix = 'INSTANCE; ' if target_hierarchy == 'enum' else ''
            method = 'public default void a' if target_hierarchy == 'interface' else 'public void a'
            sources['game/Target1.java'] = ('package game; public '+declaration+' { '+prefix+
                                             method+target_signature+' { '+body+' } }')
            if target_hierarchy in ('indirect', 'missing-parent'):
                sources['game/Base.java'] = 'package game; public class Base extends RuntimeException {}'
            if game_inherited:
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public int value; public void run() {} }'
                sources['net/minecraft/class_1.java'] = 'package net.minecraft; public class class_1 extends org.joml.Api {}'
                sources['game/Target1.java'] = ('package game; public class Target1 extends org.joml.Api { '
                                                'public void a'+target_signature+' { '+body+' } }')
            if candidate_case == 'platform-inherited':
                sources['net/minecraft/class_1.java'] = 'package net.minecraft; public class class_1 extends RuntimeException {}'
            if inherited:
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public int value; public void run() {} }'
            if inherited and inherited.startswith('hidden'):
                sources['org/joml/Hidden.java'] = 'package org.joml; public class Hidden {}'
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public static Hidden value() { return null; } }'
            paths = []
            for name, source in sources.items():
                path=root/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(source);paths.append(str(path))
            subprocess.run([self.javac, '--release', '17' if target_hierarchy == 'record' else '8', '-d', str(support), *paths],
                           check=True, capture_output=True)
            out = root/'mod'; out.mkdir(); mixin_paths=[]
            for index, mixin_name in enumerate(config['client']):
                number = 1 if mixin_name == 'ReadableMapLayerMixin' else 2
                injection = point if number == 1 else 'HEAD'
                options = extra if number == 1 else ''
                path = root/(mixin_name+'.java')
                path.write_text('package '+config['package']+'; import org.spongepowered.asm.mixin.Mixin; '
                                'import org.spongepowered.asm.mixin.injection.*; '
                                'import org.spongepowered.asm.mixin.injection.callback.CallbackInfo; '
                                '@Mixin(net.minecraft.class_'+str(number)+'.class) public class '+mixin_name+' { ' +
                                ('private void helper() {} ' if mixin_helper and number==1 else '') +
                                '@Inject(method="method_'+str(number)+'", at=@At("'+injection+'")'+options+') '
                                'private void inject(CallbackInfo ci) {' +
                                (('Object x=this; '+mixin_name+' m=('+mixin_name+')x;') if self_cast and number==1 else '') +
                                ('helper();' if mixin_helper and number==1 else '') + '} }')
                mixin_paths.append(str(path))
            subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), *mixin_paths],
                           check=True, capture_output=True)
            if candidate_case == 'platform-inherited':
                caller = root/'PlatformCaller.java'
                caller.write_text('package fixture; public class PlatformCaller { '
                                  'public String invoke(net.minecraft.class_1 t) { return t.getMessage(); } '
                                  'public static void main(String[] a) { '
                                  'new PlatformCaller().invoke(new net.minecraft.class_1()); } }')
                subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(caller)],
                               check=True, capture_output=True)
                subprocess.run([java_toolchain.which('java'), '-cp', str(out)+os.pathsep+str(support),
                                'fixture.PlatformCaller'], check=True, capture_output=True)
            elif candidate_case:
                nest = root/'Nest.java'
                nest.write_text('package fixture; public class Nest { private int value; '
                                'static class Member { int read(Nest n) { return n.value; } } }')
                subprocess.run([self.javac, '--release', '21', '-d', str(out), str(nest)],
                               check=True, capture_output=True)
                if candidate_case == 'mixin-cross':
                    cross = root/'Cross.java'
                    cross.write_text('package fixture; public class Cross { Object f(Object x) { '
                                     'return (tech.rolly.thirdpersonreadablemaps.mixin.ReadableMapLayerMixin)x; } }')
                    subprocess.run([self.javac, '--release', '21', '-classpath', str(out)+os.pathsep+str(support),
                                    '-d', str(out), str(cross)], check=True, capture_output=True)
                if candidate_case == 'broken':
                    member = out/'fixture/Nest$Member.class'
                    raw = member.read_bytes(); assert b'NestHost' in raw
                    member.write_bytes(raw.replace(b'NestHost', b'NestH0st', 1))
            if inherited:
                caller = root/'Caller.java'
                if inherited.startswith('hidden'):
                    caller.write_text('package app; public class Caller { Object invoke() { return org.joml.Api.value(); } }')
                else:
                    caller.write_text('package app; public class Caller extends org.joml.Api { '
                                      'public void invoke() { run(); value = 1; } }')
                subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(caller)],
                               check=True, capture_output=True)
                if inherited.startswith('hidden'):
                    hidden = root/'org/joml/Hidden.java'
                    hidden.write_text('package org.joml; class Hidden {}')
                    subprocess.run([self.javac, '--release', '8', '-d', str(support), str(hidden)],
                                   check=True, capture_output=True)
                if inherited in ('final', 'removed'):
                    api = root/'org/joml/Api.java'
                    member = 'public final int value = 0; public void run() {}' if inherited == 'final' else 'public int value;'
                    api.write_text('package org.joml; public class Api { '+member+' }')
                    subprocess.run([self.javac, '--release', '8', '-d', str(support), str(api)],
                                   check=True, capture_output=True)
            if game_inherited:
                caller = root/'GameCaller.java'
                caller.write_text('package fixture; public class GameCaller { '
                                  'public void invoke(net.minecraft.class_1 t) { t.run(); t.value = 1; } '
                                  'public static void main(String[] a) { '
                                  'new GameCaller().invoke(new net.minecraft.class_1()); } }')
                subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(caller)],
                               check=True, capture_output=True)
                subprocess.run([java_toolchain.which('java'), '-cp', str(out)+os.pathsep+str(support),
                                'fixture.GameCaller'], check=True, capture_output=True)
                if game_inherited in ('removed', 'static', 'private', 'field-removed', 'field-static', 'field-private'):
                    method = {'removed':'', 'static':'public static void run() {}',
                              'private':'private void run() {}'}.get(game_inherited, 'public void run() {}')
                    field = {'field-removed':'', 'field-static':'public static int value;',
                             'field-private':'private int value;'}.get(game_inherited, 'public int value;')
                    api = root/'org/joml/Api.java'
                    api.write_text('package org.joml; public class Api { '+field+method+' }')
                    subprocess.run([self.javac, '--release', '8', '-d', str(support), str(api)],
                                   check=True, capture_output=True)
                    result = subprocess.run([java_toolchain.which('java'), '-cp', str(out)+os.pathsep+str(support),
                                             'fixture.GameCaller'], capture_output=True, text=True)
                    expected = ('NoSuchMethodError' if game_inherited == 'removed' else
                                'NoSuchFieldError' if game_inherited == 'field-removed' else
                                'IllegalAccessError' if game_inherited in ('private', 'field-private') else
                                'IncompatibleClassChangeError')
                    assert result.returncode != 0 and expected in result.stderr, result.stderr
            hierarchy_info = hierarchy_fixtures.prepare(root, support, out, self.javac, hierarchy) if hierarchy else None
            jar = root/'candidate.jar'
            with ZipFile(jar, 'w') as z:
                z.writestr('fabric.mod.json', json.dumps({'depends':{'minecraft':advertised}}))
                z.writestr('thirdpersonreadablemaps.mixins.json', json.dumps(config))
                for mixin_name in config['client']:
                    name = config['package'].replace('.', '/')+'/'+mixin_name+'.class'
                    z.write(out/name, name)
                if inherited:
                    z.write(out/'app/Caller.class', 'app/Caller.class')
                if candidate_case:
                    for item in sorted((out/'fixture').glob('*.class')):
                        z.write(item, 'fixture/'+item.name)
                if game_inherited:
                    z.write(out/'fixture/GameCaller.class', 'fixture/GameCaller.class')
                if hierarchy_info:
                    z.write(out/hierarchy_info['probe'], str(hierarchy_info['probe']))
                    if hierarchy_info['location'] == 'candidate' and hierarchy_info['variant'] != 'missing':
                        z.write(out/hierarchy_info['parent'], str(hierarchy_info['parent']))
            game_buffer = io.BytesIO()
            with ZipFile(game_buffer, 'w') as z:
                for name in ('Target1', 'Target2'):
                    if name != 'Target1' or target_hierarchy != 'missing':
                        z.write(support/('game/'+name+'.class'), 'game/'+name+'.class')
                if target_hierarchy == 'indirect':
                    z.write(support/'game/Base.class', 'game/Base.class')
                if hierarchy_info and hierarchy_info['location'] == 'game' and hierarchy_info['variant'] != 'missing':
                    z.write(support/hierarchy_info['parent'], str(hierarchy_info['parent']))
            game_data = game_buffer.getvalue()
            map_buffer = io.BytesIO()
            with ZipFile(map_buffer, 'w') as z:
                z.writestr('mappings/mappings.tiny', 'tiny\t2\t0\tofficial\tintermediary\n'
                           'c\tgame/Target1\tnet/minecraft/class_1\n\tm\t()V\ta\tmethod_1\n'
                           'c\tgame/Target2\tnet/minecraft/class_2\n\tm\t()V\tb\tmethod_2\n')
            mapping = map_buffer.getvalue()
            library_buffer = io.BytesIO()
            with ZipFile(library_buffer, 'w') as z:
                if inherited or game_inherited:
                    z.write(support/'org/joml/Api.class', 'org/joml/Api.class')
                    if inherited == 'hidden':
                        z.write(support/'org/joml/Hidden.class', 'org/joml/Hidden.class')
                if hierarchy_info and hierarchy_info['location'] == 'library' and hierarchy_info['variant'] != 'missing':
                    z.write(support/hierarchy_info['parent'], str(hierarchy_info['parent']))
            library = library_buffer.getvalue()
            alternative = None
            if (inherited and inherited.startswith('platform-')) or game_inherited == 'platform-missing':
                api = root/'org/joml/Api.java'
                method = '' if inherited == 'platform-missing' or game_inherited == 'platform-missing' else 'public void run() {}'
                api.write_text('package org.joml; public class Api { public int value; public int extra; '+method+' }')
                subprocess.run([self.javac, '--release', '8', '-d', str(support), str(api)],
                               check=True, capture_output=True)
                alternative_buffer = io.BytesIO()
                with ZipFile(alternative_buffer, 'w') as z:
                    z.write(support/'org/joml/Api.class', 'org/joml/Api.class')
                alternative = alternative_buffer.getvalue()
            script = (ROOT/'scripts/verify_supported_apis.py').read_text()
            pin = re.search(r"org\.joml:joml:[0-9][0-9.]*", script)
            libs = []
            if pin or inherited or game_inherited or (hierarchy_info and hierarchy_info['location'] == 'library'):
                libs.append({'name':pin.group(0) if pin else 'org.joml:joml:1.0', 'downloads':{'artifact':{
                    'url':'https://fixture/library','sha1':hashlib.sha1(library).hexdigest(),'size':len(library)}}})
            if alternative is not None:
                libs[0]['rules'] = [{'action':'allow'}, {'action':'disallow','os':{'name':'osx'}}]
                libs.append({'name':'org.joml:joml:2.0', 'rules':[{'action':'allow','os':{'name':'osx'}}],
                             'downloads':{'artifact':{'url':'https://fixture/alternative',
                             'sha1':hashlib.sha1(alternative).hexdigest(),'size':len(alternative)}}})
            metadata = json.dumps({'downloads':{'client':{'url':'https://fixture/client',
                                   'sha1':hashlib.sha1(game_data).hexdigest(), 'size':len(game_data)}},
                                   'libraries':libs}).encode()
            manifest = json.dumps({'versions':[{'id':'fixture', 'type':'release', 'url':'https://fixture/meta',
                                   'sha1':hashlib.sha1(metadata).hexdigest()}]}).encode()
            mapping_url = 'https://maven.fabricmc.net/net/fabricmc/intermediary/fixture/intermediary-fixture-v2.jar'
            contents = {verifier.MANIFEST:manifest, 'https://fixture/meta':metadata,
                        'https://fixture/client':game_data, mapping_url:mapping,
                        mapping_url+'.sha1':hashlib.sha1(mapping).hexdigest().encode(),
                        'https://fixture/library':library, 'https://fixture/alternative':alternative}
            with patch.object(verifier, 'get', side_effect=lambda url: contents[url]):
                verifier.verify(jar, ['fixture'], None)

    def test_head_and_tail_reach_actual_entrypoint(self):
        self.fixture('HEAD', 'throw new RuntimeException();')
        self.fixture('TAIL', 'return;')
        with self.assertRaisesRegex(ValueError, 'no void return'):
            self.fixture('TAIL', 'throw new RuntimeException();')

    def test_unsupported_annotation_and_missing_target_fail(self):
        with self.assertRaisesRegex(ValueError, 'unsupported Mixin injection point|unsupported injection point'):
            self.fixture('INVOKE', 'return;')
        with self.assertRaisesRegex(ValueError, 'unsupported Inject options'):
            self.fixture('HEAD', 'return;', extra=', require=0')
        with self.assertRaisesRegex(ValueError, 'staticness|missing Mixin'):
            self.fixture('HEAD', 'return;', target_signature='(int x)')

    def test_nestmate_and_library_descriptor_reach_packaged_entrypoint(self):
        self.fixture('HEAD', 'return;', candidate_case='valid')
        self.fixture('HEAD', 'return;', self_cast=True)
        with self.assertRaisesRegex(ValueError, 'unsupported class use referencing a Mixin'):
            self.fixture('HEAD', 'return;', candidate_case='mixin-cross')
        with self.assertRaisesRegex(ValueError, 'private|nest'):
            self.fixture('HEAD', 'return;', candidate_case='broken')
        self.fixture('HEAD', 'return;', inherited='hidden')
        with self.assertRaisesRegex(ValueError, 'missing dependency class'):
            self.fixture('HEAD', 'return;', inherited='hidden-missing')

    def test_inherited_library_member_and_final_field_reach_entrypoint(self):
        self.fixture('HEAD', 'return;', inherited='valid')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            self.fixture('HEAD', 'return;', inherited='removed')
        with self.assertRaisesRegex(ValueError, 'final field write'):
            self.fixture('HEAD', 'return;', inherited='final')

    def test_game_owned_reference_inherits_runtime_library_members(self):
        self.fixture('HEAD', 'return;', game_inherited='valid')
        for case in ('removed', 'static', 'private', 'field-removed', 'field-static', 'field-private', 'platform-missing'):
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, 'missing|static|inaccessible|private'):
                self.fixture('HEAD', 'return;', game_inherited=case)

    def test_platform_library_variants_reach_entrypoint(self):
        script = (ROOT/'scripts/verify_supported_apis.py').read_text()
        if re.search(r'org\.joml:joml:[0-9][0-9.]*', script):
            self.skipTest('This adapter explicitly pins one JOML version; the 1.14 LWJGL metadata exercises platform rules')
        self.fixture('HEAD', 'return;', inherited='platform-valid')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            self.fixture('HEAD', 'return;', inherited='platform-missing')

    def test_default_mixin_parent_reaches_platform_derived_targets(self):
        # These are compiled game classes, packaged and checked via verifier.verify.
        # They exercise the static model, not an actual Mixin transformation.
        current = verifier.game_linkage.validate_product_hierarchies
        def previous_guard(nodes, targets, lookup, version):
            for name, target in targets.items():
                parent = nodes[name]['super']
                verifier.jvm_linkage.require(
                    verifier.jvm_linkage.is_subclass(lookup(target)['super'], parent, lookup),
                    'previous Mixin ancestry guard')
            return current(nodes, targets, lookup, version)
        with patch.object(verifier.game_linkage, 'validate_product_hierarchies', side_effect=previous_guard):
            with self.assertRaisesRegex(ValueError, 'previous Mixin ancestry guard'):
                self.fixture('HEAD', 'return;', target_hierarchy='runtime')
        for kind in ('object', 'runtime', 'indirect', 'enum', 'record'):
            with self.subTest(kind=kind):
                self.fixture('HEAD', 'return;', target_hierarchy=kind)
        for kind, error in (('missing', 'missing Mixin target|Mixin target descriptor is missing|missing game'),
                            ('missing-parent', 'missing direct supertype'),
                            ('interface', 'unsupported interface Mixin target')):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, error):
                self.fixture('HEAD', 'return;', target_hierarchy=kind)
        # A game-owned symbolic owner can resolve a platform member on the JVM.
        # The bounded resolver has no platform metadata, so it must fail closed.
        with self.assertRaisesRegex(ValueError, 'missing (?:member|game (?:members|references)).*getMessage'):
            self.fixture('HEAD', 'return;', target_hierarchy='runtime', candidate_case='platform-inherited')

    def test_hierarchy_and_mixin_helper_reach_packaged_entrypoint(self):
        # The former verifier checked only the library class's presence.
        with patch.object(verifier.game_linkage, 'validate_product_hierarchies', return_value=None):
            self.fixture('HEAD', 'return;', hierarchy='library-interface-hidden')
        for spec in ('library-interface-hidden', 'game-interface-hidden', 'candidate-interface-hidden',
                     'library-class-hidden', 'game-class-hidden', 'library-interface-kind',
                     'library-class-final', 'library-interface-sealed', 'library-interface-missing'):
            with self.subTest(spec=spec), self.assertRaisesRegex(ValueError, 'supertype|final class|dependency class'):
                self.fixture('HEAD', 'return;', hierarchy=spec)
        for spec in ('library-interface-public', 'game-class-public', 'candidate-interface-samepackage'):
            with self.subTest(spec=spec): self.fixture('HEAD', 'return;', hierarchy=spec)
        original = verifier.game_linkage.verify_game_instructions
        def previous_guard(nodes, targets, *args, **kwargs):
            for name, node in nodes.items():
                caller = targets.get(name, name)
                for use in node['uses']:
                    if use['operation'] == 'invokespecial' and use['name'] != '<init>':
                        verifier.jvm_linkage.require(use['owner'] == caller, 'previous owner guard')
            return original(nodes, targets, *args, **kwargs)
        with patch.object(verifier.game_linkage, 'verify_game_instructions', side_effect=previous_guard):
            with self.assertRaisesRegex(ValueError, 'previous owner guard'):
                self.fixture('HEAD', 'return;', mixin_helper=True)
        self.fixture('HEAD', 'return;', mixin_helper=True)


if __name__ == '__main__':
    unittest.main()
