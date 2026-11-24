import copy
import hashlib
import io
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
VALIDATOR_PATH = ROOT / "diagnostics/issue45-runtime/validate_runtime_evidence.py"
SPEC = importlib.util.spec_from_file_location("issue45_runtime_validator", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "issue45_agent_builder", ROOT / "diagnostics/issue45-runtime/build_agent.py")
BUILDER = importlib.util.module_from_spec(BUILDER_SPEC)
BUILDER_SPEC.loader.exec_module(BUILDER)
CONTROLS_SPEC = importlib.util.spec_from_file_location(
    "issue45_agent_controls", ROOT / "diagnostics/issue45-runtime/run_controls.py")
CONTROLS = importlib.util.module_from_spec(CONTROLS_SPEC)
CONTROLS_SPEC.loader.exec_module(CONTROLS)


class RuntimePipelineEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((EVIDENCE / "synthetic-control-verification.json").read_text())
        cls.profiles = {}
        for profile in cls.summary["profiles"]:
            events = [json.loads(line) for line in
                      (EVIDENCE / profile["observation_file"]).read_text().splitlines() if line.strip()]
            cls.profiles[profile["profile_id"]] = (profile, events)

    def test_partial_agent_dependency_cache_is_reacquired_and_verified(self):
        data = b"synthetic pinned Byte Buddy bytes"
        dep = {"url": "https://example.invalid/pinned.jar",
               "sha256": hashlib.sha256(data).hexdigest()}
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pinned.jar"
            target.write_bytes(b"truncated")
            with patch.object(BUILDER.urllib.request, "urlopen", return_value=io.BytesIO(data)) as fetch:
                BUILDER.download_pinned(dep, target)
                fetch.assert_called_once()
            self.assertEqual(data, target.read_bytes())
            with patch.object(BUILDER.urllib.request, "urlopen",
                              side_effect=AssertionError("valid cache must be offline")):
                BUILDER.download_pinned(dep, target)
            target.write_bytes(b"corrupted")
            with patch.object(BUILDER.urllib.request, "urlopen", return_value=io.BytesIO(b"wrong")):
                with self.assertRaisesRegex(SystemExit, "downloaded dependency SHA-256"):
                    BUILDER.download_pinned(dep, target)
            self.assertEqual([], list(Path(tmp).glob("*.part")))

    def test_partial_synthetic_control_cache_is_reacquired_and_verified(self):
        data = b"synthetic pinned control JAR bytes"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "control.jar"
            target.write_bytes(b"incomplete")
            with patch.object(CONTROLS.urllib.request, "urlopen", return_value=io.BytesIO(data)) as fetch:
                CONTROLS.fetch("https://example.invalid/control.jar", target,
                               digest, expected_size=len(data))
                fetch.assert_called_once()
            self.assertEqual(data, target.read_bytes())
            with patch.object(CONTROLS.urllib.request, "urlopen",
                              side_effect=AssertionError("valid cache must be offline")):
                CONTROLS.fetch("https://example.invalid/control.jar", target, digest,
                               expected_size=len(data))
            target.write_bytes(b"truncated")
            with patch.object(CONTROLS.urllib.request, "urlopen", return_value=io.BytesIO(b"bad")):
                with self.assertRaisesRegex(SystemExit, "hash or size differs"):
                    CONTROLS.fetch("https://example.invalid/control.jar", target,
                                   digest, expected_size=len(data))
            self.assertEqual([], list(Path(tmp).glob("*.part")))

    def test_source_bound_archive_is_valid_but_has_no_game_runtime_passes(self):
        errors, result = VALIDATOR.validate_evidence(EVIDENCE, ROOT)
        self.assertEqual([], errors)
        self.assertEqual(6, result["expected_environment_count"])
        self.assertEqual(0, result["captured_runtime_environment_count"])
        self.assertEqual("not_established", result["runtime_acceptance"])
        self.assertFalse(result["synthetic_controls_are_game_evidence"])

    def test_exact_client_and_server_netty_artifact_pins_are_source_bound(self):
        matrix = json.loads((EVIDENCE / "environment-matrix.json").read_text())
        baseline = json.loads((EVIDENCE / "baseline-lock.json").read_text())
        pins = {}
        for environment in matrix["environments"]:
            errors, pin = VALIDATOR.validate_environment_artifact_pin(
                environment, ROOT, baseline["retained_files"])
            with self.subTest(environment=environment["environment_id"]):
                self.assertEqual([], errors)
                self.assertTrue(pin["coordinate"].startswith("io.netty:"))
                self.assertEqual(40, len(pin["sha1"]))
                self.assertGreater(pin["size_bytes"], 0)
                pins[environment["environment_id"]] = pin
        self.assertEqual("io.netty:netty-codec:4.1.77.Final",
                         pins["minecraft-1.19-client"]["coordinate"])
        self.assertEqual("io.netty:netty-codec:4.1.76.Final",
                         pins["minecraft-1.19-dedicated-server"]["coordinate"])
        self.assertEqual("io.netty:netty-codec-compression:4.2.7.Final",
                         pins["minecraft-26.1.2-dedicated-server"]["coordinate"])

    def test_runtime_artifact_hash_must_match_the_pinned_manifest(self):
        pin = {"path": "io/netty/netty-codec/4.1.77.Final/netty-codec-4.1.77.Final.jar",
               "sha1": "a" * 40, "size_bytes": 123, "sha256": "b" * 64}
        record = {"artifact": "netty-codec-4.1.77.Final.jar", "sha1": "a" * 40,
                  "sha256": "b" * 64, "size_bytes": 123, "hash_verified": True}
        start = {"effective_classpath_sanitized": [record]}
        self.assertEqual([], VALIDATOR.validate_runtime_artifact_identity(start, {}, pin))
        changed = dict(record, sha1="c" * 40)
        errors = VALIDATOR.validate_runtime_artifact_identity(
            {"effective_classpath_sanitized": [changed]}, {}, pin)
        self.assertTrue(any("does not expose" in error for error in errors), errors)

    def test_server_loader_path_can_bind_unloaded_netty_module_without_claiming_loading(self):
        pin = {"path": "io/netty/netty-codec-compression/4.2.7.Final/netty-codec-compression-4.2.7.Final.jar",
               "sha1": "a" * 40, "size_bytes": 123, "sha256": "b" * 64}
        loader_only = {"artifact": "netty-codec-compression-4.2.7.Final.jar",
                       "sha1": "a" * 40, "size_bytes": 123, "sha256": "b" * 64,
                       "hash_verified": True, "availability_only": True,
                       "discovered_via": "loaded_class_loader_url"}
        self.assertEqual([], VALIDATOR.validate_runtime_artifact_identity(
            {"effective_classpath_sanitized": []},
            {"loaded_netty_artifacts": [], "loaded_code_source_groups": [],
             "loader_netty_artifacts": [loader_only]}, pin))
        tampered = dict(loader_only, sha256="c" * 64)
        errors = VALIDATOR.validate_runtime_artifact_identity(
            {"effective_classpath_sanitized": []},
            {"loader_netty_artifacts": [tampered]}, pin)
        self.assertTrue(any("does not expose" in error for error in errors), errors)

    def test_current_and_fixed_netty_profiles_execute_hooks_and_controls(self):
        self.assertEqual(4, len(self.profiles))
        self.assertEqual({"4.1.77.Final", "4.2.15.Final", "4.1.137.Final", "4.2.17.Final"},
                         {profile["expected_and_loaded_netty_version"]
                          for profile, _ in self.profiles.values()})
        for profile, events in self.profiles.values():
            with self.subTest(profile=profile["profile_id"]):
                environment = {
                    "environment_id": profile["profile_id"],
                    "minecraft_version": profile["synthetic_process_minecraft_version"],
                    "distribution": "synthetic", "launcher": "local-control",
                    "fabric_loader_expected": None,
                    "expected_netty_codec": profile["expected_and_loaded_netty_version"],
                }
                errors = VALIDATOR.validate_run_events(
                    events, environment, ROOT, require_remote_pipeline=False)
                self.assertEqual([], errors)
                handlers = {event.get("handler_name"): event.get("handler_class") for event in events
                            if event.get("event") == "handler_added"}
                self.assertEqual("io.netty.handler.codec.compression.Lz4FrameDecoder", handlers["control-lz4"])
                self.assertEqual("io.netty.handler.codec.compression.JdkZlibDecoder", handlers["control-zlib"])
                self.assertEqual("io.netty.channel.ChannelInboundHandlerAdapter", handlers["control-plain"])

    def test_synthetic_observations_do_not_require_a_product_commit_in_shallow_checkout(self):
        profile, original = next(iter(self.profiles.values()))
        events = copy.deepcopy(original)
        start = next(event for event in events if event.get("event") == "process_start")
        start["source_sha"] = "f" * 40
        environment = {
            "minecraft_version": profile["synthetic_process_minecraft_version"],
            "distribution": "synthetic", "launcher": "local-control",
            "fabric_loader_expected": None,
            "expected_netty_codec": profile["expected_and_loaded_netty_version"],
        }
        errors = VALIDATOR.validate_run_events(events, environment, ROOT, require_remote_pipeline=False)
        self.assertFalse(any("source SHA is not an available Git commit" in error for error in errors), errors)

    def test_minecraft_observations_still_require_the_product_source_commit(self):
        events = copy.deepcopy(next(iter(self.profiles.values()))[1])
        start = next(event for event in events if event.get("event") == "process_start")
        start["source_sha"] = "f" * 40
        environment = {
            "minecraft_version": "synthetic-1.19", "distribution": "client",
            "launcher": "local-control", "fabric_loader_expected": None,
            "expected_netty_codec": "4.1.77.Final",
        }
        errors = VALIDATOR.validate_run_events(events, environment, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("source SHA is not an available Git commit" in error for error in errors), errors)

    def test_missing_transform_hook_is_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = [event for event in events if event.get("event") != "pipeline_class_transformed"]
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("class transformations are not confirmed" in error for error in errors), errors)

    def test_missing_channel_active_hook_is_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = [event for event in events if event.get("event") != "channel_active_pipeline_snapshot"]
        end = next(event for event in mutated if event.get("event") == "process_end")
        end["channel_active_pipeline_snapshot_count"] = 0
        end["active_socket_channel_fingerprints"] = []
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("channel-active pipeline snapshot hook coverage" in error for error in errors), errors)

    def test_unobserved_active_channel_identity_is_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = copy.deepcopy(events)
        end = next(event for event in mutated if event.get("event") == "process_end")
        end["active_socket_channel_fingerprints"] = ["f" * 64]
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("aggregate disagrees with pipeline snapshots" in error for error in errors), errors)

    def test_channel_assessment_must_cover_each_connected_socket(self):
        fingerprint = "a" * 64
        end = {"connected_socket_channel_fingerprints": [fingerprint],
               "active_socket_channel_fingerprints": [fingerprint]}
        assessment = {
            "channel_fingerprint": fingerprint, "channel_role": "client play connection",
            "input_direction": "inbound", "input_origin": "remote_peer",
            "untrusted_remote_input": True, "protocol_framing": "Minecraft framed packets",
            "authentication_phase": "authenticated", "per_channel_resource_limits": "unknown",
            "aggregate_resource_limits": "unknown", "assessment_basis": "operator source review",
        }
        self.assertEqual([], VALIDATOR.validate_channel_assessments(end, [assessment]))
        errors = VALIDATOR.validate_channel_assessments(end, [])
        self.assertTrue(any("do not cover exactly" in error for error in errors), errors)

    def test_channel_assessment_rejects_raw_ip_addresses(self):
        fingerprint = "b" * 64
        end = {"connected_socket_channel_fingerprints": [fingerprint],
               "active_socket_channel_fingerprints": [fingerprint]}
        assessment = {
            "channel_fingerprint": fingerprint, "channel_role": "client play connection",
            "input_direction": "inbound", "input_origin": "remote_peer",
            "untrusted_remote_input": True, "protocol_framing": "Minecraft framed packets",
            "authentication_phase": "authenticated", "per_channel_resource_limits": "unknown",
            "aggregate_resource_limits": "unknown", "assessment_basis": "connected to 198.51.100.24",
        }
        errors = VALIDATOR.validate_channel_assessments(end, [assessment])
        self.assertTrue(any("must not contain addresses" in error for error in errors), errors)

    def test_unverified_handler_jar_identity_is_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = copy.deepcopy(events)
        target = next(event for event in mutated if event.get("event") == "handler_added"
                      and event.get("handler_name") == "control-lz4")
        target["handler_code_source"]["hash_verified"] = False
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("handler lacks a verified code-source" in error for error in errors), errors)

    def test_wrong_minecraft_version_is_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = copy.deepcopy(events)
        start = next(event for event in mutated if event.get("event") == "process_start")
        start["minecraft_version"] = "1.21.11"
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("Minecraft version does not match" in error for error in errors), errors)

    def test_mixed_process_run_ids_are_rejected(self):
        events = next(iter(self.profiles.values()))[1]
        mutated = copy.deepcopy(events)
        end = next(event for event in mutated if event.get("event") == "process_end")
        end["run_id"] = "00000000-0000-0000-0000-000000000000"
        errors = VALIDATOR.validate_run_events(
            mutated, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                      "launcher": "local-control", "fabric_loader_expected": None,
                      "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=False)
        self.assertTrue(any("different run" in error or "exactly one" in error for error in errors), errors)

    def test_synthetic_pipeline_does_not_satisfy_remote_input_coverage(self):
        events = next(iter(self.profiles.values()))[1]
        errors = VALIDATOR.validate_run_events(
            events, {"minecraft_version": "synthetic-1.19", "distribution": "synthetic",
                     "launcher": "local-control", "fabric_loader_expected": None,
                     "expected_netty_codec": "4.1.77.Final"}, ROOT, require_remote_pipeline=True)
        self.assertTrue(any("connected socket" in error for error in errors), errors)

    def test_failed_launch_without_shutdown_is_preserved_but_not_accepted(self):
        with tempfile.TemporaryDirectory(prefix="issue45-failed-capture-") as tmp:
            archive = Path(tmp) / "evidence"
            shutil.copytree(EVIDENCE, archive)
            matrix_path = archive / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            env = matrix["environments"][0]
            env["status"] = "not_passed"
            env["not_passed_reason"] = "Synthetic test: process exited before shutdown hook"
            env.pop("not_executed_reason", None)
            env["operator_exit_code"] = 1
            env["operator_startup_outcome"] = "failed"
            start = copy.deepcopy(next(event for event in self.profiles[
                "mc-1.19-netty-4.1.77"][1] if event["event"] == "process_start"))
            start.update(minecraft_version=env["minecraft_version"],
                         distribution=env["distribution"], launcher=env["launcher"],
                         source_sha=subprocess.check_output(
                             ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip())
            observation = json.dumps(start, sort_keys=True) + "\n"
            capture = archive / "captures" / "failed.jsonl"
            capture.parent.mkdir(parents=True, exist_ok=True)
            capture.write_text(observation, encoding="utf-8", newline="\n")
            env["observations_file"] = "captures/failed.jsonl"
            env["observations_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, summary = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertEqual([], errors)
            self.assertEqual(0, summary["captured_runtime_environment_count"])
            env["status"] = "captured"
            env["operator_exit_code"] = 0
            env["operator_startup_outcome"] = "started"
            matrix["captured_observations"] = [env["environment_id"]]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("process_end" in error for error in errors), errors)


    def test_control_packager_atomically_replaces_existing_jar(self):
        with tempfile.TemporaryDirectory(prefix="issue45-control-jar-") as tmp:
            root = Path(tmp)
            classes = root / "test-classes"
            classes.mkdir()
            a = classes / "ControlMain.class"
            a.write_bytes(b"compiled-control-v1")
            archive = root / "issue45-synthetic-control.jar"
            CONTROLS.package_control_classes(classes, archive)
            with zipfile.ZipFile(archive) as jar:
                self.assertEqual(b"compiled-control-v1", jar.read("ControlMain.class"))
            a.write_bytes(b"compiled-control-v2")
            b = classes / "Initializer.class"
            b.write_bytes(b"second-control")
            CONTROLS.package_control_classes(classes, archive)
            with zipfile.ZipFile(archive) as jar:
                self.assertEqual({"ControlMain.class", "Initializer.class"}, set(jar.namelist()))
                self.assertEqual(b"compiled-control-v2", jar.read("ControlMain.class"))
            self.assertFalse(list(root.glob("*.part")))

    def test_fresh_compilation_excludes_deleted_or_renamed_bytecode(self):
        with tempfile.TemporaryDirectory(prefix="issue45-fresh-classes-") as temp:
            root = Path(temp)
            old_output = root / "test-classes"
            old_output.mkdir()
            (old_output / "Obsolete.class").write_bytes(b"prior persistent build output")
            destination = root / "control.jar"
            builds = []

            def compile_fake(command, check):
                self.assertTrue(check)
                self.assertIn("-d", command)
                compiled = Path(command[command.index("-d") + 1])
                self.assertNotEqual(old_output, compiled)
                self.assertTrue(compiled.is_dir())
                if not builds:
                    (compiled / "LegacyInitializer.class").write_bytes(b"legacy initializer")
                    (compiled / "ControlMain.class").write_bytes(b"v1")
                else:
                    (compiled / "CurrentInitializer.class").write_bytes(b"current initializer")
                    (compiled / "ControlMain.class").write_bytes(b"v2")
                builds.append(compiled)
                return subprocess.CompletedProcess(command, 0)

            with patch.object(CONTROLS.subprocess, "run", side_effect=compile_fake):
                CONTROLS.compile_control_jar(root, root / "compiler.jar",
                                             root / "ControlMain.java", "pinned-classpath",
                                             destination)
                with zipfile.ZipFile(destination) as archive:
                    self.assertEqual({"LegacyInitializer.class", "ControlMain.class"},
                                     set(archive.namelist()))
                CONTROLS.compile_control_jar(root, root / "compiler.jar",
                                             root / "ControlMain.java", "pinned-classpath",
                                             destination)
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual({"CurrentInitializer.class", "ControlMain.class"},
                                 set(archive.namelist()))
                self.assertEqual(b"v2", archive.read("ControlMain.class"))
                self.assertNotIn("LegacyInitializer.class", archive.namelist())
                self.assertNotIn("Obsolete.class", archive.namelist())
            self.assertNotEqual(builds[0], builds[1])
            self.assertFalse(any(path.exists() for path in builds))
            self.assertEqual(b"prior persistent build output",
                             (old_output / "Obsolete.class").read_bytes())

    def test_fresh_synthetic_archive_cannot_reuse_retained_results(self):
        with tempfile.TemporaryDirectory(prefix="issue45-fresh-archive-") as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "environment-matrix.json").write_bytes(b"retained matrix")
            (source / "remediation-compatibility.json").write_bytes(b"historical bytes")
            (source / "synthetic-control-verification.json").write_bytes(b"old summary")
            (source / "synthetic-control-observation-old.jsonl").write_bytes(b"old capture")
            destination = root / "fresh"
            created = CONTROLS.prepare_fresh_evidence_dir(source, destination)
            # Windows tempfile may expose an 8.3 alias (RUNNER~1) while
            # resolve() returns the long path. Compare filesystem identity.
            self.assertTrue(destination.samefile(created))
            self.assertEqual(b"retained matrix", (destination / "environment-matrix.json").read_bytes())
            self.assertEqual(b"historical bytes", (destination / "remediation-compatibility.json").read_bytes())
            self.assertFalse((destination / "synthetic-control-verification.json").exists())
            self.assertEqual([], list(destination.glob("synthetic-control-observation-*.jsonl")))
            self.assertEqual(b"old summary", (source / "synthetic-control-verification.json").read_bytes())
            self.assertEqual(b"old capture", (source / "synthetic-control-observation-old.jsonl").read_bytes())
            with self.assertRaises(FileExistsError):
                CONTROLS.prepare_fresh_evidence_dir(source, destination)
            with self.assertRaisesRegex(ValueError, "outside the retained archive"):
                CONTROLS.prepare_fresh_evidence_dir(source, source / "nested")
            self.assertFalse((source / "nested").exists())

    def test_control_jar_uses_canonical_order_and_zip_metadata_across_rebuilds(self):
        with tempfile.TemporaryDirectory(prefix="issue45-canonical-zip-") as temp:
            root = Path(temp)
            classes = root / "classes"
            for name, data in (
                ("nested/alpha.class", b"a"),
                ("nested/Bee.class", b"b"),
                ("nested/Zeta.class", b"z"),
                ("Top.class", b"top")
            ):
                destination = classes / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            jar = root / "control.jar"
            CONTROLS.package_control_classes(classes, jar)
            baseline_hash = hashlib.sha256(jar.read_bytes()).hexdigest()
            # A common golden byte digest is checked by every Linux/Windows
            # Java 21/25 matrix run, not just by two builds on one host.
            self.assertEqual(
                "a040924e75b1c60dde3415371b0f1c00ea52a50187b906eebb7015d3e917c1a1",
                baseline_hash)
            expected_order = ["Top.class", "nested/Bee.class", "nested/Zeta.class",
                              "nested/alpha.class"]
            with zipfile.ZipFile(jar) as archive:
                self.assertEqual(expected_order, archive.namelist())
                for name in expected_order:
                    info = archive.getinfo(name)
                    self.assertEqual((1980, 1, 1, 0, 0, 0), info.date_time)
                    self.assertEqual(3, info.create_system)
                    self.assertEqual(0o100644, info.external_attr >> 16)
                    self.assertEqual(zipfile.ZIP_STORED, info.compress_type)
            import os
            for member in classes.rglob("*.class"):
                os.utime(member, (1_000_000_000, 1_000_000_000))
            CONTROLS.package_control_classes(classes, jar)
            self.assertEqual(baseline_hash, hashlib.sha256(jar.read_bytes()).hexdigest())

    def test_case_colliding_class_names_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix="issue45-name-collision-") as temp:
            root = Path(temp)
            classes = root / "classes"
            classes.mkdir()
            (classes / "Apple.class").write_bytes(b"first")
            (classes / "apple.class").write_bytes(b"second")
            if len(list(classes.iterdir())) != 2:
                self.skipTest("filesystem is case-insensitive")
            with self.assertRaisesRegex(ValueError, "case-insensitive"):
                CONTROLS.package_control_classes(classes, root / "control.jar")

    def test_valid_final_json_object_without_lf_is_only_allowed_for_failed_runs(self):
        with tempfile.TemporaryDirectory(prefix="issue45-lf-tail-") as tmp:
            archive = Path(tmp) / "evidence"
            shutil.copytree(EVIDENCE, archive)
            matrix_path = archive / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            env = matrix["environments"][0]
            env.update(status="not_passed",
                       not_passed_reason="Operator interrupted JVM between JSON and LF writes",
                       operator_exit_code=1, operator_startup_outcome="failed")
            env.pop("not_executed_reason", None)
            source_events = self.profiles["mc-1.19-netty-4.1.77"][1]
            start = copy.deepcopy(next(event for event in source_events
                                       if event["event"] == "process_start"))
            diagnostic = copy.deepcopy(next(event for event in source_events
                                            if event["event"] == "diagnostic"))
            start.update(minecraft_version=env["minecraft_version"],
                         distribution=env["distribution"], launcher=env["launcher"],
                         source_sha=subprocess.check_output(
                             ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                             text=True).strip())
            capture = archive / "captures" / "missing-final-lf.jsonl"
            capture.parent.mkdir(parents=True)
            prefix = (json.dumps(start) + "\n").encode("utf-8")
            final_object = json.dumps(diagnostic).encode("utf-8")
            capture.write_bytes(prefix + final_object)
            env["observations_file"] = "captures/missing-final-lf.jsonl"
            env["observations_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, summary = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertEqual([], errors)
            self.assertEqual([env["environment_id"]], summary["missing_lf_failed_capture_ids"])
            self.assertEqual([], summary["truncated_failed_capture_ids"])
            self.assertEqual(0, summary["captured_runtime_environment_count"])
            events, tail = VALIDATOR.read_capture_jsonl(capture, allow_torn_final=True)
            self.assertEqual("valid_final_record_missing_lf", tail)
            self.assertEqual(["process_start", "diagnostic"], [e["event"] for e in events])
            with self.assertRaisesRegex(ValueError, "required LF"):
                VALIDATOR.read_capture_jsonl(capture, allow_torn_final=False)
            env["status"] = "captured"
            env["operator_exit_code"] = 0
            env["operator_startup_outcome"] = "started"
            matrix["captured_observations"] = [env["environment_id"]]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("valid JSON Lines" in item for item in errors), errors)
            capture.write_bytes(prefix + final_object + b"\n")
            # Exact original bytes remain protected by the archive hash.
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("SHA-256 mismatch" in item for item in errors), errors)

    def test_missing_final_lf_does_not_hide_bad_interior_records(self):
        with tempfile.TemporaryDirectory(prefix="issue45-jsonl-interior-") as tmp:
            path = Path(tmp) / "capture.jsonl"
            path.write_bytes(b'{"event":"process_start"}\n{"bad":\n{"event":"diagnostic"}')
            with self.assertRaises((ValueError, json.JSONDecodeError)):
                VALIDATOR.read_capture_jsonl(path, allow_torn_final=True)
            path.write_bytes(b'{"event":"process_start"}\n42')
            with self.assertRaisesRegex(ValueError, "must be an object"):
                VALIDATOR.read_capture_jsonl(path, allow_torn_final=True)

    def test_failed_run_rejects_unknown_git_commit_but_exempts_synthetic(self):
        start = copy.deepcopy(next(event for event in self.profiles[
            "mc-1.19-netty-4.1.77"][1] if event["event"] == "process_start"))
        start.update(minecraft_version="1.19", distribution="client", launcher="official",
                     source_sha="f" * 40)
        environment = {"minecraft_version": "1.19", "distribution": "client",
                       "launcher": "official", "fabric_loader_expected": None}
        errors = VALIDATOR.validate_incomplete_run_events([start], environment, ROOT)
        self.assertTrue(any("source SHA is not an available Git commit" in error
                            for error in errors), errors)
        start["distribution"] = "synthetic"
        environment["distribution"] = "synthetic"
        errors = VALIDATOR.validate_incomplete_run_events([start], environment, ROOT)
        self.assertFalse(any("source SHA is not an available Git commit" in error
                             for error in errors), errors)

    def test_failed_run_torn_final_record_is_preserved_not_promoted(self):
        with tempfile.TemporaryDirectory(prefix="issue45-torn-capture-") as tmp:
            archive = Path(tmp) / "evidence"
            shutil.copytree(EVIDENCE, archive)
            matrix_path = archive / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            env = matrix["environments"][0]
            env["status"] = "not_passed"
            env["not_passed_reason"] = "Operator observed early process termination"
            env.pop("not_executed_reason", None)
            env["operator_exit_code"] = 1
            env["operator_startup_outcome"] = "failed"
            start = copy.deepcopy(next(event for event in self.profiles[
                "mc-1.19-netty-4.1.77"][1] if event["event"] == "process_start"))
            start.update(minecraft_version=env["minecraft_version"],
                         distribution=env["distribution"], launcher=env["launcher"],
                         source_sha=subprocess.check_output(
                             ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip())
            capture = archive / "captures" / "torn.jsonl"
            capture.parent.mkdir(parents=True)
            complete = (json.dumps(start, sort_keys=True) + "\n").encode("utf-8")
            torn = b'{"event":"process_end","incomplete":'
            capture.write_bytes(complete + torn)
            env["observations_file"] = "captures/torn.jsonl"
            env["observations_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, summary = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertEqual([], errors)
            self.assertEqual([env["environment_id"]], summary["truncated_failed_capture_ids"])
            self.assertEqual(0, summary["captured_runtime_environment_count"])
            env["status"] = "captured"
            env["operator_exit_code"] = 0
            env["operator_startup_outcome"] = "started"
            matrix["captured_observations"] = [env["environment_id"]]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("valid JSON Lines" in error for error in errors), errors)
            env["status"] = "not_passed"
            matrix["captured_observations"] = []
            capture.write_bytes(complete + b'{"broken":\n' + torn)
            env["observations_sha256"] = hashlib.sha256(capture.read_bytes()).hexdigest()
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("valid JSON Lines" in error for error in errors), errors)
            capture.write_bytes(complete + torn)
            # A valid prefix cannot survive an incorrect digest of the raw bytes.
            errors, _ = VALIDATOR.validate_evidence(archive, ROOT)
            self.assertTrue(any("SHA-256 mismatch" in error for error in errors), errors)

    def test_legacy_v1_capture_without_loader_list_requires_verified_pin(self):
        pin = {"path": "io/netty/netty-codec/4.1.77.Final/netty-codec-4.1.77.Final.jar",
               "sha1": "a" * 40, "sha256": "b" * 64, "size_bytes": 123}
        source = {"artifact": "netty-codec-4.1.77.Final.jar", "sha1": "a" * 40,
                  "sha256": "b" * 64, "size_bytes": 123, "hash_verified": True}
        self.assertEqual([], VALIDATOR.validate_loader_availability_contract(
            {"effective_classpath_sanitized": [source]}, {}, pin))
        self.assertTrue(VALIDATOR.validate_loader_availability_contract(
            {"effective_classpath_sanitized": []}, {}, pin))
        self.assertTrue(VALIDATOR.validate_loader_availability_contract(
            {"effective_classpath_sanitized": [source]}, {}, None))
        self.assertEqual([], VALIDATOR.validate_loader_availability_contract(
            {"effective_classpath_sanitized": []}, {"loader_netty_artifacts": []}, pin))
        self.assertTrue(VALIDATOR.validate_loader_availability_contract(
            {"effective_classpath_sanitized": [source]}, {"loader_netty_artifacts": "bad"}, pin))

    def test_failed_launch_rejects_mixed_process_ids(self):
        start = copy.deepcopy(next(event for event in self.profiles[
            "mc-1.19-netty-4.1.77"][1] if event["event"] == "process_start"))
        environment = {"minecraft_version": start["minecraft_version"],
                       "distribution": start["distribution"], "launcher": start["launcher"],
                       "fabric_loader_expected": None}
        changed = dict(start, event="pipeline_transform_error", run_id="other-run")
        errors = VALIDATOR.validate_incomplete_run_events([start, changed], environment)
        self.assertTrue(any("one nonempty run identity" in error or "another process" in error
                            for error in errors), errors)

    def test_duplicate_environment_identity_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="issue45-duplicate-env-") as temp:
            copy_path = Path(temp) / "evidence"
            shutil.copytree(EVIDENCE, copy_path)
            matrix_path = copy_path / "environment-matrix.json"
            matrix = json.loads(matrix_path.read_text())
            matrix["environments"][1]["environment_id"] = matrix["environments"][0]["environment_id"]
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            errors, _ = VALIDATOR.validate_evidence(copy_path, ROOT)
            self.assertTrue(any("duplicate identities" in error for error in errors), errors)

    def test_access_token_value_is_redacted_in_observation(self):
        for profile in self.summary["profiles"]:
            raw = (EVIDENCE / profile["observation_file"]).read_text()
            self.assertIn("-DaccessToken=<redacted>", raw)
            self.assertIn("-Dsession:<redacted>", raw)
            self.assertIn("-Dserver=<redacted>", raw)
            self.assertIn("-Dusername=<redacted>", raw)
            self.assertNotIn("synthetic-secret-must-not-appear", raw)
            self.assertNotIn("play.example.invalid", raw)
            self.assertNotIn("synthetic-player-identifier", raw)


if __name__ == "__main__":
    unittest.main()
