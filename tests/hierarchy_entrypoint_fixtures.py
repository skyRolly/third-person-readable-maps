"""Compile a candidate against one hierarchy, then replace its runtime API."""
import os
from pathlib import Path
import shutil
import subprocess


def prepare(root, support, out, javac, spec):
    location, kind, variant = spec.split('-')
    package = {'library': 'org.joml', 'game': 'com.mojang.math', 'candidate': 'fixture'}[location]
    source = root / 'hierarchy-src' / Path(package.replace('.', '/')) / 'Parent.java'
    source.parent.mkdir(parents=True, exist_ok=True)
    declaration = 'interface Parent {}' if kind == 'interface' else 'class Parent {}'
    source.write_text('package '+package+'; public '+declaration)
    subprocess.run([javac, '--release', '8', '-d', str(support), str(source)], check=True, capture_output=True)
    probe_package = package if variant == 'samepackage' else 'app'
    probe = root/'HierarchyProbe.java'
    relation = 'implements' if kind == 'interface' else 'extends'
    probe.write_text('package '+probe_package+'; public class HierarchyProbe '+relation+' '+package+'.Parent {}')
    subprocess.run([javac, '--release', '8', '-classpath', str(support), '-d', str(out), str(probe)],
                   check=True, capture_output=True)
    loader = root/'LoadHierarchy.java'; loader_out = root/'loader'; loader_out.mkdir()
    loader.write_text('public class LoadHierarchy { public static void main(String[] a) throws Exception { '
                      'Class.forName("'+probe_package+'.HierarchyProbe"); } }')
    subprocess.run([javac, '--release', '8', '-d', str(loader_out), str(loader)], check=True, capture_output=True)
    if variant in ('hidden', 'samepackage'):
        source.write_text('package '+package+'; '+declaration)
    elif variant == 'kind':
        source.write_text('package '+package+'; public '+('class Parent {}' if kind == 'interface' else 'interface Parent {}'))
    elif variant == 'final':
        source.write_text('package '+package+'; public final class Parent {}')
    elif variant == 'sealed':
        assert kind == 'interface'
        source.write_text('package '+package+'; public sealed interface Parent permits Friend {} '
                          'final class Friend implements Parent {}')
    if variant in ('hidden', 'samepackage', 'kind', 'final', 'sealed'):
        subprocess.run([javac, '--release', '17' if variant == 'sealed' else '8', '-d', str(support), str(source)],
                       check=True, capture_output=True)
    parent = Path(package.replace('.', '/'))/'Parent.class'
    if variant == 'missing':
        (support/parent).unlink()
    if location == 'candidate' and variant != 'missing':
        (out/parent).parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(support/parent, out/parent)
    java = shutil.which('java')
    if java:
        executed = subprocess.run([java, '-cp', os.pathsep.join(map(str, (out, support, loader_out))),
                                   'LoadHierarchy'], capture_output=True, text=True)
        if variant in ('public', 'samepackage'):
            assert executed.returncode == 0, executed.stderr
        else:
            assert executed.returncode != 0, 'JVM unexpectedly loaded invalid hierarchy'
            expected = {'hidden':'IllegalAccessError', 'kind':'IncompatibleClassChangeError',
                        'final':'IncompatibleClassChangeError', 'sealed':'IncompatibleClassChangeError',
                        'missing':'NoClassDefFoundError'}[variant]
            assert expected in executed.stderr, executed.stderr
    return {'location': location, 'parent': parent, 'variant': variant,
            'probe': Path(probe_package.replace('.', '/'))/'HierarchyProbe.class'}
