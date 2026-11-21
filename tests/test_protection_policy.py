"""Keep documented staged protection payloads aligned with authorization."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import authorize_release as auth


class ProtectionPolicyTests(unittest.TestCase):
    def payload(self, name):
        return json.loads((ROOT / 'docs/admin' / name).read_text())

    def checks(self, payload):
        self.assertTrue(payload['required_status_checks']['strict'])
        entries = payload['required_status_checks']['checks']
        self.assertEqual(len(entries), len({item['context'] for item in entries}))
        self.assertTrue(all(item['app_id'] == auth.ACTIONS_APP for item in entries))
        return {item['context'] for item in entries}

    def test_staged_main_and_final_maintenance_policies(self):
        baseline = self.payload('branch-protection-main-baseline.json')
        final = self.payload('branch-protection-main.json')
        maintenance = self.payload('branch-protection-maintenance.json')
        self.assertEqual(self.checks(baseline), {'Validate coordination'})
        self.assertEqual(self.checks(final), auth.role_checks('main'))
        self.assertEqual(self.checks(maintenance), auth.role_checks('mc/1.21.11'))
        for payload in (baseline, final, maintenance):
            self.assertTrue(payload['enforce_admins'])
            self.assertFalse(payload['allow_force_pushes'])
            self.assertFalse(payload['allow_deletions'])
            reviews = payload['required_pull_request_reviews']
            self.assertGreaterEqual(reviews['required_approving_review_count'], 1)
            self.assertTrue(reviews['dismiss_stale_reviews'])
            self.assertEqual(reviews['bypass_pull_request_allowances'], {'users': [], 'teams': [], 'apps': []})
        # The migration changes only the required checks, never review policy.
        self.assertEqual({k: v for k, v in baseline.items() if k != 'required_status_checks'},
                         {k: v for k, v in final.items() if k != 'required_status_checks'})
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        names = set(re.findall(r'^    name: (.+)$', workflow, re.MULTILINE))
        self.assertTrue(auth.COORDINATION_CHECKS <= names)


if __name__ == '__main__':
    unittest.main()
