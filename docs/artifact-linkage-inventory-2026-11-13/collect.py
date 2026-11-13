"""Inventory sensitive bytecode operations in the exact proposed artifacts."""
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent
BUILDS = WORKSPACE / '.tprm-dryrun/class-linkage-builds'
REPO = WORKSPACE / 'tprm-legacy-1.14'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    builds = json.loads((BUILDS / 'index.json').read_text())
    refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    parser = REPO / 'scripts/jvm_linkage.py'
    parser_bytes = parser.read_bytes()
    spec = importlib.util.spec_from_file_location('tprm_inventory_parser', parser)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {'schema': 1, 'observed_on': '2026-11-13',
              'parser_sha256': digest(parser_bytes), 'groups': {}}
    for group, build in sorted(builds.items()):
        if group in ('1.21.11', '26.1-26.2', '26.3'):
            repo = WORKSPACE / ('tprm-review-' + group)
        else:
            repo = WORKSPACE / ('tprm-legacy-' + ('1.14' if group == '1.14-1.14.4' else group))
        head = refs[group]['new_head']
        committed_parser = subprocess.check_output(['git', 'show', head + ':scripts/jvm_linkage.py'], cwd=repo)
        assert digest(committed_parser) == digest(parser_bytes) and build['source_commit'] == head
        artifact = BUILDS / group / build['artifact']
        assert digest(artifact.read_bytes()) == build['sha256']
        with ZipFile(artifact) as jar:
            nodes = [module.parse(jar.read(name)) for name in jar.namelist() if name.endswith('.class')]
        own = {node['name']: node for node in nodes}
        external = []
        for node in nodes:
            for use in node['uses']:
                declared = own.get(use['owner'])
                local_member = declared and any(
                    (m['kind'], m['name'], m['descriptor']) == (use['kind'], use['name'], use['descriptor'])
                    for m in declared['members'])
                # A reference with a mod-class owner but no local declaration
                # can name an inherited game member after Mixin transformation.
                if not local_member:
                    external.append({'caller': node['name'], **use})
        writes = [u for u in external if u['operation'] in ('putfield', 'putstatic')]
        special = [u for u in external if u['operation'] == 'invokespecial' and u['name'] != '<init>']
        result['groups'][group] = {
            'source_commit': head, 'artifact': build['artifact'], 'artifact_sha256': build['sha256'],
            'class_count': len(nodes), 'external_or_inherited_operations': dict(Counter(u['operation'] for u in external)),
            'external_or_inherited_field_writes': writes,
            'external_or_inherited_nonconstructor_invokespecial': special}
    (HERE / 'index.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Inventoried', len(result['groups']), 'exact proposed artifacts')


if __name__ == '__main__':
    main()
