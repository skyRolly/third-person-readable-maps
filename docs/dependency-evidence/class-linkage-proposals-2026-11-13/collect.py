"""Retain unmerged maintenance-proposal scans, separate from live branches."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT.parent / '.tprm-dryrun/class-linkage-proposal-security'
OLD = ROOT / 'docs/dependency-evidence/1.0.0-maintenance-proposals-2026-11-12'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signature(match):
    return (match['purl'], match['advisory'], match['fingerprint'],
            tuple(sorted(match['scopes'])), match['state'], match['failing'])


def main():
    refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    index = {'schema': 1, 'scanned_on': '2026-11-13', 'risk_acceptance': False,
             'scope': 'Unmerged maintenance proposals, not integrated maintenance branches.', 'groups': {}}
    for src, name in ((Path('/tmp/tprm-audit-proposals-class.py'), 'run.py'),
                      (Path('/tmp/tprm-audit-proposals-class.log'), 'orchestration.log')):
        shutil.copyfile(src, HERE / name)
        index[name + '_sha256'] = digest(HERE / name)
    for group in ('1.21.11', '26.1-26.2', '26.3'):
        snap = SOURCE / (group + '-snapshot.json')
        report_file = SOURCE / (group + '-osv.json')
        snapshot = json.loads(snap.read_text())
        report = json.loads(report_file.read_text())
        previous = json.loads((OLD / (group + '-osv.json')).read_text())
        head = refs[group]['new_head']
        assert snapshot['sha'] == report['source_sha'] == head
        assert snapshot['ref'] == report['snapshot_ref'] == 'refs/heads/' + report['branch']
        assert report['status'] == 'complete-unreviewed-maintenance-proposal' and not report['risk_acceptance']
        assert not report['resolved_needing_review'] and all(m['failing'] for m in report['matches'])
        assert len(report['matches']) == len(previous['matches'])
        assert {signature(m) for m in report['matches']} == {signature(m) for m in previous['matches']}
        result = {'source_sha': head, 'branch': report['branch'], 'complete': True, 'exit_code': 1,
                  'matches': len(report['matches']), 'failing': sum(m['failing'] for m in report['matches']),
                  'comparison': 'same package, advisory, fingerprint, scopes, state and failing flag as prior proposal scan'}
        paths = ((snap, 'snapshot'), (report_file, 'report'),
                 (Path('/tmp/tprm-class-proposal-snapshot-' + group + '.log'), 'snapshot_log'),
                 (Path('/tmp/tprm-class-proposal-audit-' + group + '.log'), 'audit_log'))
        for src, label in paths:
            if label == 'snapshot_log':
                assert 'BUILD SUCCESSFUL' in src.read_text(errors='replace')
            dest = HERE / (group + {'snapshot': '-snapshot.json', 'report': '-osv.json',
                                    'snapshot_log': '-snapshot.log', 'audit_log': '-audit.log'}[label])
            shutil.copyfile(src, dest)
            result[label + '_path'] = str(dest.relative_to(ROOT))
            result[label + '_sha256'] = digest(dest)
        index['groups'][group] = result
    (HERE / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    print('Retained', len(index['groups']), 'separate proposal scans')


if __name__ == '__main__':
    main()
