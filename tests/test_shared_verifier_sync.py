"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': '7a2f83acb42d2549f8471818265de3a69d4791a6584d6766e34eb10d65253a10',
    'scripts/game_linkage.py': '78e92d3b064243974a4af12388331e66ab0bf0a7f673d707a6ea650271541d94',
    'tests/test_jvm_linkage.py': '9146a19a30c49cfaaaa36a411a641d31a9a261b6720eb0ca50e4573fb4918bea',
    'tests/test_hierarchy_linkage.py': '5b65b51f77d36aef5be570f8e3d70d262de4ea398ea5b47675c3fa9433f5dced',
    'tests/hierarchy_entrypoint_fixtures.py': '4ec6751f1576c570921b8dea896d38535af8f0591c4adaf14165c9c23f16ac88',
    'scripts/verify_gradle_wrapper.py': '2730fb13bf46b091a141f8adbbb178b299bb0f67831aaeffd2f3fc4a91402481',
    'tests/test_verify_gradle_wrapper.py': 'e99e2dd2e5e4c361a7ad0db4168fd3c1e423461bf4314456197107fa28138d65',
    'tests/test_nestmate_linkage.py': '870e107ecb86a0ec97c85eed3b69509f92c66461ddf904170c4bc2f3548af235',
    'docs/verification/linkage-contract.md': '705ce4568b8e158f86d29bc6c79e68ef974d5ac3395910b68b34c18fa3b14304',
}
ADAPTERS = {
    'intermediary': '6f888a01085a75f56cc8058eddeeb3919cd32cdc2376a7309cb8c1adc0186ab7',
    'official': '15546523b6242da903013e0663ddb8deb7a4744ccdcb1fb142230d9b6ca088a5',
}


class SharedVerifierSync(unittest.TestCase):
    def test_shared_files_match_reviewed_contract(self):
        for name, expected in CANONICAL.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected,
                                 'Propagate and review shared changes across affected groups')

    def test_namespace_entrypoint_fixtures_match_reviewed_adapter(self):
        props = dict(line.split('=', 1) for line in (ROOT/'gradle.properties').read_text().splitlines()
                     if '=' in line and not line.lstrip().startswith('#'))
        namespace = 'official' if props['minecraft_version'].startswith('26.') else 'intermediary'
        digest = hashlib.sha256((ROOT/'tests/test_verify_entrypoint.py').read_bytes()).hexdigest()
        self.assertEqual(digest, ADAPTERS[namespace], 'Propagate the applicable namespace fixture')


if __name__ == '__main__':
    unittest.main()
