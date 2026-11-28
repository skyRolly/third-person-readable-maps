"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'tests/test_java_toolchain.py': '518ac476311fe8f2b4dcf875fe4fa0cc2f5cb69181bfcd9a48ef2f833e9c5989',
    'tests/java_toolchain.py': 'd977d0dddb52117746305cdbad0a2cbaf79bf65ff4c2d1ecc2882ebf2a070405',
    'scripts/jvm_linkage.py': '843aa0aa5f90e8f9746085991de57f4f3a24874e18d15322f4b2fcefa8f18b1a',
    'scripts/game_linkage.py': 'a785fe6581509be31966bbb1afc688ed9ffca044963b7ab7def8479401f398ab',
    'tests/test_jvm_linkage.py': '650d1560b6e37a857e66bbbb08aaae42f7e1e83444492ba31eeedcb5114e60dc',
    'tests/test_hierarchy_linkage.py': '3b8388aaef57bf2ac0b9ee3115ebece9a04662d9e37baed321b375c993f731b8',
    'tests/hierarchy_entrypoint_fixtures.py': '996360319c65aa6c6be74036e07a7ba2b4a18a9752da0ce6205cd99f97f6e216',
    'scripts/verify_gradle_wrapper.py': '2730fb13bf46b091a141f8adbbb178b299bb0f67831aaeffd2f3fc4a91402481',
    'tests/test_verify_gradle_wrapper.py': 'b4eeb0608cb5aca42226096c1178fbf3fed72f69158eba2cc349be96702c69cc',
    'tests/test_nestmate_linkage.py': 'bf6bef36cba8b473b657c554860caab6ebc63dad16605b3ae4b611e9256a6185',
    'docs/verification/linkage-contract.md': 'cc20bbe638fdb79da07730eb0738f965630b4f8f2ffdbd5eba002add47d71866',
}
ADAPTERS = {
    'intermediary': 'fccb16a5ff3d25ba9b80697811629a9bfcbcb16fd8b80e87b9303bbbac29cbbf',
    'official': '3a720780ffac428a282c69a14e3ee2ef02802ad405718078ed61937fc9efa843',
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
