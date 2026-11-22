"""Regression control: retained-scan validator from merged PR #58."""
from release import require


def validate_base_scan(base_scan, scan, critical, versions):
    prior = critical['supplemental_source_bound_evidence']['vanilla_classpath_scan']
    require(base_scan.get('schema') == 1 and base_scan.get('security_clearance') is False and
            base_scan.get('prior_vanilla_scan') == {'path': prior['path'], 'sha256': prior['sha256']} and
            base_scan.get('minecraft_versions') == versions, 'ClientHello scan provenance differs')
    selected = [item for item in scan['runtime_classpath_scan']['all_artifacts']
                if set(item['minecraft_versions']) & set(versions)]
    expected = {item['sha1']: item for item in selected}
    rows = base_scan['artifacts']
    require(len(expected) == len(selected) == len(rows) == 471 and
            len({row['sha1'] for row in rows}) == len(rows), 'ClientHello scan coverage differs')
    internal, external = [], []
    for row in rows:
        previous = expected.get(row['sha1'])
        require(previous is not None and row['sha256'] == previous['sha256'] and
                row['size_bytes'] == previous['size_bytes'] and row['coordinates'] == previous['coordinates'] and
                row['class_files_scanned'] == previous['class_files_scanned'] and
                row['minecraft_versions'] == sorted(set(previous['minecraft_versions']) & set(versions)),
                'ClientHello artifact identity differs')
        for hit in row['clienthello_name_references']:
            is_internal = hit['class_file'].startswith('io/netty/handler/ssl/') and any(
                coordinate.startswith('io.netty:netty-handler:') for coordinate in row['coordinates'])
            require(hit['netty_handler_internal'] == is_internal and
                    len(hit['sha256']) == 64, 'ClientHello reference classification differs')
            (internal if is_internal else external).append((row['sha1'], hit['class_file']))
    require(base_scan['class_files_scanned'] == sum(row['class_files_scanned'] for row in rows) and
            base_scan['netty_handler_reference_count'] == len(internal) and
            base_scan['external_references'] == [{'artifact_sha1': jar, 'class_file': name}
                                                  for jar, name in external] and not external,
            'ClientHello scan has uncovered callers or inconsistent counts')
