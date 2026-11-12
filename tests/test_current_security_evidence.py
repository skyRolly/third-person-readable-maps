"""Keep current security evidence source-bound and traceable, without accepting risk."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_dependencies as audit


class CurrentSecurityEvidenceTests(unittest.TestCase):
    def test_complete_current_scans_match_sources_and_individual_worklist(self):
        worklist = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json').read_text())
        candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
        registry = json.loads((ROOT / 'release/maintenance-targets.json').read_text())['groups']
        self.assertFalse(worklist['risk_acceptance'])
        self.assertEqual(worklist['missing_or_stale_groups'], [])
        self.assertEqual(set(worklist['sources']), set(candidates) | set(registry))
        expected, indexed = set(), set()
        for group, source in worklist['sources'].items():
            for key in ('snapshot', 'report'):
                path = ROOT / source[key + '_path']
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), source[key + '_sha256'])
                if key == 'snapshot':
                    snapshot = json.loads(raw)
                else:
                    report = json.loads(raw)
            self.assertEqual(snapshot['sha'], source['source_sha'])
            self.assertEqual(snapshot['ref'], source['snapshot_ref'])
            self.assertEqual(report['source_sha'], source['source_sha'])
            self.assertEqual(len(report['matches']), source['matches'])
            if group in candidates:
                self.assertEqual(source['source_kind'], 'candidate')
                self.assertEqual(source['source_sha'], candidates[group]['candidate_head'])
                self.assertEqual(report['status'], 'complete-unreviewed-candidate-scan')
            else:
                self.assertEqual(source['source_kind'], 'integrated-maintenance')
                self.assertEqual(source['source_sha'], registry[group]['integrated_commit'])
                self.assertEqual(report['status'], 'complete')
            for match in report['matches']:
                advisory = report['advisories'][match['advisory']]
                self.assertEqual(match['fingerprint'], audit.advisory_fingerprint(advisory))
                self.assertTrue(match['failing'])
                expected.add((group, match['purl'], match['advisory'], match['fingerprint']))
        for record in worklist['records'].values():
            self.assertFalse(record['risk_accepted'])
            self.assertEqual(record['disposition'], 'Further investigation')
            for occurrence in record['occurrences']:
                indexed.add((occurrence['group'], record['purl'], record['advisory'], occurrence['fingerprint']))
        self.assertEqual(indexed, expected)


if __name__ == '__main__':
    unittest.main()
