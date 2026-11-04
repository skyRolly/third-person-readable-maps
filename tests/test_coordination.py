import io
import json
import re
from contextlib import redirect_stderr
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import release
import scan_dependency_snapshot as scanner


class CoordinationTests(unittest.TestCase):
    def test_coordinator_has_no_game_build_and_documents_every_group(self):
        for path in ('src', 'build.gradle', 'gradle.properties', 'settings.gradle',
                     'gradlew', 'gradlew.bat', 'gradle', 'Build-Windows.bat'):
            with self.subTest(path=path):
                self.assertFalse((ROOT / path).exists())
        cfg = release.read_json(ROOT / 'release/compatibility.json')
        plan = release.read_json(ROOT / 'release/plan.example.json')
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertEqual(set(cfg['groups']), set(plan['groups']))
        for name, spec in cfg['groups'].items():
            self.assertIn(spec['branch'], readme)
            self.assertEqual(plan['groups'][name]['source_branch'], spec['branch'])
            for minecraft in spec['minecraft']:
                self.assertIn(minecraft, readme)
        actual_plan = ROOT / 'release/plan.json'
        if actual_plan.exists():
            release.load_plan(actual_plan)

    def test_candidate_cli_validates_all_groups_without_publishing(self):
        plan = release.read_json(ROOT / 'release/plan.example.json')
        for i, entry in enumerate(plan['groups'].values(), 1):
            entry['commit'] = str(i) * 40
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'plan.json'
            path.write_text(json.dumps(plan), encoding='utf-8')
            cmd = [sys.executable, str(ROOT / 'scripts/release.py')]
            matrix = subprocess.run(cmd + ['matrix', '--plan', str(path), '--candidate'],
                                    cwd=temp, capture_output=True, text=True, check=True)
            selected = json.loads(matrix.stdout)['include']
            self.assertEqual({x['group'] for x in selected}, set(plan['groups']))
            self.assertEqual({x['branch'] for x in selected},
                             {x['source_branch'] for x in plan['groups'].values()})
            strict = subprocess.run(cmd + ['validate', '--plan', str(path)],
                                    cwd=temp, capture_output=True, text=True)
            self.assertNotEqual(strict.returncode, 0)  # no invented runtime evidence
            self.assertEqual(list(Path(temp).iterdir()), [path])
        for script in ('release.py', 'authorize_release.py', 'release_github.py', 'scan_dependency_snapshot.py'):
            self.assertEqual(subprocess.run([sys.executable, str(ROOT / 'scripts' / script), '--help'],
                                            capture_output=True).returncode, 0)

    def test_dependency_updates_cover_each_maintained_branch(self):
        config = (ROOT / '.github/dependabot.yml').read_text(encoding='utf-8')
        blocks = re.split(r'(?m)^  - package-ecosystem: ', config)[1:]
        entries = set()
        for block in blocks:
            ecosystem = block.splitlines()[0].strip()
            branch = re.search(r'(?m)^    target-branch: (.+)$', block)
            self.assertIsNotNone(re.search(r'(?m)^    directory: /$', block))
            self.assertIsNotNone(re.search(r'(?m)^      interval: weekly$', block))
            entries.add((ecosystem, branch.group(1) if branch else 'main'))
        groups = release.read_json(ROOT / 'release/compatibility.json')['groups']
        expected = {('github-actions', 'main')}
        for spec in groups.values():
            for ecosystem in ('gradle', 'github-actions'):
                expected.add((ecosystem, spec['branch']))
            self.assertIn(spec['branch'], (ROOT / '.github/workflows/dependency-audit.yml').read_text())
        self.assertEqual(entries, expected)
        self.assertEqual(len(blocks), len(entries))

    def test_audit_refuses_snapshot_for_another_branch_or_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / 'snapshot.json'
            snapshot.write_text(json.dumps({'ref': 'refs/heads/mc/26.3', 'sha': 'a' * 40,
                'manifests': {'build': {'resolved': {'x': {'package_url': 'pkg:maven/example/x@1.0'}}}}}))
            argv = ['scan_dependency_snapshot.py', '--snapshot', str(snapshot), '--branch', 'mc/1.21.11',
                    '--source-sha', 'a' * 40, '--output', str(Path(temp) / 'report.json')]
            with patch.object(sys, 'argv', argv), patch.object(scanner, 'query') as query, redirect_stderr(io.StringIO()):
                self.assertEqual(scanner.main(), 2)
                query.assert_not_called()
            self.assertFalse((Path(temp) / 'report.json').exists())

    def test_audit_reports_and_fails_when_snapshot_contains_unscanned_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshot, output = Path(temp) / 'snapshot.json', Path(temp) / 'report.json'
            snapshot.write_text(json.dumps({'ref': 'refs/heads/mc/1.21.11', 'sha': 'a' * 40,
                'manifests': {'build': {'resolved': {'known': {'package_url': 'pkg:maven/example/x@1.0'},
                                                     'unknown': {}}}}}))
            argv = ['scan_dependency_snapshot.py', '--snapshot', str(snapshot), '--branch', 'mc/1.21.11',
                    '--source-sha', 'a' * 40, '--output', str(output)]
            with patch.object(sys, 'argv', argv), patch.object(scanner, 'query', return_value={}), \
                 patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(scanner.main(), 1)
            self.assertEqual(json.loads(output.read_text())['unscanned_snapshot_entries'], ['unknown'])

    def test_osv_snapshot_reports_skipped_entries_and_paginates(self):
        snapshot = {'manifests': {'build': {'resolved': {
            'one': {'package_url': 'pkg:maven/org.example/one@1.0'},
            'duplicate': {'package_url': 'pkg:maven/org.example/one@1.0'},
            'two': {'package_url': 'pkg:maven/org.example/two@2.0'},
            'unidentified': {},
        }}}}
        purls, skipped = scanner.packages(snapshot)
        self.assertEqual(len(purls), 2)
        self.assertEqual(skipped, ['unidentified'])
        responses = [
            {'results': [{'vulns': [{'id': 'GHSA-test-123'}], 'next_page_token': 'page2'}, {}]},
            {'results': [{'vulns': [{'id': 'GHSA-test-456'}]}]},
        ]
        requests = []
        def fake_urlopen(request, timeout):
            requests.append(json.loads(request.data))
            return io.BytesIO(json.dumps(responses.pop(0)).encode())
        with patch.object(scanner, 'urlopen', side_effect=fake_urlopen):
            found = scanner.query(purls)
        self.assertEqual(found, {purls[0]: ['GHSA-test-123', 'GHSA-test-456']})
        self.assertEqual(requests[1]['queries'][0]['page_token'], 'page2')
        with self.assertRaises(release.Invalid):
            scanner.packages({'manifests': {'build': {'resolved': {'x': {}}}}})
        with patch.object(scanner, 'urlopen', return_value=io.BytesIO(b'{"results":[]}')):
            with self.assertRaises(release.Invalid):
                scanner.query(purls)


if __name__ == '__main__':
    unittest.main()
