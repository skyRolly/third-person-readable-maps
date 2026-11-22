import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from isolated_gradle import build_environment
import check_gradle_credential_guard as guard


class IsolatedGradleTests(unittest.TestCase):
    def test_allowlist_excludes_credentials_and_isolates_gradle_home(self):
        home = Path('/tmp/isolated-home')
        env = build_environment({'PATH': '/bin', 'JAVA_HOME': '/java', 'GH_TOKEN': 'secret',
                                 'GITHUB_TOKEN': 'secret', 'INPUT_GITHUB-TOKEN': 'secret', 'HTTP_PROXY': 'secret',
                                 'GRADLE_OPTS': 'secret', 'SSH_AUTH_SOCK': 'secret'}, home)
        self.assertEqual(set(env), {'PATH', 'JAVA_HOME', 'HOME', 'GRADLE_USER_HOME', 'TMPDIR', 'TMP', 'TEMP'})
        self.assertEqual(env['GRADLE_USER_HOME'], str(home / '.gradle'))

    def test_wrapper_receives_arguments_and_minimal_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / 'gradlew'
            wrapper.write_text('#!/bin/sh\n[ -z "${GH_TOKEN+x}" ] || exit 9\n'
                               '[ "$HOME/.gradle" = "$GRADLE_USER_HOME" ] || exit 10\n'
                               '[ "$1" = "clean" ] && [ "$2" = "build" ] && [ "$3" = "--no-daemon" ]\n')
            wrapper.chmod(0o755)
            env = dict(os.environ, GH_TOKEN='test-only-secret')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/isolated_gradle.py'),
                                     '--root', str(root), '--', 'clean', 'build'], env=env)
            self.assertEqual(result.returncode, 0)

    def test_temporary_project_retries_a_transient_locked_file(self):
        real_remove = guard.shutil.rmtree
        calls = []

        def transient(path):
            calls.append(path)
            if len(calls) == 1:
                raise PermissionError('test-only lock')
            real_remove(path)

        with patch.object(guard.shutil, 'rmtree', side_effect=transient), patch.object(guard.time, 'sleep') as delay:
            with guard.temporary_project() as project:
                (project / 'fixture').write_text('test')
            self.assertFalse(project.exists())
        self.assertEqual(len(calls), 2)
        delay.assert_called_once_with(1)

    def test_settings_execution_before_rejection_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            markers = [root / 'settings.marker', root / 'configured.marker', root / 'executed.marker']
            failure = subprocess.CompletedProcess([], 1, stdout='',
                stderr='Unexpected GitHub credential environment variable: GH_TOKEN')
            guard.check_result(failure, markers, False, 'negative control')
            markers[0].write_text('settings ran before rejection')
            with self.assertRaisesRegex(RuntimeError, 'before settings evaluation'):
                guard.check_result(failure, markers, False, 'negative control')
            for marker in markers:
                marker.write_text('ran')
            success = subprocess.CompletedProcess([], 0, stdout='', stderr='')
            guard.check_result(success, markers, True, 'positive control')


if __name__ == '__main__':
    unittest.main()
