#!/usr/bin/env python3
"""Check one remapped candidate JAR against each declared Mojang client.

The check maps intermediary symbols back to each game's official obfuscated
namespace, then resolves class/member references and both Mixin descriptors in
the SHA-1-verified client JARs. It cannot prove Mixin transformation or graphics.
"""
import argparse
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import sys
from urllib.request import urlopen
from zipfile import ZipFile

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
CALLBACK = 'Lorg/spongepowered/asm/mixin/injection/callback/CallbackInfo;'
MIXIN_ANNOTATION = 'Lorg/spongepowered/asm/mixin/Mixin;'
INJECT_ANNOTATION = 'Lorg/spongepowered/asm/mixin/injection/Inject;'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def get(url):
    require(url.startswith('https://'), 'expected HTTPS')
    with urlopen(url, timeout=120) as response:
        return response.read()


def checked(data, sha1, size=None):
    require(hashlib.sha1(data).hexdigest() == sha1, 'SHA-1 mismatch')
    require(size is None or len(data) == size, 'size mismatch')
    return data


def read_class(data):
    source = io.BytesIO(data)
    def num(fmt):
        size = struct.calcsize(fmt)
        raw = source.read(size)
        require(len(raw) == size, 'truncated class file')
        result = struct.unpack(fmt, raw)
        return result[0] if len(result) == 1 else result
    require(num('>I') == 0xCAFEBABE, 'invalid class file')
    num('>HH')
    cp = [None] * num('>H')
    i = 1
    while i < len(cp):
        tag = num('>B')
        if tag == 1:
            cp[i] = (tag, source.read(num('>H')).decode('utf-8', errors='replace'))
        elif tag in (3, 4):
            cp[i] = (tag, num('>I'))
        elif tag in (5, 6):
            source.read(8); cp[i] = (tag,); i += 1
        elif tag in (7, 8, 16, 19, 20):
            cp[i] = (tag, num('>H'))
        elif tag in (9, 10, 11, 12, 17, 18):
            cp[i] = (tag, *num('>HH'))
        elif tag == 15:
            cp[i] = (tag, *num('>BH'))
        else:
            raise ValueError(f'unknown constant pool tag {tag}')
        i += 1
    def text(index):
        return cp[index][1]
    def name(index):
        return text(cp[index][1]) if index else None
    def annotation():
        kind = text(num('>H'))
        values = {}
        for _ in range(num('>H')):
            key = text(num('>H'))
            values[key] = element()
        return kind, values
    def element():
        tag = chr(num('>B'))
        if tag in 'BCDFIJSZs':
            return text(num('>H'))
        if tag == 'c':
            return text(num('>H'))
        if tag == 'e':
            return (text(num('>H')), text(num('>H')))
        if tag == '@':
            return annotation()
        if tag == '[':
            return [element() for _ in range(num('>H'))]
        raise ValueError(f'unknown annotation value tag {tag}')
    def attributes():
        found = {}
        for _ in range(num('>H')):
            attr = text(num('>H')); length = num('>I'); end = source.tell() + length
            if attr in ('RuntimeVisibleAnnotations', 'RuntimeInvisibleAnnotations'):
                for _ in range(num('>H')):
                    kind, values = annotation(); found[kind] = values
                require(source.tell() == end, 'malformed annotations')
            else:
                source.seek(end)
        return found
    _, own, parent, count = num('>HHHH')
    interfaces = [name(num('>H')) for _ in range(count)]
    members = []
    for kind in ('field', 'method'):
        for _ in range(num('>H')):
            access, member, desc = num('>HHH')
            members.append({'kind': kind, 'name': text(member), 'descriptor': text(desc),
                            'access': access, 'annotations': attributes()})
    annotations = attributes()
    refs = []
    for item in cp:
        if item and item[0] in (9, 10, 11):
            _, owner, nt = item; _, member, descriptor = cp[nt]
            refs.append(('field' if item[0] == 9 else 'method', name(owner), text(member), text(descriptor)))
    classes = {name(i) for i, item in enumerate(cp) if item and item[0] == 7}
    return {'name': name(own), 'super': name(parent), 'interfaces': interfaces, 'members': members,
            'refs': refs, 'classes': classes, 'annotations': annotations}


def intermediary_mapping(data):
    with ZipFile(io.BytesIO(data)) as jar:
        lines = jar.read('mappings/mappings.tiny').decode('utf-8').splitlines()
    require(lines[0] == 'tiny\t2\t0\tofficial\tintermediary', 'unexpected intermediary mapping format')
    forward, reverse = {}, {}
    for line in lines[1:]:
        if line.startswith('c\t'):
            _, original, mapped = line.split('\t')[:3]
            require(mapped not in reverse, 'duplicate intermediary class')
            forward[original], reverse[mapped] = mapped, original
    def map_descriptor(desc, mapping):
        return re.sub(r'L([^;]+);', lambda m: 'L' + mapping.get(m.group(1), m.group(1)) + ';', desc)
    members = {}
    original = mapped = None
    for line in lines[1:]:
        if line.startswith('c\t'):
            _, original, mapped = line.split('\t')[:3]
        elif line.startswith(('\tm\t', '\tf\t')):
            _, kind, desc, before, after = line.split('\t')[:5]
            key = ('method' if kind == 'm' else 'field', mapped, after, map_descriptor(desc, forward))
            require(key not in members, 'duplicate intermediary member')
            members[key] = before
    return forward, reverse, members


def verify(mod_path, versions=None, clients=None):
    with ZipFile(mod_path) as mod:
        meta = json.loads(mod.read('fabric.mod.json'))
        advertised = meta['depends']['minecraft']
        require(advertised == ['1.21.4', '1.21.5', '1.21.6', '1.21.7', '1.21.8'], 'unexpected Minecraft dependency list')
        versions = versions or advertised
        config = json.loads(mod.read('thirdpersonreadablemaps.mixins.json'))
        require(config['required'] is True and config['injectors']['defaultRequire'] == 1, 'Mixins must be required')
        require(config['client'] == ['ArmedEntityRenderStateMixin', 'ReadableMapLayerMixin'], 'unexpected Mixins')
        prefix = config['package'].replace('.', '/') + '/'
        mod_classes = {node['name']: node for node in (read_class(mod.read(path)) for path in mod.namelist() if path.endswith('.class'))}
        injections = []
        for mixin_name in config['client']:
            node = mod_classes[prefix + mixin_name]
            target = node['annotations'][MIXIN_ANNOTATION]['value']
            require(len(target) == 1 and target[0].startswith('L') and target[0].endswith(';'), 'unexpected Mixin target')
            target = target[0][1:-1]
            handlers = [x for x in node['members'] if INJECT_ANNOTATION in x['annotations']]
            require(len(handlers) == 1, 'expected one injection per Mixin')
            handler = handlers[0]
            methods = handler['annotations'][INJECT_ANNOTATION]['method']
            require(len(methods) == 1 and handler['descriptor'].endswith(CALLBACK + ')V'), 'unexpected injection descriptor')
            injections.append((target, methods[0], handler['descriptor'][:-len(CALLBACK + ')V')] + ')V', handler['access']))
    manifest = json.loads(get(MANIFEST))
    for version in versions:
        found = [x for x in manifest['versions'] if x['id'] == version and x['type'] == 'release']
        require(len(found) == 1, f'{version}: no unique stable release')
        entry = found[0]
        metadata = json.loads(checked(get(entry['url']), entry['sha1']))
        client = metadata['downloads']['client']
        data = (Path(clients) / (version + '.jar')).read_bytes() if clients else get(client['url'])
        checked(data, client['sha1'], client['size'])
        map_url = f'https://maven.fabricmc.net/net/fabricmc/intermediary/{version}/intermediary-{version}-v2.jar'
        mapping_data = get(map_url)
        sha1 = get(map_url + '.sha1').decode('ascii').strip().split()[0]
        forward, reverse, mapped_members = intermediary_mapping(checked(mapping_data, sha1))
        def to_original(desc):
            def convert(m):
                owner = m.group(1)
                require(not owner.startswith('net/minecraft/class_') or owner in reverse,
                        f'{version}: missing intermediary class {owner}')
                return 'L' + reverse.get(owner, owner) + ';'
            return re.sub(r'L([^;]+);', convert, desc)
        with ZipFile(io.BytesIO(data)) as game:
            @lru_cache(None)
            def game_class(original):
                try:
                    return read_class(game.read(original + '.class'))
                except KeyError:
                    return None
            def resolve(kind, owner, member, desc, seen=None):
                seen = seen or set()
                if owner in seen:
                    return False
                seen.add(owner)
                if owner in mod_classes:
                    node = mod_classes[owner]
                    if any((m['kind'], m['name'], m['descriptor']) == (kind, member, desc) for m in node['members']):
                        return True
                    return any(resolve(kind, ancestor, member, desc, seen) for ancestor in [node['super']] + node['interfaces'] if ancestor)
                original = reverse.get(owner, owner)
                node = game_class(original)
                if node is None:
                    return False
                mapped_name = mapped_members.get((kind, owner, member, desc))
                if mapped_name is None and not (member.startswith('method_') or member.startswith('field_')):
                    mapped_name = member
                original_desc = to_original(desc)
                if mapped_name is not None and any((m['kind'], m['name'], m['descriptor']) == (kind, mapped_name, original_desc) for m in node['members']):
                    return True
                if member in ('<init>', '<clinit>'):
                    return False
                return any(resolve(kind, forward.get(ancestor, ancestor), member, desc, seen)
                           for ancestor in [node['super']] + node['interfaces'] if ancestor)
            for target, name, desc, access in injections:
                require(target in reverse, f'{version}: missing Mixin target {target}')
                node = game_class(reverse[target]); original_name = mapped_members.get(('method', target, name, desc))
                require(node and original_name and any(m['kind'] == 'method' and m['name'] == original_name and
                        m['descriptor'] == to_original(desc) and (m['access'] & 8) == (access & 8) for m in node['members']),
                        f'{version}: missing Mixin target {target}.{name}{desc}')
            refs, classes = set(), set()
            for node in mod_classes.values():
                for ref in node['refs']:
                    if ref[1].startswith(('net/minecraft/', 'com/mojang/blaze3d/')) or (
                            ref[1] in mod_classes and ref[2].startswith(('method_', 'field_'))):
                        refs.add(ref)
                classes.update(c for c in node['classes'] if c.startswith(('net/minecraft/', 'com/mojang/blaze3d/')))
                for member in node['members']:
                    classes.update(x for x in re.findall(r'L([^;]+);', member['descriptor']) if x.startswith(('net/minecraft/', 'com/mojang/blaze3d/')))
            missing_classes = [c for c in sorted(classes) if not game_class(reverse.get(c, c))]
            require(not missing_classes, f'{version}: missing classes: {missing_classes}')
            missing = [ref for ref in sorted(refs) if not resolve(*ref)]
            require(not missing, f'{version}: missing game members: {missing}')
        libraries = [x for x in metadata['libraries'] if x['name'].startswith('org.joml:joml:')]
        require(len(libraries) == 1 and libraries[0]['name'] == 'org.joml:joml:1.10.8',
                f'{version}: unexpected JOML version')
        artifact = libraries[0]['downloads']['artifact']
        joml = checked(get(artifact['url']), artifact['sha1'], artifact['size'])
        joml_refs = {ref for node in mod_classes.values() for ref in node['refs'] if ref[1].startswith('org/joml/')}
        with ZipFile(io.BytesIO(joml)) as lib:
            @lru_cache(None)
            def joml_class(owner):
                try:
                    return read_class(lib.read(owner + '.class'))
                except KeyError:
                    return None
            def resolve_joml(kind, owner, member, descriptor, seen=None):
                seen = seen or set()
                if owner in seen:
                    return False
                seen.add(owner)
                node = joml_class(owner)
                if not node:
                    return False
                if any((m['kind'], m['name'], m['descriptor']) == (kind, member, descriptor) for m in node['members']):
                    return True
                if member in ('<init>', '<clinit>'):
                    return False
                return any(resolve_joml(kind, ancestor, member, descriptor, seen)
                           for ancestor in [node['super']] + node['interfaces'] if ancestor)
            missing_joml = [ref for ref in sorted(joml_refs) if not resolve_joml(*ref)]
            require(not missing_joml, f'{version}: missing JOML members: {missing_joml}')
        print(f'{version}: {len(injections)} Mixin descriptors, {len(classes)} classes, {len(refs)} game and {len(joml_refs)} JOML references verified')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', required=True)
    parser.add_argument('--client-jars-dir')
    parser.add_argument('--versions', nargs='+', help='diagnostic versions; does not change advertised metadata')
    args = parser.parse_args()
    try:
        path = Path(args.jar)
        if path.is_dir():
            jars = list(path.glob('*-mc1.21.4-1.21.8.jar'))
            require(len(jars) == 1, 'expected exactly one candidate JAR')
            path = jars[0]
        verify(path, args.versions, args.client_jars_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'API compatibility check failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
