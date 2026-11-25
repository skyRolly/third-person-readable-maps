from contextlib import redirect_stderr
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import probe

MEMBER = "io/netty/handler/codec/spdy/SpdyFrameCodec.class"


def fixture_jar(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as jar:
        for name, raw in entries.items():
            jar.writestr(name, raw)
    return buffer.getvalue()


class ProbeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        home = os.environ.get("JAVA_HOME")
        self.java = (Path(home) / "bin/java" if home else Path(shutil.which("java"))).resolve()
        javac = self.java.with_name("javac")
        source = self.directory / "SpdyFrameCodec.java"
        source.write_text("package io.netty.handler.codec.spdy; public class SpdyFrameCodec {"
                          " static { if (true) throw new AssertionError(\"must not initialize\"); } }", encoding="utf-8")
        subprocess.run([str(javac), "-d", str(self.directory), str(source)], check=True,
                       env=probe.java_environment(), timeout=30)
        self.raw_class = (self.directory / MEMBER).read_bytes()
        self.jar = fixture_jar({MEMBER: self.raw_class})
        self.empty = fixture_jar({"META-INF/MANIFEST.MF": "Manifest-Version: 1.0\n"})
        self.version = "4.1.118.Final"

    def fixture(self):
        libraries, blobs = [], {}
        for name in probe.modules(self.version):
            raw = self.jar if name == probe.HTTP else self.empty
            path = f"io/netty/{name}/{self.version}/{name}-{self.version}.jar"
            item = {"path": path, "url": probe.BASE + path, "size": len(raw), "sha1": hashlib.sha1(raw).hexdigest()}
            blobs[item["url"]] = raw
            libraries.append({"name": f"io.netty:{name}:{self.version}", "downloads": {"artifact": item}})
        manifest = {"id": "fixture", "libraries": libraries}
        return manifest, blobs

    def catalog(self, manifest):
        raw = json.dumps(manifest).encode()
        profile = ("fixture", self.version, probe.sha256(raw), probe.sha256(self.jar), probe.sha256(self.raw_class))
        return probe.catalog(raw, profile)

    def test_manifest_and_download_rejections(self):
        manifest, blobs = self.fixture()
        items = self.catalog(manifest)
        for mode in ("wrong_path", "wrong_url", "rules", "duplicate", "missing"):
            with self.subTest(mode=mode):
                candidate, _ = self.fixture()
                entry = candidate["libraries"][0]
                if mode == "wrong_path":
                    entry["downloads"]["artifact"]["path"] = "../bad.jar"
                elif mode == "wrong_url":
                    entry["downloads"]["artifact"]["url"] = "https://example.invalid/bad.jar"
                elif mode == "rules":
                    entry["rules"] = []
                elif mode == "duplicate":
                    candidate["libraries"].append(entry)
                else:
                    candidate["libraries"].pop(0)
                with self.assertRaises(probe.ProbeError):
                    self.catalog(candidate)
        with self.assertRaisesRegex(probe.ProbeError, "library size or SHA-1 mismatch"):
            probe.acquire(items, self.directory, probe.sha256(self.jar), lambda item: b"x" * item["size"])
        with self.assertRaisesRegex(probe.ProbeError, "HTTP JAR differs"):
            probe.acquire(items, self.directory, "0" * 64, lambda item: blobs[item["url"]])

    def test_real_jvm_controls_and_code_source(self):
        manifest, blobs = self.fixture()
        items = self.catalog(manifest)
        paths, hashes = probe.acquire(items, self.directory, probe.sha256(self.jar), lambda item: blobs[item["url"]])
        result = probe.observe(self.java, paths, hashes[probe.HTTP], probe.sha256(self.raw_class), self.directory)
        self.assertEqual(result["negative"], "class_not_found")
        self.assertEqual(result["positive"], "defined_by_isolated_url_loader")
        self.assertEqual(result["code_source_sha256"], probe.sha256(self.jar))
        with self.assertRaises(subprocess.CalledProcessError) as mismatch:
            probe.observe(self.java, paths, hashes[probe.HTTP], "0" * 64, self.directory)
        self.assertIn("class resource digest mismatch", mismatch.exception.stderr)
        paths["netty-common"].write_bytes(self.jar)
        with self.assertRaises(subprocess.CalledProcessError) as shadow:
            probe.observe(self.java, paths, hashes[probe.HTTP], probe.sha256(self.raw_class), self.directory)
        self.assertIn("negative control unexpectedly loaded target", shadow.exception.stderr)

    def test_main_reports_jvm_failure_without_report(self):
        manifest, blobs = self.fixture()
        raw = json.dumps(manifest).encode()
        (self.directory / "fixture.json").write_bytes(raw)
        profile = ("fixture", self.version, probe.sha256(raw), probe.sha256(self.jar), "0" * 64)
        output = self.directory / "report.json"
        # Exercise the real Java failure through the CLI; only acquisition
        # and checkout provenance are substituted with local fixture inputs.
        acquire = probe.acquire

        def fixture_acquire(items, directory, expected_http):
            return acquire(items, directory, expected_http, lambda item: blobs[item["url"]])

        with (mock.patch.object(probe, "PROFILES", (profile,)),
              mock.patch.object(probe, "MANIFESTS", self.directory),
              mock.patch.object(probe, "source_identity", return_value=("fixture", {})),
              mock.patch.object(probe, "acquire", side_effect=fixture_acquire) as acquisition,
              mock.patch.object(sys, "argv", ["probe.py", "--java", str(self.java), "--output", str(output)])):
            log = io.StringIO()
            with redirect_stderr(log), self.assertRaises(SystemExit) as failure:
                probe.main()
            self.assertEqual(failure.exception.code, 1)
            self.assertIn("JVM observation failed for fixture / " + self.version, log.getvalue())
            self.assertIn("exit 1", log.getvalue())
            self.assertIn("class resource digest mismatch", log.getvalue())
            self.assertFalse(output.exists())

            acquisition.side_effect = OSError("fixture acquisition failed")
            log = io.StringIO()
            with redirect_stderr(log), self.assertRaises(SystemExit) as failure:
                probe.main()
            self.assertEqual(failure.exception.code, 1)
            self.assertIn("input, acquisition or JVM unavailable", log.getvalue())
            self.assertNotIn("JVM observation failed", log.getvalue())
            self.assertFalse(output.exists())

    def test_main_reports_unexpected_zero_exit_output(self):
        manifest, blobs = self.fixture()
        raw = json.dumps(manifest).encode()
        (self.directory / "fixture.json").write_bytes(raw)
        profile = ("fixture", self.version, probe.sha256(raw), probe.sha256(self.jar),
                   probe.sha256(self.raw_class))
        output = self.directory / "report.json"
        # A real source-file JVM launch exits zero but violates the stdout
        # protocol. Only acquisition and checkout provenance are substituted.
        (self.directory / "SpdyClassProbe.java").write_text(
            'public class SpdyClassProbe { public static void main(String[] args) {'
            ' System.out.println("unexpected fixture line");'
            ' System.out.println("::error::fixture");'
            ' System.err.println("fixture diagnostic"); } }', encoding="utf-8")
        acquire = probe.acquire

        def fixture_acquire(items, directory, expected_http):
            return acquire(items, directory, expected_http, lambda item: blobs[item["url"]])

        with (mock.patch.object(probe, "HERE", self.directory),
              mock.patch.object(probe, "PROFILES", (profile,)),
              mock.patch.object(probe, "MANIFESTS", self.directory),
              mock.patch.object(probe, "source_identity", return_value=("fixture", {})),
              mock.patch.object(probe, "acquire", side_effect=fixture_acquire),
              mock.patch.object(sys, "argv", ["probe.py", "--java", str(self.java), "--output", str(output)])):
            log = io.StringIO()
            with redirect_stderr(log), self.assertRaises(SystemExit) as failure:
                probe.main()
            self.assertEqual(failure.exception.code, 1)
            message = log.getvalue()
            self.assertIn("JVM observation failed for fixture / " + self.version, message)
            self.assertIn("unexpected JVM observation output (exit 0)", message)
            self.assertIn("stdout='unexpected fixture line\\n::error::fixture\\n'", message)
            self.assertIn("stderr='fixture diagnostic\\n'", message)
            self.assertEqual(len(message.splitlines()), 1)
            self.assertFalse(output.exists())

    def test_unexpected_output_protocol_remains_strict(self):
        jar_hash, class_hash = probe.sha256(self.jar), probe.sha256(self.raw_class)
        paths = {probe.HTTP: self.directory / "fixture.jar"}
        expected = {"negative": "class_not_found", "positive": "defined_by_isolated_url_loader",
                    "code_source_sha256": jar_hash, "class_resource_sha256": class_hash}
        lines = [f"{key}={value}" for key, value in expected.items()]
        for name, stdout in (("empty", ""), ("missing", "\n".join(lines[:-1])),
                             ("reordered", "\n".join(reversed(lines))),
                             ("extra", "\n".join(lines + ["unexpected"])),
                             ("wrong_digest", "\n".join(lines[:-1] + ["class_resource_sha256=bad"])),
                             ("oversized", "x" * 4097 + "not-visible")):
            with self.subTest(name=name):
                completed = subprocess.CompletedProcess(["private-command"], 0, stdout, "fixture stderr")
                with mock.patch.object(probe.subprocess, "run", return_value=completed):
                    with self.assertRaisesRegex(probe.ProbeError, "unexpected JVM observation output") as failure:
                        probe.observe(self.java, paths, jar_hash, class_hash, self.directory)
                message = str(failure.exception)
                self.assertIn("stderr='fixture stderr'", message)
                self.assertIn("stdout=" + ascii(stdout[:4096]), message)
                self.assertNotIn("private-command", message)
                if name == "oversized":
                    self.assertIn("(truncated)", message)
                    self.assertNotIn("not-visible", message)
        completed = subprocess.CompletedProcess([], 0, "\n".join(lines) + "\n", "")
        with mock.patch.object(probe.subprocess, "run", return_value=completed):
            self.assertEqual(probe.observe(self.java, paths, jar_hash, class_hash, self.directory), expected)

    def test_jvm_diagnostics_bounds_and_escapes_output(self):
        error = subprocess.TimeoutExpired(["private-command"], 60,
                                          output=b"partial\n::error::fake",
                                          stderr=b"x" * 4097 + b"not-visible")
        message = probe.jvm_diagnostics(error)
        self.assertIn("partial\\n::error::fake", message)
        self.assertIn("(truncated)", message)
        self.assertNotIn("\n", message)
        self.assertNotIn("not-visible", message)
        self.assertNotIn("private-command", message)
        self.assertEqual(probe.jvm_diagnostics(subprocess.CalledProcessError(1, [])),
                         "no captured JVM output")

    def test_manifest_classpath_rejected(self):
        self.empty = fixture_jar({"META-INF/MANIFEST.MF": "Manifest-Version: 1.0\nClass-Path: extra.jar\n"})
        manifest, blobs = self.fixture()
        with self.assertRaisesRegex(probe.ProbeError, "extends the isolated classpath"):
            probe.acquire(self.catalog(manifest), self.directory, probe.sha256(self.jar), lambda item: blobs[item["url"]])


if __name__ == "__main__":
    unittest.main()
