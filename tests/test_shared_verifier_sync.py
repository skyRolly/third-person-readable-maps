"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': '0ad1804454abd40995b32d70bbe6424fb8489a1b3dda3536fd3805f9316bf046',
    'scripts/game_linkage.py': '6c23d2fba1e602ab7e1813efd8c3e53b13f1d2c482ca2f4ef32f812fd3a51e4d',
    'tests/test_jvm_linkage.py': 'ebedc9f339bfd9a274a3448fd6695fac0c4069c34c1c04d3bc1e85a318916655',
    'scripts/verify_gradle_wrapper.py': '2730fb13bf46b091a141f8adbbb178b299bb0f67831aaeffd2f3fc4a91402481',
    'tests/test_verify_gradle_wrapper.py': 'e99e2dd2e5e4c361a7ad0db4168fd3c1e423461bf4314456197107fa28138d65',
    'tests/test_nestmate_linkage.py': '870e107ecb86a0ec97c85eed3b69509f92c66461ddf904170c4bc2f3548af235',
    'docs/verification/linkage-contract.md': '0a45d58c7d566f8ba3f8b606dab5fa6209499759a05e960dc834df5ea570a4a7',
}


class SharedVerifierSync(unittest.TestCase):
    def test_shared_files_match_reviewed_contract(self):
        for name, expected in CANONICAL.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected,
                                 'Propagate and review shared changes across affected groups')


if __name__ == '__main__':
    unittest.main()
