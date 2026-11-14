"""Read actual JVM member-use instructions for compatibility verification.

The class-file reader rejects malformed bytecode instead of treating a constant
pool entry alone as proof of an invocation. Namespace adapters supply resolved
class metadata in the same namespace as the caller.
"""
import io
import re
import struct


def require(ok, message):
    if not ok:
        raise ValueError(message)


class Reader:
    def __init__(self, data):
        self.buf = io.BytesIO(data)

    def read(self, n):
        data = self.buf.read(n)
        require(len(data) == n, 'truncated class file')
        return data

    def u1(self): return self.read(1)[0]
    def u2(self): return struct.unpack('>H', self.read(2))[0]
    def u4(self): return struct.unpack('>I', self.read(4))[0]


MEMBER_OPS = {178: 'getstatic', 179: 'putstatic', 180: 'getfield', 181: 'putfield',
              182: 'invokevirtual', 183: 'invokespecial', 184: 'invokestatic', 185: 'invokeinterface'}
HANDLE_OPS = {1: 'getfield', 2: 'getstatic', 3: 'putfield', 4: 'putstatic',
              5: 'invokevirtual', 6: 'invokestatic', 7: 'invokespecial',
              8: 'newinvokespecial', 9: 'invokeinterface'}
CLASS_OPS = {187: 'new', 189: 'anewarray', 192: 'checkcast',
             193: 'instanceof', 197: 'multianewarray'}
LENGTHS = [1] * 202
for _op in (16, 18, 21, 22, 23, 24, 25, 54, 55, 56, 57, 58, 169, 188): LENGTHS[_op] = 2
for _op in (17, 19, 20, 132, *range(153, 169), *range(178, 185), 187, 189, 192, 193, 198, 199): LENGTHS[_op] = 3
for _op in (185, 186, 200, 201): LENGTHS[_op] = 5
LENGTHS[197] = 4


def instructions(code):
    pc = 0
    while pc < len(code):
        start = pc
        op = code[pc]
        require(op < len(LENGTHS), f'reserved bytecode opcode {op}')
        if op in (170, 171):
            pos = pc + 1 + (-(pc + 1) % 4)
            require(pos + (12 if op == 170 else 8) <= len(code), 'truncated switch')
            if op == 170:
                low, high = struct.unpack_from('>ii', code, pos + 4)
                require(high >= low and high - low < len(code), 'invalid tableswitch')
                pc = pos + 12 + 4 * (high - low + 1)
            else:
                count = struct.unpack_from('>i', code, pos + 4)[0]
                require(0 <= count < len(code), 'invalid lookupswitch')
                pc = pos + 8 + 8 * count
        elif op == 196:
            require(pc + 2 <= len(code), 'truncated wide instruction')
            nested = code[pc + 1]
            require(nested in (21, 22, 23, 24, 25, 54, 55, 56, 57, 58, 132, 169), 'invalid wide opcode')
            pc += 6 if nested == 132 else 4
        else:
            pc += LENGTHS[op]
        require(pc <= len(code), 'truncated bytecode instruction')
        yield op, code[start + 1:pc]
    require(pc == len(code), 'invalid bytecode length')


def parse(data, include_code=True):
    r = Reader(data)
    require(r.u4() == 0xCAFEBABE, 'invalid class file')
    r.u2(); major = r.u2()
    cp = [None] * r.u2()
    i = 1
    while i < len(cp):
        tag = r.u1()
        if tag == 1: cp[i] = (tag, r.read(r.u2()).decode('utf-8', errors='replace'))
        elif tag in (3, 4): cp[i] = (tag, r.u4())
        elif tag in (5, 6): cp[i] = (tag, r.read(8)); i += 1
        elif tag in (7, 8, 16, 19, 20): cp[i] = (tag, r.u2())
        elif tag in (9, 10, 11, 12, 17, 18): cp[i] = (tag, r.u2(), r.u2())
        elif tag == 15: cp[i] = (tag, r.u1(), r.u2())
        else: raise ValueError(f'unknown constant pool tag {tag}')
        i += 1

    def entry(index, *tags):
        require(0 < index < len(cp) and cp[index] is not None and cp[index][0] in tags,
                f'invalid constant pool reference {index}')
        return cp[index]

    def text(index): return entry(index, 1)[1]
    def class_name(index): return text(entry(index, 7)[1]) if index else None

    def attributes(reader):
        for _ in range(reader.u2()):
            name = text(reader.u2()); payload = reader.read(reader.u4())
            yield name, payload

    def annotations(payload):
        source = Reader(payload)
        def element():
            tag = chr(source.u1())
            if tag in 'BCDFIJSZ': return entry(source.u2(), 3, 4, 5, 6)[1]
            if tag in 'sc': return text(source.u2())
            if tag == 'e': return (text(source.u2()), text(source.u2()))
            if tag == '@': return annotation()
            if tag == '[': return [element() for _ in range(source.u2())]
            raise ValueError('unknown annotation element tag ' + tag)
        def annotation():
            kind = text(source.u2()); values = {}
            for _ in range(source.u2()):
                key = text(source.u2()); values[key] = element()
            return kind, values
        found = dict(annotation() for _ in range(source.u2()))
        require(not source.buf.read(1), 'trailing annotation bytes')
        return found

    access, own, parent = r.u2(), r.u2(), r.u2()
    interfaces = [class_name(r.u2()) for _ in range(r.u2())]
    members, code_blocks = [], []
    for kind in ('field', 'method'):
        for _ in range(r.u2()):
            flags, name, desc = r.u2(), text(r.u2()), text(r.u2())
            member_info = {'kind': kind, 'name': name, 'descriptor': desc, 'access': flags, 'annotations': {}}
            members.append(member_info)
            for attr, payload in attributes(r):
                if attr in ('RuntimeVisibleAnnotations', 'RuntimeInvisibleAnnotations'):
                    member_info['annotations'].update(annotations(payload))
                elif include_code and kind == 'method' and attr == 'Code':
                    c = Reader(payload); c.u2(); c.u2(); code = c.read(c.u4())
                    member_info['has_code'] = bool(code)
                    member_info['return_opcodes'] = []
                    code_blocks.append((member_info, code))
                    c.read(c.u2() * 8)
                    list(attributes(c))
                    require(not c.buf.read(1), 'trailing Code attribute bytes')
    bootstrap, class_annotations = [], {}
    for attr, payload in attributes(r):
        if attr in ('RuntimeVisibleAnnotations', 'RuntimeInvisibleAnnotations'):
            class_annotations.update(annotations(payload))
        elif attr == 'BootstrapMethods':
            b = Reader(payload)
            for _ in range(b.u2()):
                ref = b.u2(); bootstrap.append((ref, [b.u2() for _ in range(b.u2())]))
            require(not b.buf.read(1), 'trailing BootstrapMethods bytes')
    require(not r.buf.read(1), 'trailing class bytes')

    uses, class_uses, dynamic_sites = [], [], []
    def descriptor_class_uses(desc, operation):
        class_uses.extend({'name': name, 'operation': operation}
                          for name in re.findall(r'L([^;]+);', desc))

    def member(index, operation, source_kind, method_info):
        tag, owner, nt = entry(index, 9, 10, 11)
        _, name, desc = entry(nt, 12)
        if source_kind == 'method_handle':
            descriptor_class_uses(text(desc), 'method_handle_descriptor')
        uses.append({'kind': 'field' if tag == 9 else 'method', 'owner': class_name(owner),
                     'name': text(name), 'descriptor': text(desc), 'operation': operation,
                     'reference_tag': tag, 'source_kind': source_kind,
                     'enclosing_method': method_info['name'],
                     'enclosing_descriptor': method_info['descriptor'],
                     'enclosing_access': method_info['access']})

    def constant(index, method_info, seen_constants):
        if index in seen_constants: return
        seen_constants.add(index)
        item = entry(index, *range(1, 21)); tag = item[0]
        if tag == 15:
            require(item[1] in HANDLE_OPS, 'invalid method-handle kind')
            member(item[2], HANDLE_OPS[item[1]], 'method_handle', method_info)
        elif tag == 16:
            descriptor_class_uses(text(item[1]), 'method_type_descriptor')
        elif tag == 7:
            class_uses.append({'name': class_name(index), 'operation': 'class_constant'})
        elif tag in (17, 18):
            require(item[1] < len(bootstrap), 'missing bootstrap method')
            _, _, descriptor = entry(item[2], 12)
            descriptor_class_uses(text(descriptor), 'dynamic_descriptor')
            ref, args = bootstrap[item[1]]
            handle = entry(ref, 15)
            _, owner, name_type = entry(handle[2], 10, 11)
            _, bootstrap_name, bootstrap_descriptor = entry(name_type, 12)
            dynamic_sites.append({'kind': 'constant' if tag == 17 else 'invoke',
                                  'owner': class_name(owner), 'name': text(bootstrap_name),
                                  'descriptor': text(bootstrap_descriptor), 'handle_kind': handle[1],
                                  'argument_tags': [entry(arg, *range(1, 21))[0] for arg in args]})
            constant(ref, method_info, seen_constants)
            for arg in args: constant(arg, method_info, seen_constants)

    for method_info, code in code_blocks:
        for op, operands in instructions(code):
            if 172 <= op <= 177:
                method_info['return_opcodes'].append(op)
            if op in MEMBER_OPS:
                if op == 185:
                    require(operands[2] > 0 and operands[3] == 0, 'invalid invokeinterface operands')
                member(struct.unpack_from('>H', operands)[0], MEMBER_OPS[op], 'instruction', method_info)
            elif op in CLASS_OPS:
                class_uses.append({'name': class_name(struct.unpack_from('>H', operands)[0]),
                                   'operation': CLASS_OPS[op]})
            elif op == 186:
                require(operands[2:] == b'\0\0', 'invalid invokedynamic operands')
                constant(struct.unpack_from('>H', operands)[0], method_info, set())
            elif op in (18, 19, 20):
                index = operands[0] if op == 18 else struct.unpack_from('>H', operands)[0]
                constant(index, method_info, set())
    classes = set()
    def add_type(value):
        if value.startswith('['): classes.update(re.findall(r'L([^;]+);', value))
        else: classes.add(value)
    for item in cp:
        if item and item[0] == 7: add_type(text(item[1]))
        if item and item[0] == 16: classes.update(re.findall(r'L([^;]+);', text(item[1])))
        if item and item[0] == 12: classes.update(re.findall(r'L([^;]+);', text(item[2])))
    for member_info in members:
        classes.update(re.findall(r'L([^;]+);', member_info['descriptor']))
    return {'name': class_name(own), 'super': class_name(parent), 'interfaces': interfaces,
            'access': access, 'major': major, 'members': members, 'uses': uses,
            'class_uses': class_uses, 'classes': classes, 'dynamic_sites': dynamic_sites,
            'annotations': class_annotations}


def class_use_name(name):
    if not name.startswith('['): return name
    element = name.lstrip('[')
    if element.startswith('L') and element.endswith(';'): return element[1:-1]
    require(len(element) == 1 and element in 'ZBCSIJFD', 'invalid array class: ' + name)
    return None


def validate_class_use(use, caller, lookup):
    name = class_use_name(use['name'])
    if name is None: return
    node = lookup(name)
    require(node is not None, 'missing referenced class: ' + name)
    require((node['access'] & 1) or name.rpartition('/')[0] == caller.rpartition('/')[0],
            'inaccessible referenced class: ' + name)
    if use['operation'] == 'new':
        require(not use['name'].startswith('[') and not (node['access'] & (0x0200 | 0x0400)),
                'cannot instantiate interface or abstract class: ' + name)


def is_subclass(child, parent, lookup, seen=None):
    if child == parent: return True
    seen = seen or set()
    if not child or child in seen: return False
    seen.add(child); node = lookup(child)
    if not node: return False
    return any(is_subclass(a, parent, lookup, seen) for a in [node['super']] + node['interfaces'] if a)


def resolve_member(owner, kind, name, descriptor, lookup, seen=None):
    def hierarchy_node(class_name):
        node = lookup(class_name)
        require(node is not None or class_name.startswith(('java/', 'javax/')),
                'missing superclass or interface: ' + class_name)
        return node

    def own(class_name):
        node = lookup(class_name)
        if not node: return None
        found = [m for m in node['members'] if (m['kind'], m['name'], m['descriptor']) == (kind, name, descriptor)]
        require(len(found) <= 1, 'duplicate member')
        return (class_name, node, found[0]) if found else None

    if kind == 'field':
        seen = seen or set()
        if owner in seen: return None
        seen.add(owner); node = lookup(owner)
        if not node: return None
        found = own(owner)
        if found: return found
        for ancestor in node['interfaces'] + [node['super']]:
            if ancestor:
                if hierarchy_node(ancestor) is None:
                    continue  # Java platform linkage is covered by the declared --release target.
                result = resolve_member(ancestor, kind, name, descriptor, lookup, seen)
                if result: return result
        return None

    node = lookup(owner)
    if not node: return None
    found = own(owner)
    if found or name in ('<init>', '<clinit>'): return found
    interfaces, current, visited = [], node, set()
    # Class methods search each superclass before inherited interface methods.
    while current:
        interfaces.extend(current['interfaces'])
        parent = current['super']
        if not parent or parent in visited: break
        visited.add(parent)
        parent_node = hierarchy_node(parent)
        if parent_node is None:
            break
        found = own(parent)
        if found: return found
        current = parent_node
    candidates, seen_interfaces = [], set()
    while interfaces:
        interface = interfaces.pop()
        if interface in seen_interfaces: continue
        seen_interfaces.add(interface); item = hierarchy_node(interface)
        if not item: continue
        found = own(interface)
        # Static and private interface methods are not inherited.
        if found and not (found[2]['access'] & (8 | 2)):
            candidates.append(found)
        interfaces.extend(item['interfaces'])
    maximal = [c for c in candidates if not any(c[0] != d[0] and is_subclass(d[0], c[0], lookup)
                                                for d in candidates)]
    concrete = [c for c in maximal if not (c[2]['access'] & 0x0400)]
    require(len(concrete) <= 1, 'ambiguous inherited default methods')
    return concrete[0] if concrete else (maximal[0] if maximal else None)


def validate_mixin_target(node, name, descriptor, handler_access):
    require(node is not None and any(m['kind'] == 'method' and m['name'] == name and
            m['descriptor'] == descriptor and (m['access'] & 8) == (handler_access & 8)
            for m in node['members']), 'missing Mixin target or staticness mismatch')


def validate_injection_point(node, name, descriptor, point):
    targets = [m for m in node['members'] if m['kind'] == 'method' and
               m['name'] == name and m['descriptor'] == descriptor]
    require(len(targets) == 1 and targets[0].get('has_code'), 'Mixin target has no executable code')
    require(point in ('HEAD', 'TAIL'), 'unsupported Mixin injection point')
    if point == 'TAIL':
        require(177 in targets[0]['return_opcodes'], 'TAIL injection target has no void return')


def validate_use(use, caller, lookup):
    owner, name, desc, kind, op, tag = (use[k] for k in ('owner', 'name', 'descriptor', 'kind', 'operation', 'reference_tag'))
    symbol = f'{owner}.{name}{desc} ({op})'
    node = lookup(owner)
    require(node is not None, 'missing class: ' + owner)
    interface = bool(node['access'] & 0x0200)
    if kind == 'field':
        require(tag == 9 and op in ('getstatic', 'putstatic', 'getfield', 'putfield'), 'invalid field reference: ' + symbol)
    else:
        require(tag in (10, 11) and op in ('invokevirtual', 'invokestatic', 'invokespecial', 'invokeinterface', 'newinvokespecial'),
                'invalid method reference: ' + symbol)
        require((tag == 11) == interface, 'class/interface constant-pool mismatch: ' + symbol)
        require(op != 'invokeinterface' or interface, 'invokeinterface requires interface: ' + symbol)
        require(op != 'invokevirtual' or not interface, 'invokevirtual requires class: ' + symbol)
        require(name != '<clinit>', 'class initializer is not callable: ' + symbol)
        require((name == '<init>') == (op == 'newinvokespecial' or (op == 'invokespecial' and name == '<init>')),
                'invalid constructor invocation: ' + symbol)
        if op == 'newinvokespecial':
            require(not (node['access'] & (0x0200 | 0x0400)),
                    'constructor handle cannot instantiate interface or abstract class: ' + symbol)
        if op == 'invokespecial' and name != '<init>':
            raise ValueError('unsupported non-constructor invokespecial: ' + symbol)
    require((node['access'] & 1) or owner.rpartition('/')[0] == caller.rpartition('/')[0],
            'inaccessible referenced class: ' + symbol)
    resolved = resolve_member(owner, kind, name, desc, lookup)
    require(resolved is not None, 'missing member: ' + symbol)
    declared, _, member = resolved
    flags = member['access']
    static = op in ('getstatic', 'putstatic', 'invokestatic')
    require(bool(flags & 8) == static, 'static/instance mismatch: ' + symbol)
    if kind == 'field' and op in ('putfield', 'putstatic') and flags & 0x0010:
        require(use.get('source_kind') == 'instruction', 'final field setter handle or unknown use: ' + symbol)
        require(caller == declared, 'final field write outside declaring class: ' + symbol)
        method = use.get('enclosing_method')
        descriptor = use.get('enclosing_descriptor', '')
        access = use.get('enclosing_access', 0)
        if op == 'putfield':
            require(method == '<init>' and descriptor.endswith(')V') and not (access & 8),
                    'final instance field write outside constructor: ' + symbol)
        else:
            require(method == '<clinit>' and descriptor == '()V' and access & 8,
                    'final static field write outside class initializer: ' + symbol)
    package = caller.rpartition('/')[0] == declared.rpartition('/')[0]
    if not (flags & 1):
        if flags & 2:
            require(caller == declared, 'inaccessible private member: ' + symbol)
        elif flags & 4:
            require(package or is_subclass(caller, declared, lookup), 'inaccessible protected member: ' + symbol)
            if not package and not static:
                require(use.get('source_kind') == 'method_handle' and op not in ('invokespecial', 'newinvokespecial')
                        and is_subclass(owner, caller, lookup),
                        'unsupported cross-package protected receiver: ' + symbol)
        else:
            require(package, 'inaccessible package-private member: ' + symbol)
    return declared
