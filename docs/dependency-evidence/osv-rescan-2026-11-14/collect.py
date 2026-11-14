"""Retain fresh OSV queries without relabeling older Gradle snapshots."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signature(match):
    return (match['purl'], match['advisory'], match['fingerprint'],
            tuple(sorted(match['scopes'])), match['state'], match['failing'])


def main():
    previous = json.loads((ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json').read_text())
    proposal = json.loads((ROOT / 'docs/dependency-evidence/class-linkage-proposals-2026-11-13/index.json').read_text())
    index = {'schema': 1, 'scanned_on': '2026-11-14', 'risk_acceptance': False,
             'snapshot_note': 'Reused retained source-bound Gradle snapshots; OSV queried again without a new Gradle resolution.',
             'disposition_worklist': 'docs/dependency-evidence/current-security-worklist-2026-11-13.json',
             'current_sources': {}, 'unmerged_proposals': {}}
    for kind, folder, sources in (
        ('current_sources', WORKSPACE / '.tprm-dryrun/osv-rescan-20261114', previous['sources']),
        ('unmerged_proposals', WORKSPACE / '.tprm-dryrun/osv-proposal-rescan-20261114', proposal['groups'])):
        results = json.loads((folder / 'index.json').read_text())['groups']
        assert set(results) == set(sources)
        dest = HERE / kind
        dest.mkdir(exist_ok=True)
        for group, row in sorted(results.items()):
            source = sources[group]
            snapshot = ROOT / source['snapshot_path']
            assert digest(snapshot) == row['snapshot_sha256'] == source['snapshot_sha256']
            assert row['source_sha'] == source['source_sha'] and row['complete'] and row['exit_code'] == 1
            assert row['same_as_prior'] and not row['resolved_needing_review']
            report_src = folder / (group + '-osv.json')
            report = json.loads(report_src.read_text())
            prior = json.loads((ROOT / source['report_path']).read_text())
            assert report['scanned_on'] == '2026-11-14' and report['source_sha'] == source['source_sha']
            assert len(report['matches']) == len(prior['matches'])
            assert {signature(m) for m in report['matches']} == {signature(m) for m in prior['matches']}
            assert all(m['failing'] for m in report['matches'])
            result = dict(row)
            for label, suffix in (('report', '-osv.json'), ('log', '-audit.log')):
                src = folder / (group + suffix)
                target = dest / src.name
                shutil.copyfile(src, target)
                result[label + '_path'] = str(target.relative_to(ROOT))
                result[label + '_sha256'] = digest(target)
            index[kind][group] = result
    for src, name in ((Path('/tmp/tprm-osv-refresh-20261114.py'), 'run-current.py'),
                      (Path('/tmp/tprm-osv-refresh-20261114.log'), 'run-current.log'),
                      (Path('/tmp/tprm-osv-proposals-refresh-20261114.py'), 'run-proposals.py'),
                      (Path('/tmp/tprm-osv-proposals-refresh-20261114.log'), 'run-proposals.log')):
        target = HERE / name
        shutil.copyfile(src, target)
        index[name + '_sha256'] = digest(target)
    (HERE / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Retained', len(index['current_sources']), 'current-source and',
          len(index['unmerged_proposals']), 'separate proposal rescans')


if __name__ == '__main__':
    main()
