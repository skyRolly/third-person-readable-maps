import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import java_toolchain


class JavaToolchainTests(unittest.TestCase):
    def test_java_home_precedes_path_and_missing_tools_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'bin').mkdir()
            names = [name + ('.exe' if os.name == 'nt' else '') for name in ('java', 'javac')]
            for name in names:
                path = root / 'bin' / name
                path.touch()
                path.chmod(0o755)
            with patch.dict(os.environ, {'JAVA_HOME': str(root)}), \
                 patch.object(java_toolchain.shutil, 'which', return_value='/path/other'):
                for tool, name in zip(('java', 'javac'), names):
                    self.assertEqual(java_toolchain.which(tool), str(root / 'bin' / name))
                (root / 'bin' / names[1]).unlink()
                with self.assertRaisesRegex(FileNotFoundError, 'JAVA_HOME does not provide javac'):
                    java_toolchain.which('javac')

    def test_unset_java_home_uses_path(self):
        with patch.dict(os.environ, {'JAVA_HOME': ''}), \
             patch.object(java_toolchain.shutil, 'which', return_value='/path/javac') as search:
            self.assertEqual(java_toolchain.which('javac'), '/path/javac')
            search.assert_called_once_with('javac')
        with self.assertRaisesRegex(ValueError, 'unsupported JDK tool'):
            java_toolchain.which('other')


if __name__ == '__main__':
    unittest.main()
