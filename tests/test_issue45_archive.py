import gzip
import hashlib
import json
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'


class Issue45ArchiveTests(unittest.TestCase):
    def verify_archive(self, root, archive_dir, expected_reports=None):
        archive = json.loads((archive_dir / 'archive-index.json').read_text())
        index = json.loads((archive_dir / 'finding-index.json').read_text())
        self.assertEqual(archive['schema'], 1)
        self.assertEqual(index['schema'], 1)
        for field in ('candidate_run', 'integrated_run'):
            # bool is a subclass of int in Python, but JSON true/false are not run IDs.
            self.assertIs(type(archive[field]), int, field)
            self.assertGreater(archive[field], 0)
        self.assertIs(index['risk_acceptance'], False)
        self.assertIsInstance(index['reports'], dict)
        self.assertIsInstance(index['records'], list)
        by_source = {}
        paths = set()
        archive_root = archive_dir.resolve()
        for item in archive['files']:
            relative = item['path']
            self.assertNotIn(relative, paths, 'duplicate archive file path')
            paths.add(relative)
            path = (root / relative).resolve()
            self.assertTrue(path.is_relative_to(archive_root), 'file outside archived evidence')
            packed = path.read_bytes()
            raw = gzip.decompress(packed)
            self.assertEqual(hashlib.sha256(packed).hexdigest(), item['sha256_gzip'], relative)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256_uncompressed'], relative)
            document = json.loads(raw)
            self.assertIsInstance(document, dict)
            source_kind = path.relative_to(archive_root).parts[0]
            self.assertIn(source_kind, ('candidate', 'integrated'))
            source_key = (source_kind, item['source_sha'])
            trio = by_source.setdefault(source_key, {})
            if path.name in ('candidate-dependency-audit.json.gz', 'dependency-audit.json.gz'):
                role = 'report'
                self.assertEqual(document['source_sha'], item['source_sha'], relative)
                self.assertEqual(document['status'], item['status'], relative)
            elif path.name == 'gradle-tool-audit.json.gz':
                role = 'tool'
                self.assertEqual(document['source_sha'], item['source_sha'], relative)
                self.assertEqual(document['status'], item['status'], relative)
                self.assertEqual(document['status'], 'complete', relative)
                self.assertEqual(document['gradle_version'], '9.9.2', relative)
                self.assertEqual(document['advisories'], [], relative)
                self.assertIs(document['failing'], False)
            else:
                self.assertIn('/dependency-graph-reports/', relative)
                self.assertTrue(relative.endswith('.json.gz'))
                role = 'snapshot'
                self.assertEqual(document['sha'], item['source_sha'], relative)
                self.assertIsInstance(document.get('job'), dict, relative)
                declared_run = archive['candidate_run'] if source_kind == 'candidate' else archive['integrated_run']
                self.assertEqual(str(document['job'].get('id')), str(declared_run), relative)
            self.assertNotIn(role, trio, f'duplicate {role}: {source_key}')
            trio[role] = {'path': relative, 'data': document, 'sha256': item['sha256_uncompressed']}

        if expected_reports is not None:
            self.assertEqual(len(index['reports']), expected_reports)
        self.assertEqual(len(by_source), len(index['reports']))
        self.assertEqual(len(paths), 3 * len(index['reports']))
        reports = {}
        for (kind, source_sha), trio in by_source.items():
            self.assertEqual(set(trio), {'report', 'tool', 'snapshot'}, (kind, source_sha))
            report = trio['report']['data']
            snapshot = trio['snapshot']['data']
            self.assertEqual(report['source_sha'], source_sha)
            self.assertEqual(snapshot['sha'], source_sha)
            self.assertEqual(trio['tool']['data']['source_sha'], source_sha)
            group = report['group'] if kind == 'candidate' else report['branch'].removeprefix('mc/')
            branch = f'candidate/mc-{group}' if kind == 'candidate' else f'mc/{group}'
            self.assertEqual(report['branch'], branch)
            self.assertEqual(snapshot['ref'], 'refs/heads/' + branch)
            if kind == 'candidate':
                self.assertEqual(report['snapshot_ref'], snapshot['ref'])
                self.assertEqual(report['source_kind'], 'candidate')
            self.assertEqual(report['status'], 'complete-unreviewed-candidate-scan' if kind == 'candidate' else 'complete')
            if kind == 'candidate':
                self.assertIs(report['risk_acceptance'], False)
            elif 'risk_acceptance' in report:
                self.assertIs(report['risk_acceptance'], False)
            index_key = kind + '|' + group
            self.assertNotIn(index_key, reports)
            reports[index_key] = trio['report']
            listed = index['reports'][index_key]
            self.assertEqual(listed['source_sha'], source_sha)
            self.assertEqual(listed['report'], trio['report']['path'])
            self.assertEqual(listed['sha256_uncompressed'], trio['report']['sha256'])
            self.assertEqual(listed['resolved_needing_review'], report['resolved_needing_review'])
            self.assertIs(listed['failing'], bool(report.get('failing', report['matches'] or report['resolved_needing_review'])))

        self.assertEqual(set(index['reports']), set(reports))
        records = index['records']
        self.assertEqual(len({(r['source_kind'], r['key']) for r in records}), len(records))
        indexed = {(r['source_kind'], r['key']): r for r in records}
        expected = {}
        for index_key, value in reports.items():
            kind, group = index_key.split('|', 1)
            for match in value['data']['matches']:
                key = (kind, match['key'])
                self.assertNotIn(key, expected)
                expected[key] = (value['path'], value['data']['source_sha'], group, value['sha256'], match)
        self.assertEqual(set(indexed), set(expected))
        for key, (path, source_sha, group, digest, match) in expected.items():
            row = indexed[key]
            self.assertEqual((row['report'], row['source_sha'], row['group']), (path, source_sha, group))
            self.assertEqual(row['report_sha256_uncompressed'], digest)
            for field in ('purl', 'advisory', 'scopes', 'fingerprint', 'severity', 'disposition',
                          'failing', 'state'):
                self.assertEqual(row[field], match[field])
            if 'review_status' in match:
                self.assertEqual(row['review_status'], match['review_status'])
            else:
                self.assertNotIn('review_status', row)

    def test_hashes_source_bindings_and_findings(self):
        self.verify_archive(ROOT, ARCHIVE, expected_reports=13)


class Issue45ArchiveNegativeTests(unittest.TestCase):
    verify_archive = Issue45ArchiveTests.verify_archive

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive_dir = self.root / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'
        self.archive_dir.mkdir(parents=True)
        self.archive = {'schema': 1, 'candidate_run': 1234, 'integrated_run': 5678, 'files': []}
        self.index = {'schema': 1, 'risk_acceptance': False, 'reports': {}, 'records': []}
        for kind, group, source_sha in [('candidate', '1.14-1.14.4', 'a' * 40),
                                        ('integrated', '1.21.11', 'b' * 40)]:
            branch = f'candidate/mc-{group}' if kind == 'candidate' else f'mc/{group}'
            key = f'{group}|pkg:maven/example/lib@1.0|GHSA-xxxx-yyyy-zzzz'
            match = {'key': key, 'purl': 'pkg:maven/example/lib@1.0',
                     'advisory': 'GHSA-xxxx-yyyy-zzzz', 'scopes': ['gradle'],
                     'fingerprint': 'f' * 64, 'severity': 'HIGH',
                     'state': 'known', 'review_status': 'awaiting investigation',
                     'disposition': 'Further investigation', 'failing': True}
            if kind == 'integrated':
                match.pop('review_status')
            report = {'source_sha': source_sha,
                      'status': 'complete-unreviewed-candidate-scan' if kind == 'candidate' else 'complete',
                      'branch': branch, 'matches': [match], 'resolved_needing_review': [], 'failing': True}
            if kind == 'candidate':
                report.update({'group': group, 'snapshot_ref': f'refs/heads/{branch}',
                               'source_kind': kind, 'risk_acceptance': False})
            tool = {'source_sha': source_sha, 'status': 'complete', 'gradle_version': '9.9.2',
                    'advisories': [], 'failing': False}
            snapshot = {'sha': source_sha, 'ref': f'refs/heads/{branch}', 'version': 0,
                        'job': {'id': str(self.archive['candidate_run'] if kind == 'candidate'
                                          else self.archive['integrated_run'])}}
            prefix = f'{kind}/dependency-audit-0'
            report_name = 'candidate-dependency-audit.json.gz' if kind == 'candidate' else 'dependency-audit.json.gz'
            report_path = self._store(f'{prefix}/{report_name}', report, source_sha, report['status'])
            self._store(f'{prefix}/gradle-tool-audit.json.gz', tool, source_sha, 'complete')
            self._store(f'{kind}/dependency-graph-reports/snapshot.json.gz', snapshot, source_sha, None)
            digest = next(x['sha256_uncompressed'] for x in self.archive['files'] if x['path'] == report_path)
            self.index['reports'][kind + '|' + group] = {'source_sha': source_sha, 'report': report_path,
                'sha256_uncompressed': digest, 'failing': True, 'resolved_needing_review': []}
            self.index['records'].append({'source_kind': kind, 'group': group, 'source_sha': source_sha,
                'report': report_path, 'report_sha256_uncompressed': digest, **match})
        self._write_indexes()

    def _store(self, relative, document, source_sha, status):
        path = self.archive_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(document).encode()
        packed = gzip.compress(raw)
        path.write_bytes(packed)
        entry = {'path': str(path.relative_to(self.root)), 'source_sha': source_sha, 'status': status,
                 'sha256_gzip': hashlib.sha256(packed).hexdigest(),
                 'sha256_uncompressed': hashlib.sha256(raw).hexdigest()}
        self.archive['files'].append(entry)
        return entry['path']

    def _write_indexes(self):
        (self.archive_dir / 'archive-index.json').write_text(json.dumps(self.archive))
        (self.archive_dir / 'finding-index.json').write_text(json.dumps(self.index))

    def _edit_artifact(self, ending, field, value):
        entry = next(x for x in self.archive['files'] if x['path'].endswith(ending))
        path = self.root / entry['path']
        data = json.loads(gzip.decompress(path.read_bytes()))
        data[field] = value
        raw = json.dumps(data).encode()
        packed = gzip.compress(raw)
        path.write_bytes(packed)
        # Make the manifest hashes pass, so only cross-file provenance catches the mutation.
        entry['sha256_gzip'] = hashlib.sha256(packed).hexdigest()
        entry['sha256_uncompressed'] = hashlib.sha256(raw).hexdigest()
        self._write_indexes()

    def test_valid_fixture(self):
        self.verify_archive(self.root, self.archive_dir, expected_reports=2)

    def test_modified_snapshot_sha_is_rejected_even_after_rehash(self):
        self._edit_artifact('candidate/dependency-graph-reports/snapshot.json.gz', 'sha', 'c' * 40)
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_modified_snapshot_ref_is_rejected_even_after_rehash(self):
        self._edit_artifact('candidate/dependency-graph-reports/snapshot.json.gz', 'ref', 'refs/heads/unrelated')
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_incomplete_gradle_tool_rejected_even_if_manifest_agrees(self):
        ending = 'candidate/dependency-audit-0/gradle-tool-audit.json.gz'
        self._edit_artifact(ending, 'status', 'incomplete')
        entry = next(x for x in self.archive['files'] if x['path'].endswith(ending))
        entry['status'] = 'incomplete'
        self._write_indexes()
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_snapshot_from_different_run_rejected_even_after_rehash(self):
        self._edit_artifact('candidate/dependency-graph-reports/snapshot.json.gz',
                            'job', {'id': str(self.archive['candidate_run'] + 1)})
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_boolean_run_ids_are_rejected(self):
        for field, kind, original in (('candidate_run', 'candidate', 1234),
                                      ('integrated_run', 'integrated', 5678)):
            snapshot_path = kind + '/dependency-graph-reports/snapshot.json.gz'
            with self.subTest(field=field, value=True):
                self.archive[field] = True
                # Make the forged snapshot agree with str(True), including refreshed
                # gzip and raw hashes. The former isinstance(int) check accepts this.
                self._edit_artifact(snapshot_path, 'job', {'id': 'True'})
                self.assertEqual(str(self.archive[field]), 'True')
                with self.assertRaisesRegex(AssertionError, field):
                    self.verify_archive(self.root, self.archive_dir)
                self.archive[field] = original
                self._edit_artifact(snapshot_path, 'job', {'id': str(original)})
            with self.subTest(field=field, value=False):
                self.archive[field] = False
                self._write_indexes()
                with self.assertRaises(AssertionError):
                    self.verify_archive(self.root, self.archive_dir)
                self.archive[field] = original
                self._write_indexes()

    def test_string_run_ids_are_rejected(self):
        for field in ('candidate_run', 'integrated_run'):
            with self.subTest(field=field):
                self.archive[field] = str(self.archive[field])
                self._write_indexes()
                with self.assertRaises(AssertionError):
                    self.verify_archive(self.root, self.archive_dir)
                self.archive[field] = 1234 if field == 'candidate_run' else 5678
        self._write_indexes()

    def test_changed_declared_run_rejected(self):
        self.archive['integrated_run'] += 1
        self._write_indexes()
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_modified_tool_source_is_rejected_even_after_rehash(self):
        self._edit_artifact('candidate/dependency-audit-0/gradle-tool-audit.json.gz', 'source_sha', 'c' * 40)
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_modified_report_hash_in_report_index_is_rejected(self):
        self.index['reports']['candidate|1.14-1.14.4']['sha256_uncompressed'] = '0' * 64
        self._write_indexes()
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_modified_report_hash_in_finding_row_is_rejected(self):
        self.index['records'][0]['report_sha256_uncompressed'] = '0' * 64
        self._write_indexes()
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)

    def test_missing_snapshot_is_rejected(self):
        self.archive['files'] = [x for x in self.archive['files']
                                 if not x['path'].endswith('candidate/dependency-graph-reports/snapshot.json.gz')]
        self._write_indexes()
        with self.assertRaises(AssertionError):
            self.verify_archive(self.root, self.archive_dir)


if __name__ == '__main__':
    unittest.main()
