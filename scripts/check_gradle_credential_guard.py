#!/usr/bin/env python3
"""Exercise the real Gradle init guard using only synthetic credentials.

No inherited credential or arbitrary Gradle option is forwarded to the test
processes. This tests early environment checks, not sandboxing or disclosure of
historical credentials.
"""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = ('GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN')
SYNTHETIC = 'guard-regression-synthetic-value'


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
    with tempfile.TemporaryDirectory(prefix='gradle-guard-regression-') as directory:
        root = Path(directory)
        (root / 'settings.gradle').write_text("rootProject.name = 'guard-regression'\n", encoding='utf-8')
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
        configured, executed = root / 'configured.marker', root / 'executed.marker'
        args = ['--offline', '--no-daemon', '--console=plain', '--init-script', str(guard),
                'verifyCleanEnvironment']

        def invoke(command, variables, should_pass, label):
            configured.unlink(missing_ok=True)
            executed.unlink(missing_ok=True)
            result = subprocess.run(command, cwd=root, env=variables, capture_output=True, text=True, timeout=180)
            output = result.stdout + result.stderr
            if SYNTHETIC in output:
                raise RuntimeError(label + ': test credential appeared in Gradle output')
            if should_pass:
                if result.returncode != 0 or not configured.exists() or not executed.exists():
                    raise RuntimeError(label + ': clean Gradle build did not complete')
            elif (result.returncode == 0 or configured.exists() or executed.exists() or
                  'Unexpected GitHub credential environment variable:' not in output):
                raise RuntimeError(label + ': guard did not reject before project configuration')
            print(label + ': PASS')

        invoke([gradle, *args], env, True, 'Clean environment')
        for name in NAMES:
            invoke([*java_gradle, *args], dict(env, **{name: SYNTHETIC}), False, name + ' rejection')
        if os.name != 'nt':
            wrapper = root / 'gradlew'
            wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(gradle) + ' "$@"\n', encoding='utf-8')
            wrapper.chmod(0o755)
            inherited = dict(env, **{name: SYNTHETIC for name in NAMES})
            invoke([sys.executable, str(ROOT / 'scripts/isolated_gradle.py'), '--root', str(root), '--', *args],
                   inherited, True, 'Isolated local Gradle subprocess')
        else:
            print('Isolated local Gradle helper: not tested on Windows (Linux helper)')


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
