"""Inventory exact advisory class references in the 13 proposed mod JARs.

Run from the coordination worktree with the locally built product worktrees
alongside it. This inspects packaged class files; it is not a call-graph or
reflection analysis of Minecraft, the loader, or other installed mods.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT.parent
MANIFEST = ROOT / 'docs/legacy-dry-run-1.0.0/release-manifest.json'
PARSER = WORKSPACE / 'tprm-review-26.3/scripts/jvm_linkage.py'
TARGETS = {
    'GHSA-xxph-c9ww-hj94': ['com/google/common/collect/CompactHashMap', 'com/google/common/collect/CompactHashSet', 'com/google/common/collect/MapMakerInternalMap'],
    'GHSA-558v-64gr-wgg4': ['io/netty/handler/codec/compression/Bzip2Decoder'],
    'GHSA-mj4r-2hfc-f8p6': ['io/netty/handler/codec/compression/Lz4FrameDecoder'],
    'GHSA-3qp7-7mw8-wx86': ['io/netty/handler/ipfilter/IpSubnetFilterRule'],
    'GHSA-c653-97m9-rcg9': ['io/netty/handler/ssl/util/SimpleTrustManagerFactory'],
    'GHSA-x4gw-5cx5-pgmh': ['io/netty/handler/ssl/SslClientHelloHandler'],
    'GHSA-mcr4-qmvw-px4g': ['net/jpountz/util/Native'],
    'GHSA-cmp6-m4wj-q63q': ['net/jpountz/lz4/LZ4Factory'],
    'GHSA-4g8c-wm8x-jfhw': ['io/netty/handler/ssl/SslHandler'],
    'GHSA-78wr-2p64-hpwj': ['org/apache/commons/io/input/XmlStreamReader'],
    'GHSA-vqf4-7m7x-wgfc': ['net/jpountz/lz4/LZ4Factory'],
}

spec = importlib.util.spec_from_file_location('jvm_linkage', PARSER)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
manifest = json.loads(MANIFEST.read_text())
assert manifest['candidate'] and manifest['version'] == '1.0.0' and len(manifest['groups']) == 13
parser_group = next(group for group in manifest['groups'] if group['id'] == '26.3')
results = {}
for group in manifest['groups']:
    name = group['id']
    if name in ('1.21.11', '26.1-26.2', '26.3'):
        repo = WORKSPACE / ('tprm-review-' + name)
    else:
        repo = WORKSPACE / ('tprm-legacy-' + ('1.14' if name == '1.14-1.14.4' else name))
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    jar = repo / 'build/libs' / group['artifact']
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    assert head == group['source_commit'] and digest == group['sha256'], name
    refs, external_field_writes = set(), []
    with zipfile.ZipFile(jar) as artifact:
        classes = [entry for entry in artifact.namelist() if entry.endswith('.class')]
        assert classes, name
        for entry in classes:
            node = parser.parse(artifact.read(entry))
            refs.update(node['classes'])
            external_field_writes.extend({'class': node['name'], **use} for use in node['uses']
                                         if use['operation'] in ('putfield', 'putstatic') and
                                         not use['owner'].startswith('tech/rolly/thirdpersonreadablemaps/'))
    results[name] = {
        'source_commit': head,
        'artifact_sha256': digest,
        'class_files': len(classes),
        'external_field_writes': external_field_writes,
        'direct_class_references': {key: sorted(refs.intersection(names)) for key, names in TARGETS.items()},
    }
out = Path(__file__).with_name('mod-class-reference-inventory.json')
out.write_text(json.dumps({'schema': 1, 'observed_on': '2026-11-12',
                           'parser': {'group': '26.3', 'source_commit': parser_group['source_commit'],
                                      'path': 'scripts/jvm_linkage.py', 'sha256': hashlib.sha256(PARSER.read_bytes()).hexdigest()},
                           'targets': TARGETS, 'groups': results}, indent=2) + '\n')
print('Inventoried', len(results), 'artifact-identified mod JARs; target hits:', sum(len(x) for r in results.values() for x in r['direct_class_references'].values()))
