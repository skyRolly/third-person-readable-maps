"""Prove verifyModJar rejects a common Mixin in the built distributable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = 'thirdpersonreadablemaps.mixins.json'


def run():
    jars = [path for path in (ROOT / 'build/libs').glob('*-mc*.jar')
            if not path.name.endswith(('-sources.jar', '-dev.jar'))]
    if len(jars) != 1:
        raise RuntimeError('expected exactly one built distributable JAR')
    jar = jars[0]
    gradle_script = (ROOT / 'gradle/verification.gradle').read_text()
    if "dependsOn tasks.named('remapJar')" in gradle_script:
        producer = 'remapJar'
    elif "dependsOn tasks.named('jar')" in gradle_script:
        producer = 'jar'
    else:
        raise RuntimeError('unrecognized distributable JAR producer')
    env = {key: value for key, value in os.environ.items()
           if key not in ('GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN')}
    with tempfile.TemporaryDirectory() as temp:
        backup = Path(temp) / 'original.jar'
        shutil.copyfile(jar, backup)
        try:
            with ZipFile(backup) as original, ZipFile(jar, 'w') as modified:
                found = 0
                for entry in original.infolist():
                    data = original.read(entry)
                    if entry.filename == CONFIG:
                        config = json.loads(data)
                        config['mixins'] = ['MissingMixin']
                        data = json.dumps(config).encode()
                        found += 1
                    modified.writestr(entry, data)
                if found != 1:
                    raise RuntimeError('expected one Mixin configuration')
            result = subprocess.run(
                ['./gradlew', '--no-daemon', '--console=plain', 'verifyModJar',
                 '-x', producer, '--rerun-tasks'], cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
            if result.returncode == 0 or 'Unsupported common Mixin registration' not in result.stdout:
                raise RuntimeError('common Mixin control did not fail for the expected reason:\n' + result.stdout[-5000:])
            print('Unverified common Mixin control: PASS', flush=True)
        finally:
            shutil.copyfile(backup, jar)


if __name__ == '__main__':
    run()
