import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import sys
import tempfile
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
        stored = json.loads((ROOT / 'docs/dependency-evidence/issue45-live-source-2026-11-22/mod-jar-literal-inspection-v2.json').read_text())
        self.assertEqual(result, stored)
        self.assertEqual(len(result['groups']), 13)
        self.assertFalse(result['security_clearance'])
        self.assertTrue(all(row['classes'] for row in result['groups'].values()))

    def test_historical_inspection_survives_current_head_and_build_changes(self):
        expected = inspect.collect()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def copy(relative):
                dest = root / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, dest)
            for name in (inspect.INPUTS, inspect.HEADS_SNAPSHOT, inspect.BUILDS_SNAPSHOT):
                copy(name)
            inputs = json.loads((root / inspect.INPUTS).read_bytes())['groups']
            for row in inputs.values():
                copy(row['archive_path'])
            # Deliberately advance the mutable records; the archived reports
            # remain bound to their own source/build snapshots.
            current_heads = json.loads((ROOT / inspect.HEADS_SNAPSHOT).read_bytes())
            current_builds = json.loads((ROOT / inspect.BUILDS_SNAPSHOT).read_bytes())
            group = next(iter(current_builds))
            current_heads['groups'][group]['new_head'] = '0' * 40
            current_builds[group]['source_commit'] = '0' * 40
            current_builds[group]['sha256'] = '0' * 64
            for name, value in [('docs/version-consistency-1.0.0/current-heads.json', current_heads),
                                ('docs/version-consistency-1.0.0/current-validation/builds.json', current_builds)]:
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(value))
            self.assertEqual(inspect.collect(root), expected)
            # A changed historical snapshot cannot be substituted silently.
            snapshot = root / inspect.HEADS_SNAPSHOT
            snapshot.write_bytes(snapshot.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'historical source or build snapshot checksum mismatch'):
                inspect.collect(root)

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
