"""Run each game's own MapId codec with its hash-verified Mojang artifacts.

Requires network access, the local JDK 25 toolchain, and the cached Minecraft
libraries from installed-client tests. No mod, world or server is loaded.
"""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
LIBRARIES = Path('/workspace/.minecraft-test/libraries')
JAVA = Path('/workspace/.toolchains/jdk25/bin')
VERSIONS = ['1.20.5', '1.20.6', '1.21', '1.21.1', '1.21.2', '1.21.3',
            '1.21.4', '1.21.5', '1.21.6', '1.21.7', '1.21.8', '1.21.9',
            '1.21.10', '1.21.11', '26.1', '26.1.1', '26.1.2', '26.2', '26.3']
URL = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'


def sha1(raw):
    return hashlib.sha1(raw).hexdigest()


def fetch(url):
    with urlopen(url, timeout=90) as response:
        return response.read()


def checked(spec):
    raw = fetch(spec['url'])
    if sha1(raw) != spec['sha1'] or ('size' in spec and len(raw) != spec['size']):
        raise ValueError('Mojang artifact identity mismatch: ' + spec['url'])
    return raw


def mapping_names(mapping):
    text = mapping.decode('utf-8')
    excerpts = {}
    def block(name):
        match = re.search(r'(?m)^' + re.escape(name) + r' -> (\S+):\n((?:(?:[ \t]+|#).*(?:\n|$))*)', text)
        if not match:
            raise ValueError('missing official class mapping: ' + name)
        excerpts[name] = match.group(0)
        return match.group(1), match.group(2)
    map_class, map_block = block('net.minecraft.world.level.saveddata.maps.MapId')
    nbt_class, nbt_block = block('net.minecraft.nbt.NbtOps')
    def member(block_text, pattern):
        found = re.findall(pattern, block_text, re.MULTILINE)
        if len(found) != 1:
            raise ValueError('ambiguous official member mapping: ' + pattern)
        return found[0]
    codec = member(map_block, r'^\s+com\.mojang\.serialization\.Codec CODEC -> (\S+)$')
    nbt = member(nbt_block, r'^\s+net\.minecraft\.nbt\.NbtOps INSTANCE -> (\S+)$')
    accessor = member(map_block, r'^\s+(?:\d+:\d+:)?int id\(\) -> (\S+)$')
    return [map_class, codec, nbt_class, nbt, accessor], excerpts


def save(results, manifest_sha256):
    (HERE / 'results.json').write_text(json.dumps({
        'schema': 1, 'observed_on': '2026-11-13', 'manifest_url': URL,
        'manifest_sha256': manifest_sha256,
        'probe_source_sha256': hashlib.sha256((HERE / 'MapCodecProbe.java').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'java_version': subprocess.check_output([str(JAVA / 'java'), '-version'], stderr=subprocess.STDOUT, text=True).splitlines()[0],
        'cases': results}, indent=2) + '\n')


manifest_raw = fetch(URL)
manifest = json.loads(manifest_raw)
entries = {entry['id']: entry for entry in manifest['versions']}
results = {}
with tempfile.TemporaryDirectory(prefix='tprm-codec-sweep-') as temp:
    temp = Path(temp)
    for version in VERSIONS:
        try:
            entry = entries[version]
            metadata_raw = checked(entry)
            metadata = json.loads(metadata_raw)
            if metadata['id'] != version:
                raise ValueError('metadata version mismatch')
            (HERE / (version + '-metadata.json')).write_bytes(metadata_raw)
            libraries, verified, missing, dfu = [], {}, [], None
            for library in metadata['libraries']:
                artifact = library.get('downloads', {}).get('artifact')
                if not artifact:
                    continue
                path = LIBRARIES / artifact['path']
                if not path.is_file():
                    missing.append(artifact['path'])
                    continue
                raw = path.read_bytes()
                if len(raw) != artifact['size'] or sha1(raw) != artifact['sha1']:
                    raise ValueError('cached library identity mismatch: ' + str(path))
                libraries.append(str(path))
                verified[artifact['path']] = artifact['sha1']
                if library['name'].startswith('com.mojang:datafixerupper:'):
                    dfu = (library['name'], path, artifact['sha1'])
            if not dfu:
                raise ValueError('missing metadata-selected DataFixerUpper artifact')
            mapping_spec = metadata['downloads'].get('client_mappings')
            if mapping_spec:
                names, excerpts = mapping_names(checked(mapping_spec))
                mapping = {'url': mapping_spec['url'], 'sha1': mapping_spec['sha1'], 'excerpts': excerpts}
            else:
                names = ['net.minecraft.world.level.saveddata.maps.MapId', 'CODEC',
                         'net.minecraft.nbt.NbtOps', 'INSTANCE', 'id']
                mapping = None
            client_spec = metadata['downloads']['client']
            client = temp / 'client.jar'
            client.write_bytes(checked(client_spec))
            subprocess.run([str(JAVA / 'javac'), '-cp', str(dfu[1]), '-d', str(temp),
                            str(HERE / 'MapCodecProbe.java')], check=True, capture_output=True, text=True)
            result = subprocess.run([str(JAVA / 'java'), '-cp', ':'.join([str(temp), str(client), *libraries]),
                                     'tech.rolly.probe.MapCodecProbe', *names],
                                    capture_output=True, text=True, check=True)
            output = result.stdout.splitlines()
            if len(output) != 6:
                raise ValueError('unexpected probe output: ' + result.stdout)
            results[version] = {'status': 'complete', 'metadata_url': entry['url'], 'metadata_sha1': entry['sha1'],
                                'client_url': client_spec['url'], 'client_sha1': client_spec['sha1'],
                                'datafixerupper': dfu[0], 'datafixerupper_sha1': dfu[2],
                                'verified_library_artifacts': verified, 'unavailable_library_artifacts': missing,
                                'official_mapping': mapping, 'probe_arguments': names, 'output': output,
                                'stderr': result.stderr.splitlines()}
            print(version, ' '.join(output), flush=True)
        except Exception as exc:
            details = (exc.stderr or '')[-3000:] if isinstance(exc, subprocess.CalledProcessError) else str(exc)
            results[version] = {'status': 'failed', 'error': details}
            print(version, 'FAILED', details, flush=True)
        finally:
            client = temp / 'client.jar'
            if client.exists():
                client.unlink()
            save(results, hashlib.sha256(manifest_raw).hexdigest())
if any(case['status'] != 'complete' for case in results.values()):
    raise SystemExit('Some codec probes failed; see results.json')
