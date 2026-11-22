"""Source and static-evidence controls for the High Netty IP-filter review."""
import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import BytesIO, StringIO
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
import inspect_issue45_netty_ipfilter_high as ipfilter


class HighIpFilterEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.ledger, cls.v2, cls.target, cls.previous, cls.catalog,
         cls.versions, cls.prior) = ipfilter.context()
        cls.records = {path: (ROOT / path).read_bytes()
                       for path in (ipfilter.KNOWN, ipfilter.SCAN, ipfilter.FABRIC, ipfilter.PRODUCT)}
        cls.known, cls.scan, cls.fabric, cls.product = (json.loads(cls.records[path])
            for path in (ipfilter.KNOWN, ipfilter.SCAN, ipfilter.FABRIC, ipfilter.PRODUCT))

    def validate(self, known=None, scan=None, fabric=None, product=None):
        ipfilter.validate_inputs(self.ledger, self.prior, self.versions, self.catalog,
            self.known if known is None else known, self.scan if scan is None else scan,
            self.fabric if fabric is None else fabric, self.product if product is None else product)

    def test_source_bound_review_and_both_priority_registers(self):
        self.validate()
        review = ipfilter.make_review(self.ledger, self.target, self.previous, self.catalog,
                                      self.versions, self.records)
        review_raw = (ROOT / ipfilter.REVIEW).read_bytes()
        self.assertEqual(json.loads(review_raw), review)
        current_raw = (ROOT / ipfilter.CURRENT).read_bytes()
        current = json.loads(current_raw)
        self.assertEqual(current, ipfilter.make_register(self.v2, review, review_raw))
        self.assertEqual((review['occurrence_count'], review['source_group_count'],
                          review['minecraft_version_count']), (12, 10, 27))
        self.assertEqual(current['focused_coverage'], {'advisory_ids': 22, 'critical_occurrences': 22,
            'high_occurrences': 95, 'total_occurrences': 117, 'high_occurrences_without_focused_evidence': 82})
        self.assertTrue(all(row['release_blocking'] and not row['risk_accepted']
                            for advisory in current['advisories'] for row in advisory['occurrences']))
        ref = self.ledger['latest_focused_priority_register']
        self.assertEqual((ref['path'], ref['sha256']), (ipfilter.CURRENT, hashlib.sha256(current_raw).hexdigest()))
        out, err = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['inspect_issue45_netty_ipfilter_high.py']), \
             patch.object(ipfilter, 'download_mojang_library', side_effect=AssertionError('unexpected network')), \
             redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(ipfilter.main(), 0, err.getvalue())

    def test_changed_occurrence_identity_scope_or_blocker_is_rejected(self):
        ipfilter.validate_target(self.target, self.previous)
        for kind in ('duplicate', 'source', 'package', 'scope', 'blocking', 'accepted', 'range'):
            with self.subTest(kind=kind):
                target = copy.deepcopy(self.target)
                row = target['occurrences'][0]
                if kind == 'duplicate':
                    target['occurrences'][0] = copy.deepcopy(target['occurrences'][1])
                elif kind == 'source':
                    row['source_sha'] = '0' * 40
                elif kind == 'package':
                    row['purl'] = row['purl'].rsplit('@', 1)[0] + '@4.1.999.Final'
                elif kind == 'scope':
                    row['scopes'] = row['scopes'][1:]
                elif kind == 'blocking':
                    row['release_blocking'] = False
                elif kind == 'accepted':
                    row['risk_accepted'] = True
                else:
                    target['affected_ranges']['pkg:maven/io.netty/netty-handler'][0][0]['events'][-1]['fixed'] = '4.2.16.Final'
                with self.assertRaisesRegex(ValueError, 'IP-filter (occurrence|OSV)'):
                    ipfilter.validate_target(target, self.previous)

    def test_previous_register_cannot_be_replaced_with_a_rehashed_unreviewed_revision(self):
        original_inputs = ipfilter.sni.load_inputs()
        altered_ledger = copy.deepcopy(original_inputs[0])
        altered = copy.deepcopy(self.v2)
        unrelated = next(row for row in altered['advisories'] if row['advisory_id'] == 'GHSA-4jrv-ppp4-jm57')
        unrelated['follow_up'] = ['Changed without review']
        raw = (json.dumps(altered, indent=2, sort_keys=True) + '\n').encode()
        altered_ledger['sni_high_focused_priority_register']['sha256'] = hashlib.sha256(raw).hexdigest()
        inputs = (altered_ledger, *original_inputs[1:])
        real_read = ipfilter.sni.read
        def read_with_mutation(root, path, expected=None):
            if path == ipfilter.sni.CURRENT:
                self.assertEqual(expected, hashlib.sha256(raw).hexdigest())
                return raw
            return real_read(root, path, expected)
        with patch.object(ipfilter.sni, 'load_inputs', return_value=inputs), \
             patch.object(ipfilter.sni, 'read', side_effect=read_with_mutation):
            # With the cross-check removed, the rehashed ledger and unrelated
            # altered row would be accepted as the prior register.
            with patch.object(ipfilter.sni, 'validate_outputs', return_value=None):
                ipfilter.context()
            with self.assertRaisesRegex(ValueError, 'current priority register does not match source-bound review'):
                ipfilter.context()

    def test_runtime_scan_cannot_hide_or_forge_known_class_hits(self):
        self.validate()
        for kind in ('missing', 'duplicate', 'digest'):
            with self.subTest(kind=kind):
                scan = copy.deepcopy(self.scan)
                row = next(item for item in scan['artifacts'] if item['sha1'] == self.catalog[0]['sha1'])
                if kind == 'missing':
                    row['literal_hits'].pop()
                    scan['netty_internal_hits'] -= 1
                    reason = 'IP-filter known library hits differ'
                elif kind == 'duplicate':
                    row['literal_hits'].append(copy.deepcopy(row['literal_hits'][0]))
                    scan['netty_internal_hits'] += 1
                    reason = 'duplicate IP-filter class observation'
                else:
                    row['literal_hits'][0]['sha256'] = '0' * 64
                    reason = 'IP-filter known library hits differ'
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate(scan=scan)

    def test_runtime_scan_rejects_missing_artifact_or_external_hit(self):
        self.validate()
        scan = copy.deepcopy(self.scan)
        scan['artifacts'].pop()
        with self.assertRaisesRegex(ValueError, 'IP-filter scan coverage differs'):
            self.validate(scan=scan)
        scan = copy.deepcopy(self.scan)
        row = next(item for item in scan['artifacts'] if item['sha1'] not in {lib['sha1'] for lib in self.catalog})
        row['literal_hits'].append({'class_file': 'example/Caller.class', 'sha256': 'a' * 64,
                                    'terms': ['IpSubnetFilter']})
        scan['external_hits'].append({'sha1': row['sha1'], 'class_file': 'example/Caller.class'})
        with self.assertRaisesRegex(ValueError, 'external callers'):
            self.validate(scan=scan)

    def test_library_fabric_and_product_provenance_cannot_drift(self):
        self.validate()
        for field in ('version', 'sha256'):
            known = copy.deepcopy(self.known)
            known['libraries'][0][field] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'IP-filter library identity differs'):
                self.validate(known=known)
        known = copy.deepcopy(self.known)
        known['libraries'][0]['literal_hits'].pop()
        with self.assertRaisesRegex(ValueError, 'IP-filter known class coverage differs'):
            self.validate(known=known)
        fabric = copy.deepcopy(self.fabric)
        fabric['nested_jars'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Fabric static scan differs'):
            self.validate(fabric=fabric)
        product = copy.deepcopy(self.product)
        next(iter(product['groups'].values()))['classes'][0]['matches'].append('IpSubnetFilter')
        with self.assertRaisesRegex(ValueError, 'product static scan differs'):
            self.validate(product=product)
        with self.assertRaisesRegex(ValueError, 'Fabric loader checksum differs'):
            ipfilter.inspect_fabric(b'not the pinned JAR')

    def test_scanner_checks_class_literals_and_artifact_checksums(self):
        out = BytesIO()
        with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('example/Caller.class', b'IpSubnetFilter example')
            archive.writestr('example/Other.class', b'unrelated')
        raw = out.getvalue()
        count, hits = ipfilter.scan_jar(raw)
        self.assertEqual(count, 2)
        self.assertEqual(hits[0]['class_file'], 'example/Caller.class')
        self.assertEqual(hits[0]['terms'], ['IpSubnetFilter'])
        self.assertEqual(hits[0]['sha256'], hashlib.sha256(b'IpSubnetFilter example').hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fixture.jar').write_bytes(raw)
            artifact = {'cache_object': 'fixture.jar', 'size_bytes': len(raw),
                'sha1': hashlib.sha1(raw).hexdigest(), 'sha256': hashlib.sha256(raw).hexdigest(),
                'class_files_scanned': 2, 'coordinates': ['example:dependency:1'], 'minecraft_versions': ['1.19']}
            observed = ipfilter.scan_runtime_artifact(root, artifact, ['1.19'])
            self.assertEqual(observed['literal_hits'], hits)
            (root / 'fixture.jar').write_bytes(raw + b'changed')
            with self.assertRaisesRegex(ValueError, 'runtime artifact checksum differs'):
                ipfilter.scan_runtime_artifact(root, artifact, ['1.19'])

    def test_independent_jar_bytes_reject_matching_forged_class_digests(self):
        out = BytesIO()
        with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('example/Caller.class', b'IpSubnetFilter example')
            archive.writestr('example/Other.class', b'unrelated')
        raw = out.getvalue()
        count, hits = ipfilter.scan_jar(raw)
        library = {'version': 'fixture', 'sha1': hashlib.sha1(raw).hexdigest(),
                   'sha256': hashlib.sha256(raw).hexdigest(),
                   'classes': [{'path': 'example/Caller.class',
                                'sha256': hashlib.sha256(b'IpSubnetFilter example').hexdigest()}]}
        ipfilter.verify_known_library(raw, library, hits, count)
        forged_known = copy.deepcopy(hits)
        forged_known[0]['sha256'] = '0' * 64
        forged_scan = copy.deepcopy(forged_known)
        self.assertEqual(forged_known, forged_scan)  # the former cross-record comparison accepted this
        with self.assertRaisesRegex(ValueError, 'downloaded Netty class observations differ'):
            ipfilter.verify_known_library(raw, library, forged_known, count)

    def test_cli_requires_independent_download_verification_when_requested(self):
        def mutant(change):
            tree = ast.parse(inspect.getsource(ipfilter.main))
            for node in ast.walk(tree):
                if (isinstance(node, ast.If) and isinstance(node.test, ast.Attribute) and
                        node.test.attr == 'verify_known_download'):
                    calls = [statement for statement in node.body if isinstance(statement, ast.Expr) and
                             isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name)]
                    selected = [statement for statement in calls if statement.value.func.id ==
                                ('verify_known_downloads' if change == 'omit' else 'print')]
                    self.assertEqual(len(selected), 1)
                    if change == 'omit':
                        node.body.remove(selected[0])
                    else:
                        selected[0].value.args = [ast.Constant('Different success wording')]
                    break
            else:
                self.fail('download verification branch not found')
            namespace = {}
            exec(compile(ast.fix_missing_locations(tree), '<download-cli-mutation>', 'exec'),
                 ipfilter.__dict__, namespace)
            return namespace['main']

        def invoke(main, failure=False):
            out, err = StringIO(), StringIO()
            with patch.object(sys, 'argv', ['inspect_issue45_netty_ipfilter_high.py', '--verify-known-download']), \
                 patch.object(ipfilter, 'verify_known_downloads',
                              side_effect=ValueError('independent check failed') if failure else None) as verify, \
                 patch('socket.socket.connect', side_effect=AssertionError('unexpected network')), \
                 patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')), \
                 redirect_stdout(out), redirect_stderr(err):
                result = main()
            return result, err.getvalue(), verify

        def assert_success(main):
            result, error, verify = invoke(main)
            self.assertEqual(result, 0, error)
            verify.assert_called_once_with(self.catalog, self.prior, self.known)

        def assert_failure(main):
            result, error, verify = invoke(main, failure=True)
            self.assertEqual(result, 1)
            self.assertIn('independent check failed', error)
            verify.assert_called_once_with(self.catalog, self.prior, self.known)

        # A wording-only edit leaves both behavioral checks valid. Removing the
        # invocation fails both the call-count and failure-propagation controls.
        wording = mutant('wording')
        missing = mutant('omit')
        for main in (ipfilter.main, wording):
            assert_success(main)
            assert_failure(main)
        with self.assertRaises(AssertionError):
            assert_success(missing)
        with self.assertRaises(AssertionError):
            assert_failure(missing)

    def test_download_rejects_untrusted_urls_and_redirects_before_following(self):
        with patch.object(ipfilter, 'build_opener') as opener:
            with self.assertRaisesRegex(ValueError, 'invalid Mojang library URL'):
                ipfilter.download_mojang_library('https://example.invalid/netty.jar', 10)
            opener.assert_not_called()
        with self.assertRaisesRegex(ValueError, 'unexpected Mojang artifact redirect'):
            ipfilter.NoRedirect().redirect_request(None, None, 302, None, None, 'https://example.invalid/')

    def test_input_generation_cannot_silently_skip_requested_download_verification(self):
        out, err = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['inspect_issue45_netty_ipfilter_high.py', '--write-inputs',
                                       '--verify-known-download']), \
             patch.object(ipfilter, 'context') as context, redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(ipfilter.main(), 1)
        context.assert_not_called()
        self.assertIn('must run separately', err.getvalue())


if __name__ == '__main__':
    unittest.main()
