"""The packaged verifier must read long and double annotation values."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import verify_supported_apis as verifier


class AnnotationConstantsTests(unittest.TestCase):
    def test_long_and_double_values_remain_available(self):
        javac = shutil.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'Fixture.java'
            source.write_text(
                'import java.lang.annotation.*;\n'
                '@Retention(RetentionPolicy.RUNTIME) @interface Values { long count(); double ratio(); }\n'
                '@Values(count=0x1122334455667788L, ratio=3.25) public class Fixture {}\n', encoding='utf-8')
            subprocess.run([javac, '--release', '17', str(source)], check=True, capture_output=True, timeout=60)
            values = verifier.read_class((root / 'Fixture.class').read_bytes())['annotations']['LValues;']
            self.assertEqual(values['count'], 0x1122334455667788)
            self.assertEqual(values['ratio'], struct.unpack('>Q', struct.pack('>d', 3.25))[0])


if __name__ == '__main__':
    unittest.main()
