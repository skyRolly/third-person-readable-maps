import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_candidate_source as source
from release import Invalid


class SourceTransitionTests(unittest.TestCase):
    def setUp(self):
        self.group = '1.14-1.14.4'
        self.branch = 'candidate/mc-' + self.group
        self.sha = 'a' * 40
        self.merged = 'b' * 40
        self.tree = 'c' * 40
        self.entry = {'candidate_head': self.sha,
                      'pull_request': 'https://github.com/skyRolly/third-person-readable-maps/pull/23'}
        self.data = {
            'branches/candidate%2Fmc-1.14-1.14.4': {'commit': {'sha': self.sha}},
            'pulls/23': {'state': 'closed', 'merged_at': '2026-11-12T00:00:00Z',
                         'merge_commit_sha': self.merged,
                         'head': {'sha': self.sha, 'ref': self.branch, 'repo': {'full_name': source.REPO}},
                         'base': {'ref': 'mc/' + self.group, 'repo': {'full_name': source.REPO}}},
            'branches/mc%2F1.14-1.14.4': {'commit': {'sha': self.merged}},
            'git/commits/' + self.sha: {'tree': {'sha': self.tree}},
            'git/commits/' + self.merged: {'tree': {'sha': self.tree}},
        }

    def verify(self, data=None, branch=None):
        values = data if data is not None else self.data
        return source.verify_live_source(self.group, branch or self.branch, self.sha, self.entry,
                                         lambda path, allow_missing=False: values.get(path))

    def test_current_pin_and_changed_or_missing_unmerged_branch(self):
        self.assertEqual(self.verify(), 'pinned-branch')
        changed = copy.deepcopy(self.data)
        changed['branches/candidate%2Fmc-1.14-1.14.4']['commit']['sha'] = 'd' * 40
        with self.assertRaises(Invalid): self.verify(changed)
        del changed['branches/candidate%2Fmc-1.14-1.14.4']
        changed['pulls/23']['merged_at'] = None
        with self.assertRaises(Invalid): self.verify(changed)

    def test_deleted_merged_candidate_remains_pinned_candidate_evidence(self):
        deleted = copy.deepcopy(self.data)
        del deleted['branches/candidate%2Fmc-1.14-1.14.4']
        self.assertEqual(self.verify(deleted), 'deleted-merged-candidate')
        for mutate in (
            lambda x: x['pulls/23']['head'].update(sha='d' * 40),
            lambda x: x['pulls/23']['base'].update(ref='mc/1.21.11'),
            lambda x: x['branches/mc%2F1.14-1.14.4']['commit'].update(sha='d' * 40),
            lambda x: x['git/commits/' + self.merged]['tree'].update(sha='d' * 40),
        ):
            broken = copy.deepcopy(deleted); mutate(broken)
            with self.subTest(broken=broken), self.assertRaises(Invalid): self.verify(broken)

    def test_missing_integrated_transition_never_falls_back(self):
        with self.assertRaises(Invalid): self.verify({}, 'mc/' + self.group)


if __name__ == '__main__':
    unittest.main()
