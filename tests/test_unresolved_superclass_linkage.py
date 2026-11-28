"""An opaque platform superclass must not be skipped before an interface default."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

import java_toolchain

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import game_linkage
import jvm_linkage


class UnresolvedSuperclassTests(unittest.TestCase):
    def test_platform_superclass_precedes_interface_default(self):
        javac, java = java_toolchain.which('javac'), java_toolchain.which('java')
        if not javac or not java:
            self.skipTest('JDK is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {
                'com/mojang/math/Face.java': 'package com.mojang.math; public interface Face { '
                    'default StackTraceElement[] getOurStackTrace() { return new StackTraceElement[0]; } }',
                'com/mojang/math/Api.java': 'package com.mojang.math; '
                    'public class Api extends RuntimeException implements Face {}',
                'com/mojang/math/RootApi.java': 'package com.mojang.math; public class RootApi implements Face {}',
                'com/mojang/math/OwnApi.java': 'package com.mojang.math; public class OwnApi extends RuntimeException '
                    'implements Face { public StackTraceElement[] getOurStackTrace() { return null; } }',
                'com/mojang/math/Base.java': 'package com.mojang.math; public class Base extends RuntimeException '
                    '{ public StackTraceElement[] getOurStackTrace() { return null; } }',
                'com/mojang/math/Derived.java': 'package com.mojang.math; public class Derived extends Base implements Face {}',
                'app/Caller.java': 'package app; public class Caller { public static void main(String[] args) { '
                    'new com.mojang.math.Api().getOurStackTrace(); } }',
            }
            paths = []
            for name, contents in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding='utf-8')
                paths.append(str(path))
            subprocess.run([javac, '--release', '8', '-d', str(root), *paths], check=True, capture_output=True)
            result = subprocess.run([java, '-cp', str(root), 'app.Caller'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('IllegalAccessError', result.stderr)
            nodes = {}
            for path in root.rglob('*.class'):
                node = jvm_linkage.parse(path.read_bytes())
                nodes[node['name']] = dict(node, origin='game')
            descriptor = '()[Ljava/lang/StackTraceElement;'
            for owner, declared in (('RootApi', 'Face'), ('OwnApi', 'OwnApi'), ('Derived', 'Base')):
                with self.subTest(owner=owner):
                    result = jvm_linkage.resolve_member('com/mojang/math/' + owner, 'method', 'getOurStackTrace',
                                                        descriptor, nodes.get)
                    self.assertEqual(result[0], 'com/mojang/math/' + declared)
            with self.assertRaisesRegex(ValueError, 'unresolved platform superclass'):
                jvm_linkage.resolve_member('com/mojang/math/Api', 'method', 'getOurStackTrace', descriptor, nodes.get)
            caller = dict(nodes['app/Caller'], origin='candidate')
            game = root / 'game.jar'
            with ZipFile(game, 'w') as jar:
                for path in (root / 'com/mojang/math').glob('*.class'):
                    jar.write(path, str(path.relative_to(root)))
            with ZipFile(game) as jar, self.assertRaisesRegex(ValueError, 'unresolved platform superclass'):
                game_linkage.verify_game_instructions({'app/Caller': caller}, {}, jar, {}, {}, {}, 'fixture')


if __name__ == '__main__':
    unittest.main()
