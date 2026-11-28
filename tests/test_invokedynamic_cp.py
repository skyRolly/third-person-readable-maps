"""An invokedynamic instruction must point to an InvokeDynamic constant."""
from pathlib import Path
import shutil
import java_toolchain
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import jvm_linkage


def constant_indices(data):
    count = struct.unpack_from('>H', data, 8)[0]
    offset, index, found = 10, 1, {}
    while index < count:
        tag = data[offset]
        offset += 1
        found.setdefault(tag, []).append(index)
        if tag == 1:
            size = struct.unpack_from('>H', data, offset)[0]
            offset += 2 + size
        elif tag in (3, 4, 9, 10, 11, 12, 17, 18):
            offset += 4
        elif tag in (5, 6):
            offset += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            offset += 2
        elif tag == 15:
            offset += 3
        else:
            raise AssertionError('unexpected fixture constant tag: ' + str(tag))
        index += 1
    return found


class InvokeDynamicConstantTests(unittest.TestCase):
    def test_valid_lambda_and_wrong_constant_tag(self):
        javac = java_toolchain.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'Fixture.java'
            source.write_text('public class Fixture { static final String TEXT="marker"; '
                              'Runnable get() { return () -> {}; } }', encoding='utf-8')
            subprocess.run([javac, '--release', '8', str(source)], check=True, capture_output=True, timeout=60)
            data = (root / 'Fixture.class').read_bytes()
            cp = constant_indices(data)
            self.assertTrue(jvm_linkage.parse(data)['dynamic_sites'])
            old = b'\xba' + struct.pack('>H', cp[18][0]) + b'\0\0'
            new = b'\xba' + struct.pack('>H', cp[8][0]) + b'\0\0'
            self.assertEqual(data.count(old), 1)
            with self.assertRaisesRegex(ValueError, 'invalid constant pool reference'):
                jvm_linkage.parse(data.replace(old, new, 1))


if __name__ == '__main__':
    unittest.main()
