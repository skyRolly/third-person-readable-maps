"""Focused bounded hierarchy and transformed-owner regression fixtures."""
from pathlib import Path
import io
import shutil
import java_toolchain
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import game_linkage as game
import jvm_linkage as jvm


def node(name, parent='java/lang/Object', interfaces=(), access=1, origin='candidate', permitted=None):
    return {'name':name, 'super':parent, 'interfaces':list(interfaces), 'access':access,
            'origin':origin, 'permitted_subclasses':permitted, 'members':[], 'uses':[],
            'classes':set(), 'class_uses':[], 'dynamic_sites':[], 'annotations':{}}


class HierarchyModelTests(unittest.TestCase):
    def test_nonpublic_class_and_member_need_proven_runtime_package(self):
        caller = node('pkg/Caller', origin='candidate')
        hidden = node('pkg/Hidden', access=0, origin='game')
        nodes = {n['name']: n for n in (caller, hidden)}
        use = {'name':'pkg/Hidden', 'operation':'class_constant'}
        with self.assertRaisesRegex(ValueError, 'inaccessible referenced class'):
            jvm.validate_class_use(use, 'pkg/Caller', nodes.get)
        hidden['origin'] = 'candidate'
        jvm.validate_class_use(use, 'pkg/Caller', nodes.get)
        hidden['access'] = 1
        hidden['members'] = [{'kind':'method', 'name':'run', 'descriptor':'()V', 'access':0}]
        member = {'owner':'pkg/Hidden', 'name':'run', 'descriptor':'()V', 'kind':'method',
                  'operation':'invokevirtual', 'reference_tag':10}
        self.assertEqual(jvm.validate_use(member, 'pkg/Caller', nodes.get), 'pkg/Hidden')
        hidden['origin'] = 'game'
        with self.assertRaisesRegex(ValueError, 'package-private'):
            jvm.validate_use(member, 'pkg/Caller', nodes.get)

    def test_kind_access_cycles_final_and_sealed_are_checked(self):
        base = node('pkg/Base', access=0, origin='candidate')
        child = node('pkg/Child', parent='pkg/Base')
        nodes = {n['name']:n for n in (base, child)}
        jvm.validate_hierarchy('pkg/Child', nodes.get)  # Same runtime package and origin.
        base['origin'] = 'game'
        with self.assertRaisesRegex(ValueError, 'inaccessible direct supertype'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        base['origin'] = 'candidate'; base['access'] = 1 | 0x0010
        with self.assertRaisesRegex(ValueError, 'final class'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        base['access'] = 1 | 0x0200
        with self.assertRaisesRegex(ValueError, 'class/interface mismatch'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        child['super'] = 'java/lang/Object'; child['interfaces'] = ['pkg/Base']
        base['permitted_subclasses'] = ['pkg/Child']
        with self.assertRaisesRegex(ValueError, 'sealed supertype'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        base['permitted_subclasses'] = None
        jvm.validate_hierarchy('pkg/Child', nodes.get)
        child['interfaces'] = ['pkg/Base', 'pkg/Base']
        with self.assertRaisesRegex(ValueError, 'duplicate superinterface'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        child['interfaces'] = ['pkg/Missing']
        with self.assertRaisesRegex(ValueError, 'missing direct supertype'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        child['interfaces'] = []; child['super'] = 'pkg/Base'; base['access'] = 1; base['super'] = 'pkg/Child'
        with self.assertRaisesRegex(ValueError, 'cyclic hierarchy'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)
        child['super'] = 'java/util/ArrayList'
        with self.assertRaisesRegex(ValueError, 'unsupported candidate platform supertype'):
            jvm.validate_hierarchy('pkg/Child', nodes.get)

    def test_mixin_superclass_and_contributed_interface_use_target_context(self):
        base = node('game/Base', origin='game')
        target = node('game/Target', parent='game/Base', origin='game')
        interface = node('app/Face', access=1 | 0x0200)
        mixin = node('app/Mixin', parent='game/Base', interfaces=['app/Face'])
        nodes = {n['name']:n for n in (base, target, interface, mixin)}
        game.validate_product_hierarchies({'app/Mixin':mixin, 'app/Face':interface},
                                          {'app/Mixin':'game/Target'}, nodes.get, 'fixture')
        interface['access'] = 0x0200
        with self.assertRaisesRegex(ValueError, 'inaccessible direct supertype'):
            game.validate_product_hierarchies({'app/Mixin':mixin, 'app/Face':interface},
                                              {'app/Mixin':'game/Target'}, nodes.get, 'fixture')
        interface['access'] = 1 | 0x0200
        other = node('game/Other', origin='game'); nodes[other['name']] = other; mixin['super'] = other['name']
        with self.assertRaisesRegex(ValueError, 'not in target ancestry'):
            game.validate_product_hierarchies({'app/Mixin':mixin}, {'app/Mixin':'game/Target'}, nodes.get, 'fixture')
        mixin['super'] = 'game/Base'; mixin['interfaces'] = ['java/lang/Runnable']
        with self.assertRaisesRegex(ValueError, 'unsupported Mixin platform superinterface'):
            game.validate_product_hierarchies({'app/Mixin':mixin}, {'app/Mixin':'game/Target'}, nodes.get, 'fixture')

    def test_default_object_does_not_bypass_target_hierarchy_checks(self):
        mixin = node('app/Mixin')
        base = node('game/Base', parent='java/lang/RuntimeException', origin='game')
        target = node('game/Target', parent='game/Base', origin='game')
        nodes = {n['name']: n for n in (mixin, base, target)}
        def validate():
            game.validate_product_hierarchies({'app/Mixin': mixin},
                                              {'app/Mixin': 'game/Target'}, nodes.get, 'fixture')
        validate()
        # Other users of is_subclass must not gain speculative platform ancestry.
        self.assertFalse(jvm.is_subclass('java/lang/RuntimeException', 'java/lang/Object', nodes.get))
        mixin['super'] = 'game/Base'; validate()
        mixin['super'] = 'java/lang/Exception'
        with self.assertRaisesRegex(ValueError, 'not in target ancestry'): validate()
        mixin['super'] = 'java/lang/Object'; del nodes['game/Base']
        with self.assertRaisesRegex(ValueError, 'missing direct supertype'): validate()
        nodes['game/Base'] = base; base['super'] = 'game/Target'
        with self.assertRaisesRegex(ValueError, 'cyclic hierarchy'): validate()
        base['super'] = 'java/lang/Object'; base['access'] = 0x0201
        with self.assertRaisesRegex(ValueError, 'class/interface mismatch'): validate()
        base['access'] = 0; target['name'] = 'other/Target'
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): validate()
        target['name'] = 'game/Target'; base['origin'] = 'library:other'
        with self.assertRaisesRegex(ValueError, 'inaccessible direct supertype'): validate()
        target['access'] = 0x0201
        with self.assertRaisesRegex(ValueError, 'unsupported interface Mixin target'): validate()
        del nodes['game/Target']
        with self.assertRaisesRegex(ValueError, 'missing Mixin target'): validate()

    def test_compiled_private_helpers_and_cross_mixin_restrictions(self):
        javac, java = java_toolchain.which('javac'), java_toolchain.which('java')
        if not javac or not java: self.skipTest('JDK required')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); src = root/'src'; out = root/'classes'; out.mkdir()
            files = {
                'net/minecraft/Target.java':'package net.minecraft; public class Target {}',
                'net/minecraft/Other.java':'package net.minecraft; public class Other {}',
                'app/MixA.java':'package app; public class MixA { private void helper() {} public void call() { helper(); } }',
                'app/MixB.java':'package app; public class MixB { public void helper() {} }',
                'app/Launch.java':'package app; public class Launch { public static void main(String[] a) { new MixA().call(); } }',
            }
            paths=[]
            for name, content in files.items():
                p=src/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_text(content);paths.append(str(p))
            subprocess.run([javac,'--release','8','-d',str(out),*paths],check=True,capture_output=True)
            subprocess.run([java,'-cp',str(out),'app.Launch'],check=True,capture_output=True)
            a=jvm.parse((out/'app/MixA.class').read_bytes());b=jvm.parse((out/'app/MixB.class').read_bytes())
            helper=next(u for u in a['uses'] if u['name']=='helper')
            self.assertEqual((helper['owner'],helper['operation']),('app/MixA','invokespecial'))
            archive=io.BytesIO()
            with ZipFile(archive,'w') as z:
                for name in ('Target','Other'):
                    z.write(out/('net/minecraft/'+name+'.class'),'net/minecraft/'+name+'.class')
            def verify(nodes, targets):
                with ZipFile(io.BytesIO(archive.getvalue())) as z:
                    return game.verify_game_instructions(nodes,targets,z,{}, {}, {},'fixture')
            self.assertGreater(verify({'app/MixA':a},{'app/MixA':'net/minecraft/Target'}),0)
            self.assertGreater(verify({'app/MixA':a},{}),0)  # Ordinary Java 8 class.
            changed=dict(a, uses=[dict(u, owner='app/MixB') if u is helper else u for u in a['uses']])
            with self.assertRaisesRegex(ValueError, 'another Mixin'):
                verify({'app/MixA':changed,'app/MixB':b},
                       {'app/MixA':'net/minecraft/Target','app/MixB':'net/minecraft/Target'})
            changed=dict(a, uses=[dict(u, owner='net/minecraft/Other') if u is helper else u for u in a['uses']])
            with self.assertRaisesRegex(ValueError, 'unsupported non-constructor invokespecial'):
                verify({'app/MixA':changed},{'app/MixA':'net/minecraft/Target'})
            members=[dict(m, access=(m['access'] & ~2) | 1) if m['name']=='helper' else m for m in a['members']]
            with self.assertRaisesRegex(ValueError, 'unsupported non-constructor invokespecial'):
                verify({'app/MixA':dict(a,members=members)},{'app/MixA':'net/minecraft/Target'})
            target=src/'net/minecraft/Target.java';target.write_text('package net.minecraft; public class Target { private void helper() {} }')
            subprocess.run([javac,'--release','8','-d',str(out),str(target)],check=True,capture_output=True)
            archive=io.BytesIO()
            with ZipFile(archive,'w') as z:z.write(out/'net/minecraft/Target.class','net/minecraft/Target.class')
            with self.assertRaisesRegex(ValueError, 'Mixin member collision'):
                verify({'app/MixA':a},{'app/MixA':'net/minecraft/Target'})
            # Java 21 private helper invocation remains a valid same-class reference.
            subprocess.run([javac,'--release','21','-d',str(out),str(src/'app/MixA.java'),str(src/'app/Launch.java')],
                           check=True,capture_output=True)
            subprocess.run([java,'-cp',str(out),'app.Launch'],check=True,capture_output=True)
            modern=jvm.parse((out/'app/MixA.class').read_bytes())
            self.assertGreater(verify({'app/MixA':modern},{}),0)


if __name__ == '__main__':
    unittest.main()
