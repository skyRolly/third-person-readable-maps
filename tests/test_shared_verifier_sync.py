"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': 'c1d0d496fbe93e819678972a2bb7702d689546ff8b37ff223d4f3da420eb1d77',
    'scripts/game_linkage.py': 'afc4e41427bb1803258108c9da8e89bad6dc68ccbd9505276c0cb53b66c3e08d',
    'tests/test_jvm_linkage.py': 'da95b488adb548c4fa040e3af870856294c8f0837057cfc2813b6682ab3f5600',
    'scripts/verify_gradle_wrapper.py': 'fba8c993c71f0ac0b8348d2535cee1f5e4ae39a9da4f514b3c9b13334f3ef10f',
    'tests/test_verify_gradle_wrapper.py': 'cfd3278d6ae1417dc57d3d571deb1e3532ba4f0e225c03a2a93b5048cb29b3fb',
    'docs/verification/linkage-contract.md': 'cdd8a801cd4b70da2aa78d0ff014f0fe80cdfce913e066b5f600e13de50de5ce',
}


class SharedVerifierSync(unittest.TestCase):
    def test_shared_files_match_reviewed_contract(self):
        for name, expected in CANONICAL.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), expected,
                                 'Propagate and review shared changes across affected groups')


if __name__ == '__main__':
    unittest.main()
