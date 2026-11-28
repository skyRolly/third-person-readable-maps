"""Detect unreviewed drift in the verifier copied to each maintenance group."""
import hashlib
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = {
    'scripts/jvm_linkage.py': '058655e3e78516e60b1900e81dd62d26feb5ae69503ab4c2553f1d908d3d7c35',
    'scripts/game_linkage.py': '366d421a34c52e125587aa0a9bbb5d311cf98cb6e2ee1a8b4bb46d811ad4e814',
    'tests/test_jvm_linkage.py': '9146a19a30c49cfaaaa36a411a641d31a9a261b6720eb0ca50e4573fb4918bea',
    'tests/test_hierarchy_linkage.py': '5a0d46b2b2139cc917bc1a07af55d3eb551648eb9ab980d9df0134b66d81e018',
    'tests/hierarchy_entrypoint_fixtures.py': '4ec6751f1576c570921b8dea896d38535af8f0591c4adaf14165c9c23f16ac88',
    'scripts/verify_gradle_wrapper.py': '2730fb13bf46b091a141f8adbbb178b299bb0f67831aaeffd2f3fc4a91402481',
    'tests/test_verify_gradle_wrapper.py': 'd14bce590f784c2d15e7afe462d947a789c68cf0cef7632e94735678e6dfa6b2',
    'tests/test_nestmate_linkage.py': '870e107ecb86a0ec97c85eed3b69509f92c66461ddf904170c4bc2f3548af235',
    'docs/verification/linkage-contract.md': 'fcaa278b8a6ee2a7848fe9aa18801daac8ecace6379d10e31903a78ff84c89f8',
}
ADAPTERS = {
    'intermediary': '4b93019ab84f0ed7bfa057436c943080f90194e7a8c91179171512c00de5feb7',
    'official': '159ecdbb63e288a8252ee8e286754f7c9003cb872eba3043f513df642e829758',
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
