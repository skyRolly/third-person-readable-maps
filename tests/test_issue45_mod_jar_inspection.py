import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_mod_jars as inspect


def archive(class_bytes):
    jar = BytesIO()
    with ZipFile(jar, 'w', ZIP_DEFLATED) as z:
        z.writestr('fabric.mod.json', json.dumps({'id': 'thirdpersonreadablemaps'}))
        z.writestr('example/Fixture.class', class_bytes)
    package = BytesIO()
    with ZipFile(package, 'w', ZIP_DEFLATED) as z:
        z.writestr('product.jar', jar.getvalue())
    raw = package.getvalue()
    return raw, {'archive_sha256': hashlib.sha256(raw).hexdigest(), 'artifact_filename': 'product.jar',
                 'artifact_sha256': hashlib.sha256(jar.getvalue()).hexdigest()}


class ModJarInspectionTests(unittest.TestCase):
    def test_real_source_bound_archives(self):
        result = inspect.collect()
        stored = json.loads((ROOT / 'docs/dependency-evidence/issue45-live-source-2026-11-22/mod-jar-literal-inspection.json').read_text())
        self.assertEqual(result, stored)
        self.assertEqual(len(result['groups']), 13)
        self.assertFalse(result['security_clearance'])
        self.assertTrue(all(row['classes'] for row in result['groups'].values()))

    def test_literal_reference_is_detected(self):
        clean, record = archive(b'fixture')
        self.assertFalse(inspect.inspect_archive(clean, record)['classes'][0]['matches'])
        changed, record = archive(b'fixture io/netty/handler/ssl/SniHandler')
        self.assertIn('io/netty/', inspect.inspect_archive(changed, record)['classes'][0]['matches'])
        self.assertIn('SniHandler', inspect.inspect_archive(changed, record)['classes'][0]['matches'])

    def test_corrupt_archive_and_wrong_jar_hash_fail(self):
        raw, record = archive(b'fixture')
        self.assertTrue(inspect.inspect_archive(raw, record)['classes'])
        with self.assertRaisesRegex(ValueError, 'archive checksum'):
            inspect.inspect_archive(raw + b'x', record)
        record['artifact_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'JAR checksum'):
            inspect.inspect_archive(raw, record)


if __name__ == '__main__':
    unittest.main()
