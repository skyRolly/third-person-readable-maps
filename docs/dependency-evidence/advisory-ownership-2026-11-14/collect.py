"""Cross-reference each failing occurrence with its runtime manifest evidence."""
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    scan = json.loads((ROOT / 'docs/dependency-evidence/osv-rescan-2026-11-14/index.json').read_text())
    worklist = json.loads((ROOT / scan['disposition_worklist']).read_text())
    rows, scope_counts = {}, Counter()
    for group, source in scan['current_sources'].items():
        report_file = ROOT / source['report_path']
        assert digest(report_file) == source['report_sha256']
        report = json.loads(report_file.read_text())
        assert report['source_sha'] == source['source_sha'] and report['scanned_on'] == '2026-11-14'
        packaged = worklist['packaging'][group]
        assert packaged['third_party_class_files'] == 0 and packaged['nested_jars'] == 0
        for match in report['matches']:
            key = group + '|' + match['purl'] + '|' + match['advisory']
            record = worklist['records'][match['purl'] + '|' + match['advisory']]
            assert record['disposition'] == 'Further investigation' and not record['risk_accepted']
            assert match['failing'] and key not in rows
            runtime = {}
            for scope in match['scopes']:
                if not scope.startswith('runtime/'):
                    continue
                version = scope.split('/', 1)[1]
                assert match['purl'] in report['inventories'][scope]
                manifest = report['runtime_manifests'][version]
                runtime[version] = {'metadata_url': manifest['url'], 'metadata_sha1': manifest['sha1']}
            assert runtime
            gradle = 'gradle' in match['scopes']
            if gradle:
                assert match['purl'] in report['inventories']['gradle']
            scope_counts['gradle_and_runtime' if gradle else 'runtime_only'] += 1
            rows[key] = {
                'group': group, 'source_kind': source['source_kind'], 'source_sha': source['source_sha'],
                'purl': match['purl'], 'advisory': match['advisory'], 'severity': match.get('severity', 'UNKNOWN'),
                'fingerprint': match['fingerprint'], 'gradle_scope': gradle,
                'minecraft_runtime_metadata': runtime, 'report_path': source['report_path'],
                'report_sha256': source['report_sha256'], 'disposition': record['disposition'],
                'failing': True, 'risk_accepted': False,
                'proposed_jar_source_commit': packaged['source_commit'],
                'proposed_jar_sha256': packaged['artifact_sha256'],
                'proposed_jar_bundles_third_party_classes_or_nested_jars': False,
                'remediation_note': ('The listed runtime coordinate is Minecraft-managed. Assess applicability and '
                    'any separate Gradle exposure; avoid an unverified runtime override. A runtime fix may depend on upstream.')}
    result = {'schema': 1, 'observed_on': '2026-11-14',
              'scope_note': ('Runtime metadata includes all listed platform variants and does not prove a particular library '
                             'was loaded or that an advisory is exploitable. Proposed-JAR packaging is separate from actual integrated source.'),
              'scope_counts': dict(scope_counts), 'occurrences': rows}
    (HERE / 'index.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Recorded ownership evidence for', len(rows), 'failing occurrences', dict(scope_counts))


if __name__ == '__main__':
    main()
