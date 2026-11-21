import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_maintenance_proposal as proposal
from release import Invalid


class MaintenanceProposalAuditTests(unittest.TestCase):
    def setUp(self):
        self.group = '1.21.11'
        self.sha = 'a' * 40
        self.branch = 'maintenance/mc-1.21.11-1.0.0'
        self.current = {'schema': 1, 'version': '1.0.0'}
        self.spec = {'branch': 'mc/1.21.11', 'target': '1.21.11', 'minecraft': ['1.21.11'],
                     'integrated_commit': 'b' * 40}
        self.registry = {self.group: self.spec}
        self.metadata = {'id': 'thirdpersonreadablemaps', 'version': '${version}',
                         'depends': {'minecraft': '1.21.11'}}
        self.properties = {'minecraft_version': '1.21.11', 'mod_version': '1.0.0'}
        self.snapshot = {'ref': 'refs/heads/' + self.branch, 'sha': self.sha,
                         'manifests': {'build': {'resolved': {'one': {'package_url': 'pkg:maven/example/lib@1'}}}}}
        self.ledger = {}

    def run_audit(self, snapshot=None, metadata=None, properties=None, branch=None, observed=None):
        return proposal.audit_proposal(snapshot or self.snapshot, metadata or self.metadata,
            properties or self.properties, self.group, branch or self.branch, self.sha, observed or self.sha,
            self.registry, self.ledger, self.current)

    def test_proposal_cannot_inherit_risk_acceptance_or_automatic_resolution(self):
        match = {'key': 'old', 'purl': 'pkg:maven/example/lib@1', 'advisory': 'GHSA-test',
                 'scopes': ['gradle'], 'state': 'known', 'disposition': 'Risk accepted',
                 'failing': False, 'severity': 'LOW', 'fingerprint': 'c' * 64}
        comparison = {'matches': [match], 'resolved': ['old-resolved'], 'resolved_needing_review': [],
                      'inventory_sha256': 'd' * 64, 'failing': False}
        with patch.object(proposal.audit, 'runtime_inventories', return_value=({'runtime/1.21.11': ['pkg:maven/example/lib@1']}, {})), \
             patch.object(proposal.scanner, 'query', return_value={'pkg:maven/example/lib@1': ['GHSA-test']}), \
             patch.object(proposal.audit, 'get_json', return_value={'id': 'GHSA-test'}), \
             patch.object(proposal.audit, 'compare', return_value=comparison):
            result = self.run_audit()
        self.assertFalse(result['risk_acceptance'])
        self.assertEqual(result['source_kind'], 'maintenance-proposal')
        self.assertTrue(result['failing'])
        self.assertEqual(result['resolved_needing_review'], ['old-resolved'])
        self.assertEqual(result['matches'][0]['disposition'], 'Further investigation')
        self.assertTrue(result['matches'][0]['failing'])

    def test_wrong_proposal_source_ref_and_metadata_fail_before_scanning(self):
        bad_snapshot = copy.deepcopy(self.snapshot); bad_snapshot['ref'] = 'refs/heads/mc/1.21.11'
        bad_metadata = copy.deepcopy(self.metadata); bad_metadata['depends']['minecraft'] = '1.14'
        with patch.object(proposal.scanner, 'query') as query:
            for kwargs in ({'snapshot': bad_snapshot}, {'metadata': bad_metadata},
                           {'properties': {'minecraft_version': '1.21.11', 'mod_version': '0.0.2'}},
                           {'branch': 'mc/1.21.11'}, {'observed': 'f' * 40}):
                with self.subTest(kwargs=kwargs), self.assertRaises((Invalid, ValueError)):
                    self.run_audit(**kwargs)
            query.assert_not_called()


if __name__ == '__main__':
    unittest.main()
