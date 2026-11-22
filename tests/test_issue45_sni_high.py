"""Source and artifact controls for the scoped High Netty SNI investigation."""
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_sni_high as sni


class HighSniEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger, cls.priority, cls.critical, cls.scan, cls.mod = sni.load_inputs()
        cls.high = next(row for row in cls.priority['advisories'] if row['advisory_id'] == sni.HIGH)

    def test_unchanged_evidence_and_current_register(self):
        catalog, occurrences, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        review_raw = (ROOT / sni.REVIEW).read_bytes()
        current_raw = (ROOT / sni.CURRENT).read_bytes()
        expected = sni.make_review(self.ledger, self.critical, self.scan, catalog, occurrences, versions,
                                   (ROOT / sni.ARTIFACTS).read_bytes(), (ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_outputs(self.priority, review_raw, current_raw, expected)
        current = json.loads(current_raw)
        self.assertEqual((len(catalog), len(occurrences), len(versions)), (6, 12, 27))
        self.assertEqual(current['focused_coverage']['high_occurrences_without_focused_evidence'], 94)
        self.assertEqual(current['focused_coverage']['high_occurrences'], 83)
        self.assertTrue(all(row['release_blocking'] and not row['risk_accepted']
                            for advisory in current['advisories'] for row in advisory['occurrences']))
        ref = self.ledger['latest_focused_priority_register']
        self.assertEqual((ref['path'], ref['sha256']), (sni.CURRENT, hashlib.sha256(current_raw).hexdigest()))

    def test_duplicate_or_changed_source_and_scope_are_rejected(self):
        sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        for kind in ('duplicate', 'source', 'scope'):
            with self.subTest(kind=kind):
                high = copy.deepcopy(self.high)
                if kind == 'duplicate':
                    high['occurrences'][0] = copy.deepcopy(high['occurrences'][1])
                elif kind == 'source':
                    high['occurrences'][0]['source_sha'] = '0' * 40
                else:
                    high['occurrences'][0]['scopes'] = high['occurrences'][0]['scopes'][1:]
                with self.assertRaisesRegex(ValueError, 'missing or duplicate SNI occurrence|scope or disposition'):
                    sni.bind_occurrences(high, self.critical, self.scan, self.mod)

    def test_upstream_range_and_patched_boundaries(self):
        self.assertTrue(sni.affected_version('4.1.134.Final'))
        self.assertFalse(sni.affected_version('4.1.135.Final'))
        self.assertTrue(sni.affected_version('4.2.14.Final'))
        self.assertFalse(sni.affected_version('4.2.15.Final'))
        high = copy.deepcopy(self.high)
        high['affected_ranges']['pkg:maven/io.netty/netty-handler'][0][0]['events'][1]['fixed'] = '4.2.16.Final'
        with self.assertRaisesRegex(ValueError, 'OSV affected ranges differ'):
            sni.bind_occurrences(high, self.critical, self.scan, self.mod)

    def test_new_vanilla_caller_or_wrong_mod_source_is_not_cleared(self):
        sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        scan = copy.deepcopy(self.scan)
        scan['runtime_classpath_scan']['non_self_sni_handler_callers'].append({'class_file': 'new/Caller.class'})
        with self.assertRaisesRegex(ValueError, 'prior vanilla SNI scan'):
            sni.bind_occurrences(self.high, self.critical, scan, self.mod)
        mod = copy.deepcopy(self.mod)
        mod['groups'][self.high['occurrences'][0]['group']]['source_sha'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'mod JAR evidence differs'):
            sni.bind_occurrences(self.high, self.critical, self.scan, mod)

    def test_changed_review_or_register_cannot_be_presented_as_current(self):
        catalog, occurrences, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        artifact = (ROOT / sni.ARTIFACTS).read_bytes()
        expected = sni.make_review(self.ledger, self.critical, self.scan, catalog, occurrences, versions, artifact,
                                   (ROOT / sni.BASE_SCAN).read_bytes())
        review = (ROOT / sni.REVIEW).read_bytes()
        current = (ROOT / sni.CURRENT).read_bytes()
        sni.validate_outputs(self.priority, review, current, expected)
        altered = json.loads(review)
        altered['release_blocking'] = False
        with self.assertRaisesRegex(ValueError, 'review does not match'):
            sni.validate_outputs(self.priority, json.dumps(altered).encode(), current, expected)
        altered = json.loads(current)
        altered['focused_coverage']['high_occurrences'] = 84
        with self.assertRaisesRegex(ValueError, 'priority register does not match'):
            sni.validate_outputs(self.priority, review, json.dumps(altered).encode(), expected)

    def test_library_and_class_hashes_are_checked(self):
        def jar(value):
            out = BytesIO()
            with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
                archive.writestr('example/Handler.class', value)
            return out.getvalue()
        raw = jar(b'fixture')
        expected = {'version': 'fixture', 'sha1': hashlib.sha1(raw).hexdigest(),
                    'sha256': hashlib.sha256(raw).hexdigest(),
                    'classes': [{'path': 'example/Handler.class', 'sha256': hashlib.sha256(b'fixture').hexdigest()}]}
        self.assertEqual(sni.inspect_library(raw, expected), expected)
        with self.assertRaisesRegex(ValueError, 'library checksum mismatch'):
            sni.inspect_library(raw + b'x', expected)
        changed = jar(b'changed')
        changed_expected = dict(expected, sha1=hashlib.sha1(changed).hexdigest(),
                                sha256=hashlib.sha256(changed).hexdigest())
        with self.assertRaisesRegex(ValueError, 'class checksum mismatch'):
            sni.inspect_library(changed, changed_expected)

    def test_clienthello_scanner_finds_external_literal_and_rejects_bad_hash(self):
        import tempfile
        out = BytesIO()
        with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('example/Caller.class', b'example SslClientHelloHandler literal')
            archive.writestr('example/Unrelated.class', b'unrelated')
        raw = out.getvalue()
        artifact = {'cache_object': 'sample.jar', 'size_bytes': len(raw),
                    'sha1': hashlib.sha1(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'coordinates': ['example:dependency:1'], 'minecraft_versions': ['1.19'],
                    'class_files_scanned': 2}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            (cache / 'sample.jar').write_bytes(raw)
            observed = sni.inspect_cached_classpath_jar(cache, artifact, ['1.19'])
            self.assertEqual([row['class_file'] for row in observed['clienthello_name_references']],
                             ['example/Caller.class'])
            self.assertFalse(observed['clienthello_name_references'][0]['netty_handler_internal'])
            (cache / 'sample.jar').write_bytes(raw + b'x')
            with self.assertRaisesRegex(ValueError, 'artifact checksum mismatch'):
                sni.inspect_cached_classpath_jar(cache, artifact, ['1.19'])

    def test_clienthello_scan_cannot_hide_an_external_reference(self):
        _, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        original = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_base_scan(original, self.scan, self.critical, versions)
        altered = copy.deepcopy(original)
        row = next(item for item in altered['artifacts'] if not any(
            coord.startswith('io.netty:netty-handler:') for coord in item['coordinates']))
        row['clienthello_name_references'].append({'class_file': 'example/Caller.class',
                                                  'sha256': 'a' * 64, 'netty_handler_internal': False})
        altered['external_references'].append({'artifact_sha1': row['sha1'], 'class_file': 'example/Caller.class'})
        with self.assertRaisesRegex(ValueError, 'uncovered callers'):
            sni.validate_base_scan(altered, self.scan, self.critical, versions)


if __name__ == '__main__':
    unittest.main()
