#!/usr/bin/env python3
"""Run a local Gradle wrapper with a minimal environment and disposable user home.

This isolates inherited environment credentials, not the build from files or the
network. Review source and plugins before executing them.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def build_environment(environ, home):
    # Deliberately do not forward arbitrary proxy, GitHub, cloud, or Gradle
    # settings: these can contain credentials. JAVA_HOME and PATH select tools.
    env = {key: environ[key] for key in ('PATH', 'JAVA_HOME', 'LANG', 'LC_ALL', 'TZ') if key in environ}
    env.update(HOME=str(home), GRADLE_USER_HOME=str(home / '.gradle'),
               TMPDIR=str(home / 'tmp'), TMP=str(home / 'tmp'), TEMP=str(home / 'tmp'))
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='project containing gradlew')
    parser.add_argument('gradle_args', nargs=argparse.REMAINDER, help='arguments after --')
    args = parser.parse_args()
    root = args.root.resolve()
    wrapper = root / 'gradlew'
    if not wrapper.is_file():
        parser.error('project has no gradlew')
    gradle_args = args.gradle_args
    if gradle_args[:1] == ['--']:
        gradle_args = gradle_args[1:]
    if not gradle_args:
        parser.error('provide Gradle arguments after --')
    with tempfile.TemporaryDirectory(prefix='readable-maps-gradle-') as directory:
        home = Path(directory)
        (home / 'tmp').mkdir()
        try:
            return subprocess.call([str(wrapper), *gradle_args], cwd=root,
                                   env=build_environment(os.environ, home))
        except OSError as exc:
            print(f'Unable to run Gradle wrapper: {exc}', file=sys.stderr)
            return 2


if __name__ == '__main__':
    sys.exit(main())
