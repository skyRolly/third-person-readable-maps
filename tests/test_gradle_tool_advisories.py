"""Exercise the source-bound upstream Gradle advisory gate and its workflow wiring."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import audit_gradle_tool as audit


def advisory(identifier, expression, severity='high', name='org.gradle:gradle-core'):
    return {'ghsa_id': identifier, 'state': 'published', 'withdrawn_at': None,
            'summary': 'Example build-tool issue', 'severity': severity,
            'updated_at': '2026-11-21T00:00:00Z',
            'vulnerabilities': [{'package': {'name': name, 'ecosystem': 'maven'},
                                 'vulnerable_version_range': expression,
                                 'patched_versions': '9.9.2'}]}


class Response:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return json.dumps(self.value).encode()


class GradleToolAdvisoryTests(unittest.TestCase):
    def test_numeric_and_historical_upstream_ranges(self):
        for current, expression, expected in [
            ('9.8.2', '>= 9.0.0, <= 9.9.0', True),
            ('9.9.1', '>= 9.0.0, <= 9.9.0', False),
            ('9.9.1', '>= 9.0.0, <= 9.9.1', True),
            ('9.9.2', '>= 9.0.0, <= 9.9.1', False),
            ('8.1.1', '<7.6.1, [8.0,8.1.1]', True),
            ('8.2.0', '<7.6.1, [8.0,8.1.1]', False),
            ('6.4.9', '4.5 through 6.4.x', True),
            ('6.5.0', '4.5 through 6.4.x', False),
            ('7.6.0', '6.2 to 7.6', True),
            ('8.12.0', '8.12', True),
        ]:
            with self.subTest(current=current, expression=expression):
                self.assertEqual(audit.affected(current, expression), expected)
        with self.assertRaisesRegex(ValueError, 'unsupported advisory version range'):
            audit.affected('9.9.2', 'something ambiguous')

    def test_upstream_filter_and_fail_closed_pages(self):
        rows = [advisory('GHSA-aaaa-bbbb-cccc', '>= 9.0.0, <= 9.9.0', 'critical'),
                advisory('GHSA-dddd-eeee-ffff', '>= 9.0.0, <= 9.9.1'),
                advisory('GHSA-gggg-hhhh-jjjj', '< 6.0', name='Gradle')]
        self.assertEqual(len(audit.upstream('9.8.2', lambda page: rows, {})), 2)
        self.assertEqual(len(audit.upstream('9.9.1', lambda page: rows, {})), 1)
        self.assertEqual(audit.upstream('9.9.2', lambda page: rows, {}), [])
        with self.assertRaisesRegex(ValueError, 'duplicate upstream advisory'):
            audit.upstream('9.8.2', lambda page: [rows[0], rows[0]], {})
        bad = advisory('GHSA-kkkk-mmmm-nnnn', 'not a supported range')
        with self.assertRaisesRegex(ValueError, 'unsupported advisory version range'):
            audit.upstream('9.9.2', lambda page: [bad], {})
        bad = dict(rows[0], state='unknown')
        with self.assertRaisesRegex(ValueError, 'unknown upstream advisory state'):
            audit.upstream('9.9.2', lambda page: [bad], {})
        bad = dict(rows[0], vulnerabilities=[])
        with self.assertRaisesRegex(ValueError, 'missing upstream affected versions'):
            audit.upstream('9.9.2', lambda page: [bad], {})
        bad = advisory('GHSA-pppp-qqqq-rrrr', '< 9.0', name='unexpected-package')
        with self.assertRaisesRegex(ValueError, 'unsupported upstream advisory package'):
            audit.upstream('9.9.2', lambda page: [bad], {})
        with self.assertRaisesRegex(ValueError, 'disappeared; review required'):
            audit.upstream('9.9.2', lambda page: [], {'GHSA-aaaa-bbbb-cccc': '2026-11-21T00:00:00Z'})
        with self.assertRaisesRegex(ValueError, 'changed or was withdrawn; review required'):
            audit.upstream('9.9.2', lambda page: [rows[0]], {'GHSA-aaaa-bbbb-cccc': 'older'})

    def test_real_cli_rejects_affected_version_and_invalid_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'gradle/wrapper/gradle-wrapper.properties'
            path.parent.mkdir(parents=True)
            path.write_text('distributionBase=GRADLE_USER_HOME\ndistributionPath=wrapper/dists\n'
                            'distributionSha256Sum=' + 'a' * 64 + '\n'
                            'distributionUrl=https\\://services.gradle.org/distributions/gradle-9.8.2-bin.zip\n'
                            'zipStoreBase=GRADLE_USER_HOME\nzipStorePath=wrapper/dists\n')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'fixture'], check=True)
            sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
            output = root / 'report.json'; row = advisory('GHSA-aaaa-bbbb-cccc', '<= 9.9.0', 'critical')
            argv = ['audit_gradle_tool.py', '--root', str(root), '--source-sha', sha, '--output', str(output)]
            with patch.object(sys, 'argv', argv), patch.object(audit, 'KNOWN_UPDATES', {}), \
                    patch.object(audit, 'open_request', return_value=Response([row])), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(), 1)
            report = json.loads(output.read_text()); self.assertEqual(report['source_sha'], sha)
            self.assertEqual(report['advisories'][0]['severity'], 'critical')
            self.assertFalse(report['risk_accepted'])
            path.write_text(path.read_text().replace('9.8.2', '9.9.2'))
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'fixed fixture'], check=True)
            sha = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
            argv[argv.index('--source-sha') + 1] = sha
            with patch.object(sys, 'argv', argv), patch.object(audit, 'KNOWN_UPDATES', {}), \
                    patch.object(audit, 'open_request', return_value=Response([row])), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(), 0)
            report = json.loads(output.read_text()); self.assertEqual(report['advisories'], [])
            with patch.object(sys, 'argv', argv), patch.object(audit, 'open_request', side_effect=OSError('offline')), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(), 2)
            self.assertEqual(json.loads(output.read_text())['status'], 'incomplete')
            path.write_text(path.read_text() + '# uncommitted change\n')
            with patch.object(sys, 'argv', argv), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(), 2)
            self.assertEqual(json.loads(output.read_text())['status'], 'incomplete')

    def test_api_failure_is_incomplete_and_not_a_passing_scan(self):
        with patch.object(audit, 'open_request', side_effect=OSError('network unavailable')):
            with self.assertRaisesRegex(OSError, 'network unavailable'):
                audit.upstream('9.9.2')
        with self.assertRaisesRegex(ValueError, 'unexpected upstream advisory redirect'):
            audit.RejectRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example/')

    def test_audits_and_release_execute_the_source_bound_check(self):
        for name, label in [('dependency-audit.yml', 'dependency-audit.json'),
                            ('candidate-dependency-audit.yml', 'candidate-dependency-audit.json')]:
            workflow = (ROOT / '.github/workflows' / name).read_text()
            self.assertIn('audit_gradle_tool.py --root source --source-sha "$SOURCE_SHA"', workflow)
            self.assertIn('gradle-tool-audit.json', workflow)
            self.assertIn(label, workflow)
            self.assertIn('if: always()', workflow[workflow.index('Query upstream Gradle build-tool advisories'):])
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        check = workflow.index('audit_gradle_tool.py --root . --source-sha "$SOURCE_SHA"')
        self.assertLess(workflow.index('verify_gradle_wrapper.py --root .'), check)
        self.assertLess(check, workflow.index('./gradlew', check))


if __name__ == '__main__':
    unittest.main()
