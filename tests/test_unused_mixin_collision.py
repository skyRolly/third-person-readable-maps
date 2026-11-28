"""Mixin declarations must be checked even when no instruction uses them."""
import io
from pathlib import Path
import shutil
import java_toolchain
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import game_linkage
import jvm_linkage


class UnusedMixinCollisionTests(unittest.TestCase):
    def test_unused_helper_collision_and_noncolliding_control(self):
        javac = java_toolchain.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'net/minecraft/Target.java'
            mixin = root / 'app/Mixin.java'
            target.parent.mkdir(parents=True)
            mixin.parent.mkdir(parents=True)
            target.write_text('package net.minecraft; public class Target {}', encoding='utf-8')
            mixin.write_text('package app; public class Mixin { private void helper() {} }', encoding='utf-8')
            subprocess.run([javac, '--release', '8', '-d', str(root), str(target), str(mixin)],
                           check=True, capture_output=True, timeout=60)
            mixin_node = jvm_linkage.parse((root / 'app/Mixin.class').read_bytes())
            self.assertFalse(any(use['name'] == 'helper' for use in mixin_node['uses']))

            def verify():
                buffer = io.BytesIO()
                with ZipFile(buffer, 'w') as jar:
                    jar.write(root / 'net/minecraft/Target.class', 'net/minecraft/Target.class')
                with ZipFile(io.BytesIO(buffer.getvalue())) as jar:
                    return game_linkage.verify_game_instructions(
                        {'app/Mixin': mixin_node}, {'app/Mixin': 'net/minecraft/Target'},
                        jar, {}, {}, {}, 'fixture')

            verify()
            target.write_text('package net.minecraft; public class Target { private void helper() {} }',
                              encoding='utf-8')
            subprocess.run([javac, '--release', '8', '-d', str(root), str(target)],
                           check=True, capture_output=True, timeout=60)
            with self.assertRaisesRegex(ValueError, 'Mixin member collision'):
                verify()


if __name__ == '__main__':
    unittest.main()
