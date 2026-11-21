"""Run MapCodecProbe on exact local game and metadata-selected libraries."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
LIBRARIES = Path('/workspace/.minecraft-test/libraries')
JAVA = Path('/workspace/.toolchains/jdk25/bin')
CASES = [
    ('1.21.11', HERE / '1.21.11-metadata.json',
     Path('/workspace/.cloud-env/third-person-readable-maps/gradle-home/caches/fabric-loom/1.21.11/minecraft-client.jar'),
     ['fmu', 'a', 'vn', 'a', 'b']),
    ('26.1.2', HERE / '26.1.2-metadata.json',
     Path('/tmp/tprm-codec-26.1.2-client.jar'),
     ['net.minecraft.world.level.saveddata.maps.MapId', 'CODEC', 'net.minecraft.nbt.NbtOps', 'INSTANCE', 'id']),
]


def digest(data):
    return hashlib.sha1(data).hexdigest()


with urlopen('https://piston-meta.mojang.com/mc/game/version_manifest_v2.json', timeout=60) as response:
    version_manifest = json.load(response)
results = {}
with tempfile.TemporaryDirectory(prefix='tprm-map-codec-') as temp:
    for version, metadata_file, client, names in CASES:
        metadata_bytes = metadata_file.read_bytes()
        metadata = json.loads(metadata_bytes)
        manifest_entry = next(entry for entry in version_manifest['versions'] if entry['id'] == version)
        assert digest(metadata_bytes) == manifest_entry['sha1'] and metadata['id'] == version
        client_spec = metadata['downloads']['client']
        assert digest(client.read_bytes()) == client_spec['sha1'] and client.stat().st_size == client_spec['size']
        libraries, verified, missing, dfu = [], {}, [], None
        for library in metadata['libraries']:
            artifact = library.get('downloads', {}).get('artifact')
            if not artifact:
                continue
            path = LIBRARIES / artifact['path']
            if not path.is_file():
                missing.append(artifact['path'])
                continue
            assert path.stat().st_size == artifact['size'] and digest(path.read_bytes()) == artifact['sha1'], str(path)
            libraries.append(str(path))
            verified[artifact['path']] = artifact['sha1']
            if library['name'].startswith('com.mojang:datafixerupper:'):
                dfu = (library['name'], path, artifact['sha1'])
        assert dfu
        mapping = None
        if version == '1.21.11':
            mapping_spec = metadata['downloads']['client_mappings']
            with urlopen(mapping_spec['url'], timeout=60) as response:
                mapping_bytes = response.read()
            assert digest(mapping_bytes) == mapping_spec['sha1'] and len(mapping_bytes) == mapping_spec['size']
            mapping_lines = [line for line in mapping_bytes.decode().splitlines()
                             if line.startswith(('net.minecraft.world.level.saveddata.maps.MapId -> ',
                                                 'net.minecraft.nbt.NbtOps -> '))]
            assert mapping_lines == ['net.minecraft.nbt.NbtOps -> vn:',
                                     'net.minecraft.world.level.saveddata.maps.MapId -> fmu:']
            mapping = {'url': mapping_spec['url'], 'sha1': mapping_spec['sha1'], 'classes': mapping_lines}
        subprocess.run([str(JAVA / 'javac'), '-cp', str(dfu[1]), '-d', temp, str(HERE / 'MapCodecProbe.java')], check=True)
        classpath = ':'.join([temp, str(client), *libraries])
        output = subprocess.check_output([str(JAVA / 'java'), '-cp', classpath, 'tech.rolly.probe.MapCodecProbe', *names], text=True)
        results[version] = {'metadata_url': manifest_entry['url'], 'metadata_sha1': digest(metadata_bytes),
                            'client_url': client_spec['url'], 'client_sha1': client_spec['sha1'],
                            'datafixerupper': dfu[0], 'datafixerupper_sha1': dfu[2],
                            'verified_library_artifacts': verified,
                            'unavailable_library_artifacts': missing, 'official_mapping': mapping,
                            'output': output.splitlines()}
(HERE / 'results.json').write_text(json.dumps({'observed_on': '2026-11-12',
        'probe_source_sha256': hashlib.sha256((HERE / 'MapCodecProbe.java').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'java_version': subprocess.check_output([str(JAVA / 'java'), '-version'], stderr=subprocess.STDOUT, text=True).splitlines()[0],
        'cases': results}, indent=2) + '\n')
print(json.dumps(results, indent=2))
