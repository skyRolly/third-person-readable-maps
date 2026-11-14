"""Check retained final-proposal evidence without granting release approval."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / 'docs/version-consistency-1.0.0/stabilization-2026-11-14'
SECURITY = ROOT / 'docs/dependency-evidence/osv-rescan-2026-11-14/final-proposals'
REHEARSAL = ROOT / 'docs/legacy-dry-run-1.0.0-2026-11-14/stabilization-final'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StabilizationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.heads = read(ROOT / 'docs/version-consistency-1.0.0/current-heads.json')['groups']
        cls.builds = read(VALIDATION / 'builds.json')
        cls.runtime = read(ROOT / 'docs/runtime-smoke-verifier-followup-2026-11-13/index.json')['versions']
        cls.api = read(VALIDATION / 'api.json')['results']

    def test_clean_builds_and_api_logs_match_historical_artifact_bytes(self):
        self.assertEqual(set(self.builds), set(self.heads))
        self.assertEqual(len(self.heads), 13)
        self.assertEqual(len(self.api), 48)
        self.assertEqual({row['version'] for row in self.api}, set(self.runtime))
        for row in self.api:
            group, version = row['group'], row['version']
            build, head, runtime = self.builds[group], self.heads[group], self.runtime[version]
            with self.subTest(group=group, version=version):
                self.assertEqual(row['exit_code'], 0)
                self.assertEqual(row['source_commit'], head['new_head'])
                self.assertEqual(build['source_commit'], head['new_head'])
                self.assertEqual(runtime['source_commit'], head['old_head'])
                self.assertEqual(row['artifact_sha256'], build['sha256'])
                self.assertEqual(runtime['artifact_sha256'], build['sha256'])
                self.assertTrue(build['same_as_previous'])
                self.assertEqual(sha256(VALIDATION / 'api-logs' / (version + '.log')), row['log_sha256'])
                self.assertEqual(sha256(VALIDATION / 'build-logs' / (group + '-build.log')), build['log_sha256'])

    def test_hosted_checks_are_for_the_recorded_proposal_heads(self):
        checks = read(VALIDATION / 'hosted-checks.json')['pull_requests']
        by_number = {row['number']: row for row in checks}
        merge_trees = read(VALIDATION / 'hosted-pr-merge-trees.json')['groups']
        self.assertEqual(set(merge_trees), set(self.heads))
        for group, head in self.heads.items():
            with self.subTest(group=group):
                item = by_number[head['pr']]
                self.assertEqual(item['headRefOid'], head['new_head'])
                self.assertTrue(item['isDraft'])
                self.assertIsNone(item['autoMergeRequest'])
                observed = {(x.get('name'), x.get('conclusion')) for x in item['statusCheckRollup']}
                self.assertIn(('Build (ubuntu-latest)', 'SUCCESS'), observed)
                self.assertIn(('Build (windows-latest)', 'SUCCESS'), observed)
                merge = merge_trees[group]
                self.assertEqual(merge['head_sha'], head['new_head'])
                self.assertEqual(merge['merge_parents'], [merge['base_sha'], merge['head_sha']])
                self.assertEqual(merge['merge_tree'], merge['head_tree'])

    def test_scans_remain_bound_to_their_distinct_source_kinds(self):
        index = read(SECURITY / 'index.json')
        self.assertFalse(index['risk_acceptance'])
        self.assertEqual(set(index['groups']), set(self.heads))
        for group, item in index['groups'].items():
            with self.subTest(group=group):
                head = self.heads[group]
                self.assertEqual(item['source_sha'], head['new_head'])
                self.assertEqual(item['branch'], head['branch'])
                for record in item['files'].values():
                    self.assertEqual(sha256(SECURITY / record['path']), record['sha256'])
                snap = read(SECURITY / item['files']['hosted_snapshot']['path'])
                self.assertEqual(snap['sha'], head['new_head'])
                self.assertEqual(snap['ref'], f"refs/pull/{head['pr']}/merge")
                report = read(SECURITY / item['files']['scan_report']['path'])
                self.assertEqual(report['source_sha'], head['new_head'])
                self.assertEqual(len(report['matches']), item['matches'])
                self.assertTrue(all(match['failing'] for match in report['matches']))
                self.assertFalse(report['risk_acceptance'])
                if head['branch'].startswith('candidate/'):
                    self.assertEqual(item['source_kind'], 'candidate')
                    self.assertEqual(report['status'], 'complete-unreviewed-candidate-scan')
                else:
                    self.assertEqual(item['source_kind'], 'unmerged-maintenance-proposal')
                    self.assertEqual(report['status'], 'complete-unreviewed-maintenance-proposal')
                    self.assertNotEqual(item['integrated_maintenance']['source_sha'], head['new_head'])
                    local = read(SECURITY / item['files']['local_resolved_snapshot']['path'])
                    self.assertEqual(local['sha'], head['new_head'])
                    self.assertEqual(local['ref'], 'refs/heads/' + head['branch'])

    def test_candidate_rehearsal_is_not_production_authorization(self):
        manifest = read(REHEARSAL / 'release-manifest.json')
        self.assertTrue(manifest['candidate'])
        self.assertEqual(manifest['version'], '1.0.0')
        self.assertEqual(len(manifest['groups']), len(self.heads))
        versions = []
        for entry in manifest['groups']:
            group = entry['id']
            self.assertEqual(entry['source_commit'], self.heads[group]['new_head'])
            self.assertEqual(entry['sha256'], self.builds[group]['sha256'])
            versions.extend(entry['minecraft'])
        self.assertEqual(len(versions), 48)
        self.assertEqual(len(set(versions)), 48)
        self.assertEqual(len(read(REHEARSAL / 'negative-controls.json')), 15)
        negatives = read(VALIDATION / 'negative-controls/index.json')
        self.assertEqual(len(negatives), 9)
        for result in negatives.values():
            self.assertTrue(result['discriminating_rejection'])
            self.assertEqual(result['source_commit'], self.heads[result['group']]['new_head'])
            self.assertEqual(result['artifact_sha256'], self.builds[result['group']]['sha256'])
            self.assertEqual(sha256(VALIDATION / 'negative-controls' / result['log']),
                             result['log_sha256'])


if __name__ == '__main__':
    unittest.main()
