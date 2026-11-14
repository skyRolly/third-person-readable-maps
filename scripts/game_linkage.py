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
        mixin = node['annotations'].get(prefix + 'Mixin;')
        if mixin is not None:
            jvm.require(set(mixin) == {'value'}, name + ': unsupported Mixin options')
        for member in node['members']:
            annotations = member['annotations']
            unknown = {a for a in annotations if a.startswith(prefix)} - allowed_member
            jvm.require(not unknown, name + ': unsupported Mixin member annotations: ' + str(sorted(unknown)))
            unique = annotations.get(prefix + 'Unique;')
            jvm.require(unique is None or not unique, name + ': unsupported Unique options')
            inject = annotations.get(prefix + 'injection/Inject;')
            if inject is not None:
                jvm.require(set(inject) <= {'method', 'at', 'cancellable'},
                            name + ': unsupported Inject options: ' + str(sorted(set(inject) - {'method', 'at', 'cancellable'})))
                jvm.require(isinstance(inject.get('method'), list) and len(inject['method']) == 1 and
                            isinstance(inject['method'][0], str) and inject['method'][0],
                            name + ': expected exactly one injection target')
                jvm.require('cancellable' not in inject or inject['cancellable'] in (0, 1),
                            name + ': invalid cancellable flag')
                jvm.require(inject.get('at') in ([(at_type, {'value': 'HEAD'})],
                                                 [(at_type, {'value': 'TAIL'})]),
                            name + ': unsupported injection point; verify it explicitly')


def make_class_lookup(mod_nodes, game, forward, reverse, mapped_members, version, library_lookup=None):
    """Resolve a symbolic owner across candidate, mapped game and pinned libraries."""
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
        # Runtime libraries retain their own namespace and are never remapped.
        if name.startswith(('org/joml/', 'org/lwjgl/')):
            return library_lookup(name) if library_lookup else None
        original = reverse.get(name, name)
        try:
            node = jvm.parse(game.read(original + '.class'), include_code=False)
        except KeyError:
            return library_lookup(name) if library_lookup else None
        node['name'] = forward.get(node['name'], node['name'])
        node['super'] = forward.get(node['super'], node['super'])
        node['interfaces'] = [forward.get(i, i) for i in node['interfaces']]
        for member in node['members']:
            member['descriptor'] = mapped_descriptor(member['descriptor'])
            key = (member['kind'], node['name'], member['name'], member['descriptor'])
            member['name'] = original_members.get(key, member['name'])
        return node
    return lookup


def verify_game_instructions(mod_nodes, mixin_targets, game, forward, reverse, mapped_members, version,
                             class_lookup=None):
    validate_mixin_semantics(mod_nodes, mixin_targets)
    lookup = class_lookup or make_class_lookup(mod_nodes, game, forward, reverse, mapped_members, version)
    lambda_descriptor = ('(Ljava/lang/invoke/MethodHandles$Lookup;Ljava/lang/String;'
                         'Ljava/lang/invoke/MethodType;Ljava/lang/invoke/MethodType;'
                         'Ljava/lang/invoke/MethodHandle;Ljava/lang/invoke/MethodType;)Ljava/lang/invoke/CallSite;')
    for name, node in mod_nodes.items():
        for site in node.get('dynamic_sites', []):
            jvm.require(site == {'kind':'invoke', 'owner':'java/lang/invoke/LambdaMetafactory',
                                 'name':'metafactory', 'descriptor':lambda_descriptor, 'handle_kind':6,
                                 'argument_tags':[16, 15, 16]},
                        version + ': unsupported dynamic bootstrap from ' + name)

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
            jvm.require(not (use['operation'] == 'invokespecial' and use['name'] != '<init>'),
                        version + ': unsupported non-constructor invokespecial from ' + name)
            owner = use['owner']
            declared_locally = owner in mod_nodes and any(
                (member['kind'], member['name'], member['descriptor']) ==
                (use['kind'], use['name'], use['descriptor']) for member in mod_nodes[owner]['members'])
            if not (owner.startswith(('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/')) or
                    owner in mod_nodes):
                continue
            if owner in mixin_targets:
                jvm.require(name == owner, version + ': unsupported reference to another Mixin from ' + name)
            if declared_locally and owner in mixin_targets:
                target = mixin_targets[owner]
                target_node = lookup(target)
                jvm.require(target_node is not None, version + ': missing Mixin target ' + target)
                match = lambda m: (m['kind'], m['name'], m['descriptor']) == (use['kind'], use['name'], use['descriptor'])
                jvm.require(not any(match(m) for m in target_node['members']),
                            version + ': unsupported Mixin member collision: ' + use['name'])
                # A non-colliding Mixin member is merged into the target.
                overlay = dict(target_node, members=target_node['members'] +
                               [m for m in mod_nodes[owner]['members'] if match(m)])
                rewritten = dict(use, owner=target)
                def merged_lookup(name):
                    return overlay if name == target else lookup(name)
                try:
                    jvm.validate_use(rewritten, caller, merged_lookup)
                except ValueError as exc:
                    raise ValueError(version + ': ' + str(exc) + ' from ' + name) from exc
                verified.add((rewritten['operation'], target, rewritten['name'], rewritten['descriptor']))
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


def verify_library_instructions(mod_nodes, mixin_targets, library, prefix, version, excluded=(), class_lookup=None):
    """Validate consumed members of one hash-verified runtime library."""
    @lru_cache(None)
    def local_lookup(name):
        if name in mod_nodes:
            return mod_nodes[name]
        try:
            return jvm.parse(library.read(name + '.class'), include_code=False)
        except KeyError:
            return None
    lookup = class_lookup or local_lookup

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


LIBRARY_PREFIXES = {
    'org/joml/': ('org.joml', 'joml'),
    'org/lwjgl/opengl/': ('org.lwjgl', 'lwjgl-opengl'),
    'org/lwjgl/': ('org.lwjgl', 'lwjgl'),
}


class RuntimeLibraries:
    """Lazy classpath of uniquely selected, integrity-checked runtime libraries."""
    def __init__(self, metadata, fetch_checked, version):
        self.metadata, self.fetch_checked, self.version = metadata, fetch_checked, version
        self._archives, self._classes = {}, {}

    def archive(self, prefix):
        from io import BytesIO
        from zipfile import ZipFile
        if prefix not in self._archives:
            coordinate = LIBRARY_PREFIXES[prefix]
            artifacts = {}
            for entry in self.metadata.get('libraries', []):
                parts = entry.get('name', '').split(':')
                if tuple(parts[:2]) == coordinate and len(parts) == 3:
                    artifact = entry.get('downloads', {}).get('artifact')
                    if artifact:
                        key = (artifact['url'], artifact['sha1'], artifact['size'])
                        artifacts[key] = artifact
            jvm.require(artifacts, f'{self.version}: no declared library for {prefix}')
            jvm.require(len(artifacts) == 1, f'{self.version}: ambiguous declared libraries for {prefix}')
            artifact = next(iter(artifacts.values()))
            self._archives[prefix] = (ZipFile(BytesIO(self.fetch_checked(artifact))), artifact['sha1'])
        return self._archives[prefix]

    def lookup(self, name):
        if name in self._classes:
            return self._classes[name]
        prefix = next((p for p in LIBRARY_PREFIXES if name.startswith(p)), None)
        if prefix is None:
            return None
        archive, _ = self.archive(prefix)
        path = name + '.class'
        matches = [entry for entry in archive.infolist() if entry.filename == path]
        jvm.require(len(matches) <= 1, f'{self.version}: duplicate library class {name}')
        self._classes[name] = jvm.parse(archive.read(matches[0]), include_code=False) if matches else None
        return self._classes[name]


def verify_declared_libraries(metadata, mod_nodes, mixin_targets, fetch_checked, version,
                              runtime_libraries=None, class_lookup=None):
    """Verify used game-provided library classes against metadata-pinned JARs.

    Java platform APIs are constrained by the branch's --release build; the
    sole Mixin callback class is supplied by the pinned Fabric Loader runtime.
    Unexpected external namespaces fail instead of being silently skipped.
    """
    own = set(mod_nodes)
    names = {n for node in mod_nodes.values() for n in node['classes']}
    names.update(use['owner'] for node in mod_nodes.values() for use in node['uses'])
    game = ('net/minecraft/', 'com/mojang/blaze3d/', 'com/mojang/math/')
    platform = ('java/', 'javax/')
    callback = {'org/spongepowered/asm/mixin/injection/callback/CallbackInfo'}
    prefixes = LIBRARY_PREFIXES
    unknown = sorted(n for n in names if n not in own and n not in callback and
                     not n.startswith(game + platform + tuple(prefixes)))
    jvm.require(not unknown, f'{version}: unclassified external classes: {unknown}')
    used = []
    runtime_libraries = runtime_libraries or RuntimeLibraries(metadata, fetch_checked, version)
    for prefix in prefixes:
        selected = {n for n in names if n.startswith(prefix) and
                    not (prefix == 'org/lwjgl/' and n.startswith('org/lwjgl/opengl/'))}
        if not selected:
            continue
        archive, digest = runtime_libraries.archive(prefix)
        excluded = ('org/lwjgl/opengl/',) if prefix == 'org/lwjgl/' else ()
        count = verify_library_instructions(mod_nodes, mixin_targets, archive, prefix, version, excluded,
                                            class_lookup=class_lookup)
        used.append((prefix, count, digest))
    return used
