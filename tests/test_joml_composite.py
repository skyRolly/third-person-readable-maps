"""Exercise JOML references inherited from a game class through the real adapter."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_supported_apis as verifier


class JomlCompositeTests(unittest.TestCase):
    def test_inherited_game_member_and_missing_member(self):
        javac = shutil.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {
                'com/mojang/math/Base.java': 'package com.mojang.math; public class Base { public void run() {} }',
                'org/joml/Api.java': 'package org.joml; public class Api extends com.mojang.math.Base {}',
                'game/Target.java': 'package game; public class Target { public void a() {} }',
                'net/minecraft/class_1.java': 'package net.minecraft; public class class_1 {}',
                'org/spongepowered/asm/mixin/Mixin.java':
                    'package org.spongepowered.asm.mixin; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface Mixin { Class<?>[] value(); }',
                'org/spongepowered/asm/mixin/injection/At.java':
                    'package org.spongepowered.asm.mixin.injection; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface At { String value(); }',
                'org/spongepowered/asm/mixin/injection/Inject.java':
                    'package org.spongepowered.asm.mixin.injection; import java.lang.annotation.*; '
                    '@Retention(RetentionPolicy.CLASS) public @interface Inject { String[] method(); At[] at(); }',
                'org/spongepowered/asm/mixin/injection/callback/CallbackInfo.java':
                    'package org.spongepowered.asm.mixin.injection.callback; public class CallbackInfo {}',
                'tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin.java':
                    'package tech.rolly.thirdpersonreadablemaps.mixin; '
                    'import org.spongepowered.asm.mixin.Mixin; import org.spongepowered.asm.mixin.injection.*; '
                    'import org.spongepowered.asm.mixin.injection.callback.CallbackInfo; '
                    '@Mixin(net.minecraft.class_1.class) public class ReadableMapLayerMixin { '
                    '@Inject(method="method_1", at=@At("HEAD")) private void inject(CallbackInfo c) {} }',
                'app/Caller.java':
                    'package app; public class Caller { public void invoke(org.joml.Api x) { x.run(); } }',
            }
            paths = []
            for name, text in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
                paths.append(str(path))
            classes = root / 'classes'
            subprocess.run([javac, '--release', '8', '-d', str(classes), *paths],
                           check=True, capture_output=True, timeout=60)

            def archive(entries):
                out = io.BytesIO()
                with ZipFile(out, 'w') as jar:
                    for name, content in entries.items():
                        jar.writestr(name, content)
                return out.getvalue()

            def klass(name):
                return (classes / (name + '.class')).read_bytes()

            mod = root / 'mod.jar'
            with ZipFile(mod, 'w') as jar:
                jar.writestr('fabric.mod.json', json.dumps({'depends': {'minecraft': '1.19.3'}}))
                jar.writestr('thirdpersonreadablemaps.mixins.json', json.dumps({
                    'required': True, 'injectors': {'defaultRequire': 1},
                    'package': 'tech.rolly.thirdpersonreadablemaps.mixin', 'client': ['ReadableMapLayerMixin']}))
                for name in ('app/Caller', 'tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin'):
                    jar.writestr(name + '.class', klass(name))
            library = archive({'org/joml/Api.class': klass('org/joml/Api')})
            mapping = archive({'mappings/mappings.tiny':
                               b'tiny\t2\t0\tofficial\tintermediary\nc\tgame/Target\tnet/minecraft/class_1\n'
                               b'\tm\t()V\ta\tmethod_1\n'})

            def verify_fixture():
                client = archive({'game/Target.class': klass('game/Target'),
                                  'com/mojang/math/Base.class': klass('com/mojang/math/Base')})
                def artifact(url, data):
                    return {'url': url, 'sha1': hashlib.sha1(data).hexdigest(), 'size': len(data)}
                metadata = json.dumps({'downloads': {'client': artifact('https://fixture/client', client)},
                                       'libraries': [{'name': 'org.joml:joml:1.10.5',
                                                      'downloads': {'artifact': artifact('https://fixture/joml', library)}}]}).encode()
                manifest = json.dumps({'versions': [{'id': 'fixture', 'type': 'release', 'url': 'https://fixture/meta',
                                                      'sha1': hashlib.sha1(metadata).hexdigest()}]}).encode()
                mapping_url = 'https://maven.fabricmc.net/net/fabricmc/intermediary/fixture/intermediary-fixture-v2.jar'
                data = {verifier.MANIFEST: manifest, 'https://fixture/meta': metadata,
                        'https://fixture/client': client, 'https://fixture/joml': library,
                        mapping_url: mapping, mapping_url + '.sha1': hashlib.sha1(mapping).hexdigest().encode()}
                with patch.object(verifier, 'get', side_effect=lambda url: data[url]):
                    verifier.verify(mod, ['fixture'])

            verify_fixture()
            base = root / 'com/mojang/math/Base.java'
            base.write_text('package com.mojang.math; public class Base {}', encoding='utf-8')
            subprocess.run([javac, '--release', '8', '-d', str(classes), str(base)],
                           check=True, capture_output=True, timeout=60)
            with self.assertRaisesRegex(ValueError, 'missing.*member|missing method'):
                verify_fixture()


if __name__ == '__main__':
    unittest.main()
