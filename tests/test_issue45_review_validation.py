"""Regression controls for the Issue #45 source and report bindings."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/validate_critical_reachability_evidence.py'
ARCHIVE = ROOT / 'docs/dependency-evidence/critical-reachability-2026-11-21/issue45-review-2026-11-22/historical-scripts'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


current = load_module('current_issue45_validator', SCRIPT)
previous = load_module('previous_issue45_validator', ARCHIVE / SCRIPT.name)
mojang = load_module('current_mojang_validator', ROOT / 'scripts/validate_mojang_log4j_runtime_probes.py')
old_mojang = load_module('previous_mojang_validator', ARCHIVE / 'validate_mojang_log4j_runtime_probes.py')
for name in ('ROOT', 'BASE', 'ARCHIVE', 'EVIDENCE', 'LEDGER'):
    setattr(previous, name, getattr(current, name))
for name in ('ROOT', 'EVIDENCE', 'SOURCE_REPORT'):
    setattr(old_mojang, name, getattr(mojang, name))


class FindingCoverageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = current.load(current.EVIDENCE)
        cls.index = current.load(current.ARCHIVE / 'finding-index.json')

    def prior_validate(self, mutated, commons=None):
        # The immutable report cites old script bytes. Resolve those citations
        # to their retained snapshots while leaving every other reference real.
        original_load, original_hash = previous.load, previous.raw_hash
        def read(path):
            if path == previous.EVIDENCE:
                return mutated
            if commons is not None and path == previous.BASE / 'commons-compress-reachability-2026-11-21.json':
                return commons
            return original_load(path)
        def digest(path):
            path = Path(path)
            try:
                rel = path.relative_to(ROOT).as_posix()
            except ValueError:
                rel = ''
            if rel in current.HISTORICAL_SCRIPT_PATHS:
                path = ARCHIVE / path.name
            return original_hash(path)
        with patch.object(previous, 'load', side_effect=read), \
                patch.object(previous, 'raw_hash', side_effect=digest):
            return previous.validate()

    def current_validate(self, mutated, commons=None):
        original_load = current.load
        def read(path):
            if path == current.EVIDENCE:
                return mutated
            if commons is not None and path == current.BASE / 'commons-compress-reachability-2026-11-21.json':
                return commons
            return original_load(path)
        with patch.object(current, 'load', side_effect=read):
            return current.validate()

    def test_unmodified_source_bound_evidence_passes(self):
        self.assertEqual(current.validate(), (490, 93))
        self.assertEqual(self.prior_validate(copy.deepcopy(self.evidence)), (490, 93))

    def test_duplicate_replacing_other_occurrence_is_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        finding = next(row for row in evidence['findings'] if row['advisory_id'] == 'GHSA-7rjr-3q55-vv33')
        finding['occurrences'][1] = copy.deepcopy(finding['occurrences'][0])
        self.assertEqual(len(finding['occurrences']), 3)
        self.assertEqual(self.prior_validate(evidence), (490, 93))
        with self.assertRaisesRegex(ValueError, 'duplicate evidence occurrence'):
            self.current_validate(evidence)

    def test_other_valid_audit_for_same_source_is_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        finding = next(row for row in evidence['findings'] if row['advisory_id'] == 'GHSA-7rjr-3q55-vv33')
        finding['occurrences'][0]['source_report'] = {
            'path': 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/candidate/candidate-dependency-audit-0/gradle-tool-audit.json.gz',
            'sha256_uncompressed': '6137c9e6a7ebabc3130581363b31de627cf2a05b83fcf180bf711d6f707c7460',
        }
        self.assertEqual(self.prior_validate(evidence), (490, 93))
        with self.assertRaisesRegex(ValueError, 'source report does not match indexed dependency audit'):
            self.current_validate(evidence)

    def test_source_sha_and_package_version_are_checked(self):
        for field, value in (('source_sha', '0' * 40), ('package_version', '0.0')):
            with self.subTest(field=field):
                evidence = copy.deepcopy(self.evidence)
                evidence['findings'][1]['occurrences'][0][field] = value
                with self.assertRaisesRegex(ValueError, field.replace('_', ' ') if field == 'package_version' else field):
                    current.validate_occurrence_coverage(evidence, self.index)

    def test_realms_caller_coverage_and_digest_mutations(self):
        commons_path = current.BASE / 'commons-compress-reachability-2026-11-21.json'
        original = current.load(commons_path)
        inspection = current.load(current.REVIEW_INSPECTION)
        import gzip
        high_family = json.loads(gzip.decompress((current.BASE / 'high-family-inspection.json.gz').read_bytes()))
        current.validate_realms_caller_equivalence(original['additional_runtime_library_callers'], inspection, high_family)
        for mutation in ('empty', 'missing', 'duplicate', 'incorrect'):
            with self.subTest(mutation=mutation):
                commons = copy.deepcopy(original)
                row = commons['additional_runtime_library_callers'][0]
                classes = row['related_call_path_classes']
                if mutation == 'empty':
                    row['related_call_path_classes'] = []
                elif mutation == 'missing':
                    classes.pop()
                elif mutation == 'duplicate':
                    classes[1] = copy.deepcopy(classes[0])
                else:
                    classes[1]['sha256'] = 'a' * 64
                self.assertEqual(self.prior_validate(self.evidence, commons), (490, 93))
                with self.assertRaisesRegex(ValueError, 'Realms caller class'):
                    self.current_validate(self.evidence, commons)
        commons = copy.deepcopy(original)
        changed_inspection = copy.deepcopy(inspection)
        commons['additional_runtime_library_callers'][1]['related_call_path_classes'][1]['sha256'] = 'a' * 64
        changed_inspection['realms'][1]['related_call_path_classes'][1]['sha256'] = 'a' * 64
        self.assertEqual(self.prior_validate(self.evidence, commons), (490, 93))
        with self.assertRaisesRegex(ValueError, 'differs across versions'):
            current.validate_realms_caller_equivalence(commons['additional_runtime_library_callers'],
                                                       changed_inspection, high_family)

    def test_log4j_exact_configuration_binding_and_historical_correction(self):
        import gzip
        import tempfile
        inspection = current.load(current.REVIEW_INSPECTION)
        correction = current.load(current.LOG4J_ATTRIBUTION)
        chat_probe = current.load(current.BASE / 'log4j-chat-parameter-probes-2026-11-21.json')
        family = json.loads(gzip.decompress((current.BASE / 'high-family-inspection.json.gz').read_bytes()))
        current.validate_historical_log4j_attribution(correction, inspection, chat_probe, family)
        wrong = copy.deepcopy(correction)
        next(row for row in wrong['historical_runtime_case_attributions']
             if row['minecraft_version'] == '1.17.1')['historical_attribution'] = 'exact_client_embedded'
        with self.assertRaisesRegex(ValueError, 'attribution does not match client bytes'):
            current.validate_historical_log4j_attribution(wrong, inspection, chat_probe, family)

        report_path = current.BASE / 'log4j-runtime-hosted-2026-11-22/linux-report.json'
        report = current.load(report_path)
        mojang.validate_embedded_configurations(report, inspection, historical=True)
        bad = copy.deepcopy(report)
        one = next(row for row in bad['cases'] if row['name'] == '1.17.1-embedded-chat-jndi')
        one['configuration_scope'] = 'exact_client_embedded'
        # The prior validator accepts the false exact-configuration claim.
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'report.json'
            path.write_text(json.dumps(bad))
            self.assertEqual(old_mojang.validate(path)['case_count'], 27)
        with self.assertRaisesRegex(ValueError, 'must remain explicitly representative'):
            mojang.validate_embedded_configurations(bad, inspection, historical=True)

        new = copy.deepcopy(report)
        digest_by_version = {row['minecraft_version']: row['entry_sha256'] for row in inspection['clients']}
        for version in ('1.14.4', '1.17.1', '1.18.1'):
            case = next(row for row in new['cases'] if row['name'] == version + '-embedded-chat-jndi')
            case['logging_configuration'] = '1.18.1-embedded.xml' if version == '1.18.1' else '1.14.4-embedded.xml'
            case['configuration_scope'] = 'exact_client_embedded'
            case['configuration_sha256'] = digest_by_version[version]
        core_first = next(row for row in new['cases'] if row['name'] == '1.14.4-embedded-core-first-chat-jndi')
        core_first['configuration_scope'] = 'exact_client_embedded'
        core_first['configuration_sha256'] = digest_by_version['1.14.4']
        mojang.validate_embedded_configurations(new, inspection, historical=False)
        next(row for row in new['cases'] if row['name'] == '1.17.1-embedded-chat-jndi')['logging_configuration'] = '1.18.1-embedded.xml'
        with self.assertRaisesRegex(ValueError, 'does not match exact client bytes'):
            mojang.validate_embedded_configurations(new, inspection, historical=False)


if __name__ == '__main__':
    unittest.main()
