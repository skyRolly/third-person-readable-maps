"""Exercise verifyMixinTarget with a non-void handler descriptor."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import jvm_linkage

INJECT = 'Lorg/spongepowered/asm/mixin/injection/Inject;'


def run():
    classes = ROOT / 'build/classes/java/main'
    matches = []
    for path in classes.rglob('*.class'):
        node = jvm_linkage.parse(path.read_bytes())
        for member in node['members']:
            if INJECT in member['annotations']:
                matches.append((path, member['descriptor']))
    if not matches:
        raise RuntimeError('no compiled Mixin injection handler found')
    path, descriptor = matches[0]
    if not descriptor.endswith(')V'):
        raise RuntimeError('expected the original handler to return void')
    raw = path.read_bytes()
    before, after = descriptor.encode('utf-8'), (descriptor[:-1] + 'I').encode('utf-8')
    if raw.count(before) != 1:
        raise RuntimeError('handler descriptor is not uniquely encoded')
    env = {key: value for key, value in os.environ.items()
           if key not in ('GH_TOKEN', 'GITHUB_TOKEN', 'INPUT_GITHUB-TOKEN')}
    try:
        path.write_bytes(raw.replace(before, after, 1))
        result = subprocess.run(
            ['./gradlew', '--no-daemon', '--console=plain', 'verifyMixinTarget',
             '-x', 'classes', '-x', 'compileJava', '--rerun-tasks'], cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=300)
        if result.returncode == 0 or 'Mixin injection handler must return void' not in result.stdout:
            raise RuntimeError('non-void handler did not fail for the expected reason:\n' + result.stdout[-5000:])
        print('Non-void Mixin handler control: PASS', flush=True)
    finally:
        path.write_bytes(raw)


if __name__ == '__main__':
    run()
