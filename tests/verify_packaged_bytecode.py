"""Exercise verifyModJar against a valid older class and a preview class."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def run():
    jars = list((ROOT / 'build/libs').glob('*-mc1.19.3.jar'))
    if len(jars) != 1:
        raise RuntimeError('expected exactly one built 1.19.3 JAR')
    jar = jars[0]
    env = {key: value for key, value in os.environ.items()
           if key not in ('GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN')}
    javac = str(Path(env['JAVA_HOME']) / 'bin' / 'javac') if env.get('JAVA_HOME') else 'javac'
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        source = root / 'Fixture.java'
        source.write_text('public class Fixture {}\n', encoding='utf-8')
        subprocess.run([javac, '--release', '8', str(source)], check=True, env=env, timeout=60)
        older = (root / 'Fixture.class').read_bytes()
        if older[4:8] != b'\x00\x00\x00\x34':
            raise RuntimeError('fixture is not ordinary Java 8 bytecode')
        preview = older[:4] + b'\xff\xff\x00\x41' + older[8:]
        backup = root / 'original.jar'
        shutil.copyfile(jar, backup)
        try:
            for label, payload, should_pass in (('older', older, True), ('preview', preview, False)):
                shutil.copyfile(backup, jar)
                with ZipFile(jar, 'a') as archive:
                    archive.writestr('Fixture.class', payload)
                result = subprocess.run(
                    ['./gradlew', '--no-daemon', '--console=plain', 'verifyModJar',
                     '-x', 'remapJar', '--rerun-tasks'], cwd=ROOT, env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
                if (result.returncode == 0) != should_pass:
                    raise RuntimeError(label + ' class produced an unexpected result:\n' + result.stdout[-5000:])
                if not should_pass and 'Unsupported class version or preview bytecode: Fixture.class' not in result.stdout:
                    raise RuntimeError('preview class failed for a different reason:\n' + result.stdout[-5000:])
                print(label + ' bytecode control: PASS', flush=True)
        finally:
            shutil.copyfile(backup, jar)


if __name__ == '__main__':
    run()
