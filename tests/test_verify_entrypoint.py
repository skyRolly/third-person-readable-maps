"""Exercise the production verifier with packaged Mixin and game fixtures."""
import hashlib
import io
import json
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


class OfficialEntrypointFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javac = shutil.which('javac')
        if not cls.javac:
            raise unittest.SkipTest('javac is required for packaged verifier fixtures')
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.addClassCleanup(cls.temp.cleanup)

    def compile_source(self, relative, source, out, classpath=None):
        path = self.root/'src'/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        command = [self.javac, '--release', '8', '-d', str(out)]
        if classpath: command += ['-classpath', str(classpath)]
        subprocess.run(command+[str(path)], check=True, capture_output=True)

    def fixture(self, point, body, extra='', target_signature='()', inherited=None):
        with tempfile.TemporaryDirectory(dir=self.root) as directory:
            root = Path(directory); support = root/'support'; support.mkdir()
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
                'net/minecraft/client/renderer/entity/layers/ItemInHandLayer.java':
                    'package net.minecraft.client.renderer.entity.layers; public class ItemInHandLayer { '
                    'public void submitArmWithItem'+target_signature+' { '+body+' } }',
            }
            if inherited:
                sources['org/joml/Api.java'] = 'package org.joml; public class Api { public int value; public void run() {} }'
            paths = []
            for name, source in sources.items():
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source); paths.append(str(path))
            subprocess.run([self.javac, '--release', '8', '-d', str(support), *paths],
                           check=True, capture_output=True)
            mixin = root/'ReadableMapLayerMixin.java'
            mixin.write_text('package tech.rolly.thirdpersonreadablemaps.mixin; '
                             'import org.spongepowered.asm.mixin.Mixin; '
                             'import org.spongepowered.asm.mixin.injection.*; '
                             'import org.spongepowered.asm.mixin.injection.callback.CallbackInfo; '
                             'import net.minecraft.client.renderer.entity.layers.ItemInHandLayer; '
                             '@Mixin(ItemInHandLayer.class) public class ReadableMapLayerMixin { '
                             '@Inject(method="submitArmWithItem", at=@At("'+point+'")'+extra+') '
                             'private void inject(CallbackInfo ci) {} }')
            out = root/'mod'; out.mkdir()
            subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(mixin)],
                           check=True, capture_output=True)
            if inherited:
                caller = root/'Caller.java'
                caller.write_text('package app; public class Caller extends org.joml.Api { '
                                  'public void invoke() { run(); value = 1; } }')
                subprocess.run([self.javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(caller)],
                               check=True, capture_output=True)
                if inherited in ('final', 'removed'):
                    api = root/'org/joml/Api.java'
                    member = 'public final int value = 0; public void run() {}' if inherited == 'final' else 'public int value;'
                    api.write_text('package org.joml; public class Api { '+member+' }')
                    subprocess.run([self.javac, '--release', '8', '-d', str(support), str(api)],
                                   check=True, capture_output=True)
            game_buf = io.BytesIO()
            with ZipFile(game_buf, 'w') as z:
                path = 'net/minecraft/client/renderer/entity/layers/ItemInHandLayer.class'
                z.write(support/path, path)
            game_data = game_buf.getvalue()
            props = (ROOT/'gradle.properties').read_text()
            declared = '26.3' if 'minecraft_version=26.3' in props else ['26.1']
            jar = root/'candidate.jar'
            with ZipFile(jar, 'w') as z:
                z.writestr('fabric.mod.json', json.dumps({'depends':{'minecraft':declared}}))
                z.writestr('thirdpersonreadablemaps.mixins.json', json.dumps({
                    'required':True, 'package':'tech.rolly.thirdpersonreadablemaps.mixin',
                    'client':['ReadableMapLayerMixin'], 'injectors':{'defaultRequire':1}}))
                name = 'tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin.class'
                z.write(out/name, name)
                if inherited:
                    z.write(out/'app/Caller.class', 'app/Caller.class')
            library_buf = io.BytesIO()
            with ZipFile(library_buf, 'w') as z:
                if inherited:
                    z.write(support/'org/joml/Api.class', 'org/joml/Api.class')
            library = library_buf.getvalue()
            alternative = None
            if inherited and inherited.startswith('platform-'):
                api = root/'org/joml/Api.java'
                method = '' if inherited == 'platform-missing' else 'public void run() {}'
                api.write_text('package org.joml; public class Api { public int value; public int extra; '+method+' }')
                subprocess.run([self.javac, '--release', '8', '-d', str(support), str(api)],
                               check=True, capture_output=True)
                alternative_buf = io.BytesIO()
                with ZipFile(alternative_buf, 'w') as z:
                    z.write(support/'org/joml/Api.class', 'org/joml/Api.class')
                alternative = alternative_buf.getvalue()
            libraries = [] if not inherited else [{'name':'org.joml:joml:1.0', 'downloads':{'artifact':{
                'url':'https://fixture/library','sha1':hashlib.sha1(library).hexdigest(),'size':len(library)}}}]
            if alternative is not None:
                libraries[0]['rules'] = [{'action':'allow'}, {'action':'disallow','os':{'name':'osx'}}]
                libraries.append({'name':'org.joml:joml:2.0', 'rules':[{'action':'allow','os':{'name':'osx'}}],
                                  'downloads':{'artifact':{'url':'https://fixture/alternative',
                                  'sha1':hashlib.sha1(alternative).hexdigest(),'size':len(alternative)}}})
            metadata = json.dumps({'downloads':{'client':{'url':'https://fixture/client',
                                   'sha1':hashlib.sha1(game_data).hexdigest(), 'size':len(game_data)}},
                                   'libraries':libraries}).encode()
            manifest = json.dumps({'versions':[{'id':'fixture', 'type':'release', 'url':'https://fixture/meta',
                                   'sha1':hashlib.sha1(metadata).hexdigest()}]}).encode()
            contents = {verifier.MANIFEST:manifest, 'https://fixture/meta':metadata,
                        'https://fixture/client':game_data, 'https://fixture/library':library,
                        'https://fixture/alternative':alternative}
            with patch.object(verifier, 'get', side_effect=lambda url: contents[url]):
                verifier.verify(jar, ['fixture'], None)

    def test_head_and_tail_reach_actual_entrypoint(self):
        self.fixture('HEAD', 'throw new RuntimeException();')
        self.fixture('TAIL', 'return;')
        validate = verifier.jvm_linkage.validate_injection_point
        # Reproduce the former entry-point wiring: it forced HEAD for TAIL.
        with patch.object(verifier.jvm_linkage, 'validate_injection_point',
                          side_effect=lambda node, name, desc, point: validate(node, name, desc, 'HEAD')):
            self.fixture('TAIL', 'throw new RuntimeException();')
        with self.assertRaisesRegex(ValueError, 'no void return'):
            self.fixture('TAIL', 'throw new RuntimeException();')

    def test_unsupported_annotation_and_missing_target_fail(self):
        with self.assertRaisesRegex(ValueError, 'unsupported injection point'):
            self.fixture('INVOKE', 'return;')
        with self.assertRaisesRegex(ValueError, 'unsupported Inject options'):
            self.fixture('HEAD', 'return;', extra=', require=0')
        with self.assertRaisesRegex(ValueError, 'target descriptor is missing'):
            self.fixture('HEAD', 'return;', target_signature='(int x)')

    def test_inherited_library_member_and_final_field_reach_entrypoint(self):
        self.fixture('HEAD', 'return;', inherited='valid')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            self.fixture('HEAD', 'return;', inherited='removed')
        with self.assertRaisesRegex(ValueError, 'final field write'):
            self.fixture('HEAD', 'return;', inherited='final')

    def test_platform_library_variants_reach_entrypoint(self):
        self.fixture('HEAD', 'return;', inherited='platform-valid')
        with self.assertRaisesRegex(ValueError, 'missing member'):
            self.fixture('HEAD', 'return;', inherited='platform-missing')


if __name__ == '__main__':
    unittest.main()
