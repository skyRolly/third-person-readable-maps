#!/usr/bin/env python3
"""Validate a non-destructive erratum for three retained build records."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from release import require, unique_object

ROOT = Path(__file__).resolve().parents[1]
BASE = 'docs/version-consistency-1.0.0/current-validation/rehearsal-2026-11-21-owner-policy/'
SOURCES = {
    'build_snapshot': ('docs/dependency-evidence/issue45-live-source-2026-11-22/product-builds-snapshot.json',
                       '1c98da271fbf0bb4d6ce94e7831c7ae044e5a6bffceca36d0942e93be9820bd1'),
    'previous_build_record': (BASE + 'superseded-current-state/builds.json',
                              'e4a6b2f5fe93c6ce808da8d1437dd877e7dbf43540b3dd7d31cc0ec8c090bd21'),
    'current_inputs': (BASE + 'artifact-inputs.json',
                       '43534e0d7d1d7e309a42f29bc8533df20c3d9871741a11bebe0136992623e2a8'),
    'previous_inputs': (BASE + 'superseded-current-state/artifact-inputs.json',
                        '6e3bb313cfddaa36870c9cd6f2c3612f4b8007b72be37fddfa0adaa082e4d9a7'),
}
GROUPS = ('1.21.11', '26.1-26.2', '26.3')
ERRATUM = 'docs/dependency-evidence/issue45-review-fixes-2026-11-22/build-continuity-erratum.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(root, path):
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root.resolve()), 'evidence path escapes repository')
    return resolved.read_bytes()


def build_expected(root=ROOT):
    sources, data = {}, {}
    for name, (path, expected) in SOURCES.items():
        raw = read(root, path)
        require(sha(raw) == expected, name + ': source checksum mismatch')
        sources[name] = {'path': path, 'sha256': expected}
        data[name] = json.loads(raw, object_pairs_hook=unique_object)
    builds = data['build_snapshot']
    previous = data['previous_build_record']
    inputs = data['current_inputs']['groups']
    earlier_inputs = data['previous_inputs']['groups']
    groups = {}
    for group in GROUPS:
        now, before = builds[group], previous[group]
        current_input, old_input = inputs[group], earlier_inputs[group]
        require(now['previous_record'] == SOURCES['previous_build_record'][0] and
                now['previous_source'] == before['source_commit'] == old_input['source_commit'] and
                now['source_commit'] == current_input['source_commit'] and
                now['sha256'] == current_input['artifact_sha256'] and
                now['previous_sha256'] == before['sha256'] == old_input['artifact_sha256'],
                group + ': source or artifact record mismatch')
        require(before['same_as_previous'] == (before['sha256'] == before['previous_sha256']) and
                now['same_as_previous'] == before['same_as_previous'] and
                now['same_as_previous'] is False and now['continuity'] == 'same',
                group + ': legacy continuity context differs from the recorded erratum')
        archives = []
        for label, item, path_key, hash_key in (
                ('current Linux', current_input, 'archive_path', 'archive_sha256'),
                ('current Windows', current_input, 'windows_archive_path', 'windows_archive_sha256'),
                ('previous Linux', old_input, 'archive_path', 'archive_sha256')):
            raw = read(root, item[path_key])
            require(sha(raw) == item[hash_key], group + ': ' + label + ' archive checksum mismatch')
            with ZipFile(BytesIO(raw)) as archive:
                require(archive.namelist() == [item['artifact_filename']], group + ': unexpected archive content')
                jar = archive.read(item['artifact_filename'])
            require(sha(jar) == item['artifact_sha256'], group + ': ' + label + ' JAR checksum mismatch')
            archives.append({'role': label, 'path': item[path_key], 'archive_sha256': sha(raw),
                             'jar_sha256': sha(jar)})
        source_unchanged = now['source_commit'] == before['source_commit']
        artifact_unchanged = now['sha256'] == before['sha256']
        require(not source_unchanged and artifact_unchanged, group + ': expected source/artifact comparison differs')
        groups[group] = {'current_source_sha': now['source_commit'], 'previous_source_sha': before['source_commit'],
                         'current_jar_sha256': now['sha256'], 'previous_jar_sha256': before['sha256'],
                         'source_unchanged': source_unchanged, 'artifact_unchanged': artifact_unchanged,
                         'artifact_continuity': 'same' if artifact_unchanged else 'different',
                         'legacy_same_as_previous': now['same_as_previous'],
                         'legacy_field_status': 'stale value copied from the prior artifact comparison',
                         'previous_record': SOURCES['previous_build_record'][0], 'verified_archives': archives}
    return {'schema': 1, 'status': 'historical-erratum-no-release-authorization',
            'sources': sources, 'groups': groups}


def validate(value, root=ROOT):
    expected = build_expected(root)
    require(isinstance(value, dict) and value.get('schema') == expected['schema'] and
            value.get('status') == expected['status'] and value.get('sources') == expected['sources'] and
            isinstance(value.get('groups'), dict) and set(value['groups']) == set(GROUPS),
            'invalid erratum identity or provenance')
    for group in GROUPS:
        require(value['groups'][group] == expected['groups'][group],
                group + ': inconsistent source or artifact continuity interpretation')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', type=Path, help='write a new erratum; never overwrite an existing report')
    args = parser.parse_args()
    try:
        if args.write:
            require(not args.write.exists(), 'refusing to overwrite an existing erratum')
            args.write.parent.mkdir(parents=True, exist_ok=True)
            args.write.write_text(json.dumps(build_expected(), indent=2) + '\n', encoding='utf-8')
        else:
            validate(json.loads(read(ROOT, ERRATUM), object_pairs_hook=unique_object))
        print('Verified three source and artifact continuity comparisons; no release authorization')
        return 0
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as exc:
        print('Continuity validation failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
