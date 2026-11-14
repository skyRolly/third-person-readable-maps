"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': '0ad1804454abd40995b32d70bbe6424fb8489a1b3dda3536fd3805f9316bf046',
    'scripts/game_linkage.py': '8a312239b054617333d5b894839adbeffaba580c2b0b7b95751e2b7f402fec65',
    'tests/test_jvm_linkage.py': 'ebedc9f339bfd9a274a3448fd6695fac0c4069c34c1c04d3bc1e85a318916655',
    'scripts/verify_gradle_wrapper.py': '2730fb13bf46b091a141f8adbbb178b299bb0f67831aaeffd2f3fc4a91402481',
    'tests/test_verify_gradle_wrapper.py': '85c8b5f2ff42940c94bb0caf26b86526e19b35478d0f4736d2e0fbfe49cd672d',
    'tests/test_nestmate_linkage.py': '870e107ecb86a0ec97c85eed3b69509f92c66461ddf904170c4bc2f3548af235',
    'docs/verification/linkage-contract.md': '875b34189f40a35dc8c3c60fc55db9dfd59db0d6dee428222c9bfe332ab8e102',
}


class SharedVerifierSync(unittest.TestCase):
    def test_shared_files_match_reviewed_contract(self):
        for name, expected in CANONICAL.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected,
                                 'Propagate and review shared changes across affected groups')


if __name__ == '__main__':
    unittest.main()
