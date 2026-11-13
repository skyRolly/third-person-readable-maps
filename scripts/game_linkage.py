"""Adapter from intermediary-named mod references to a verified game JAR."""
from functools import lru_cache
import re
import jvm_linkage as jvm


def validate_mixin_semantics(mod_nodes, mixin_targets):
    prefix = 'Lorg/spongepowered/asm/mixin/'
    allowed_class = {prefix + 'Mixin;'}
    allowed_member = {prefix + 'Unique;', prefix + 'injection/Inject;'}
    at_type = prefix + 'injection/At;'
    for name in mixin_targets:
        node = mod_nodes[name]
        unknown = {a for a in node['annotations'] if a.startswith(prefix)} - allowed_class
        jvm.require(not unknown, name + ': unsupported Mixin class annotations: ' + str(sorted(unknown)))
        for member in node['members']:
            annotations = member['annotations']
            unknown = {a for a in annotations if a.startswith(prefix)} - allowed_member
            jvm.require(not unknown, name + ': unsupported Mixin member annotations: ' + str(sorted(unknown)))
            inject = annotations.get(prefix + 'injection/Inject;')
            if inject is not None:
                jvm.require(inject.get('at') in ([(at_type, {'value': 'HEAD'})],
                                                 [(at_type, {'value': 'TAIL'})]),
                            name + ': unsupported injection point; verify it explicitly')


def verify_game_instructions(mod_nodes, mixin_targets, game, forward, reverse, mapped_members, version):
    validate_mixin_semantics(mod_nodes, mixin_targets)
    original_members = {}
    for (kind, owner, mapped, desc), original in mapped_members.items():
        key = (kind, owner, original, desc)
        jvm.require(key not in original_members, version + ': ambiguous mapped member')
        original_members[key] = mapped

    def mapped_descriptor(desc):
        return re.sub(r'L([^;]+);', lambda m: 'L' + forward.get(m.group(1), m.group(1)) + ';', desc)

    @lru_cache(None)
    def lookup(name):
        if name in mod_nodes:
            return mod_nodes[name]
        original = reverse.get(name, name)
        try:
            node = jvm.parse(game.read(original + '.class'), include_code=False)
        except KeyError:
            return None
        node['name'] = forward.get(node['name'], node['name'])
        node['super'] = forward.get(node['super'], node['super'])
        node['interfaces'] = [forward.get(i, i) for i in node['interfaces']]
        for member in node['members']:
            member['descriptor'] = mapped_descriptor(member['descriptor'])
            key = (member['kind'], node['name'], member['name'], member['descriptor'])
            member['name'] = original_members.get(key, member['name'])
        return node

    classes = {c for node in mod_nodes.values() for c in node['classes']
               if c.startswith(('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/'))}
    missing_classes = sorted(c for c in classes if lookup(c) is None)
    jvm.require(not missing_classes, f'{version}: missing game or descriptor classes: {missing_classes}')
    verified = set()
    for name, node in mod_nodes.items():
        caller = mixin_targets.get(name, name)
        for use in node.get('class_uses', []):
            target = jvm.class_use_name(use['name'])
            if target and target.startswith(('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/')):
                try:
                    jvm.validate_class_use(use, caller, lookup)
                except ValueError as exc:
                    raise ValueError(version + ': ' + str(exc) + ' from ' + name) from exc
        for use in node['uses']:
            owner = use['owner']
            inherited_mod_member = owner in mod_nodes and not any(
                (member['kind'], member['name'], member['descriptor']) ==
                (use['kind'], use['name'], use['descriptor']) for member in mod_nodes[owner]['members'])
            if not (owner.startswith(('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/')) or
                    inherited_mod_member):
                continue
            # A reference to a Mixin's inherited game member is rewritten to
            # the target class when Mixin merges that code into the target.
            if owner in mixin_targets:
                use = dict(use, owner=mixin_targets[owner])
            try:
                jvm.validate_use(use, caller, lookup)
            except ValueError as exc:
                raise ValueError(version + ': ' + str(exc) + ' from ' + name) from exc
            verified.add((use['operation'], use['owner'], use['name'], use['descriptor']))
    return len(verified)


def verify_library_instructions(mod_nodes, mixin_targets, library, prefix, version, excluded=()):
    """Validate consumed members of one hash-verified runtime library."""
    @lru_cache(None)
    def lookup(name):
        if name in mod_nodes:
            return mod_nodes[name]
        try:
            return jvm.parse(library.read(name + '.class'), include_code=False)
        except KeyError:
            return None

    classes = {c for node in mod_nodes.values() for c in node['classes']
               if c.startswith(prefix) and not c.startswith(excluded)}
    for name in sorted(classes):
        node = lookup(name)
        jvm.require(node is not None, f'{version}: missing dependency class {name}')
        jvm.require(node['access'] & 1, f'{version}: inaccessible dependency class {name}')
    verified = set()
    for name, node in mod_nodes.items():
        caller = mixin_targets.get(name, name)
        for use in node.get('class_uses', []):
            target = jvm.class_use_name(use['name'])
            if target and target.startswith(prefix) and not target.startswith(excluded):
                try:
                    jvm.validate_class_use(use, caller, lookup)
                except ValueError as exc:
                    raise ValueError(version + ': ' + str(exc) + ' from ' + name) from exc
        for use in node['uses']:
            if not use['owner'].startswith(prefix) or use['owner'].startswith(excluded):
                continue
            try:
                jvm.validate_use(use, caller, lookup)
            except ValueError as exc:
                raise ValueError(version + ': ' + str(exc) + ' from ' + name) from exc
            verified.add((use['operation'], use['owner'], use['name'], use['descriptor']))
    return len(verified)


def verify_declared_libraries(metadata, mod_nodes, mixin_targets, fetch_checked, version):
    """Verify used game-provided library classes against metadata-pinned JARs.

    Java platform APIs are constrained by the branch's --release build; the
    sole Mixin callback class is supplied by the pinned Fabric Loader runtime.
    Unexpected external namespaces fail instead of being silently skipped.
    """
    from io import BytesIO
    from zipfile import ZipFile

    own = set(mod_nodes)
    names = {n for node in mod_nodes.values() for n in node['classes']}
    names.update(use['owner'] for node in mod_nodes.values() for use in node['uses'])
    game = ('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/')
    platform = ('java/', 'javax/')
    callback = {'org/spongepowered/asm/mixin/injection/callback/CallbackInfo'}
    prefixes = {
        'org/joml/': ('org.joml', 'joml'),
        'org/lwjgl/opengl/': ('org.lwjgl', 'lwjgl-opengl'),
        'org/lwjgl/': ('org.lwjgl', 'lwjgl'),
    }
    unknown = sorted(n for n in names if n not in own and n not in callback and
                     not n.startswith(game + platform + tuple(prefixes)))
    jvm.require(not unknown, f'{version}: unclassified external classes: {unknown}')
    used = []
    for prefix, coordinate in prefixes.items():
        selected = {n for n in names if n.startswith(prefix) and
                    not (prefix == 'org/lwjgl/' and n.startswith('org/lwjgl/opengl/'))}
        if not selected:
            continue
        artifacts = {}
        for entry in metadata.get('libraries', []):
            parts = entry.get('name', '').split(':')
            if tuple(parts[:2]) == coordinate and len(parts) == 3:
                artifact = entry.get('downloads', {}).get('artifact')
                if artifact:
                    key = (artifact['url'], artifact['sha1'], artifact['size'])
                    artifacts[key] = artifact
        jvm.require(artifacts, f'{version}: no declared library for {prefix}')
        for artifact in artifacts.values():
            with ZipFile(BytesIO(fetch_checked(artifact))) as archive:
                excluded = ('org/lwjgl/opengl/',) if prefix == 'org/lwjgl/' else ()
                count = verify_library_instructions(mod_nodes, mixin_targets, archive, prefix, version, excluded)
                used.append((prefix, count, artifact['sha1']))
    return used
