"""Reject invalid class operands and runtime-library class identities."""
import hashlib
import io
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import warnings
from zipfile import ZipFile

import java_toolchain

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import game_linkage
import jvm_linkage


def u2(value):
    return struct.pack('>H', value)


def u4(value):
    return struct.pack('>I', value)


def utf(value):
    raw = value.encode('utf-8')
    return b'\x01' + u2(len(raw)) + raw


def new_fixture(owner_index, literal=False):
    pool = [utf('fixture/Caller'), b'\x07' + u2(1), utf('java/lang/Object'), b'\x07' + u2(3),
            utf('<init>'), utf('()V'), b'\x0c' + u2(5) + u2(6), b'\x0a' + u2(4) + u2(7),
            utf('Code'), utf('main'), utf('([Ljava/lang/String;)V'), utf('[I'), b'\x07' + u2(12),
            utf('[Ljava/lang/Object;'), b'\x07' + u2(14)]
    def method(access, name, desc, code, stack, locals_):
        code_attr = u2(stack) + u2(locals_) + u4(len(code)) + code + u2(0) + u2(0)
        return u2(access) + u2(name) + u2(desc) + u2(1) + u2(9) + u4(len(code_attr)) + code_attr
    init = method(1, 5, 6, b'\x2a\xb7\x00\x08\xb1', 1, 1)
    code = (b'\x12' + bytes([owner_index]) + b'\x57\xb1' if literal else
            b'\xbb' + u2(owner_index) + b'\x59\xb7\x00\x08\x57\xb1')
    main = method(9, 10, 11, code, 2, 1)
    return (b'\xca\xfe\xba\xbe' + u2(0) + u2(52) + u2(len(pool) + 1) + b''.join(pool) +
            u2(0x21) + u2(2) + u2(4) + u2(0) + u2(0) + u2(2) + init + main + u2(0))


def handle_fixture(kind):
    pool = [utf('fixture/Caller'), b'\x07' + u2(1), utf('java/lang/Object'), b'\x07' + u2(3),
            utf('<init>'), utf('()V'), b'\x0c' + u2(5) + u2(6), b'\x0a' + u2(4) + u2(7),
            utf('Code'), utf('main'), utf('([Ljava/lang/String;)V'), b'\x0f' + bytes([kind]) + u2(8)]
    def method(access, name, desc, code, stack, locals_):
        body = u2(stack) + u2(locals_) + u4(len(code)) + code + u2(0) + u2(0)
        return u2(access) + u2(name) + u2(desc) + u2(1) + u2(9) + u4(len(body)) + body
    init = method(1, 5, 6, b'\x2a\xb7\x00\x08\xb1', 1, 1)
    main = method(9, 10, 11, b'\x12\x0c\x57\xb1', 1, 1)
    return (b'\xca\xfe\xba\xbe' + u2(0) + u2(52) + u2(len(pool) + 1) + b''.join(pool) +
            u2(0x21) + u2(2) + u2(4) + u2(0) + u2(0) + u2(2) + init + main + u2(0))


class InvalidLinkageInputs(unittest.TestCase):
    def test_new_rejects_array_owners_but_array_class_literals_work(self):
        java = java_toolchain.which('java')
        with tempfile.TemporaryDirectory() as temp:
            cls = Path(temp) / 'fixture' / 'Caller.class'
            cls.parent.mkdir()
            for index, literal, valid in ((4, False, True), (13, True, True),
                                          (13, False, False), (15, False, False)):
                raw = new_fixture(index, literal)
                cls.write_bytes(raw)
                if java:
                    result = subprocess.run([java, '-cp', temp, 'fixture.Caller'], capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, valid, result.stderr)
                if valid:
                    jvm_linkage.parse(raw)
                else:
                    with self.assertRaisesRegex(ValueError, 'new.*array'):
                        jvm_linkage.parse(raw)
            jvm_linkage.validate_class_use({'name': '[I', 'operation': 'class_constant'}, 'fixture/Caller', lambda _: None)
            with self.assertRaisesRegex(ValueError, 'new.*array'):
                jvm_linkage.validate_class_use({'name': '[I', 'operation': 'new'}, 'fixture/Caller', lambda _: None)

    def test_constructor_handle_requires_new_invoke_special(self):
        java = java_toolchain.which('java')
        target = {'name': 'java/lang/Object', 'super': None, 'interfaces': [], 'access': 1,
                  'members': [{'kind': 'method', 'name': '<init>', 'descriptor': '()V', 'access': 1}]}
        with tempfile.TemporaryDirectory() as temp:
            cls = Path(temp) / 'fixture' / 'Caller.class'
            cls.parent.mkdir()
            for kind in (7, 8):
                raw = handle_fixture(kind)
                cls.write_bytes(raw)
                if java:
                    result = subprocess.run([java, '-cp', temp, 'fixture.Caller'], capture_output=True, text=True)
                    self.assertEqual(result.returncode == 0, kind == 8, result.stderr)
                uses = jvm_linkage.parse(raw)['uses']
                ordinary = next(use for use in uses if use['source_kind'] == 'instruction')
                handle = next(use for use in uses if use['source_kind'] == 'method_handle')
                jvm_linkage.validate_use(ordinary, 'fixture/Caller', lambda _: target)
                if kind == 8:
                    jvm_linkage.validate_use(handle, 'fixture/Caller', lambda _: target)
                else:
                    with self.assertRaisesRegex(ValueError, 'invalid constructor invocation'):
                        jvm_linkage.validate_use(handle, 'fixture/Caller', lambda _: target)

    def test_invokeinterface_slot_count_handles_arrays_and_rejects_bad_parameters(self):
        self.assertEqual(jvm_linkage.interface_argument_slots('([J[DLjava/lang/Object;J)V'), 6)
        for desc in ('(V)V', '(J', '([)V', '(L;)V', '()'):
            with self.subTest(descriptor=desc), self.assertRaisesRegex(ValueError, 'invalid method descriptor'):
                jvm_linkage.interface_argument_slots(desc)

    def test_invokeinterface_count_includes_receiver_and_wide_parameters(self):
        javac = java_toolchain.which('javac')
        java = java_toolchain.which('java')
        if not javac or not java:
            self.skipTest('JDK is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'Caller.java'
            source.write_text('interface Api { void run(long x, double y, Object[] z); } '
                              'public class Caller implements Api { public void run(long x, double y, Object[] z) {} '
                              'public static void main(String[] args) { Api a = new Caller(); '
                              'a.run(1L, 2d, new Object[0]); } }')
            subprocess.run([javac, '--release', '8', '-d', str(root), str(source)], check=True, capture_output=True)
            cls = root / 'Caller.class'
            original = cls.read_bytes()
            positions = [i for i in range(len(original)-4)
                         if original[i] == 185 and original[i+3:i+5] == b'\x06\x00']
            self.assertEqual(len(positions), 1)
            index = positions[0]
            for count in (6, 5):
                raw = bytearray(original)
                raw[index + 3] = count
                cls.write_bytes(raw)
                result = subprocess.run([java, '-cp', temp, 'Caller'], capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, count == 6, result.stderr)
                if count == 6:
                    jvm_linkage.parse(raw)
                else:
                    with self.assertRaisesRegex(ValueError, 'invalid invokeinterface operands'):
                        jvm_linkage.parse(raw)

    def test_library_lookup_requires_identity_and_unique_archive_path(self):
        javac = java_toolchain.which('javac')
        if not javac:
            self.skipTest('javac is required')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {'org/joml/Api.java': 'package org.joml; public class Api { public static void run() {} }',
                       'org/joml/Other.java': 'package org.joml; public class Other { public static void run() {} }',
                       'app/Caller.java': 'package app; public class Caller { void run() { org.joml.Api.run(); } }'}
            paths = []
            for name, text in sources.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
                paths.append(str(path))
            subprocess.run([javac, '--release', '8', '-d', str(root), *paths], check=True, capture_output=True)
            mod = jvm_linkage.parse((root / 'app/Caller.class').read_bytes())
            for kind in ('matching', 'wrong-name', 'duplicate'):
                buffer = io.BytesIO()
                with warnings.catch_warnings(), ZipFile(buffer, 'w') as jar:
                    warnings.simplefilter('ignore', UserWarning)
                    content = (root / ('org/joml/Other.class' if kind == 'wrong-name' else 'org/joml/Api.class')).read_bytes()
                    jar.writestr('org/joml/Api.class', content)
                    if kind == 'duplicate':
                        jar.writestr('org/joml/Api.class', content)
                blob = buffer.getvalue()
                artifact = {'sha1': hashlib.sha1(blob).hexdigest(), 'size': len(blob), 'url': 'fixture'}
                metadata = {'libraries': [{'name': 'org.joml:joml:1.0', 'downloads': {'artifact': artifact}}]}
                runtime = game_linkage.RuntimeLibraries(metadata, lambda _: blob, 'fixture')
                with self.subTest(kind=kind, path='runtime'):
                    if kind == 'matching':
                        self.assertEqual(runtime.lookup('org/joml/Api')['name'], 'org/joml/Api')
                    else:
                        with self.assertRaisesRegex(ValueError, 'class name mismatch|duplicate library class'):
                            runtime.lookup('org/joml/Api')
                with self.subTest(kind=kind, path='standalone'), ZipFile(io.BytesIO(blob)) as jar:
                    if kind == 'matching':
                        self.assertEqual(game_linkage.verify_library_instructions(
                            {mod['name']: mod}, {}, jar, 'org/joml/', 'fixture'), 1)
                    else:
                        with self.assertRaisesRegex(ValueError, 'class name mismatch|duplicate library class'):
                            game_linkage.verify_library_instructions(
                                {mod['name']: mod}, {}, jar, 'org/joml/', 'fixture')


if __name__ == '__main__':
    unittest.main()
