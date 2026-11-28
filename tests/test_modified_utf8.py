"""JVM constant-pool text uses modified UTF-8, including UTF-16 surrogate pairs."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import jvm_linkage
import verify_supported_apis as adapter


class ModifiedUtf8Tests(unittest.TestCase):
    def test_decoder_handles_nul_supplementary_and_rejects_invalid_sequences(self):
        decode = jvm_linkage.decode_modified_utf8
        self.assertEqual(decode(b'A\xc0\x80B'), 'A\0B')
        self.assertEqual(decode(b'\xed\xa0\x81\xed\xb0\x80'), '\U00010400')
        self.assertEqual(decode(b'\xed\xa0\x80'), '\ud800')
        for raw in (b'\0', b'\xc0\x81', b'\xc1\x80', b'\xe0\x80\x80', b'\xf0\x90\x90\x80', b'\xe2\x82'):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'modified UTF-8'):
                decode(raw)

    def test_both_class_readers_preserve_distinct_supplementary_names(self):
        javac = shutil.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'Fixture.java'
            source.write_text('public class Fixture { public void \U00010400() {} '
                              'public void \U00010401() {} }', encoding='utf-8')
            subprocess.run([javac, '-encoding', 'UTF-8', '--release', '8', str(source)],
                           check=True, capture_output=True, timeout=60)
            data = (root / 'Fixture.class').read_bytes()
            nodes = [jvm_linkage.parse(data),
                     (adapter.read_class(data) if hasattr(adapter, 'read_class') else adapter.parse_class(data))]
            for node in nodes:
                names = [member['name'] if isinstance(member, dict) else member[1] for member in node['members']]
                self.assertIn('\U00010400', names)
                self.assertIn('\U00010401', names)
            name_bytes = b'\xed\xa0\x81\xed\xb0\x80'
            self.assertEqual(data.count(name_bytes), 1)
            bad = data.replace(name_bytes, b'\0' + name_bytes[1:], 1)
            for read in (jvm_linkage.parse,
                         adapter.read_class if hasattr(adapter, 'read_class') else adapter.parse_class):
                with self.assertRaisesRegex(ValueError, 'modified UTF-8'):
                    read(bad)


if __name__ == '__main__':
    unittest.main()
