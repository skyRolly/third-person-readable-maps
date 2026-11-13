"""Inventory tracked paths and Git blob identities across proposed sources."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import subprocess
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent
INTRO = ('A client-side Fabric mod that renders filled map contents on maps held in third-person view. '
         'Maps follow the holding arm, with layouts for the main hand, off hand, and occupied opposite hand, '
         'including left-handed players.')


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo)


def category(path):
    if path.startswith('docs/verification/'):
        return 'branch diagnostic and verification evidence'
    if path.startswith('docs/'):
        return 'coordination or historical documentation and evidence'
    if path.startswith('src/'):
        return 'game-specific product source and resources'
    if path.startswith('.github/'):
        return 'workflow and automation configuration'
    if path.startswith(('scripts/', 'tests/')):
        return 'verification, coordination, or test code'
    if path.startswith('release/'):
        return 'coordination and release configuration'
    if path.startswith('gradle/') or path in ('build.gradle', 'settings.gradle', 'gradle.properties',
                                               'gradlew', 'gradlew.bat', 'Build-Windows.bat'):
        return 'build configuration and wrapper'
    return 'shared metadata, user documentation, or other tracked file'


def tree(repo, commit):
    result = {}
    for item in git(repo, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not item:
            continue
        meta, path = item.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        result[path.decode('utf-8')] = {'mode': mode, 'type': kind, 'object': oid}
    return result


def main():
    refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    products, sources = {}, {}
    for group, ref in sorted(refs.items()):
        if group in ('1.21.11', '26.1-26.2', '26.3'):
            repo = WORKSPACE / ('tprm-review-' + group)
        else:
            repo = WORKSPACE / ('tprm-legacy-' + ('1.14' if group == '1.14-1.14.4' else group))
        head = ref['new_head']
        products[group] = tree(repo, head)
        readme = git(repo, 'show', head + ':README.md').decode()
        props = git(repo, 'show', head + ':gradle.properties').decode()
        assert readme.splitlines()[0] == '# Third Person Readable Maps' and INTRO in readme
        assert 'branch=' + quote('mc/' + group, safe='') in readme
        assert 'mod_version=1.0.0' in props.splitlines()
        sources[group] = {'kind': 'proposed-product-head', 'commit': head,
                          'tracked_files': len(products[group]),
                          'verification_evidence_files': sum(p.startswith('docs/verification/') for p in products[group]),
                          'readme_title_and_introduction_match': True,
                          'readme_branch_badge_matches': True, 'mod_version': '1.0.0'}
    coordination_commit = git(ROOT, 'rev-parse', 'HEAD').decode().strip()
    main_commit = git(ROOT, 'rev-parse', 'origin/main').decode().strip()
    coordination = tree(ROOT, coordination_commit)
    main_tree = tree(ROOT, main_commit)
    for commit in (coordination_commit, main_commit):
        readme = git(ROOT, 'show', commit + ':README.md').decode()
        assert readme.splitlines()[0] == '# Third Person Readable Maps' and INTRO in readme
    sources['coordination-snapshot'] = {'kind': 'coordination-pr-snapshot', 'commit': coordination_commit,
                                        'tracked_files': len(coordination)}
    sources['main'] = {'kind': 'integrated-coordination', 'commit': main_commit, 'tracked_files': len(main_tree)}
    rows = defaultdict(lambda: {'product_objects': {}})
    for group, files in products.items():
        for path, blob in files.items():
            rows[path]['product_objects'][group] = blob
    for label, files in (('coordination_object', coordination), ('main_object', main_tree)):
        for path, blob in files.items():
            rows[path][label] = blob
    paths = {}
    categories = Counter()
    for path, row in sorted(rows.items()):
        row['classification'] = category(path)
        categories[row['classification']] += 1
        paths[path] = row
    common = [row for row in paths.values() if len(row['product_objects']) == len(products)]
    identical = [row for row in common if len({json.dumps(v, sort_keys=True) for v in row['product_objects'].values()}) == 1]
    result = {'schema': 1, 'observed_on': '2026-11-13',
              'scope_note': 'Coordination commit is a prior snapshot; this generated inventory and subsequent evidence commits are not in that snapshot.',
              'sources': sources, 'path_classification_counts': dict(categories),
              'product_common_paths': len(common), 'product_common_identical_paths': len(identical),
              'paths': paths}
    (HERE / 'index.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('Inventoried', len(paths), 'distinct paths;', len(common), 'common to all products,', len(identical), 'identical')


if __name__ == '__main__':
    main()
