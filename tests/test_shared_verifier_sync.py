"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': 'c1d0d496fbe93e819678972a2bb7702d689546ff8b37ff223d4f3da420eb1d77',
    'scripts/game_linkage.py': 'ae07fbce9aed74e6f65ffa243feac6d61830909b954b4edb6c7cb13c8e98eca9',
    'tests/test_jvm_linkage.py': 'ebedc9f339bfd9a274a3448fd6695fac0c4069c34c1c04d3bc1e85a318916655',
    'scripts/verify_gradle_wrapper.py': 'fba8c993c71f0ac0b8348d2535cee1f5e4ae39a9da4f514b3c9b13334f3ef10f',
    'tests/test_verify_gradle_wrapper.py': 'cfd3278d6ae1417dc57d3d571deb1e3532ba4f0e225c03a2a93b5048cb29b3fb',
    'docs/verification/linkage-contract.md': '946e972da2392d2f00e0cbe3ca7311ca361339e87768f260b8a776208e4c7a47',
}


class SharedVerifierSync(unittest.TestCase):
    def test_shared_files_match_reviewed_contract(self):
        for name, expected in CANONICAL.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected,
                                 'Propagate and review shared changes across affected groups')


if __name__ == '__main__':
    unittest.main()
