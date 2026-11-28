import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_candidate_shared_sync as check


class CandidateSharedSyncTests(unittest.TestCase):
    def setUp(self):
        self.candidates = {'a': {'candidate_head': 'a' * 40}, 'b': {'candidate_head': 'b' * 40}}
        self.maintenance = {'c': {'integrated_commit': 'c' * 40}}

    def test_candidate_difference_fails_and_maintenance_difference_is_pending(self):
        self.assertEqual(check.compare(self.candidates, self.maintenance, lambda sha, path: path.encode()), [])
        def candidate_changed(sha, path):
            return (path + (' changed' if sha == 'b' * 40 and path == check.shared.SHARED[0] else '')).encode()
        with self.assertRaisesRegex(ValueError, 'candidate shared file differs'):
            check.compare(self.candidates, self.maintenance, candidate_changed)
        def maintenance_changed(sha, path):
            return (path + (' changed' if sha == 'c' * 40 and path == check.shared.SHARED[0] else '')).encode()
        self.assertEqual(check.compare(self.candidates, self.maintenance, maintenance_changed),
                         ['c: shared file differs: ' + check.shared.SHARED[0]])

    def test_missing_and_invalid_sources_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'groups are required'):
            check.compare({}, self.maintenance, lambda sha, path: b'')
        with self.assertRaisesRegex(ValueError, 'invalid candidate head'):
            check.compare({'a': {'candidate_head': 'bad'}}, self.maintenance, lambda sha, path: b'')


if __name__ == '__main__':
    unittest.main()
