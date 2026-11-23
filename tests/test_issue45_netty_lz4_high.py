"""Source, artifact, and boundary controls for the Netty Lz4FrameDecoder review."""
import copy
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_netty_lz4_high as lz4


class Lz4EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = lz4.baseline_context()
        cls.inputs = lz4.load_evidence(cls.baseline)
        (cls.advisory, cls.source_index, cls.runtime_scan, cls.server_scan, cls.fabric,
         cls.product, cls.fixed, cls.pipeline, cls.manifests) = cls.inputs

    def assertRejected(self, callback):
        with self.assertRaises((ValueError, KeyError, StopIteration)):
            callback()

    def test_retained_review_and_register_are_source_bound_and_blocking(self):
        baseline, review, register = lz4.validate_current()
        self.assertEqual(review['occurrence_count'], 12)
        self.assertEqual(review['source_group_count'], 10)
        self.assertEqual(review['minecraft_version_count'], 27)
        self.assertEqual(register['focused_coverage'], {
            'advisory_ids': 25, 'critical_occurrences': 22, 'high_occurrences': 132,
            'total_occurrences': 154, 'high_occurrences_without_focused_evidence': 45})
        self.assertEqual(len({(row['source_kind'], row['group'], row['purl'])
                              for row in review['occurrences']}), 12)
        self.assertTrue(all(occurrence['release_blocking'] and not occurrence['risk_accepted']
                            for advisory in register['advisories'] for occurrence in advisory['occurrences']))
        self.assertFalse(review['security_clearance'])
        self.assertFalse(register['security_clearance'])
        self.assertEqual(baseline['ledger']['trust_high_focused_priority_register']['path'], lz4.trust.CURRENT)

    def test_occurrence_mutations_fail_exact_audit_set_validation(self):
        mutations = {
            'missing': lambda target: target['occurrences'].pop(),
            'duplicate': lambda target: target['occurrences'].__setitem__(
                0, copy.deepcopy(target['occurrences'][1])),
            'source group': lambda target: target['occurrences'][0].update(group='unlisted-group'),
            'source commit': lambda target: target['occurrences'][0].update(source_sha='0' * 40),
            'package version': lambda target: target['occurrences'][0].update(
                purl='pkg:maven/io.netty/netty-codec@4.1.78.Final'),
            'scope': lambda target: target['occurrences'][0]['scopes'].append('runtime/1.20.4'),
            'fingerprint': lambda target: target['occurrences'][0].update(fingerprint='forged'),
            'report id': lambda target: target['occurrences'][0].update(source_report_artifact_id=0),
            'report archive': lambda target: target['occurrences'][0].update(
                source_report_archive_sha256='0' * 64),
            'report member': lambda target: target['occurrences'][0].update(
                source_report_member='different-report.json'),
            'dependency owner': lambda target: target['occurrences'][0].update(dependency_owner='mod-owned'),
            'disposition': lambda target: target['occurrences'][0].update(disposition='Fixed'),
            'blocking': lambda target: target['occurrences'][0].update(release_blocking=False),
            'risk acceptance': lambda target: target['occurrences'][0].update(risk_accepted=True),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                target = copy.deepcopy(self.baseline['target'])
                mutate(target)
                self.assertRejected(lambda: lz4.validate_occurrences(target, self.baseline['reports']))

    def test_runtime_inventory_mutations_fail_exact_artifact_and_class_checks(self):
        args = (self.baseline['prior'], self.baseline['versions'], self.manifests)
        mutations = {
            'missing artifact': lambda scan: scan['artifacts'].pop(),
            'duplicate artifact': lambda scan: scan['artifacts'].append(copy.deepcopy(scan['artifacts'][0])),
            'class digest': lambda scan: next(row for row in scan['artifacts']
                if row['coordinates'] == ['io.netty:netty-codec-compression:4.2.7.Final'])[
                    'decoder_reference_hits'][0].update(sha256='0' * 64),
            'invented caller': lambda scan: next(row for row in scan['artifacts']
                if row['coordinates'] == ['io.netty:netty-codec-compression:4.2.7.Final'])[
                    'decoder_reference_hits'].append({'class_file': 'net/minecraft/InjectedCaller.class',
                        'sha256': '0' * 64, 'terms': [lz4.TERMS[0]]}),
            'manifest sha': lambda scan: next(row for row in scan['artifacts']
                if row['coordinates'] == ['io.netty:netty-codec-compression:4.2.7.Final'])[
                    'manifest_artifacts'][0].update(manifest_sha1='0' * 40),
        }
        lz4.validate_runtime_scan(copy.deepcopy(self.runtime_scan), *args)
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                scan = copy.deepcopy(self.runtime_scan)
                mutate(scan)
                self.assertRejected(lambda: lz4.validate_runtime_scan(scan, *args))

    def test_server_inventory_mutations_fail_nested_identity_and_reference_checks(self):
        args = (self.baseline['prior'], self.baseline['versions'], self.manifests)
        lz4.validate_server_scan(copy.deepcopy(self.server_scan), *args)
        mutations = {
            'missing server': lambda scan: scan['servers'].pop(),
            'duplicate server': lambda scan: scan['servers'].append(copy.deepcopy(scan['servers'][0])),
            'nested class digest': lambda scan: next(item for row in scan['servers']
                for item in row['nested_jars'] if item['decoder_reference_hits'])[
                    'decoder_reference_hits'][0].update(sha256='0' * 64),
            'forged reference': lambda scan: next(row for row in scan['servers']
                if row['minecraft_version'] == '1.19')['decoder_reference_hits'].append({
                    'class_file': 'net/minecraft/InjectedCaller.class', 'sha256': '0' * 64,
                    'terms': [lz4.TERMS[0]]}),
            'class totals': lambda scan: next(row for row in scan['servers']
                if row['minecraft_version'] == '1.19').update(total_class_files_scanned=1),
        }
        for label, mutate in mutations.items():
            with self.subTest(mutation=label):
                scan = copy.deepcopy(self.server_scan)
                mutate(scan)
                self.assertRejected(lambda: lz4.validate_server_scan(scan, *args))

    def test_advisory_and_fixed_boundary_mutations_fail(self):
        lz4.advisory_ranges(self.advisory)
        advisory = copy.deepcopy(self.advisory)
        advisory['vulnerabilities'][0]['first_patched_version'] = '4.1.134.Final'
        self.assertRejected(lambda: lz4.advisory_ranges(advisory))
        args = (self.baseline, self.baseline['reports'], self.manifests)
        lz4.validate_fixed_scan(copy.deepcopy(self.fixed), *args)
        for label, mutate in (
            ('decoder class', lambda scan: scan['artifacts'][0]['codec']['decoder_reference_hits'][-1].update(
                sha256='0' * 64)),
            ('client manifest artifact', lambda scan: scan['artifacts'][0]['client'].update(sha1='0' * 40)),
            ('server bundle codec', lambda scan: scan['artifacts'][0]['server']['bundled_codec_compression'][0]
                .update(sha256='0' * 64)),
            ('fixed boundary coordinate', lambda scan: scan['artifacts'][0]['codec'].update(
                coordinate='io.netty:netty-codec-compression:4.2.14.Final')),
        ):
            with self.subTest(mutation=label):
                scan = copy.deepcopy(self.fixed)
                mutate(scan)
                self.assertRejected(lambda: lz4.validate_fixed_scan(scan, *args))

    def test_pipeline_mutations_fail_exact_jar_class_or_behavior_checks(self):
        lz4.validate_pipeline_observation(self.pipeline, self.runtime_scan, self.server_scan)
        for label, mutate in (
            ('client JAR identity', lambda row: row['client'].update(jar_sha256='0' * 64)),
            ('class digest', lambda row: row['client']['class_files']['net/minecraft/network/Connection.class']
                .update(sha256='0' * 64)),
            ('claimed LZ4 path', lambda row: row['server_inner'].update(
                connection_setup_compression=row['server_inner']['connection_setup_compression'] +
                '\\nLz4FrameDecoder')),
            ('Inflate evidence', lambda row: row['client'].update(
                compression_decoder_disassembly_lines=['ByteToMessageDecoder']))
        ):
            with self.subTest(mutation=label):
                observation = copy.deepcopy(self.pipeline)
                mutate(observation)
                self.assertRejected(lambda: lz4.validate_pipeline_observation(
                    observation, self.runtime_scan, self.server_scan))

    def test_full_cache_mode_consumes_each_required_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_cache, server_cache, fixed_cache = (root / name for name in
                ('runtime-cache', 'server-cache', 'fixed-cache'))
            manifest_cache = root / 'manifest-cache'
            for directory in (runtime_cache, server_cache, fixed_cache, manifest_cache):
                directory.mkdir()
            for game in lz4.ALL_MANIFEST_VERSIONS:
                (manifest_cache / (game + '.json')).write_bytes(
                    (ROOT / lz4.MANIFEST_DIR / (game + '.json')).read_bytes())
            fabric_jar = root / 'fabric-loader.jar'
            fabric_jar.write_bytes(b'fabric-cache-input')
            calls = []

            def runtime_builder(prior, versions, manifests, cache):
                calls.append(('runtime', cache.resolve()))
                return self.runtime_scan

            def server_builder(prior, versions, manifests, cache):
                calls.append(('server', cache.resolve()))
                return self.server_scan

            def cached_bytes(cache, relative, size, expected_sha1, expected_sha256):
                calls.append(('cache-bytes', cache.resolve(), str(relative)))
                return b'pipeline-client' if cache.resolve() == runtime_cache.resolve() else b'pipeline-server'

            out, err = StringIO(), StringIO()
            argv = ['inspect_issue45_netty_lz4_high.py', '--verify-cache',
                '--runtime-cache', str(runtime_cache), '--server-cache', str(server_cache),
                '--manifest-cache', str(manifest_cache), '--fabric-jar', str(fabric_jar),
                '--fixed-cache', str(fixed_cache)]
            with patch.object(sys, 'argv', argv), \
                 patch.object(lz4, 'validate_current', return_value=(self.baseline, None, None)), \
                 patch.object(lz4, 'build_runtime_scan', side_effect=runtime_builder), \
                 patch.object(lz4, 'build_server_scan', side_effect=server_builder), \
                 patch.object(lz4, 'build_fabric_scan', side_effect=lambda raw: calls.append(
                     ('fabric', raw)) or self.fabric), \
                 patch.object(lz4, 'build_fixed_scan', side_effect=lambda manifests, cache, baseline:
                     calls.append(('fixed', cache.resolve())) or self.fixed), \
                 patch.object(lz4, 'product_scan', side_effect=lambda: calls.append(('product',)) or self.product), \
                 patch.object(lz4, 'cache_bytes', side_effect=cached_bytes), \
                 patch.object(lz4, 'manifest_bytes', wraps=lz4.manifest_bytes) as manifest_reader, \
                 patch.object(lz4, '_sha256_from_server_scan_cache', return_value='0' * 64), \
                 patch.object(lz4, 'build_pipeline_observation', side_effect=lambda client, server:
                     calls.append(('pipeline', client, server)) or self.pipeline), \
                 patch.object(lz4, 'build_opener', side_effect=AssertionError('unexpected network access')), \
                 redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(lz4.main(), 0)
            self.assertEqual(err.getvalue(), '')
            self.assertIn(('runtime', runtime_cache.resolve()), calls)
            self.assertIn(('server', server_cache.resolve()), calls)
            self.assertIn(('fabric', b'fabric-cache-input'), calls)
            self.assertIn(('fixed', fixed_cache.resolve()), calls)
            self.assertIn(('product',), calls)
            self.assertIn(('pipeline', b'pipeline-client', b'pipeline-server'), calls)
            cache_reads = [call for call in calls if call[0] == 'cache-bytes']
            self.assertEqual(len(cache_reads), 2)
            client = next(row for row in lz4.ipfilter.selected_artifacts(
                self.baseline['prior'], self.baseline['versions'])
                if row['coordinates'] == ['minecraft-client:26.1.2'])
            self.assertEqual({(call[1], call[2]) for call in cache_reads}, {
                (runtime_cache.resolve(), client['cache_object']),
                (server_cache.resolve(), '26.1.2.jar')})
            self.assertEqual(manifest_reader.call_count, len(lz4.ALL_MANIFEST_VERSIONS))
            self.assertEqual(len(list(manifest_cache.glob('*.json'))), len(lz4.ALL_MANIFEST_VERSIONS))

    def test_default_cli_is_offline_and_rejects_unused_cache_arguments(self):
        out, err = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['inspect_issue45_netty_lz4_high.py']), \
             patch.object(lz4, 'build_opener', side_effect=AssertionError('unexpected network access')), \
             redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(lz4.main(), 0)
        self.assertIn('no security clearance', out.getvalue())
        self.assertEqual(err.getvalue(), '')

        for arguments, expected in (
            (['--verify-cache', '--runtime-cache', '/existing/runtime'],
             '--write-inputs and --verify-cache require'),
            (['--runtime-cache', '/existing/runtime'], 'cache inputs are only consumed'),
        ):
            with self.subTest(arguments=arguments):
                out, err = StringIO(), StringIO()
                with patch.object(sys, 'argv', ['inspect_issue45_netty_lz4_high.py', *arguments]), \
                     patch.object(lz4, 'build_opener', side_effect=AssertionError('unexpected network access')), \
                     redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(lz4.main(), 1)
                self.assertIn(expected, err.getvalue())
                self.assertNotIn('Validated 12 blocking Lz4', out.getvalue())

    def test_manifest_cache_rejects_paths_outside_the_supplied_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'manifest-cache'
            root.mkdir()
            outside = Path(tmp) / 'outside.json'
            outside.write_text('{}', encoding='utf-8')
            self.assertRejected(lambda: lz4.manifest_bytes('../outside', root))


if __name__ == '__main__':
    unittest.main()
