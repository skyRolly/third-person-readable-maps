"""Exercise the intermediary packaged-JAR verifier, including Mixin injection points."""
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import verify_supported_apis as verifier


class IntermediaryEntrypointFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javac = shutil.which('javac')
        if not cls.javac:
            raise unittest.SkipTest('javac is required for packaged verifier fixtures')

    def fixture(self, point, body, extra='', target_signature='()', inherited=None, candidate_case=None):
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
            if inherited:
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public int value; public void run() {} }'
            if inherited and inherited.startswith('hidden'):
                sources['org/joml/Hidden.java'] = 'package org.joml; public class Hidden {}'
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public static Hidden value() { return null; } }'
            paths = []
            for name, source in sources.items():
                path=root/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text(source);paths.append(str(path))
            subprocess.run([self.javac, '--release', '8', '-d', str(support), *paths],
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
                                '@Mixin(net.minecraft.class_'+str(number)+'.class) public class '+mixin_name+' { '
                                '@Inject(method="method_'+str(number)+'", at=@At("'+injection+'")'+options+') '
                                'private void inject(CallbackInfo ci) {} }')
                mixin_paths.append(str(path))
            subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), *mixin_paths],
                           check=True, capture_output=True)
            if candidate_case:
                nest = root/'Nest.java'
                nest.write_text('package fixture; public class Nest { private int value; '
                                'static class Member { int read(Nest n) { return n.value; } } }')
                subprocess.run([self.javac, '--release', '21', '-d', str(out), str(nest)],
                               check=True, capture_output=True)
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
            game_buffer = io.BytesIO()
            with ZipFile(game_buffer, 'w') as z:
                for name in ('Target1', 'Target2'):
                    z.write(support/('game/'+name+'.class'), 'game/'+name+'.class')
            game_data = game_buffer.getvalue()
            map_buffer = io.BytesIO()
            with ZipFile(map_buffer, 'w') as z:
                z.writestr('mappings/mappings.tiny', 'tiny\t2\t0\tofficial\tintermediary\n'
                           'c\tgame/Target1\tnet/minecraft/class_1\n\tm\t()V\ta\tmethod_1\n'
                           'c\tgame/Target2\tnet/minecraft/class_2\n\tm\t()V\tb\tmethod_2\n')
            mapping = map_buffer.getvalue()
            library_buffer = io.BytesIO()
            with ZipFile(library_buffer, 'w') as z:
                if inherited:
                    z.write(support/'org/joml/Api.class', 'org/joml/Api.class')
                    if inherited == 'hidden':
                        z.write(support/'org/joml/Hidden.class', 'org/joml/Hidden.class')
            library = library_buffer.getvalue()
            alternative = None
            if inherited and inherited.startswith('platform-'):
                api = root/'org/joml/Api.java'
                method = '' if inherited == 'platform-missing' else 'public void run() {}'
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
            if pin or inherited:
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

    def test_platform_library_variants_reach_entrypoint(self):
        script = (ROOT/'scripts/verify_supported_apis.py').read_text()
        if re.search(r'org\.joml:joml:[0-9][0-9.]*', script):
            self.skipTest('This adapter explicitly pins one JOML version; the 1.14 LWJGL metadata exercises platform rules')
        self.fixture('HEAD', 'return;', inherited='platform-valid')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            self.fixture('HEAD', 'return;', inherited='platform-missing')


if __name__ == '__main__':
    unittest.main()
