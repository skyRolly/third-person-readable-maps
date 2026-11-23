"""Source, artifact and bounded-observation controls for the Netty TLS review."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_netty_trust_high as trust


def make_jar(entries):
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for name, raw in entries:
            archive.writestr(name, raw)
    return output.getvalue()


class TrustEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.ledger, cls.v4, cls.target, cls.previous, cls.catalog, cls.versions,
         cls.prior, cls.mod, cls.clients, cls.index_ref, cls.index) = trust.context()
        paths = (trust.SCAN, trust.KNOWN, trust.FABRIC, trust.PRODUCT, trust.MANAGEMENT)
        cls.records = {path: (ROOT / path).read_bytes() for path in paths}
        cls.scan, cls.known, cls.fabric, cls.product, cls.management = (json.loads(cls.records[path]) for path in paths)

    def validate(self, scan=None, known=None, fabric=None, product=None, management=None):
        trust.validate_inputs(self.prior, self.versions, self.catalog, self.index_ref, self.index,
            self.scan if scan is None else scan, self.known if known is None else known,
            self.fabric if fabric is None else fabric, self.product if product is None else product,
            self.management if management is None else management)

    def test_review_covers_exact_sources_and_preserves_every_blocker(self):
        self.validate()
        review = trust.make_review(self.ledger, self.target, self.previous, self.known,
                                   self.management, self.records, self.prior)
        review_raw = (ROOT / trust.REVIEW).read_bytes()
        self.assertEqual(review, json.loads(review_raw))
        self.assertEqual((review['occurrence_count'], review['source_group_count'],
                          review['minecraft_version_count']), (12, 10, 27))
        fixed = review['fixed_version_example']
        self.assertEqual((fixed['minecraft_version'], fixed['scope'], fixed['handler']['coordinate']),
                         ('26.2', 'runtime/26.2', 'io.netty:netty-handler:4.2.15.Final'))
        self.assertFalse(fixed['security_clearance'])
        self.assertEqual(len({trust.sni.identity(row) for row in review['occurrences']}), 12)
        for row in review['occurrences']:
            self.assertTrue(row['release_blocking'])
            self.assertFalse(row['risk_accepted'])
            self.assertRegex(row['source_report_sha256_uncompressed'], r'^[a-f0-9]{64}$')
            self.assertRegex(row['source_report_archive_sha256'], r'^[a-f0-9]{64}$')
            self.assertRegex(row['product_jar_sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(all(len(game['version_metadata_sha256']) == 64 for game in row['minecraft_artifacts']))
        register_raw = (ROOT / trust.CURRENT).read_bytes()
        register = json.loads(register_raw)
        self.assertEqual(register, trust.make_register(self.v4, review, review_raw))
        self.assertEqual(register['focused_coverage'], {'advisory_ids': 24, 'critical_occurrences': 22,
            'high_occurrences': 120, 'total_occurrences': 142, 'high_occurrences_without_focused_evidence': 57})
        self.assertTrue(all(row['release_blocking'] and not row['risk_accepted']
                            for advisory in register['advisories'] for row in advisory['occurrences']))
        self.assertEqual(self.ledger['latest_focused_priority_register']['sha256'], trust.sha(register_raw))

    def test_occurrence_mutations_preserve_count_but_fail_identity_or_scope(self):
        trust.validate_target(self.target, self.previous)
        for kind in ('duplicate', 'source', 'package', 'scope', 'blocking', 'accepted', 'range'):
            with self.subTest(kind=kind):
                target = copy.deepcopy(self.target)
                row = target['occurrences'][0]
                if kind == 'duplicate':
                    target['occurrences'][0] = copy.deepcopy(target['occurrences'][1])
                elif kind == 'source':
                    row['source_sha'] = '0' * 40
                elif kind == 'package':
                    row['purl'] = row['purl'].replace('4.1.77.Final', '4.1.78.Final')
                elif kind == 'scope':
                    row['scopes'].pop()
                elif kind == 'blocking':
                    row['release_blocking'] = False
                elif kind == 'accepted':
                    row['risk_accepted'] = True
                else:
                    target['affected_ranges']['pkg:maven/io.netty/netty-handler'][0][0]['events'][1]['fixed'] = '4.2.16.Final'
                with self.assertRaisesRegex(ValueError, 'Trust Manager (occurrence|scope|affected ranges)'):
                    trust.validate_target(target, self.previous)

    def test_same_commit_wrong_audit_member_and_fingerprint_are_rejected(self):
        trust.report_hashes(self.target)
        for kind in ('member', 'fingerprint', 'scope', 'archive'):
            with self.subTest(kind=kind):
                target = copy.deepcopy(self.target)
                row = target['occurrences'][0]
                if kind == 'member':
                    row['source_report_member'] = 'gradle-tool-audit.json'
                elif kind == 'fingerprint':
                    row['fingerprint'] = '0' * 64
                elif kind == 'scope':
                    row['scopes'].pop()
                else:
                    row['source_report_archive_sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'Trust Manager report (provenance|finding) differs'):
                    trust.report_hashes(target)

    def test_prior_register_cannot_be_replaced_by_rehashed_unreviewed_data(self):
        bzip_context = trust.bzip.context()
        ledger = copy.deepcopy(bzip_context[0])
        altered = copy.deepcopy(self.v4)
        unrelated = next(row for row in altered['advisories'] if row['advisory_id'] == 'GHSA-4jrv-ppp4-jm57')
        unrelated['follow_up'] = ['Changed without a review']
        raw = (json.dumps(altered, indent=2, sort_keys=True) + '\n').encode()
        ledger['bzip2_high_focused_priority_register']['sha256'] = trust.sha(raw)
        fake_context = (ledger, *bzip_context[1:])
        original_read = trust.sni.read
        def read(root, path, expected=None):
            if path == trust.bzip.CURRENT:
                self.assertEqual(expected, trust.sha(raw))
                return raw
            return original_read(root, path, expected)
        with patch.object(trust.bzip, 'context', return_value=fake_context), \
             patch.object(trust.sni, 'read', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'historical Bzip2 register differs'):
                trust.context()
            # Without the reconstruction comparison, rehashing an unrelated
            # change would allow the prior register to be accepted.
            with patch.object(trust.bzip, 'make_register', return_value=altered):
                trust.context()

    def test_scan_rejects_missing_duplicate_or_rehashed_known_class_records(self):
        self.validate()
        for kind in ('missing_artifact', 'duplicate_artifact', 'missing_known', 'duplicate_class', 'source_hash',
                     'library_version'):
            with self.subTest(kind=kind):
                scan, known = copy.deepcopy(self.scan), copy.deepcopy(self.known)
                if kind == 'missing_artifact':
                    scan['artifacts'].pop()
                    reason = 'Trust Manager scan artifact coverage differs'
                elif kind == 'duplicate_artifact':
                    scan['artifacts'][0] = copy.deepcopy(scan['artifacts'][1])
                    reason = 'Trust Manager scan artifact coverage differs'
                else:
                    library = known['libraries'][0]
                    row = next(item for item in scan['artifacts'] if item['sha1'] == library['sha1'])
                    if kind == 'missing_known':
                        row['literal_hits'].pop()
                        library['literal_hits'].pop()
                        scan['handler_hits'] -= 1
                        reason = 'Trust Manager known handler hits differ'
                    elif kind == 'duplicate_class':
                        row['literal_hits'].append(copy.deepcopy(row['literal_hits'][0]))
                        reason = 'Trust Manager class observation differs'
                    elif kind == 'library_version':
                        library['version'] = '4.1.999.Final'
                        reason = 'Trust Manager known handler hits differ'
                    else:
                        row['sha256'] = '0' * 64
                        reason = 'Trust Manager artifact identity differs'
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate(scan=scan, known=known)

    def test_external_positive_cannot_be_hidden_or_given_a_forged_class_digest(self):
        self.validate()
        for kind in ('missing', 'digest'):
            with self.subTest(kind=kind):
                scan = copy.deepcopy(self.scan)
                hit = scan['external_hits'][0]
                row = next(item for item in scan['artifacts'] if item['sha1'] == hit['sha1'])
                if kind == 'missing':
                    row['literal_hits'].clear()
                    scan['external_hits'].pop(0)
                else:
                    row['literal_hits'][0]['sha256'] = '0' * 64
                    hit['sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'Trust Manager external observations differ'):
                    self.validate(scan=scan)

    def test_fabric_product_and_management_provenance_cannot_drift(self):
        self.validate()
        fabric = copy.deepcopy(self.fabric)
        fabric['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Trust Manager Fabric observations differ'):
            self.validate(fabric=fabric)
        product = copy.deepcopy(self.product)
        next(iter(product['groups'].values()))['jar_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Trust Manager product observations differ'):
            self.validate(product=product)
        management = copy.deepcopy(self.management)
        management['observations'][0]['selected_calls'].pop()
        with self.assertRaisesRegex(ValueError, 'management source observations differ'):
            self.validate(management=management)

    def test_independent_handler_bytes_reject_correlated_forged_hashes(self):
        prior, catalog = copy.deepcopy(self.prior), copy.deepcopy(self.catalog)
        scan, known = copy.deepcopy(self.scan), copy.deepcopy(self.known)
        library = catalog[0]
        old_sha1 = library['sha1']
        prior_row = next(row for row in prior['runtime_classpath_scan']['all_artifacts'] if row['sha1'] == old_sha1)
        scan_row = next(row for row in scan['artifacts'] if row['sha1'] == old_sha1)
        known_row = next(row for row in known['libraries'] if row['sha1'] == old_sha1)

        # Replace one handler with a complete synthetic pinned artifact while
        # preserving the real fixture's class count and all other source rows.
        entries = [(path, ('synthetic:' + path + ':').encode() + b'|'.join(t.encode() for t in trust.TERMS))
                   for path in sorted(trust.KNOWN_PATHS)]
        sni_classes = [(row['path'], ('sni:' + row['path']).encode()) for row in library['classes']]
        entries.extend(sni_classes)
        entries.extend(('fixture/Filler' + str(i) + '.class', b'no selected literals')
                       for i in range(prior_row['class_files_scanned'] - len(entries)))
        raw = make_jar(entries)
        identifier = hashlib.sha1(raw).hexdigest()
        digest = trust.sha(raw)
        count, hits = trust.scan_jar(raw)
        self.assertEqual(count, prior_row['class_files_scanned'])
        self.assertEqual({hit['class_file'] for hit in hits}, trust.KNOWN_PATHS)
        library.update(sha1=identifier, sha256=digest,
                       classes=[{'path': path, 'sha256': trust.sha(content)} for path, content in sni_classes])
        prior_row.update(sha1=identifier, sha256=digest, size_bytes=len(raw), cache_object=identifier)
        scan_row.update(sha1=identifier, sha256=digest, size_bytes=len(raw), literal_hits=copy.deepcopy(hits))
        known_row.update(sha1=identifier, sha256=digest, literal_hits=copy.deepcopy(hits))
        def validate():
            trust.validate_inputs(prior, self.versions, catalog, self.index_ref, self.index,
                                  scan, known, self.fabric, self.product, self.management)
        validate()
        trust.verify_known_handler(raw, library, count, known_row['literal_hits'])

        # A matching forged digest in both retained records passes consistency,
        # but independent verification against the same pinned JAR must fail.
        target = next(iter(sorted(trust.KNOWN_PATHS)))
        scan_hit = next(hit for hit in scan_row['literal_hits'] if hit['class_file'] == target)
        known_hit = next(hit for hit in known_row['literal_hits'] if hit['class_file'] == target)
        self.assertNotEqual(scan_hit['sha256'], '0' * 64)
        scan_hit['sha256'] = known_hit['sha256'] = '0' * 64
        self.assertEqual(scan_hit, known_hit)
        validate()
        with self.assertRaisesRegex(ValueError, 'downloaded Trust Manager handler hits differ'):
            trust.verify_known_handler(raw, library, count, known_row['literal_hits'])
        # Bypassing the actual class-byte scan would accept the paired forgery.
        with patch.object(trust, 'scan_jar', return_value=(count, known_row['literal_hits'])):
            trust.verify_known_handler(raw, library, count, known_row['literal_hits'])
        with self.assertRaisesRegex(ValueError, 'cached Netty library checksum mismatch'):
            trust.verify_known_handler(raw + b'x', library, count, hits)

    def test_representative_client_bytes_and_disassembly_must_match(self):
        class_file = 'example/Management.class'
        content = trust.TERMS[3].encode()
        raw = make_jar([(class_file, content)])
        row = {'client_size_bytes': len(raw), 'client_sha1': hashlib.sha1(raw).hexdigest(),
               'client_sha256': trust.sha(raw), 'class_files_scanned': 1}
        expected = {'class_file': class_file, 'class_sha256': trust.sha(content),
                    'selected_calls': list(trust.CALL_MARKERS)}
        output = '\n'.join('  // ' + marker for marker in trust.CALL_MARKERS)
        with patch.object(trust.subprocess, 'run', return_value=SimpleNamespace(stdout=output)) as javap:
            trust.verify_management_client_bytes(raw, row, expected, Path('javap'))
            self.assertEqual(javap.call_count, 1)
            self.assertTrue(javap.call_args.kwargs['check'])
            self.assertNotIn('GH_TOKEN', javap.call_args.kwargs['env'])
            javap.return_value.stdout = output.replace(trust.CALL_MARKERS[0], 'changed')
            with self.assertRaisesRegex(ValueError, 'management disassembly differs'):
                trust.verify_management_client_bytes(raw, row, expected, Path('javap'))
        bad = dict(expected, class_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'management client class scan differs'):
            trust.verify_management_client_bytes(raw, row, bad, Path('javap'))

    def test_cli_defaults_offline_and_propagates_optional_verification_failure(self):
        with patch.object(sys, 'argv', ['trust']), \
             patch.object(trust, 'build_opener', side_effect=AssertionError('unexpected network')), \
             patch.object(trust.ipfilter, 'download_mojang_library', side_effect=AssertionError('unexpected network')), \
             patch('socket.socket.connect', side_effect=AssertionError('unexpected network')), \
             patch('socket.socket.connect_ex', side_effect=AssertionError('unexpected network')), \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
            self.assertEqual(trust.main(), 0, error.getvalue())
        with patch.object(sys, 'argv', ['trust', '--verify-known-download', '--verify-management-download',
                                       '--verify-fixed-download',
                                       '--javap', 'synthetic-javap']), \
             patch.object(trust, 'verify_known_downloads') as known, \
             patch.object(trust, 'verify_management_download') as management, \
             patch.object(trust, 'verify_fixed_download') as fixed, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(trust.main(), 0)
            known.assert_called_once_with(self.catalog, self.prior, self.known)
            management.assert_called_once_with(self.clients, self.management, Path('synthetic-javap'))
            fixed.assert_called_once_with(trust.fixed_runtime_example(self.prior, self.target))
        for flag, name in (('--verify-known-download', 'verify_known_downloads'),
                           ('--verify-management-download', 'verify_management_download'),
                           ('--verify-fixed-download', 'verify_fixed_download')):
            argv = ['trust', flag]
            if flag == '--verify-management-download':
                argv.extend(['--javap', 'synthetic-javap'])
            with self.subTest(flag=flag), patch.object(sys, 'argv', argv), \
                 patch.object(trust, name, side_effect=ValueError('synthetic verification failure')), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
                self.assertEqual(trust.main(), 1)
                self.assertIn('synthetic verification failure', error.getvalue())

    def test_cli_rejects_incomplete_or_unused_cache_inputs_before_evidence_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, manifest = root / 'runtime-cache', root / 'manifest-cache'
            runtime.mkdir()
            manifest.mkdir()
            fabric, javap = root / 'fabric.jar', root / 'javap'
            fabric.write_bytes(b'valid-looking Fabric path')
            javap.write_bytes(b'valid-looking javap path')
            cases = {
                'manifest alone': ['--manifest-cache', str(manifest)],
                'fabric alone': ['--fabric-jar', str(fabric)],
                'manifest and Fabric without runtime': ['--manifest-cache', str(manifest),
                                                       '--fabric-jar', str(fabric)],
                'runtime alone': ['--runtime-cache', str(runtime)],
                'runtime and manifest without Fabric': ['--runtime-cache', str(runtime),
                                                        '--manifest-cache', str(manifest)],
                'runtime and Fabric without manifest': ['--runtime-cache', str(runtime),
                                                        '--fabric-jar', str(fabric)],
                'full cache set without javap': ['--runtime-cache', str(runtime),
                    '--manifest-cache', str(manifest), '--fabric-jar', str(fabric)],
                'javap alone': ['--javap', str(javap)],
                'unused cache input with download verification': ['--fabric-jar', str(fabric),
                                                                  '--verify-known-download'],
            }
            for label, options in cases.items():
                with self.subTest(case=label), \
                     patch.object(sys, 'argv', ['trust', *options]), \
                     patch.object(trust, 'context', wraps=trust.context) as load_evidence, \
                     patch.object(trust, 'build_opener', side_effect=AssertionError('unexpected network')), \
                     patch.object(trust.ipfilter, 'download_mojang_library',
                                  side_effect=AssertionError('unexpected network')), \
                     patch('socket.socket.connect', side_effect=AssertionError('unexpected network')), \
                     patch('socket.socket.connect_ex', side_effect=AssertionError('unexpected network')), \
                     redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()) as error:
                    self.assertEqual(trust.main(), 1)
                    if label == 'javap alone':
                        self.assertIn('--javap is only used by cached reinspection or --verify-management-download',
                                      error.getvalue())
                    else:
                        self.assertIn('Trust Manager investigation incomplete: cached reinspection requires',
                                      error.getvalue())
                    self.assertNotIn('Verified cached Trust Manager static observations offline', output.getvalue())
                    load_evidence.assert_not_called()

    def test_cli_regression_distinguishes_the_former_silent_acceptance(self):
        # This simulates deleting the new early guard: the old branch condition
        # ignores --manifest-cache and falls through to successful retained JSON.
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory)
            with patch.object(sys, 'argv', ['trust', '--manifest-cache', str(manifest)]), \
                 patch.object(trust, 'validate_cli_arguments'), \
                 patch.object(trust, 'build_opener', side_effect=AssertionError('unexpected network')), \
                 redirect_stdout(StringIO()) as output, redirect_stderr(StringIO()) as error:
                self.assertEqual(trust.main(), 0, error.getvalue())
                self.assertIn('Validated 12 blocking Trust Manager occurrences', output.getvalue())
                self.assertNotIn('Verified cached Trust Manager static observations offline', output.getvalue())

    def test_generation_modes_reject_only_inputs_they_cannot_consume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, manifest = root / 'runtime', root / 'manifest'
            fabric, javap = root / 'fabric.jar', root / 'javap'
            good = SimpleNamespace(runtime_cache=runtime, manifest_cache=None, fabric_jar=fabric,
                javap=None, write_inputs=True, write_review=False, verify_known_download=False,
                verify_management_download=False, verify_fixed_download=False)
            trust.validate_cli_arguments(good)
            good.manifest_cache = manifest
            with self.assertRaisesRegex(ValueError, '--write-inputs does not use --manifest-cache or --javap'):
                trust.validate_cli_arguments(good)
            good.manifest_cache = None
            good.javap = javap
            with self.assertRaisesRegex(ValueError, '--write-inputs does not use --manifest-cache or --javap'):
                trust.validate_cli_arguments(good)

    def test_management_download_accepts_javap_without_cache_inputs(self):
        with patch.object(sys, 'argv', ['trust', '--verify-management-download', '--javap', 'synthetic-javap']), \
             patch.object(trust, 'verify_management_download') as management, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
            self.assertEqual(trust.main(), 0, error.getvalue())
            management.assert_called_once_with(self.clients, self.management, Path('synthetic-javap'))

        with patch.object(sys, 'argv', ['trust', '--verify-management-download']), \
             patch.object(trust, 'context') as load_evidence, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
            self.assertEqual(trust.main(), 1)
            self.assertIn('--verify-management-download requires --javap', error.getvalue())
            load_evidence.assert_not_called()

    def test_untrusted_management_download_url_fails_before_network(self):
        clients = copy.deepcopy(self.clients)
        row = next(x for x in clients['games'] if x['minecraft_version'] == '26.1')
        row['client_url'] = 'https://example.invalid/client.jar'
        with patch.object(trust, 'build_opener', side_effect=AssertionError('unexpected network')):
            with self.assertRaisesRegex(ValueError, 'management client source differs'):
                trust.verify_management_download(clients, self.management, Path('javap'))

    def test_cached_reinspection_cli_runs_every_artifact_and_propagates_failures(self):
        by_sha = {row['sha1']: row for row in self.scan['artifacts']}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fabric_file = root / 'fabric.jar'
            fabric_file.write_bytes(b'synthetic Fabric bytes')
            (root / '26.2.json').write_bytes(b'synthetic manifest')
            argv = ['trust', '--runtime-cache', str(root), '--fabric-jar', str(fabric_file),
                    '--manifest-cache', str(root), '--javap', 'synthetic-javap']
            def scan(cache, artifact, versions):
                self.assertEqual(cache, root)
                self.assertEqual(versions, self.versions)
                return by_sha[artifact['sha1']]
            with patch.object(sys, 'argv', argv), \
                 patch.object(trust, 'scan_runtime_artifact', side_effect=scan) as inspect_artifact, \
                 patch.object(trust, 'inspect_fabric', return_value=self.fabric) as inspect_fabric, \
                 patch.object(trust.bzip, 'cache_bytes', side_effect=[b'synthetic client', b'synthetic handler']) as cached, \
                 patch.object(trust, 'verify_management_client_bytes') as management, \
                 patch.object(trust, 'verify_fixed_manifest_bytes') as manifest, \
                 patch.object(trust, 'verify_fixed_handler_bytes') as handler, \
                 patch('socket.socket.connect', side_effect=AssertionError('unexpected network')), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
                self.assertEqual(trust.main(), 0, error.getvalue())
                self.assertEqual(inspect_artifact.call_count, 471)
                inspect_fabric.assert_called_once_with(b'synthetic Fabric bytes')
                self.assertEqual(cached.call_count, 2)
                self.assertEqual(management.call_count, 1)
                self.assertEqual(management.call_args.args[0], b'synthetic client')
                self.assertEqual(management.call_args.args[-1], Path('synthetic-javap'))
                manifest.assert_called_once()
                self.assertEqual(manifest.call_args.args[0], b'synthetic manifest')
                handler.assert_called_once()
                self.assertEqual(handler.call_args.args[0], b'synthetic handler')
            with patch.object(sys, 'argv', argv), \
                 patch.object(trust, 'scan_runtime_artifact', side_effect=ValueError('cached verification failed')), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()) as error:
                self.assertEqual(trust.main(), 1)
                self.assertIn('cached verification failed', error.getvalue())

    def test_fixed_boundary_manifest_and_handler_are_source_bound(self):
        example = trust.fixed_runtime_example(self.prior, self.target)
        self.assertEqual(example['handler']['coordinate'], 'io.netty:netty-handler:4.2.15.Final')
        self.assertFalse(example['security_clearance'])
        wrong_source = copy.deepcopy(self.target)
        row = next(row for row in wrong_source['occurrences'] if row['group'] == '26.1-26.2')
        row['source_sha'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'fixed-boundary runtime inventory differs'):
            trust.fixed_runtime_example(self.prior, wrong_source)

        handler_bytes = b'synthetic pinned handler'
        handler = {'coordinate': 'io.netty:netty-handler:4.2.15.Final', 'url': 'https://example.invalid/handler.jar',
                   'sha1': hashlib.sha1(handler_bytes).hexdigest(), 'sha256': trust.sha(handler_bytes),
                   'size_bytes': len(handler_bytes)}
        manifest = {'libraries': [{'name': handler['coordinate'], 'downloads': {'artifact': {
            'url': handler['url'], 'sha1': handler['sha1'], 'size': handler['size_bytes']}}}]}
        raw = json.dumps(manifest).encode()
        fixture = {'handler': handler, 'manifest': {'size_bytes': len(raw),
                   'sha1': hashlib.sha1(raw).hexdigest(), 'sha256': trust.sha(raw)}}
        trust.verify_fixed_manifest_bytes(raw, fixture)
        trust.verify_fixed_handler_bytes(handler_bytes, fixture)
        manifest['libraries'][0]['name'] = 'io.netty:netty-handler:4.2.7.Final'
        changed = json.dumps(manifest).encode()
        fixture['manifest'].update(size_bytes=len(changed), sha1=hashlib.sha1(changed).hexdigest(),
                                   sha256=trust.sha(changed))
        with self.assertRaisesRegex(ValueError, 'fixed-boundary manifest handler entry differs'):
            trust.verify_fixed_manifest_bytes(changed, fixture)
        with self.assertRaisesRegex(ValueError, 'fixed-boundary handler checksum differs'):
            trust.verify_fixed_handler_bytes(handler_bytes + b'x', fixture)

    def test_untrusted_fixed_boundary_url_fails_before_network(self):
        example = trust.fixed_runtime_example(self.prior, self.target)
        example['manifest']['url'] = 'https://example.invalid/26.2.json'
        with patch.object(trust, 'build_opener', side_effect=AssertionError('unexpected network')):
            with self.assertRaisesRegex(ValueError, 'fixed-boundary source URL or size differs'):
                trust.verify_fixed_download(example)


if __name__ == '__main__':
    unittest.main()
