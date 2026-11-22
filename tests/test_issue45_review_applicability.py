"""Show that PR #54's old exporter accepted stale focused-review evidence."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import gzip
import hashlib
from io import BytesIO, StringIO
import importlib.util
import inspect
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
candidate_spec = importlib.util.spec_from_file_location('pr58_priority_export',
    ROOT / 'tests/fixtures/issue45_pr58_priority_export.py')
candidate = importlib.util.module_from_spec(candidate_spec)
candidate_spec.loader.exec_module(candidate)
merged_spec = importlib.util.spec_from_file_location('pr58_merged_priority_export',
    ROOT / 'tests/fixtures/issue45_pr58_merged_priority_export.py')
merged = importlib.util.module_from_spec(merged_spec)
merged_spec.loader.exec_module(merged)

EVIDENCE = 'docs/dependency-evidence/critical-reachability-2026-11-21/source-bound-dispositions-2026-11-21.json'
INDEX = 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/finding-index.json'
ARCHIVE_INDEX = 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2/archive-index.json'
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

    def mutate_historical_report(self, edit):
        # Copy the full archive only for these tests, then rebuild every changed
        # checksum/reference in the disposable fixture, never in retained evidence.
        archive_path = self.root / ARCHIVE_INDEX
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / ARCHIVE_INDEX, archive_path)
        archive_index = json.loads(archive_path.read_bytes())
        for entry in archive_index['files']:
            target = self.root / entry['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(ROOT / entry['path'], target)
        index_path = self.root / INDEX
        index = json.loads(index_path.read_bytes())
        spec = index['reports']['candidate|1.14-1.14.4']
        path = self.root / spec['report']
        report = json.loads(gzip.decompress(path.read_bytes()))
        edit(report)
        raw = (json.dumps(report, indent=2) + '\n').encode()
        packed = gzip.compress(raw, mtime=0)
        path.write_bytes(packed)
        report_hash = hashlib.sha256(raw).hexdigest()
        spec['sha256_uncompressed'] = report_hash
        for row in index['records']:
            if row['report'] == spec['report']:
                row['report_sha256_uncompressed'] = report_hash
        index_path.write_text(json.dumps(index, indent=2) + '\n')
        archived = next(row for row in archive_index['files'] if row['path'] == spec['report'])
        archived['sha256_uncompressed'] = report_hash
        archived['sha256_gzip'] = hashlib.sha256(packed).hexdigest()
        archive_path.write_text(json.dumps(archive_index, indent=2) + '\n')
        def update(evidence):
            evidence['source_provenance']['finding_index']['sha256'] = hashlib.sha256(index_path.read_bytes()).hexdigest()
            evidence['source_provenance']['archive_index']['sha256'] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            for finding in evidence['findings']:
                for row in finding['occurrences']:
                    if row['source_report']['path'] == spec['report']:
                        row['source_report']['sha256_uncompressed'] = report_hash
        self.mutate_focused(update)
        for row in archive_index['files']:
            packed = (self.root / row['path']).read_bytes()
            self.assertEqual(hashlib.sha256(packed).hexdigest(), row['sha256_gzip'])
            self.assertEqual(hashlib.sha256(gzip.decompress(packed)).hexdigest(), row['sha256_uncompressed'])
        return spec['report']

    def assert_historical_manifest_is_checked(self):
        old_index, old_reports, _ = live.historic(self.root)
        _, reports, _ = live.verify_live(self.live, old_index)
        reviewed = json.loads((self.root / EVIDENCE).read_bytes())
        finding = next(row for row in reviewed['findings'] if row['advisory_id'] == ADVISORY)
        observed = finding['occurrences'][0]['minecraft_artifacts'][0]['version_metadata_sha1']
        self.assertEqual(reports['candidate|1.14-1.14.4'][0]['runtime_manifests']['1.14']['sha1'], observed)
        self.assertNotEqual(old_reports['candidate|1.14-1.14.4']['runtime_manifests'].get('1.14', {}).get('sha1'),
                            observed)
        # Remove exactly the historical half of the production check as a
        # mutation control: all other validation remains the real implementation.
        source = inspect.getsource(live.validate_focused_review)
        condition = "old_manifests.get(version, {}).get('sha1') == metadata_sha and\n"
        self.assertEqual(source.count(condition), 1)
        mutant = {}
        exec(compile(source.replace(condition, ''), '<historical-check-removed>', 'exec'), live.__dict__, mutant)
        with patch.object(live, 'validate_focused_review', mutant['validate_focused_review']):
            self.assertTrue(live.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'focused review stale: runtime manifest identity: .* 1.14'):
            live.priority_register(self.live, self.root)

    def labels_with_advisory(self, identifier):
        index = json.loads((self.live / 'artifact-index.json').read_bytes())
        labels = []
        for item in index['artifacts']:
            if not item['name'].startswith(('candidate-dependency-audit-', 'dependency-audit-')):
                continue
            with ZipFile(self.live / 'raw' / (str(item['id']) + '.zip')) as archive:
                member = ('candidate-dependency-audit.json' if item['name'].startswith('candidate-')
                          else 'dependency-audit.json')
                if identifier in json.loads(archive.read(member))['advisories']:
                    labels.append(item['name'])
        return labels

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

    def test_changed_historical_manifest_invalidates_review_independently(self):
        self.mutate_historical_report(lambda report:
            report['runtime_manifests']['1.14'].update(sha1='0' * 40))
        self.assert_historical_manifest_is_checked()

    def test_missing_historical_manifest_invalidates_review_independently(self):
        self.mutate_historical_report(lambda report: report['runtime_manifests'].pop('1.14'))
        self.assert_historical_manifest_is_checked()

    def test_duplicate_reviewed_manifest_version_is_rejected(self):
        def edit(evidence):
            finding = next(row for row in evidence['findings'] if row['advisory_id'] == ADVISORY)
            artifacts = finding['occurrences'][0]['minecraft_artifacts']
            artifacts[-1] = copy.deepcopy(artifacts[0])
        self.mutate_focused(edit)
        with patch.object(live, 'validate_focused_review', prior.validate_focused_review):
            self.assertTrue(live.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'focused review stale: runtime manifest coverage'):
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
        for label in self.labels_with_advisory(ADVISORY):
            self.mutate_report(label, edit)
        self.assert_legacy_accepts_but_current_rejects('focused review stale: advisory fingerprint')

    def test_changed_review_relevant_metadata_invalidates_review(self):
        def edit(report):
            report['advisories'][ADVISORY]['summary'] += ' changed'
        for label in self.labels_with_advisory(ADVISORY):
            self.mutate_report(label, edit)
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
        for label in self.labels_with_advisory('GHSA-4jrv-ppp4-jm57'):
            self.mutate_report(label,
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
        labels = self.labels_with_advisory(ADVISORY)
        self.assertEqual(len(labels), 3)
        for label in labels:
            self.mutate_report(label, lambda report: report['advisories'][ADVISORY].update(
                modified='2026-11-23T00:00:00Z'))
        after = live.priority_register(self.live, self.root)
        self.assertEqual(after['schema'], 1)
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
        self.assertEqual(after['schema'], 2)
        self.assertIn('Schema 2', after['schema_note'])
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

    def test_mixed_timestamps_with_changed_unfocused_range_fail_closed(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        def edit(report):
            advisory = report['advisories'][identifier]
            advisory['modified'] = '2026-11-23T00:00:00Z'
            advisory['affected'][0]['ranges'][0]['events'][-1]['fixed'] = '2.9.0'
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.mutate_report('candidate-dependency-audit-0', edit)
        index, _, _ = live.historic(self.root)
        live.verify_live(self.live, index)
        # The initial PR #58 implementation accepted the mixed revisions.
        self.assertTrue(candidate.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'inconsistent advisory content across sources'):
            live.priority_register(self.live, self.root)

    def test_lower_severity_observation_is_not_dropped_before_consistency_check(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        labels = self.labels_with_advisory(identifier)
        self.assertEqual(len(labels), 3)
        for number, label in enumerate(labels):
            def edit(report, number=number):
                advisory = report['advisories'][identifier]
                advisory['modified'] = f'2026-11-{23 + number}T00:00:00Z'
                if number == 2:
                    advisory['database_specific']['severity'] = 'MODERATE'
                for row in report['matches']:
                    if row['advisory'] == identifier:
                        row['severity'] = advisory['database_specific']['severity']
                        row['fingerprint'] = audit.advisory_fingerprint(advisory)
            self.mutate_report(label, edit)
        index, _, _ = live.historic(self.root)
        _, reports, rows = live.verify_live(self.live, index)
        observations = [row for key, row in rows.items() if key[3] == identifier]
        self.assertEqual({row['severity'] for row in observations}, {'HIGH', 'MODERATE'})
        self.assertEqual(len({reports[key][0]['advisories'][identifier]['modified']
                              for key in reports if identifier in reports[key][0]['advisories']}), 3)
        old = merged.priority_register(self.live, self.root)
        old_row = next(item for item in old['advisories'] if item['advisory_id'] == identifier)
        self.assertLess(len(old_row['occurrences']), len(observations))
        with self.assertRaisesRegex(ValueError, 'inconsistent advisory severity across sources: ' + identifier):
            live.priority_register(self.live, self.root)

    def test_changed_severity_alone_is_a_cross_source_conflict(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        label = self.labels_with_advisory(identifier)[0]
        def edit(report):
            advisory = report['advisories'][identifier]
            advisory['database_specific']['severity'] = 'MODERATE'
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['severity'] = 'MODERATE'
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.mutate_report(label, edit)
        index, _, _ = live.historic(self.root)
        live.verify_live(self.live, index)
        self.assertTrue(merged.priority_register(self.live, self.root)['advisories'])
        with self.assertRaisesRegex(ValueError, 'inconsistent advisory severity across sources: ' + identifier):
            live.priority_register(self.live, self.root)

    def test_cli_does_not_write_a_register_with_a_severity_conflict(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        def edit(report):
            advisory = report['advisories'][identifier]
            advisory['database_specific']['severity'] = 'MODERATE'
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['severity'] = 'MODERATE'
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.mutate_report(self.labels_with_advisory(identifier)[0], edit)
        index, _, _ = live.historic(self.root)
        live.verify_live(self.live, index)
        comparison = live.reconcile(self.live, self.root)
        target = Path(self.temp.name) / 'priority.json'
        current = live.priority_register
        def invoke(exporter):
            out, err = StringIO(), StringIO()
            with patch.object(sys, 'argv', ['reconcile', '--live', str(self.live), '--priority-register', str(target)]), \
                 patch.object(live, 'reconcile', return_value=comparison), \
                 patch.object(live, 'priority_register', side_effect=lambda unused: exporter(self.live, self.root)), \
                 redirect_stdout(out), redirect_stderr(err):
                result = live.main()
            return result, err.getvalue()
        self.assertEqual(invoke(merged.priority_register)[0], 1)  # findings still block
        self.assertTrue(target.exists())  # but the old exporter emitted the incomplete register
        target.unlink()
        status, error = invoke(current)
        self.assertEqual(status, 2)
        self.assertIn('inconsistent advisory severity across sources: ' + identifier, error)
        self.assertFalse(target.exists())

    def test_conflicting_aliases_are_rejected(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        def edit(report):
            advisory = report['advisories'][identifier]
            advisory['aliases'].append('CVE-2099-12345')
            for row in report['matches']:
                if row['advisory'] == identifier:
                    row['fingerprint'] = audit.advisory_fingerprint(advisory)
        self.mutate_report(self.labels_with_advisory(identifier)[0], edit)
        index, _, _ = live.historic(self.root)
        live.verify_live(self.live, index)
        with self.assertRaisesRegex(ValueError, 'inconsistent advisory content across sources: ' + identifier):
            live.priority_register(self.live, self.root)

    def test_moderate_only_advisories_remain_outside_priority_export(self):
        index, _, _ = live.historic(self.root)
        _, _, rows = live.verify_live(self.live, index)
        selected = {key[3] for key, row in rows.items() if row['severity'] in ('HIGH', 'CRITICAL')}
        moderate_only = {key[3] for key, row in rows.items() if row['severity'] == 'MODERATE'} - selected
        self.assertTrue(moderate_only)
        result = live.priority_register(self.live, self.root)
        self.assertEqual((result['advisory_ids'], result['occurrences']), (37, 199))
        self.assertFalse(moderate_only & {row['advisory_id'] for row in result['advisories']})

    def test_schema_one_timestamp_contract_uses_verified_sources(self):
        index, _, _ = live.historic(self.root)
        _, reports, rows = live.verify_live(self.live, index)
        observations = live.priority_observations(reports, rows)
        baseline = live.priority_register(self.live, self.root)
        live.validate_priority_schema(baseline, observations)
        identifier = 'GHSA-4jrv-ppp4-jm57'
        for kind in ('unsupported', 'unmixed_schema_two', 'null', 'wrong_value', 'source_map', 'missing_source'):
            with self.subTest(kind=kind):
                result = copy.deepcopy(baseline)
                row = next(a for a in result['advisories'] if a['advisory_id'] == identifier)
                if kind == 'unsupported':
                    result['schema'] = 3
                    reason = 'unsupported priority register schema'
                elif kind == 'unmixed_schema_two':
                    result['schema'] = 2
                    reason = 'priority schema does not match timestamp observations'
                elif kind == 'null':
                    row['modified'] = None
                    reason = 'invalid single priority timestamp'
                elif kind == 'wrong_value':
                    row['modified'] = '2026-11-23T00:00:00Z'
                    reason = 'invalid single priority timestamp'
                elif kind == 'source_map':
                    row['modified_by_source'] = {'candidate|extra': row['modified']}
                    reason = 'invalid single priority timestamp'
                else:
                    row['occurrences'] = [item for item in row['occurrences'] if item['group'] != '1.14-1.14.4']
                    reason = 'priority occurrence coverage differs'
                with self.assertRaisesRegex(ValueError, reason):
                    live.validate_priority_schema(result, observations)

    def test_schema_two_requires_all_verified_mixed_timestamps(self):
        identifier = 'GHSA-4jrv-ppp4-jm57'
        label = self.labels_with_advisory(identifier)[0]
        self.mutate_report(label, lambda report: report['advisories'][identifier].update(
            modified='2026-11-23T00:00:00Z'))
        index, _, _ = live.historic(self.root)
        _, reports, rows = live.verify_live(self.live, index)
        observations = live.priority_observations(reports, rows)
        baseline = live.priority_register(self.live, self.root)
        self.assertEqual(baseline['schema'], 2)
        live.validate_priority_schema(baseline, observations)
        for kind in ('schema_one', 'missing', 'extra', 'wrong_type', 'wrong_value', 'nonnull'):
            with self.subTest(kind=kind):
                result = copy.deepcopy(baseline)
                row = next(a for a in result['advisories'] if a['advisory_id'] == identifier)
                values = row['modified_by_source']
                key = next(iter(values))
                if kind == 'schema_one':
                    result['schema'] = 1
                elif kind == 'missing':
                    del values[key]
                elif kind == 'extra':
                    values['candidate|extra'] = '2026-11-23T00:00:00Z'
                elif kind == 'wrong_type':
                    values[key] = None
                elif kind == 'wrong_value':
                    values[key] = '2026-11-24T00:00:00Z'
                else:
                    row['modified'] = '2026-11-23T00:00:00Z'
                with self.assertRaisesRegex(ValueError, 'invalid mixed priority timestamps or source attribution'):
                    live.validate_priority_schema(result, observations)


if __name__ == '__main__':
    unittest.main()
