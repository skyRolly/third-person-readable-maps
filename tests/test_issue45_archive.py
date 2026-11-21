import gzip
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/dependency-evidence/issue45-exact-source-2026-11-21-v2'


class Issue45ArchiveTests(unittest.TestCase):
    def test_hashes_source_bindings_and_findings(self):
        archive = json.loads((ARCHIVE / 'archive-index.json').read_text())
        index = json.loads((ARCHIVE / 'finding-index.json').read_text())
        reports = {}
        for item in archive['files']:
            path = ROOT / item['path']
            packed = path.read_bytes()
            raw = gzip.decompress(packed)
            self.assertEqual(hashlib.sha256(packed).hexdigest(), item['sha256_gzip'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256_uncompressed'])
            document = json.loads(raw)
            if path.name in ('candidate-dependency-audit.json.gz', 'dependency-audit.json.gz'):
                self.assertEqual(document['source_sha'], item['source_sha'])
                reports[str(path.relative_to(ROOT))] = document
        self.assertEqual(len(reports), 13)
        records = index['records']
        self.assertEqual(len({(r['source_kind'], r['key']) for r in records}), len(records))
        indexed = {(r['source_kind'], r['key']): r for r in records}
        expected = {}
        for path, report in reports.items():
            kind = 'candidate' if '/candidate/' in path else 'integrated'
            for match in report['matches']:
                key = (kind, match['key'])
                self.assertNotIn(key, expected)
                expected[key] = (path, report['source_sha'], match)
        self.assertEqual(set(indexed), set(expected))
        for key, (path, source_sha, match) in expected.items():
            row = indexed[key]
            self.assertEqual((row['report'], row['source_sha']), (path, source_sha))
            for field in ('purl', 'advisory', 'scopes', 'fingerprint', 'severity', 'disposition', 'failing'):
                self.assertEqual(row[field], match[field])


if __name__ == '__main__':
    unittest.main()
