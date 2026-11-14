"""Collect exact-head candidate scans without changing historical findings."""
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / '.tprm-dryrun/class-linkage-security'
PREVIOUS = ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-12.json'
OUTPUT = ROOT / 'docs/dependency-evidence/current-security-worklist-2026-11-13.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signature(match):
    return (match['purl'], match['advisory'], match['fingerprint'],
            tuple(sorted(match['scopes'])), match['state'], match['failing'])


def main():
    worklist = json.loads(PREVIOUS.read_text())
    candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
    builds = json.loads((ROOT / 'docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups']
    transition = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    reports = {}
    index = {'schema': 1, 'scanned_on': '2026-11-13', 'risk_acceptance': False,
             'scope': 'Fresh Gradle inventories and OSV queries for ten unmerged candidate heads.',
             'groups': {}}
    for src, filename in ((Path('/tmp/tprm-refresh-audits-class.py'), 'run-resumed.py'),
                          (Path('/tmp/tprm-refresh-audits-class.log'), 'orchestration.log')):
        target = HERE / filename
        shutil.copyfile(src, target)
        index[filename + '_sha256'] = digest(target)
    for group, candidate in sorted(candidates.items()):
        source = worklist['sources'][group]
        previous = json.loads((ROOT / source['report_path']).read_text())
        snapshot = json.loads((SOURCE / (group + '-snapshot.json')).read_text())
        report = json.loads((SOURCE / (group + '-osv.json')).read_text())
        head = candidate['candidate_head']
        assert source['source_kind'] == 'candidate'
        assert snapshot['sha'] == report['source_sha'] == transition[group]['new_head'] == head
        assert snapshot['ref'] == report['snapshot_ref'] == source['snapshot_ref']
        assert report['status'] == 'complete-unreviewed-candidate-scan' and not report['risk_acceptance']
        assert not report['resolved_needing_review']
        assert len(report['matches']) == len(previous['matches'])
        assert {signature(m) for m in report['matches']} == {signature(m) for m in previous['matches']}
        assert all(m['failing'] for m in report['matches'])
        reports[group] = {(m['purl'], m['advisory']): m for m in report['matches']}
        result = {'source_sha': head, 'branch': report['branch'], 'exit_code': 1,
                  'complete': True, 'matches': len(report['matches']),
                  'states': dict(Counter(m['state'] for m in report['matches'])),
                  'failing': sum(m['failing'] for m in report['matches']),
                  'comparison': 'same package, advisory, fingerprint, scopes, state and failing flag as prior scan'}
        for suffix, label in (('-snapshot.json', 'snapshot'), ('-osv.json', 'report'),
                              ('-snapshot.log', 'snapshot_log'), ('-audit.log', 'audit_log')):
            src = SOURCE / (group + suffix)
            if label == 'snapshot_log':
                assert 'BUILD SUCCESSFUL' in src.read_text(errors='replace')
            elif label == 'audit_log':
                assert 'unreviewed, failing matches' in src.read_text(errors='replace')
            target = HERE / src.name
            shutil.copyfile(src, target)
            result[label + '_path'] = str(target.relative_to(ROOT))
            result[label + '_sha256'] = digest(target)
        source.update({'source_sha': head, 'snapshot_path': result['snapshot_path'],
                       'snapshot_sha256': result['snapshot_sha256'],
                       'report_path': result['report_path'], 'report_sha256': result['report_sha256'],
                       'matches': result['matches'], 'states': result['states'],
                       'resolved_needing_review': []})
        index['groups'][group] = result

    for record in worklist['records'].values():
        for occurrence in record['occurrences']:
            group = occurrence['group']
            if group not in reports:
                continue
            match = reports[group][(record['purl'], record['advisory'])]
            assert occurrence['fingerprint'] == match['fingerprint']
            occurrence.update({'source_sha': candidates[group]['candidate_head'],
                               'scopes': match['scopes'], 'state': match['state'],
                               'failing': match['failing'], 'review_status': match['review_status'],
                               'report': worklist['sources'][group]['report_path']})

    for group, build in builds.items():
        artifact = WORKSPACE / '.tprm-dryrun/class-linkage-builds' / group / build['artifact']
        assert digest(artifact) == build['sha256'] and build['source_commit'] == transition[group]['new_head']
        with ZipFile(artifact) as jar:
            third_party = [n for n in jar.namelist() if n.endswith('.class')
                           and not n.startswith('tech/rolly/thirdpersonreadablemaps/')]
            nested = [n for n in jar.namelist() if n.endswith('.jar')]
        assert not third_party and not nested, (group, third_party, nested)
        worklist['packaging'][group] = {
            'source_commit': build['source_commit'], 'artifact_sha256': build['sha256'],
            'third_party_class_files': 0, 'nested_jars': 0,
            'note': 'Proposed 1.0.0 JAR; unbundled runtime dependencies can still be relevant.'}

    worklist['scanned_on'] = '2026-11-13'
    worklist['scope'] = ('Fresh candidate-head snapshots and OSV queries; integrated maintenance entries '
                         'retain their actual 2026-11-12 source snapshots and 2026-11-13 OSV rescan. '
                         'Unmerged maintenance proposals are recorded separately.')
    worklist['historical_osv_rescan'] = worklist.pop('last_osv_rescan')
    worklist['candidate_followup'] = {'index_path': str((HERE / 'index.json').relative_to(ROOT)),
                                      'scanned_on': '2026-11-13'}
    (HERE / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    OUTPUT.write_text(json.dumps(worklist, indent=2) + '\n')
    print('Recorded', len(index['groups']), 'candidate scans;',
          sum(row['failing'] for row in index['groups'].values()), 'failing candidate occurrences')


if __name__ == '__main__':
    main()
