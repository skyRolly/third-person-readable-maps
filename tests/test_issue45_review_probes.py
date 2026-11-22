"""Offline cache, redirect, and output-path regressions for Issue #45 tools."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21/issue45-review-2026-11-22/historical-scripts'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_module('issue45_probe', ROOT / 'scripts/probe_dependency_reachability.py')
old_probe = load_module('old_issue45_probe', HISTORICAL / 'probe_dependency_reachability.py')
inspector = load_module('issue45_netty_inspector', ROOT / 'scripts/inspect_netty_manifest_artifacts.py')
old_inspector = load_module('old_issue45_netty_inspector', HISTORICAL / 'inspect_netty_manifest_artifacts.py')


def spec_for(data):
    return {'url': 'https://repo.maven.apache.org/maven2/example.jar',
            'checksum_url': 'https://repo.maven.apache.org/maven2/example.jar.sha256',
            'size': len(data), 'sha1': hashlib.sha1(data).hexdigest(),
            'sha256': hashlib.sha256(data).hexdigest(),
            'verified_against': 'Previously recorded upstream checksum'}


class Response:
    def __init__(self, url, data, final_url=None):
        self.url, self.data, self.final_url = url, data, final_url or url
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.final_url
    def read(self, size=-1):
        return self.data[:size] if size >= 0 else self.data


class ProbeCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name)
        self.data = b'fixed local artifact for cache verification'
        self.spec = spec_for(self.data)

    def test_cached_set_and_manifest_need_no_network(self):
        specs = [self.spec, spec_for(b'another verified cache entry')]
        for item, data in zip(specs, (self.data, b'another verified cache entry')):
            (self.cache / item['sha1']).write_bytes(data)
        manifest = json.dumps({'id': '1.0'}).encode()
        manifest_spec = {'url': 'https://piston-meta.mojang.com/v1/1.0.json',
                         'sha1': hashlib.sha1(manifest).hexdigest()}
        (self.cache / manifest_spec['sha1']).write_bytes(manifest)
        with patch.object(probe, 'build_opener', side_effect=AssertionError('network used')):
            for item in specs:
                provenance = {}
                self.assertTrue(probe.verified_artifact(item, self.cache, False, provenance).exists())
                self.assertEqual(provenance['upstream_checksum'], 'not_retrieved_offline')
                self.assertEqual(provenance['previously_recorded_provenance'], item['verified_against'])
            self.assertEqual(probe.verified_minecraft_manifest('1.0', manifest_spec, self.cache, False)['id'], '1.0')
        # The previous implementation attempted to fetch the sidecar here.
        with patch.object(old_probe, 'urlopen', side_effect=AssertionError('unexpected network access')):
            with self.assertRaisesRegex(AssertionError, 'unexpected network access'):
                old_probe.verified_artifact(self.spec, self.cache, False)

    def test_missing_and_corrupt_cache_fail_without_network(self):
        with patch.object(probe, 'build_opener', side_effect=AssertionError('network used')):
            with self.assertRaisesRegex(ValueError, 'missing cached artifact'):
                probe.verified_artifact(self.spec, self.cache, False)
            (self.cache / self.spec['sha1']).write_bytes(b'X' + self.data[1:])
            with self.assertRaisesRegex(ValueError, 'artifact size or digest mismatch'):
                probe.verified_artifact(self.spec, self.cache, False)
            (self.cache / self.spec['sha1']).write_bytes(self.data)
            with self.assertRaisesRegex(ValueError, 'artifact size or digest mismatch'):
                probe.verified_artifact(dict(self.spec, sha256='a' * 64), self.cache, False)

    def test_explicit_download_checks_artifact_and_sidecar(self):
        calls = []
        spec, data = self.spec, self.data
        class Opener:
            def open(self, url, timeout):
                calls.append(url)
                return Response(url, spec['sha256'].encode() if url.endswith('.sha256') else data)
        provenance = {}
        with patch.object(probe, 'build_opener', return_value=Opener()):
            result = probe.verified_artifact(spec, self.cache, True, provenance)
        self.assertEqual(result.read_bytes(), data)
        self.assertEqual(calls, [spec['url'], spec['checksum_url']])
        self.assertEqual(provenance['artifact_source'], 'download')
        self.assertEqual(provenance['upstream_checksum'], 'retrieved_and_verified')
        calls.clear()
        with patch.object(probe, 'build_opener', return_value=Opener()):
            probe.verified_artifact(spec, self.cache, True)
        self.assertEqual(calls, [spec['checksum_url']])
        (self.cache / spec['sha1']).unlink()
        class WrongSidecar(Opener):
            def open(self, url, timeout):
                return Response(url, b'0' * 64 if url.endswith('.sha256') else data)
        with patch.object(probe, 'build_opener', return_value=WrongSidecar()):
            with self.assertRaisesRegex(ValueError, 'sidecar mismatch'):
                probe.verified_artifact(spec, self.cache, True)

    def test_invalid_url_and_redirect_fail_before_accepting_data(self):
        bad = dict(self.spec, url='http://attacker.invalid/example.jar')
        with patch.object(probe, 'build_opener', side_effect=AssertionError('network used')):
            with self.assertRaisesRegex(ValueError, 'untrusted source URL'):
                probe.verified_artifact(bad, self.cache, True)
            (self.cache / self.spec['sha1']).write_bytes(self.data)
            with self.assertRaisesRegex(ValueError, 'untrusted source URL'):
                probe.verified_artifact(bad, self.cache, True)
        (self.cache / self.spec['sha1']).unlink()
        class Redirected:
            def open(self, url, timeout):
                return Response(url, self_data, 'https://other.invalid/example.jar')
        self_data = self.data
        with patch.object(probe, 'build_opener', return_value=Redirected()):
            with self.assertRaisesRegex(ValueError, 'unexpected redirect'):
                probe.verified_artifact(self.spec, self.cache, True)
        with self.assertRaisesRegex(ValueError, 'unexpected redirect'):
            probe.RejectRedirects().redirect_request(None, None, 302, '', {}, 'https://other.invalid/')
        self.assertFalse((self.cache / self.spec['sha1']).exists())


class NettyOutputPathTests(unittest.TestCase):
    def test_relative_inside_absolute_inside_and_absolute_outside(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            root = temporary / 'repository'
            root.mkdir()
            index = root / 'index.json'
            index.write_text('{"records": []}')
            cases = [('relative/inventory.json', root / 'relative/inventory.json'),
                     (str(root / 'inside/inventory.json'), root / 'inside/inventory.json'),
                     (str(temporary / 'outside/inventory.json'), temporary / 'outside/inventory.json')]
            saved = Path.cwd()
            try:
                os.chdir(root)
                outputs = []
                for requested, path in cases:
                    with self.subTest(requested=requested), patch.object(inspector, 'ROOT', root), \
                            patch.object(inspector, 'INDEX', index), \
                            patch('sys.argv', ['inspector', '--output', requested]), \
                            contextlib.redirect_stdout(io.StringIO()) as stdout:
                        self.assertEqual(inspector.main(), 0)
                        self.assertTrue(path.is_file())
                        outputs.append(json.loads(path.read_text()))
                        displayed = json.loads(stdout.getvalue())['output']
                        expected = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
                        self.assertEqual(displayed, expected)
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1], outputs[2])
                for requested, _ in (cases[0], cases[2]):
                    with self.subTest(old_requested=requested), patch.object(old_inspector, 'ROOT', root), \
                            patch.object(old_inspector, 'INDEX', index), \
                            patch('sys.argv', ['inspector', '--output', requested]), \
                            contextlib.redirect_stdout(io.StringIO()):
                        with self.assertRaises(ValueError):
                            old_inspector.main()
            finally:
                os.chdir(saved)


if __name__ == '__main__':
    unittest.main()
