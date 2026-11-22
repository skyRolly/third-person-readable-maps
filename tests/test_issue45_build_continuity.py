import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import validate_issue45_build_continuity as continuity


class BuildContinuityTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((ROOT / continuity.ERRATUM).read_bytes())
        continuity.validate(self.report)

    def test_three_integrated_sources_changed_but_artifacts_match(self):
        for group in continuity.GROUPS:
            with self.subTest(group=group):
                row = self.report['groups'][group]
                self.assertFalse(row['source_unchanged'])
                self.assertTrue(row['artifact_unchanged'])
                self.assertEqual(row['artifact_continuity'], 'same')
                self.assertFalse(row['legacy_same_as_previous'])
                self.assertEqual(len(row['verified_archives']), 3)

    def test_inconsistent_interpretations_are_rejected_for_each_group(self):
        for group in continuity.GROUPS:
            for field, value in (('source_unchanged', True), ('artifact_unchanged', False),
                                 ('artifact_continuity', 'different'), ('previous_source_sha', '0' * 40)):
                with self.subTest(group=group, field=field):
                    altered = copy.deepcopy(self.report)
                    altered['groups'][group][field] = value
                    with self.assertRaisesRegex(ValueError, 'inconsistent source or artifact continuity'):
                        continuity.validate(altered)

    def test_changed_original_snapshot_is_rejected(self):
        real_read = continuity.read
        def changed(root, path):
            raw = real_read(root, path)
            return raw + b' ' if path == continuity.SOURCES['build_snapshot'][0] else raw
        with patch.object(continuity, 'read', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'build_snapshot: source checksum mismatch'):
                continuity.validate(self.report)


if __name__ == '__main__':
    unittest.main()
