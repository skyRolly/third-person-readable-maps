"""Array clone references are JVM operations, with checked component types."""
from pathlib import Path
import shutil
import java_toolchain
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import game_linkage
import jvm_linkage


class ArrayCloneLinkageTests(unittest.TestCase):
    def test_primitive_platform_and_game_arrays_with_negative_controls(self):
        javac = java_toolchain.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vector = root / 'com/mojang/math/Vector.java'
            vector.parent.mkdir(parents=True)
            vector.write_text('package com.mojang.math; public class Vector {}', encoding='utf-8')
            source = root / 'Fixture.java'
            source.write_text('public class Fixture { '
                              'Object a(String[] x) { return x.clone(); } '
                              'Object b(int[] x) { return x.clone(); } '
                              'Object c(com.mojang.math.Vector[] x) { return x.clone(); } }', encoding='utf-8')
            subprocess.run([javac, '--release', '8', '-d', str(root), str(vector), str(source)],
                           check=True, capture_output=True, timeout=60)
            node = jvm_linkage.parse((root / 'Fixture.class').read_bytes())
            component = dict(jvm_linkage.parse((root / 'com/mojang/math/Vector.class').read_bytes()), origin='game')
            nodes = {'Fixture': node}
            lookup = {'Fixture': dict(node, origin='candidate'), 'com/mojang/math/Vector': component}.get

            def verify(candidate, resolver):
                return game_linkage.verify_declared_libraries({}, {'Fixture': candidate}, {},
                                                              lambda _: None, 'fixture', class_lookup=resolver)

            verify(node, lookup)
            with self.assertRaisesRegex(ValueError, 'missing referenced class'):
                verify(node, {'Fixture': dict(node, origin='candidate')}.get)
            uses = [dict(use, name='unexpected') if use['owner'].startswith('[') else use for use in node['uses']]
            with self.assertRaisesRegex(ValueError, 'unsupported array member'):
                verify(dict(node, uses=uses), lookup)
            for invalid in ('[L;', '[Q'):
                uses = [dict(use, owner=invalid) if use['owner'].startswith('[') else use for use in node['uses']]
                with self.subTest(owner=invalid), self.assertRaisesRegex(ValueError, 'invalid array class'):
                    verify(dict(node, uses=uses), lookup)


if __name__ == '__main__':
    unittest.main()
