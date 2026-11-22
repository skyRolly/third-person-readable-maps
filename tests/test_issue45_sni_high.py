"""Source and artifact controls for the scoped High Netty SNI investigation."""
import copy
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
from io import BytesIO, StringIO
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_sni_high as sni
spec = importlib.util.spec_from_file_location('pr58_base_scan', ROOT / 'tests/fixtures/issue45_pr58_base_scan.py')
prior_scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior_scan)


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
        sni.validate_ledger_reference(self.ledger, current_raw)
        ref = self.ledger['sni_high_focused_priority_register']
        self.assertEqual((ref['path'], ref['sha256']), (sni.CURRENT, hashlib.sha256(current_raw).hexdigest()))

    def test_ledger_summary_fields_cannot_drift(self):
        raw = (ROOT / sni.CURRENT).read_bytes()
        sni.validate_ledger_reference(self.ledger, raw)
        for field, value in (('advisory_ids', 22), ('focused_occurrences', 106),
                             ('remaining_unfocused_high_occurrences', 93), ('security_clearance', True),
                             ('path', 'wrong.json'), ('sha256', '0' * 64)):
            with self.subTest(field=field):
                ledger = copy.deepcopy(self.ledger)
                ref = ledger['sni_high_focused_priority_register']
                ref[field] = value
                if field not in ('path', 'sha256'):
                    # PR #56's CI checked only these two fields and accepted this mutation.
                    self.assertEqual((ref['path'], ref['sha256']),
                                     (sni.CURRENT, hashlib.sha256(raw).hexdigest()))
                with self.assertRaisesRegex(ValueError, 'current priority ledger reference differs'):
                    sni.validate_ledger_reference(ledger, raw)

    def test_cli_fails_if_ledger_summary_changes(self):
        def invoke(ledger, remove_cli_check=False):
            out, err = StringIO(), StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(sys, 'argv', ['inspect_issue45_sni_high.py']))
                stack.enter_context(patch.object(sni, 'load_inputs', return_value=(
                    ledger, self.priority, self.critical, self.scan, self.mod)))
                stack.enter_context(redirect_stdout(out))
                stack.enter_context(redirect_stderr(err))
                if remove_cli_check:
                    stack.enter_context(patch.object(sni, 'validate_ledger_reference', return_value=None))
                result = sni.main()
            return result, out.getvalue(), err.getvalue()

        self.assertEqual(invoke(self.ledger)[0], 0)
        altered = copy.deepcopy(self.ledger)
        altered['sni_high_focused_priority_register']['focused_occurrences'] += 1
        result, _, error = invoke(altered)
        self.assertEqual(result, 1)
        self.assertIn('current priority ledger reference differs', error)
        # A missing main-to-validator call would accept the same stale ledger.
        self.assertEqual(invoke(altered, remove_cli_check=True)[0], 0)

    def test_evidence_writer_is_lf_stable_under_windows_text_translation(self):
        value = {'test': ['a', 'b']}
        expected = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')

        def windows_text_write(path, text, encoding=None, **kwargs):
            return path.write_bytes(text.replace('\n', '\r\n').encode(encoding or 'utf-8'))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(Path, 'write_text', windows_text_write):
                # This is the merged PR #56 writer, run under simulated Windows translation.
                legacy = root / 'legacy.json'
                legacy.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
                self.assertNotEqual(legacy.read_bytes(), expected)
                target = root / 'review.json'
                sni.write_new(target, value)
            raw = target.read_bytes()
            self.assertEqual(raw, expected)
            self.assertNotIn(b'\r\n', raw)
            self.assertEqual(hashlib.sha256(raw).digest(), hashlib.sha256(raw.replace(b'\r\n', b'\n')).digest())
            with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
                sni.write_new(target, {'changed': True})

    def test_writer_cannot_replace_file_created_after_existence_check(self):
        source = inspect.getsource(sni.write_new)
        self.assertEqual(source.count("path.open('xb')"), 1)
        mutant = {}
        exec(compile(source.replace("path.open('xb')", "path.open('wb')"),
                     '<exclusive-open-removed>', 'exec'), sni.__dict__, mutant)
        competitor = b'an independently created evidence record\n'
        real_open = Path.open
        with tempfile.TemporaryDirectory() as directory:
            def run(writer, name, exclusive):
                target = Path(directory) / name
                self.assertFalse(target.exists())
                def interleaved_open(path, mode='r', *args, **kwargs):
                    if path == target and mode in ('xb', 'wb'):
                        with real_open(path, 'wb') as other:
                            other.write(competitor)
                    return real_open(path, mode, *args, **kwargs)
                with patch.object(Path, 'open', interleaved_open):
                    if exclusive:
                        with self.assertRaises(FileExistsError) as error:
                            writer(target, {'new': True})
                        self.assertEqual(Path(error.exception.filename), target)
                    else:
                        writer(target, {'new': True})
                return target.read_bytes()
            self.assertNotEqual(run(mutant['write_new'], 'mutant.json', False), competitor)
            self.assertEqual(run(sni.write_new, 'protected.json', True), competitor)

    def test_regenerated_review_and_register_match_retained_bytes(self):
        catalog, occurrences, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        expected = sni.make_review(self.ledger, self.critical, self.scan, catalog, occurrences, versions,
                                   (ROOT / sni.ARTIFACTS).read_bytes(), (ROOT / sni.BASE_SCAN).read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review_path, register_path = root / 'review.json', root / 'register.json'
            sni.write_new(review_path, expected)
            review_raw = review_path.read_bytes()
            sni.write_new(register_path, sni.make_current_register(self.priority, expected, review_raw))
            current_raw = register_path.read_bytes()
            self.assertEqual(review_raw, (ROOT / sni.REVIEW).read_bytes())
            self.assertEqual(current_raw, (ROOT / sni.CURRENT).read_bytes())
            sni.validate_outputs(self.priority, review_raw, current_raw, expected)
            sni.validate_ledger_reference(self.ledger, current_raw)

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

    def test_unreviewed_schema_two_priority_is_not_used_as_historical_baseline(self):
        self.assertTrue(sni.load_inputs()[1]['security_clearance'] is False)
        mixed = copy.deepcopy(self.priority)
        mixed['schema'] = 2
        mixed['schema_note'] = 'mixed timestamps by source'
        row = next(item for item in mixed['advisories'] if item['advisory_id'] == sni.HIGH)
        row['modified'] = None
        row['modified_by_source'] = {'candidate|example': '2026-11-23T00:00:00Z'}
        with patch.object(sni.audits, 'priority_register', return_value=mixed):
            with self.assertRaisesRegex(ValueError, 'historical priority register does not match verified reports'):
                sni.load_inputs()

    def test_sni_register_builder_rejects_unsupported_priority_schemas(self):
        review_raw = (ROOT / sni.REVIEW).read_bytes()
        review = json.loads(review_raw)
        sni.make_current_register(self.priority, review, review_raw)
        source = inspect.getsource(sni.make_current_register)
        guard = ("    require(type(priority.get('schema')) is int and priority['schema'] == 1,\n"
                 "            'unsupported priority schema for retained SNI evidence')\n")
        self.assertEqual(source.count(guard), 1)
        mutant = {}
        exec(compile(source.replace(guard, ''), '<schema-check-removed>', 'exec'), sni.__dict__, mutant)
        for schema in (2, 3, True):
            with self.subTest(schema=schema):
                changed = copy.deepcopy(self.priority)
                changed['schema'] = schema
                self.assertEqual(mutant['make_current_register'](changed, review, review_raw)['schema'], schema)
                with self.assertRaisesRegex(ValueError, 'unsupported priority schema'):
                    sni.make_current_register(changed, review, review_raw)

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
        catalog, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        original = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_base_scan(original, self.scan, self.critical, versions, catalog)
        altered = copy.deepcopy(original)
        row = next(item for item in altered['artifacts'] if not any(
            coord.startswith('io.netty:netty-handler:') for coord in item['coordinates']))
        row['clienthello_name_references'].append({'class_file': 'example/Caller.class',
                                                  'sha256': 'a' * 64, 'netty_handler_internal': False})
        altered['external_references'].append({'artifact_sha1': row['sha1'], 'class_file': 'example/Caller.class'})
        with self.assertRaisesRegex(ValueError, 'uncovered callers'):
            sni.validate_base_scan(altered, self.scan, self.critical, versions, catalog)

    def test_known_literal_hits_cannot_be_removed_duplicated_or_changed(self):
        catalog, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        baseline = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_base_scan(baseline, self.scan, self.critical, versions, catalog)
        for kind in ('missing', 'duplicate', 'digest'):
            with self.subTest(kind=kind):
                altered = copy.deepcopy(baseline)
                row = next(r for r in altered['artifacts'] if r['sha1'] == catalog[0]['sha1'])
                hits = row['clienthello_name_references']
                hit = next(h for h in hits if h['class_file'].endswith('/SslClientHelloHandler.class'))
                if kind == 'missing':
                    hits.remove(hit)
                    altered['netty_handler_reference_count'] -= 1
                    reason = 'known Netty ClientHello class missing'
                elif kind == 'duplicate':
                    hits.append(copy.deepcopy(hit))
                    altered['netty_handler_reference_count'] += 1
                    reason = 'duplicate ClientHello class observation'
                else:
                    hit['sha256'] = '0' * 64
                    reason = 'known Netty ClientHello class digest differs'
                # Adjusted aggregates fool the merged validator in all three cases.
                prior_scan.validate_base_scan(altered, self.scan, self.critical, versions)
                with self.assertRaisesRegex(ValueError, reason):
                    sni.validate_base_scan(altered, self.scan, self.critical, versions, catalog)

    def test_cli_checks_known_hit_inventory_before_accepting_retained_review(self):
        baseline = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        catalog, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        sni.validate_base_scan(baseline, self.scan, self.critical, versions, catalog)
        altered = copy.deepcopy(baseline)
        row = next(r for r in altered['artifacts'] if r['sha1'] == catalog[0]['sha1'])
        row['clienthello_name_references'] = [h for h in row['clienthello_name_references']
                                             if not h['class_file'].endswith('/SslClientHelloHandler.class')]
        altered['netty_handler_reference_count'] -= 1
        prior_scan.validate_base_scan(altered, self.scan, self.critical, versions)
        real_read = sni.read
        def read_with_mutation(root, path, expected=None):
            return json.dumps(altered).encode() if path == sni.BASE_SCAN else real_read(root, path, expected)
        out, err = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['inspect_issue45_sni_high.py']), \
             patch.object(sni, 'read', side_effect=read_with_mutation), \
             redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(sni.main(), 1)
        self.assertIn('known Netty ClientHello class missing from scan', err.getvalue())

    def test_known_hit_catalog_is_bound_to_jar_and_version(self):
        catalog, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        baseline = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_base_scan(baseline, self.scan, self.critical, versions, catalog)
        for field, value in (('sha1', '0' * 40), ('sha256', '0' * 64), ('version', '4.1.999.Final')):
            with self.subTest(field=field):
                changed = copy.deepcopy(catalog)
                changed[0][field] = value
                # The former validator did not consult the library catalog.
                prior_scan.validate_base_scan(baseline, self.scan, self.critical, versions)
                with self.assertRaisesRegex(ValueError, 'known Netty library identity differs'):
                    sni.validate_base_scan(baseline, self.scan, self.critical, versions, changed)

        for kind in ('missing_class', 'changed_class_digest'):
            with self.subTest(kind=kind):
                changed = copy.deepcopy(catalog)
                classes = changed[0]['classes']
                hit = next(item for item in classes if item['path'].endswith('/AbstractSniHandler.class'))
                if kind == 'missing_class':
                    classes.remove(hit)
                else:
                    hit['sha256'] = '0' * 64
                prior_scan.validate_base_scan(baseline, self.scan, self.critical, versions)
                with self.assertRaisesRegex(ValueError, 'known Netty ClientHello class digest differs from library catalog'):
                    sni.validate_base_scan(baseline, self.scan, self.critical, versions, changed)

    def test_scan_artifact_identity_and_version_cannot_change(self):
        catalog, _, versions = sni.bind_occurrences(self.high, self.critical, self.scan, self.mod)
        baseline = json.loads((ROOT / sni.BASE_SCAN).read_bytes())
        sni.validate_base_scan(baseline, self.scan, self.critical, versions, catalog)
        for field in ('sha1', 'sha256', 'coordinates'):
            with self.subTest(field=field):
                altered = copy.deepcopy(baseline)
                row = next(r for r in altered['artifacts'] if r['sha1'] == catalog[0]['sha1'])
                row[field] = ['io.netty:netty-handler:4.1.999.Final'] if field == 'coordinates' else '0' * len(row[field])
                with self.assertRaisesRegex(ValueError, 'ClientHello artifact identity differs'):
                    sni.validate_base_scan(altered, self.scan, self.critical, versions, catalog)


if __name__ == '__main__':
    unittest.main()
