"""Show that PR #54's old exporter accepted stale focused-review evidence."""
import copy
import gzip
import hashlib
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_dependencies as audit
import reconcile_issue45_live_audits as live

spec = importlib.util.spec_from_file_location('pr54_priority_export',
    ROOT / 'tests/fixtures/issue45_pr54_priority_export.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
prior_spec = importlib.util.spec_from_file_location('pr55_focused_review',
    ROOT / 'tests/fixtures/issue45_pr55_focused_review.py')
prior = importlib.util.module_from_spec(prior_spec)
prior_spec.loader.exec_module(prior)

EVIDENCE = 'docs/dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json'
INDEX = 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
LEDGER = 'docs/security-advisories.json'
ADVISORY = 'GHSA-jfh8-c2jp-5v3q'


class FocusedReviewApplicabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'root'
        self.live = Path(self.temp.name) / 'live'
        shutil.copytree(live.LIVE, self.live)
        index = json.loads((ROOT / INDEX).read_bytes())
        for name in [INDEX, EVIDENCE, LEDGER, *(item['report'] for item in index['reports'].values())]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        baseline = live.priority_register(self.live, self.root)
        self.assertEqual(baseline, legacy.priority_register(self.live, self.root))
        self.assertEqual(baseline, json.loads((live.LIVE / 'priority-register.json').read_bytes()))

    def mutate_report(self, label, edit):
        index_path = self.live / 'artifact-index.json'
        index = json.loads(index_path.read_bytes())
        item = next(row for row in index['artifacts'] if row['name'] == label)
        path = self.live / 'raw' / (str(item['id']) + '.zip')
        with ZipFile(path) as archive:
            data = {name: archive.read(name) for name in archive.namelist()}
        member = 'candidate-dependency-audit.json' if label.startswith('candidate-') else 'dependency-audit.json'
        report = json.loads(data[member])
        edit(report)
        data[member] = (json.dumps(report, indent=2) + '\n').encode()
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name, raw in data.items():
                archive.writestr(name, raw)
        raw = output.getvalue()
        path.write_bytes(raw)
        item['size'] = len(raw)
        item['digest'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
        index_path.write_text(json.dumps(index, indent=2) + '\n')

    def mutate_focused(self, edit):
        path = self.root / EVIDENCE
        evidence = json.loads(path.read_bytes())
        edit(evidence)
        path.write_text(json.dumps(evidence, indent=2) + '\n')
        ledger_path = self.root / LEDGER
        ledger = json.loads(ledger_path.read_bytes())
        ledger['critical_reachability_evidence']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        ledger_path.write_text(json.dumps(ledger, indent=2) + '\n')

    def assert_legacy_accepts_but_current_rejects(self, reason):
        # Ensure the mutated report is internally sound and the previous exporter
        # really accepted it, rather than failing for an unrelated ZIP checksum.
        old_index, _, _ = live.historic(self.root)
        live.verify_live(self.live, old_index)
        self.assertTrue(legacy.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, reason):
            live.priority_register(self.live, self.root)

    def test_changed_scope_invalidates_review(self):
        def edit(report):
            row = next(r for r in report['matches'] if r['advisory'] == ADVISORY)
            purl = row['purl']
            report['inventories']['runtime/1.14'].remove(purl)
            for match in report['matches']:
                if match['purl'] == purl:
                    match['scopes'] = sorted(s for s, items in report['inventories'].items() if purl in items)
        self.mutate_report('candidate-dependency-audit-0', edit)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: dependency scopes')

    def test_changed_runtime_manifest_invalidates_prior_review(self):
        self.mutate_report('candidate-dependency-audit-0',
            lambda report: report['runtime_manifests']['1.14'].update(sha1='0' * 40))
        old_index, _, _ = live.historic(self.root)
        live.verify_live(self.live, old_index)
        # The merged PR #55 check accepted the same source/scopes/fingerprint.
        with patch.object(live, 'validate_focused_review', prior.validate_focused_review):
            self.assertTrue(live.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'focused review stale: runtime manifest identity'):
            live.priority_register(self.live, self.root)

    def test_missing_reviewed_runtime_manifest_is_rejected(self):
        def edit(evidence):
            finding = next(row for row in evidence['findings'] if row['advisory_id'] == ADVISORY)
            finding['occurrences'][0]['minecraft_artifacts'].pop()
        self.mutate_focused(edit)
        with patch.object(live, 'validate_focused_review', prior.validate_focused_review):
            self.assertTrue(live.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'focused review stale: runtime manifest coverage'):
            live.priority_register(self.live, self.root)

    def test_changed_advisory_fingerprint_invalidates_review(self):
        def edit(report):
            advisory = report['advisories'][ADVISORY]
            advisory['details'] += ' Changed vulnerability details for the test.'
            for match in report['matches']:
                if match['advisory'] == ADVISORY:
                    match['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.mutate_report('candidate-dependency-audit-0', edit)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: advisory fingerprint')

    def test_changed_review_relevant_metadata_invalidates_review(self):
        def edit(report):
            report['advisories'][ADVISORY]['summary'] += ' changed'
        self.mutate_report('candidate-dependency-audit-0', edit)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: advisory metadata')

    def test_changed_disposition_invalidates_review(self):
        def edit(report):
            next(r for r in report['matches'] if r['advisory'] == ADVISORY)['disposition'] = 'Actionable'
        self.mutate_report('candidate-dependency-audit-0', edit)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: severity, disposition')

    def test_count_preserving_duplicate_focused_occurrence_is_rejected(self):
        def edit(evidence):
            row = next(f for f in evidence['findings'] if f['advisory_id'] == ADVISORY)
            row['occurrences'][0] = copy.deepcopy(row['occurrences'][1])
        self.mutate_focused(edit)
        with self.assertRaises(ValueError):
            legacy.priority_register(self.live, self.root)
        with self.assertRaisesRegex(ValueError, 'duplicate focused review occurrence'):
            live.priority_register(self.live, self.root)

    def test_missing_focused_advisory_cannot_silently_remove_review_coverage(self):
        self.mutate_focused(lambda evidence: evidence.update(
            findings=[row for row in evidence['findings'] if row['advisory_id'] != ADVISORY]))
        self.assertTrue(legacy.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'incomplete focused advisory coverage: CRITICAL'):
            live.priority_register(self.live, self.root)

    def test_same_source_changed_historical_report_needs_review(self):
        index_path = self.root / INDEX
        index = json.loads(index_path.read_bytes())
        spec = index['reports']['candidate|1.14-1.14.4']
        path = self.root / spec['report']
        raw = gzip.decompress(path.read_bytes()) + b'\n'
        path.write_bytes(gzip.compress(raw, mtime=0))
        digest = hashlib.sha256(raw).hexdigest()
        spec['sha256_uncompressed'] = digest
        for row in index['records']:
            if row['report'] == spec['report']:
                row['report_sha256_uncompressed'] = digest
        index_path.write_text(json.dumps(index, indent=2) + '\n')
        def update(evidence):
            evidence['source_provenance']['finding_index']['sha256'] = hashlib.sha256(index_path.read_bytes()).hexdigest()
        self.mutate_focused(update)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: historical report provenance')

    def test_unrelated_advisory_change_keeps_focused_review(self):
        before = live.priority_register(self.live, self.root)
        self.mutate_report('candidate-dependency-audit-0',
                           lambda report: report['advisories']['GHSA-4jrv-ppp4-jm57'].update(summary='changed'))
        after = live.priority_register(self.live, self.root)
        def focused(report):
            row = copy.deepcopy(next(row for row in report['advisories'] if row['advisory_id'] == ADVISORY))
            # Repacking the report legitimately changes its enclosing archive hash.
            for occurrence in row['occurrences']:
                occurrence.pop('source_report_archive_sha256')
            return row
        self.assertEqual(focused(before), focused(after))

    def test_fresh_report_timestamp_does_not_change_review(self):
        before = live.priority_register(self.live, self.root)
        self.mutate_report('candidate-dependency-audit-0', lambda report: report.update(scanned_on='2026-11-23'))
        after = live.priority_register(self.live, self.root)
        def provenance(report):
            item = next(row for row in report['advisories'] if row['advisory_id'] == ADVISORY)
            return item['focused_evidence'], item['reviewer'], item['review_date'], item['follow_up']
        self.assertEqual(provenance(before), provenance(after))

    def test_advisory_modified_timestamp_alone_does_not_stale_review(self):
        before = live.priority_register(self.live, self.root)
        index = json.loads((self.live / 'artifact-index.json').read_bytes())
        labels = []
        for item in index['artifacts']:
            if not item['name'].startswith(('candidate-dependency-audit-', 'dependency-audit-')):
                continue
            with ZipFile(self.live / 'raw' / (str(item['id']) + '.zip')) as archive:
                member = ('candidate-dependency-audit.json' if item['name'].startswith('candidate-')
                          else 'dependency-audit.json')
                if ADVISORY in json.loads(archive.read(member))['advisories']:
                    labels.append(item['name'])
        self.assertEqual(len(labels), 3)
        for label in labels:
            self.mutate_report(label, lambda report: report['advisories'][ADVISORY].update(
                modified='2026-11-23T00:00:00Z'))
        after = live.priority_register(self.live, self.root)
        def provenance(report):
            row = next(item for item in report['advisories'] if item['advisory_id'] == ADVISORY)
            return row['focused_evidence'], row['reviewer'], row['review_date'], row['follow_up']
        self.assertEqual(provenance(before), provenance(after))

    def test_mixed_administrative_timestamps_preserve_review_and_source_values(self):
        before = live.priority_register(self.live, self.root)
        self.mutate_report('candidate-dependency-audit-0', lambda report:
            report['advisories'][ADVISORY].update(modified='2026-11-23T00:00:00Z'))
        # The former exporter rejected mixed timestamps before checking review applicability.
        with self.assertRaisesRegex(ValueError, 'inconsistent advisory metadata'):
            legacy.priority_register(self.live, self.root)
        after = live.priority_register(self.live, self.root)
        def focused(report):
            return next(row for row in report['advisories'] if row['advisory_id'] == ADVISORY)
        old, new = focused(before), focused(after)
        self.assertEqual((new['focused_evidence'], new['reviewer'], new['review_date'], new['follow_up']),
                         (old['focused_evidence'], old['reviewer'], old['review_date'], old['follow_up']))
        self.assertIsNone(new['modified'])
        self.assertEqual(new['modified_by_source']['candidate|1.14-1.14.4'], '2026-11-23T00:00:00Z')
        self.assertEqual(len(new['modified_by_source']), 3)
        scan = live.reconcile(self.live, self.root)
        self.assertIn('candidate|1.14-1.14.4|' + ADVISORY, scan['metadata_changed'])
        self.assertEqual(scan['failing_occurrences'], 490)


if __name__ == '__main__':
    unittest.main()
