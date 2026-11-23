import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/dependency-evidence/issue45-runtime-pipeline-2026-11-23"
VALIDATOR_PATH = ROOT / "diagnostics/issue45-runtime/validate_runtime_evidence.py"
SPEC = importlib.util.spec_from_file_location("issue45_runtime_validator", VALIDATOR_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class RuntimePipelineEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads((EVIDENCE / "synthetic-control-verification.json").read_text())
        cls.profiles = {}
        for profile in cls.summary["profiles"]:
            events = [json.loads(line) for line in
                      (EVIDENCE / profile["observation_file"]).read_text().splitlines() if line.strip()]
            cls.profiles[profile["profile_id"]] = (profile, events)

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
                         distribution=env["distribution"], launcher=env["launcher"])
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
