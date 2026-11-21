"""A candidate cannot establish cross-branch identity with its own digest table."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_shared_verifier_sync as sync


class SharedVerifierCrossBranchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q'); self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        for path in sync.SHARED:
            file = self.repo/path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('shared\n')
        (self.repo/sync.ADAPTER).write_text('intermediary\n')
        self.git('add', '.'); self.git('commit', '-qm', 'intermediary')
        self.a = self.git('rev-parse', 'HEAD')
        (self.repo/sync.ADAPTER).write_text('official\n')
        self.git('commit', '-qam', 'official')
        self.b = self.git('rev-parse', 'HEAD')
        self.groups = {'a': {'new_head': self.a, 'namespace': 'intermediary'},
                       'b': {'new_head': self.b, 'namespace': 'official'}}

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

    def read(self, commit, path):
        return subprocess.run(['git', 'show', commit+':'+path], cwd=self.repo, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    def test_compares_committed_contents_and_permits_adapter_variants(self):
        self.assertEqual(sync.verify(self.groups, {'a', 'b'}, self.read)['groups'], 2)
        # Changing both a verifier and its own local manifest is still detectable.
        (self.repo/'scripts/game_linkage.py').write_text('drifted\n')
        (self.repo/'tests/test_shared_verifier_sync.py').write_text('updated own digest\n')
        self.git('commit', '-qam', 'drift including local digest')
        self.groups['b']['new_head'] = self.git('rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'shared file differs'):
            sync.verify(self.groups, {'a', 'b'}, self.read)

    def test_missing_groups_and_unknown_namespace_fail(self):
        with self.assertRaisesRegex(ValueError, 'groups do not match'):
            sync.verify(self.groups, {'a', 'b', 'c'}, self.read)
        self.groups['b']['namespace'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'unknown namespace'):
            sync.verify(self.groups, {'a', 'b'}, self.read)

    def test_different_fixtures_within_one_namespace_fail(self):
        self.groups['b']['namespace'] = 'intermediary'
        with self.assertRaisesRegex(ValueError, 'adapter fixture differs'):
            sync.verify(self.groups, {'a', 'b'}, self.read)


if __name__ == '__main__':
    unittest.main()
