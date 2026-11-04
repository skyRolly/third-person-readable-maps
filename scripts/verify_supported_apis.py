#!/usr/bin/env python3
"""Check the packaged mod's Mixin target and game member references per version.

Downloads Mojang's official client JARs (or accepts predownloaded copies),
checks their manifest SHA-1s, and inspects class files without executing them.
This detects linkage errors; it is not a substitute for gameplay tests.
"""
import argparse
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
from urllib.request import urlopen
from zipfile import ZipFile

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
MIXIN = 'tech/rolly/thirdpersonreadablemaps/mixin/ReadableMapLayerMixin.class'
TARGET = 'net/minecraft/client/renderer/entity/layers/ItemInHandLayer'
CALLBACK = 'Lorg/spongepowered/asm/mixin/injection/callback/CallbackInfo;'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def get(url):
    require(url.startswith('https://'), 'Mojang metadata must use HTTPS')
    with urlopen(url, timeout=60) as response:
        return response.read()


def checked(data, expected, label):
    require(hashlib.sha1(data).hexdigest() == expected, f'{label}: Mojang SHA-1 mismatch')
    return data


def parse_class(data):
    source = io.BytesIO(data)
    def number(fmt):
        size = struct.calcsize(fmt)
        value = source.read(size)
        require(len(value) == size, 'truncated class file')
        unpacked = struct.unpack(fmt, value)
        return unpacked[0] if len(unpacked) == 1 else unpacked
    require(number('>I') == 0xcafebabe, 'invalid class file')
    number('>HH')
    pool = [None] * number('>H')
    i = 1
    while i < len(pool):
        tag = number('>B')
        if tag == 1:
            pool[i] = (tag, source.read(number('>H')).decode('utf-8', errors='replace'))
        elif tag in (3, 4):
            source.read(4); pool[i] = (tag,)
        elif tag in (5, 6):
            source.read(8); pool[i] = (tag,); i += 1
        elif tag in (7, 8, 16, 19, 20):
            pool[i] = (tag, number('>H'))
        elif tag in (9, 10, 11, 12, 17, 18):
            pool[i] = (tag, *number('>HH'))
        elif tag == 15:
            pool[i] = (tag, *number('>BH'))
        else:
            raise ValueError(f'unknown constant-pool tag {tag}')
        i += 1
    def text(index):
        return pool[index][1]
    def name(index):
        return text(pool[index][1]) if index else None
    refs = []
    for item in pool:
        if item and item[0] in (9, 10, 11):
            _, owner, nt = item
            _, member, descriptor = pool[nt]
            refs.append(('field' if item[0] == 9 else 'method', name(owner), text(member), text(descriptor)))
    _, this, parent, count = number('>HHHH')
    interfaces = [name(number('>H')) for _ in range(count)]
    members = []
    for kind in ('field', 'method'):
        for _ in range(number('>H')):
            _, member, descriptor, attributes = number('>HHHH')
            members.append((kind, text(member), text(descriptor)))
            for _ in range(attributes):
                number('>H')
                source.seek(number('>I'), 1)
    return {'name': name(this), 'super': name(parent), 'interfaces': interfaces, 'members': set(members), 'refs': refs}


def verify(mod_path, versions, clients):
    with ZipFile(mod_path) as mod:
        metadata = json.loads(mod.read('fabric.mod.json'))
        required = metadata['depends']['minecraft']
        require(isinstance(required, list) and required, 'expected an explicit supported-version list')
        if versions is None:
            versions = required
        mixin = parse_class(mod.read(MIXIN))
        handlers = [x[2] for x in mixin['members'] if x[0] == 'method' and x[1].startswith('thirdpersonreadablemaps$')]
        require(len(handlers) == 1 and handlers[0].endswith(CALLBACK + ')V'), 'unexpected Mixin handler descriptor')
        target_descriptor = handlers[0][:-len(CALLBACK + ')V')] + ')V'
        refs = set()
        for path in mod.namelist():
            if path.endswith('.class'):
                refs.update(ref for ref in parse_class(mod.read(path))['refs']
                            if ref[1].startswith(('net/minecraft/', 'com/mojang/blaze3d/')))
    manifest = json.loads(get(MANIFEST))
    for version in versions:
        items = [x for x in manifest['versions'] if x['type'] == 'release' and x['id'] == version]
        require(len(items) == 1, f'{version}: not a stable release in the Mojang manifest')
        spec = items[0]
        meta = json.loads(checked(get(spec['url']), spec['sha1'], version + ' metadata'))
        client = meta['downloads']['client']
        data = (Path(clients) / (version + '.jar')).read_bytes() if clients else get(client['url'])
        checked(data, client['sha1'], version + ' client')
        require(len(data) == client['size'], f'{version}: client size mismatch')
        with ZipFile(io.BytesIO(data)) as game:
            @lru_cache(None)
            def game_class(owner):
                try:
                    return parse_class(game.read(owner + '.class'))
                except KeyError:
                    return None
            def resolve(kind, owner, member, descriptor, seen=None):
                seen = seen or set()
                if owner in seen:
                    return False
                seen.add(owner)
                node = game_class(owner)
                if node is None:
                    return False
                if (kind, member, descriptor) in node['members']:
                    return True
                if member in ('<init>', '<clinit>'):
                    return False
                return any(resolve(kind, ancestor, member, descriptor, seen)
                           for ancestor in [node['super']] + node['interfaces'] if ancestor)
            target = game_class(TARGET)
            require(target and ('method', 'submitArmWithItem', target_descriptor) in target['members'],
                    f'{version}: Mixin target descriptor is missing')
            missing = [ref for ref in sorted(refs) if not resolve(*ref)]
            require(not missing, f'{version}: missing game references: {missing}')
            print(f'{version}: Mixin target and {len(refs)} game/Blaze3D member references verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', required=True)
    parser.add_argument('--client-jars-dir', help='optional directory of <version>.jar files')
    parser.add_argument('--versions', nargs='+', help='override list for diagnostic negative checks')
    args = parser.parse_args()
    try:
        jar = Path(args.jar)
        if jar.is_dir():
            candidates = list(jar.glob('*-mc26.1-26.2.jar'))
            require(len(candidates) == 1, 'expected exactly one 26.1–26.2 distributable JAR')
            jar = candidates[0]
        verify(jar, args.versions, args.client_jars_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'API compatibility check failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
