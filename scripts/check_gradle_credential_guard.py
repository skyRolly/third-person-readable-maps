#!/usr/bin/env python3
"""Exercise the real Gradle init guard using only synthetic credentials.

No inherited credential or arbitrary Gradle option is forwarded to the test
processes. This tests early environment checks, not sandboxing or disclosure of
historical credentials.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN')
SYNTHETIC = 'guard-regression-synthetic-value'


@contextmanager
def temporary_project():
    root = Path(tempfile.mkdtemp(prefix='gradle-guard-regression-'))
    try:
        yield root
    finally:
        # Single-use Gradle daemons can briefly keep native DLLs open after the
        # client exits on Windows. Retry cleanup without treating the guard as
        # failed or retaining test files indefinitely.
        for attempt in range(20):
            try:
                shutil.rmtree(root)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(1)


def check_result(result, markers, should_pass, label):
    output = result.stdout + result.stderr
    if SYNTHETIC in output:
        raise RuntimeError(label + ': test credential appeared in Gradle output')
    if should_pass:
        if result.returncode != 0 or not all(path.exists() for path in markers):
            raise RuntimeError(label + ': clean Gradle build did not complete')
    elif (result.returncode == 0 or any(path.exists() for path in markers) or
          'Unexpected GitHub credential environment variable:' not in output):
        raise RuntimeError(label + ': guard did not reject before settings evaluation')


def run(gradle):
    gradle = shutil.which(gradle)
    if not gradle:
        raise RuntimeError('Gradle executable is unavailable')
    distribution = Path(gradle).resolve().parent.parent
    launchers = list((distribution / 'lib').glob('gradle-gradle-cli-main-*.jar'))
    agents = list((distribution / 'lib/agents').glob('gradle-instrumentation-agent-*.jar'))
    java = (str(Path(os.environ['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java'))
            if os.environ.get('JAVA_HOME') else shutil.which('java'))
    if len(launchers) != 1 or len(agents) != 1 or not java:
        raise RuntimeError('Gradle distribution or Java launcher is unavailable')
    # Invoke Java directly for negative controls. Some POSIX shells drop names
    # containing a hyphen before Gradle starts, which would leave that guard
    # branch untested even though INPUT_GITHUB-TOKEN was set in the parent.
    java_gradle = [java, '-Xmx64m', '-Xms64m', '-javaagent:' + str(agents[0]),
                   '-Dorg.gradle.appname=gradle', '-jar', str(launchers[0])]
    guard = ROOT / '.github/gradle/no-github-credentials.init.gradle'
    with temporary_project() as root:
        (root / 'settings.gradle').write_text("new File(settingsDir, 'settings.marker').text = 'evaluated'\n"
                                              "rootProject.name = 'guard-regression'\n", encoding='utf-8')
        (root / 'build.gradle').write_text(
            "file('configured.marker').text = 'configured'\n"
            "tasks.register('verifyCleanEnvironment') { doLast {\n"
            "  ['GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN'].each { name ->\n"
            "    if (System.getenv(name)) throw new GradleException('Unexpected test credential name: ' + name)\n"
            "  }\n"
            "  file('executed.marker').text = 'executed'\n"
            "} }\n", encoding='utf-8')
        allowed = ('PATH', 'JAVA_HOME', 'LANG', 'LC_ALL', 'TZ', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT')
        env = {name: os.environ[name] for name in allowed if name in os.environ}
        env.update(HOME=str(root), GRADLE_USER_HOME=str(root / 'gradle-home'),
                   TMP=str(root), TEMP=str(root), TMPDIR=str(root))
        markers = [root / 'settings.marker', root / 'configured.marker', root / 'executed.marker']
        args = ['--offline', '--no-daemon', '--console=plain', '--init-script', str(guard),
                'verifyCleanEnvironment']

        def invoke(command, variables, should_pass, label):
            for marker in markers:
                marker.unlink(missing_ok=True)
            result = subprocess.run(command, cwd=root, env=variables, capture_output=True, text=True, timeout=180)
            check_result(result, markers, should_pass, label)
            print(label + ': PASS')

        invoke([gradle, *args], env, True, 'Clean environment')
        for name in NAMES:
            invoke([*java_gradle, *args], dict(env, **{name: SYNTHETIC}), False, name + ' rejection')
        # Negative control: the old project-only marker check would accept a
        # guard that runs too late, after settings.gradle has already executed.
        delayed = root / 'delayed.init.gradle'
        delayed.write_text("gradle.beforeProject {\n"
                           "  if (System.getenv('GH_TOKEN')) throw new GradleException(\n"
                           "    'Unexpected GitHub credential environment variable: GH_TOKEN')\n"
                           "}\n", encoding='utf-8')
        delayed_args = [str(delayed) if arg == str(guard) else arg for arg in args]
        try:
            invoke([*java_gradle, *delayed_args], dict(env, GH_TOKEN=SYNTHETIC), False, 'Delayed guard')
        except RuntimeError as exc:
            if ('before settings evaluation' not in str(exc) or not markers[0].exists() or
                    markers[1].exists() or markers[2].exists()):
                raise
        else:
            raise RuntimeError('Delayed guard was incorrectly accepted')
        print('Delayed-guard mutation rejected: PASS')
        if os.name != 'nt':
            wrapper = root / 'gradlew'
            wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(gradle) + ' "$@"\n', encoding='utf-8')
            wrapper.chmod(0o755)
            inherited = dict(env, **{name: SYNTHETIC for name in NAMES})
            invoke([sys.executable, str(ROOT / 'scripts/isolated_gradle.py'), '--root', str(root), '--', *args],
                   inherited, True, 'Isolated local Gradle subprocess')
        else:
            print('Isolated local Gradle helper: not tested on Windows (Linux helper)')
            stopped = subprocess.run([*java_gradle, '--stop'], cwd=root, env=env, capture_output=True,
                                     text=True, timeout=60)
            if stopped.returncode:
                raise RuntimeError('Unable to stop test Gradle daemons before cleanup')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gradle', default='gradle')
    args = parser.parse_args()
    try:
        run(args.gradle)
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print('Credential guard regression failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
