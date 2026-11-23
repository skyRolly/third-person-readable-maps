"""Exercise the real offline SNI cache CLI using six synthetic pinned JARs."""
import ast
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
from io import BytesIO, StringIO
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_sni_high as sni
import prepare_issue45_sni_cache as acquisition

INNER = 'io/netty/handler/ssl/SslClientHelloHandler$1.class'
ABSTRACT = 'io/netty/handler/ssl/AbstractSniHandler.class'
HELLO = 'io/netty/handler/ssl/SslClientHelloHandler.class'
SNI = 'io/netty/handler/ssl/SniHandler.class'


def make_jar(number, omit_inner=False, no_literal=False):
    values = {SNI: b'sni-' + bytes([number]), ABSTRACT: b'SslClientHelloHandler-abstract-' + bytes([number]),
              HELLO: b'SslClientHelloHandler-main-' + bytes([number]),
              INNER: (b'without-reference-' if no_literal else b'SslClientHelloHandler-inner-') + bytes([number]),
              'padding.txt': b'padding-' + bytes([number])}
    out = BytesIO()
    with ZipFile(out, 'w', ZIP_STORED) as jar:
        for name, raw in sorted(values.items()):
            if omit_inner and name == INNER:
                continue
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED
            jar.writestr(info, raw)
    return out.getvalue(), values


class KnownHitsCacheCliTests(unittest.TestCase):
    def fixture(self, root, omit_inner=False, no_literal=False):
        catalog, known, artifacts = [], [], []
        for number in range(6):
            raw, values = make_jar(number, omit_inner=omit_inner and number == 0,
                                   no_literal=no_literal and number == 0)
            sha1, sha256 = hashlib.sha1(raw).hexdigest(), hashlib.sha256(raw).hexdigest()
            version = '4.1.' + str(100 + number) + '.Final'
            (root / sha1).write_bytes(raw)
            catalog.append({'version': version, 'sha1': sha1, 'sha256': sha256,
                'classes': [{'path': name, 'sha256': hashlib.sha256(values[name]).hexdigest()}
                            for name in (SNI, ABSTRACT, HELLO)]})
            known.append({'version': version, 'sha1': sha1, 'sha256': sha256,
                'literal_hits': [{'path': name, 'sha256': hashlib.sha256(values[name]).hexdigest()}
                                 for name in (ABSTRACT, HELLO, INNER)]})
            artifacts.append({'sha1': sha1, 'sha256': sha256, 'size_bytes': len(raw),
                              'coordinates': ['io.netty:netty-handler:' + version]})
        return {'root': root, 'catalog': catalog, 'known': {'schema': 1, 'security_clearance': False,
                'libraries': known}, 'scan': {'runtime_classpath_scan': {'all_artifacts': artifacts}}}

    def invoke(self, fixture, main=sni.main, cache=None):
        reads, out, err = [], StringIO(), StringIO()
        original_read_bytes = Path.read_bytes
        def tracked_read(path):
            reads.append(path)
            return original_read_bytes(path)
        def read_known(root, path, expected=None):
            self.assertEqual((path, expected), (sni.KNOWN_HITS, sni.KNOWN_HITS_SHA))
            return json.dumps(fixture['known']).encode()
        inputs = ({}, {'advisories': [{'advisory_id': sni.HIGH}]}, {}, fixture['scan'], {})
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['inspect_issue45_sni_high.py', '--verify-known-hits-cache',
                                                          str(fixture['root'] if cache is None else cache)]))
            stack.enter_context(patch.object(sni, 'load_inputs', return_value=inputs))
            stack.enter_context(patch.object(sni, 'bind_occurrences', return_value=(fixture['catalog'], [], [])))
            stack.enter_context(patch.object(sni, 'read', side_effect=read_known))
            stack.enter_context(patch.object(Path, 'read_bytes', tracked_read))
            stack.enter_context(patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network')))
            stack.enter_context(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('unexpected network')))
            stack.enter_context(patch.object(urllib.request, 'urlopen', side_effect=AssertionError('unexpected network')))
            stack.enter_context(redirect_stdout(out))
            stack.enter_context(redirect_stderr(err))
            result = main()
        return result, err.getvalue(), reads

    def assert_valid(self, fixture, main=sni.main):
        result, error, reads = self.invoke(fixture, main)
        self.assertEqual(result, 0, error)
        expected = [fixture['root'].resolve() / row['sha1'] for row in fixture['catalog']]
        self.assertEqual(reads, expected)

    def assert_invalid(self, fixture, reason, main=sni.main, cache=None):
        result, error, _ = self.invoke(fixture, main, cache)
        self.assertEqual(result, 1, error)
        self.assertIn(reason, error)

    def test_complete_cache_reads_and_verifies_all_six_artifacts_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assert_valid(self.fixture(Path(directory)))

    def test_corrupt_missing_or_incorrectly_pinned_cache_is_rejected(self):
        for kind in ('corrupt', 'missing', 'size', 'sha1', 'sha256', 'class_digest', 'invalid_identity'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(Path(directory))
                self.assert_valid(fixture)
                lib = fixture['catalog'][0]
                record = fixture['known']['libraries'][0]
                artifact = fixture['scan']['runtime_classpath_scan']['all_artifacts'][0]
                path = fixture['root'] / lib['sha1']
                if kind == 'corrupt':
                    raw = path.read_bytes()
                    self.assertIn(b'padding-\x00', raw)
                    path.write_bytes(raw.replace(b'padding-\x00', b'padding-\x01', 1))
                    reason = 'cached Netty library checksum mismatch'
                elif kind == 'missing':
                    path.unlink()
                    reason = lib['sha1']
                elif kind == 'size':
                    artifact['size_bytes'] += 1
                    reason = 'cached Netty library size mismatch'
                elif kind in ('sha1', 'invalid_identity'):
                    old = lib['sha1']
                    new = '0' * 40 if kind == 'sha1' else '../unexpected'
                    lib['sha1'] = record['sha1'] = artifact['sha1'] = new
                    if kind == 'sha1':
                        (fixture['root'] / new).write_bytes((fixture['root'] / old).read_bytes())
                    reason = 'cached Netty library checksum mismatch' if kind == 'sha1' else 'invalid Netty cache artifact identity'
                elif kind == 'sha256':
                    lib['sha256'] = record['sha256'] = artifact['sha256'] = '0' * 64
                    reason = 'cached Netty library checksum mismatch'
                else:
                    next(row for row in record['literal_hits'] if row['path'] == INNER)['sha256'] = '0' * 64
                    reason = 'known cached ClientHello literal or class digest differs'
                self.assert_invalid(fixture, reason)

    def test_missing_class_and_missing_literal_are_rejected_with_valid_jar_hashes(self):
        for kind in ('missing_class', 'missing_literal'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                valid = self.fixture(root)
                self.assert_valid(valid)
                with tempfile.TemporaryDirectory() as other:
                    changed = self.fixture(Path(other), omit_inner=kind == 'missing_class',
                                           no_literal=kind == 'missing_literal')
                    self.assert_invalid(changed, INNER if kind == 'missing_class' else
                                        'known cached ClientHello literal or class digest differs')

    def test_cache_path_must_be_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self.fixture(root)
            self.assert_valid(fixture)
            invalid = root / 'not-a-directory'
            invalid.write_bytes(b'not a directory')
            self.assert_invalid(fixture, 'Netty cache is not a directory', cache=invalid)

    def test_cache_artifact_symlink_cannot_escape_its_root(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as other:
            fixture = self.fixture(Path(directory))
            self.assert_valid(fixture)
            jar = fixture['root'] / fixture['catalog'][0]['sha1']
            outside = Path(other) / jar.name
            outside.write_bytes(jar.read_bytes())
            jar.unlink()
            try:
                jar.symlink_to(outside)
            except (OSError, NotImplementedError) as exc:
                self.skipTest('file symlinks unavailable: ' + str(exc))
            self.assert_invalid(fixture, 'Netty cache artifact path escapes root')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires Linux double-slash path semantics')
    def test_linux_double_slash_cli_reads_and_verifies_the_same_six_jars(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(Path(directory))
            double = '/' + str(fixture['root'])
            self.assertTrue(os.path.samefile(fixture['root'], double))
            read_sets = []
            for cache in (fixture['root'], double):
                with patch.object(sni, 'verify_known_cached_library', wraps=sni.verify_known_cached_library) as known, \
                     patch.object(sni, 'inspect_library', wraps=sni.inspect_library) as inspect_jar, \
                     patch.object(sni.hashlib, 'sha1', wraps=hashlib.sha1) as sha1, \
                     patch.object(sni, 'sha', wraps=sni.sha) as sha256:
                    result, error, reads = self.invoke(fixture, cache=cache)
                    self.assertEqual(result, 0, error)
                    self.assertEqual((known.call_count, inspect_jar.call_count, sha1.call_count), (6, 6, 6))
                    self.assertGreaterEqual(sha256.call_count, 42)
                    read_sets.append(reads)
            expected = [fixture['root'].resolve() / row['sha1'] for row in fixture['catalog']]
            self.assertEqual(read_sets, [expected, expected])
            # The previous slash conversion rejected these same valid bytes
            # before opening any JAR; keep that defective behavior explicit.
            with patch.object(sni, 'is_network_cache_path',
                              side_effect=lambda value: str(value).replace('/', '\\').startswith('\\\\')):
                self.assert_invalid(fixture, 'network cache paths are not allowed', cache=double)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'requires Linux double-slash path semantics')
    def test_linux_double_slash_cache_still_rejects_missing_or_altered_artifacts(self):
        for kind in ('missing', 'corrupt', 'size', 'sha1', 'sha256', 'class_digest'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(Path(directory))
                double = '/' + str(fixture['root'])
                result, error, reads = self.invoke(fixture, cache=double)
                self.assertEqual(result, 0, error)
                self.assertEqual(len(reads), 6)
                lib = fixture['catalog'][0]
                known = fixture['known']['libraries'][0]
                artifact = fixture['scan']['runtime_classpath_scan']['all_artifacts'][0]
                jar = fixture['root'] / lib['sha1']
                if kind == 'missing':
                    jar.unlink()
                    reason = lib['sha1']
                elif kind == 'corrupt':
                    jar.write_bytes(jar.read_bytes().replace(b'padding-\x00', b'padding-\x01', 1))
                    reason = 'cached Netty library checksum mismatch'
                elif kind == 'size':
                    artifact['size_bytes'] += 1
                    reason = 'cached Netty library size mismatch'
                elif kind == 'sha1':
                    replacement = '0' * 40
                    (fixture['root'] / replacement).write_bytes(jar.read_bytes())
                    lib['sha1'] = known['sha1'] = artifact['sha1'] = replacement
                    reason = 'cached Netty library checksum mismatch'
                elif kind == 'sha256':
                    lib['sha256'] = known['sha256'] = artifact['sha256'] = '0' * 64
                    reason = 'cached Netty library checksum mismatch'
                else:
                    next(row for row in known['literal_hits'] if row['path'] == INNER)['sha256'] = '0' * 64
                    reason = 'known cached ClientHello literal or class digest differs'
                self.assert_invalid(fixture, reason, cache=double)

    def test_windows_path_grammar_and_posix_paths_are_distinct(self):
        for local in (r'C:\cache', r'\\?\C:\cache', 'C:/cache', '//?/C:/cache'):
            with self.subTest(local=local):
                self.assertFalse(sni.is_network_cache_path(local, windows=True))
        for remote in (r'\\server\share\cache', r'\\?\UNC\server\share\cache', '//server/share/cache'):
            with self.subTest(remote=remote):
                self.assertTrue(sni.is_network_cache_path(remote, windows=True))
        self.assertFalse(sni.is_network_cache_path('//tmp/netty-cache', windows=False))

    @unittest.skipUnless(os.name == 'nt', 'requires Windows path semantics')
    def test_windows_cli_accepts_local_paths_and_rejects_unc_before_resolving(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(Path(directory))
            self.assert_valid(fixture)
            extended = '\\\\?\\' + str(fixture['root'].resolve())
            result, error, reads = self.invoke(fixture, cache=extended)
            self.assertEqual(result, 0, error)
            self.assertEqual([path.name for path in reads], [row['sha1'] for row in fixture['catalog']])
            for remote in (r'\\server\share\cache', r'\\?\UNC\server\share\cache', '//server/share/cache'):
                with self.subTest(remote=remote), \
                     patch.object(Path, 'resolve', side_effect=AssertionError('UNC path was resolved')):
                    self.assert_invalid(fixture, 'network cache paths are not allowed', cache=remote)
                    # Removing the guard attempts resolution and fails this test
                    # without accessing any actual share.
                    with patch.object(sni, 'is_network_cache_path', return_value=False), \
                         self.assertRaisesRegex(AssertionError, 'UNC path was resolved'):
                        self.assert_invalid(fixture, 'network cache paths are not allowed', cache=remote)

    def test_acquisition_verifies_bytes_and_cleans_partial_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = parent / 'source'
            source.mkdir()
            fixture = self.fixture(source)
            self.assert_valid(fixture)
            known = {row['sha1']: {'version': row['version'], 'sha256': row['sha256'],
                                   'hits': {hit['path']: hit['sha256'] for hit in row['literal_hits']}}
                     for row in fixture['known']['libraries']}
            artifacts = fixture['scan']['runtime_classpath_scan']['all_artifacts']
            inventory = {'netty_artifacts': []}
            sources = {}
            for library, artifact in zip(fixture['catalog'], artifacts):
                version = library['version']
                url = ('https://libraries.minecraft.net/io/netty/netty-handler/' + version +
                       '/netty-handler-' + version + '.jar')
                inventory['netty_artifacts'].append({'coordinate': 'io.netty:netty-handler:' + version,
                    'sha1': library['sha1'], 'sha256': library['sha256'], 'size': artifact['size_bytes'], 'url': url})
                sources[url] = (source / library['sha1']).read_bytes()
            calls = []
            def fetch(url, size):
                calls.append((url, size))
                return sources[url]
            output = parent / 'prepared'
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('unexpected network')):
                acquisition.prepare_cache(output, fixture['catalog'], known, fixture['scan'], inventory, fetch)
            self.assertEqual(len(calls), 6)
            prepared = {**fixture, 'root': output}
            self.assert_valid(prepared)
            self.assertEqual({p.name for p in output.iterdir()}, {row['sha1'] for row in fixture['catalog']})
            with self.assertRaisesRegex(ValueError, 'refusing to replace an existing cache'):
                acquisition.prepare_cache(output, fixture['catalog'], known, fixture['scan'], inventory, fetch)
            self.assert_valid(prepared)
            broken = parent / 'broken'
            count = 0
            def corrupt_second(url, size):
                nonlocal count
                count += 1
                raw = sources[url]
                return raw if count == 1 else raw.replace(b'padding-\x01', b'padding-\x02', 1)
            with self.assertRaisesRegex(ValueError, 'cached Netty library checksum mismatch'):
                acquisition.prepare_cache(broken, fixture['catalog'], known, fixture['scan'], inventory, corrupt_second)
            self.assertFalse(broken.exists())
            altered = copy.deepcopy(inventory)
            altered['netty_artifacts'][0]['url'] = 'https://example.invalid/netty.jar'
            calls.clear()
            with self.assertRaisesRegex(ValueError, 'source URL, size or identity differs'):
                acquisition.prepare_cache(broken, fixture['catalog'], known, fixture['scan'], altered, fetch)
            self.assertFalse(broken.exists())
            self.assertEqual(calls, [])

    @staticmethod
    def mutate(function, change):
        tree = ast.parse(inspect.getsource(function))
        change(tree)
        namespace = {}
        exec(compile(ast.fix_missing_locations(tree), '<cache-cli-mutation>', 'exec'), sni.__dict__, namespace)
        return namespace[function.__name__]

    def test_branch_or_one_skipped_artifact_fails_the_positive_control(self):
        def remove_branch(tree):
            for node in ast.walk(tree):
                if isinstance(node, ast.If) and isinstance(node.test, ast.Attribute) and node.test.attr == 'verify_known_hits_cache':
                    node.body = [ast.Pass()]
                    return
            self.fail('cache CLI branch not found')
        def skip_one(tree):
            for node in ast.walk(tree):
                if isinstance(node, ast.For) and isinstance(node.iter, ast.Name) and node.iter.id == 'catalog':
                    node.iter = ast.Subscript(value=ast.Name(id='catalog', ctx=ast.Load()),
                        slice=ast.Slice(upper=ast.UnaryOp(op=ast.USub(), operand=ast.Constant(1))), ctx=ast.Load())
                    return
            self.fail('cache artifact loop not found')
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(Path(directory))
            self.assert_valid(fixture)
            mutant = self.mutate(sni.main, remove_branch)
            with self.assertRaises(AssertionError):
                self.assert_valid(fixture, mutant)
            mutant = self.mutate(sni.verify_known_hits_cache, skip_one)
            with patch.object(sni, 'verify_known_hits_cache', mutant), self.assertRaises(AssertionError):
                self.assert_valid(fixture)

    def test_bypassed_hash_class_or_size_checks_fail_the_negative_controls(self):
        def remove_require(function, message):
            def transform(tree):
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.For)):
                        for index, statement in enumerate(node.body):
                            if (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and
                                    isinstance(statement.value.func, ast.Name) and statement.value.func.id == 'require' and
                                    any(isinstance(arg, ast.Constant) and isinstance(arg.value, str) and message in arg.value
                                        for arg in ast.walk(statement.value))):
                                node.body.pop(index)
                                return
                self.fail('expected integrity check not found')
            return self.mutate(function, transform)
        for kind in ('hash', 'class', 'size'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(Path(directory))
                self.assert_valid(fixture)
                lib = fixture['catalog'][0]
                if kind == 'hash':
                    path = fixture['root'] / lib['sha1']
                    path.write_bytes(path.read_bytes().replace(b'padding-\x00', b'padding-\x01', 1))
                    name, function, reason = 'inspect_library', sni.inspect_library, 'cached Netty library checksum mismatch'
                    mutant = remove_require(function, 'cached Netty library checksum mismatch')
                elif kind == 'class':
                    row = fixture['known']['libraries'][0]
                    next(hit for hit in row['literal_hits'] if hit['path'] == INNER)['sha256'] = '0' * 64
                    name, function, reason = ('verify_known_cached_library', sni.verify_known_cached_library,
                                              'known cached ClientHello literal or class digest differs')
                    mutant = remove_require(function, reason)
                else:
                    fixture['scan']['runtime_classpath_scan']['all_artifacts'][0]['size_bytes'] += 1
                    name, function, reason = 'verify_known_hits_cache', sni.verify_known_hits_cache, 'cached Netty library size mismatch'
                    mutant = remove_require(function, reason)
                self.assert_invalid(fixture, reason)
                with patch.object(sni, name, mutant), self.assertRaises(AssertionError):
                    self.assert_invalid(fixture, reason)


if __name__ == '__main__':
    unittest.main()
