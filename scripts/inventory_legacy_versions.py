#!/usr/bin/env python3
"""Inventory stable 1.14–1.21.10 releases from Mojang and Fabric metadata.

Mapping excerpts identify possible port boundaries only: they are not linkage,
startup, graphical, or artifact compatibility verification. This script never
changes the release configuration or marks versions as supported.
"""
import concurrent.futures
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from zipfile import ZipFile

MANIFEST = 'https://piston-meta.mojang.com/mc/game/version_manifest_v2.json'
FABRIC = 'https://meta.fabricmc.net/v2/versions/'
ROOT = Path(__file__).resolve().parent.parent


def get(url):
    if not url.startswith('https://'):
        raise ValueError(f'insecure metadata URL: {url}')
    with urlopen(url, timeout=120) as response:
        return response.read()


def checked(data, sha1, size=None):
    if hashlib.sha1(data).hexdigest() != sha1 or (size is not None and len(data) != size):
        raise ValueError('source SHA-1 or size mismatch')
    return data


def official_api(data):
    text = data.decode('utf-8')
    result = {}
    names = ('ItemInHandLayer', 'ArmedEntityRenderState', 'MapRenderer', 'MapItem')
    for match in re.finditer(r'^([^\s]+) -> [^\n]+:\n((?:[ \t#].*\n)*)', text, re.M):
        cls = match.group(1)
        if cls.rsplit('.', 1)[-1] not in names:
            continue
        lines = [line.strip() for line in match.group(2).splitlines()
                 if not line.startswith('#') and re.search(r'(?i)render|submit|extract|saveddata|mapid|hand|mainarm', line)]
        result[cls] = lines[:25]
    return result


def yarn_api(data):
    with ZipFile(io.BytesIO(data)) as archive:
        lines = archive.read('mappings/mappings.tiny').decode('utf-8').splitlines()
    result, active = {}, None
    for line in lines:
        if line.startswith('c\t'):
            fields = line.split('\t')
            active = next((x for x in fields[1:] if x.endswith(('/HeldItemFeatureRenderer', '/MapRenderer', '/FilledMapItem'))), None)
            if active:
                result[active] = []
        elif active and line.startswith('\tm\t') and len(result[active]) < 25:
            result[active].append(line.strip())
    return result


def candidate(version):
    groups = {
        '1.21.9–1.21.10': ('1.21.9', '1.21.10'),
        '1.21.4–1.21.8': ('1.21.4', '1.21.5', '1.21.6', '1.21.7', '1.21.8'),
        '1.21.2–1.21.3': ('1.21.2', '1.21.3'),
        '1.21–1.21.1': ('1.21', '1.21.1'),
        '1.20.5–1.20.6': ('1.20.5', '1.20.6'),
        '1.19.4–1.20.4': ('1.19.4', '1.20', '1.20.1', '1.20.2', '1.20.3', '1.20.4'),
        '1.19.3': ('1.19.3',),
        '1.17–1.19.2': ('1.17', '1.17.1', '1.18', '1.18.1', '1.18.2', '1.19', '1.19.1', '1.19.2'),
        '1.15–1.16.5': ('1.15', '1.15.1', '1.15.2', '1.16', '1.16.1', '1.16.2', '1.16.3', '1.16.4', '1.16.5'),
        '1.14–1.14.4': ('1.14', '1.14.1', '1.14.2', '1.14.3', '1.14.4'),
    }
    return next((name + ' (candidate)' for name, members in groups.items() if version in members), 'undetermined')


def main():
    manifest_raw = get(MANIFEST)
    manifest = json.loads(manifest_raw)
    entries = [v for v in manifest['versions'] if v['type'] == 'release' and
               re.fullmatch(r'1\.(?:14|15|16|17|18|19|20|21)(?:\.\d+)?', v['id']) and
               v['id'] != '1.21.11']
    games = {x['version']: x for x in json.loads(get(FABRIC + 'game'))}
    intermediary = {x['version']: x for x in json.loads(get(FABRIC + 'intermediary'))}
    yarn = json.loads(get(FABRIC + 'yarn'))
    loaders = json.loads(get(FABRIC + 'loader'))
    stable_loader = next(x['version'] for x in loaders if x['stable'])

    def inspect(entry):
        version = entry['id']
        raw = checked(get(entry['url']), entry['sha1'])
        meta = json.loads(raw)
        if meta.get('id') != version or meta.get('type') != 'release':
            raise ValueError(version + ': mismatched metadata')
        client = meta.get('downloads', {}).get('client')
        if not client:
            raise ValueError(version + ': client metadata absent')
        options = [x for x in yarn if x['gameVersion'] == version]
        chosen = max(options, key=lambda x: x['build']) if options else None
        mapping = meta['downloads'].get('client_mappings')
        if mapping:
            mapping_bytes = checked(get(mapping['url']), mapping['sha1'], mapping['size'])
            api = official_api(mapping_bytes)
            source = {'kind': 'Mojang client mappings', 'url': mapping['url'], 'sha1': mapping['sha1']}
        elif chosen:
            ver = quote(chosen['version'], safe='')
            url = f'https://maven.fabricmc.net/net/fabricmc/yarn/{ver}/yarn-{ver}-v2.jar'
            mapping_bytes = get(url)
            source = {'kind': 'Fabric Yarn v2 mappings', 'url': url,
                      'sha1_observed': hashlib.sha1(mapping_bytes).hexdigest()}
            api = yarn_api(mapping_bytes)
        else:
            source, api = None, {}
        print(version, 'metadata and mapping inspected', file=sys.stderr, flush=True)
        return {'minecraft': version, 'release_type': entry['type'], 'release_time': entry['releaseTime'],
                'metadata_url': entry['url'], 'metadata_sha1': entry['sha1'],
                'client': {'url': client['url'], 'sha1': client['sha1'], 'size': client['size'],
                           'status': 'listed in Mojang metadata; download not checked by this inventory'},
                'java': meta.get('javaVersion'),
                'fabric_game_listed': version in games,
                'fabric_intermediary_listed': version in intermediary,
                'fabric_global_latest_stable_loader': stable_loader,
                'fabric_loader_runtime_verification': 'NOT RUN',
                'yarn_latest_build_listed': chosen['version'] if chosen else None,
                'mapping_source': source, 'rendering_api_mapping_excerpts': api,
                'candidate_group': candidate(version), 'artifact_status': 'UNVERIFIED',
                'static_linkage': 'NOT RUN', 'client_startup': 'NOT RUN', 'graphical': 'NOT RUN'}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(executor.map(inspect, entries))
    evidence_path = ROOT / 'docs/legacy-candidate-evidence.json'
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
        if evidence.get('schema') != 1:
            raise ValueError('invalid candidate evidence schema')
        for group in evidence['groups'].values():
            for row in rows:
                if row['minecraft'] in group['versions']:
                    for field in ('static_linkage', 'client_startup', 'graphical'):
                        row[field] = group.get('per_version', {}).get(row['minecraft'], {}).get(field, group[field])
                    row['artifact_status'] = group['status']
                    if row['static_linkage'].startswith('PASS'):
                        row['client']['status'] = 'downloaded and SHA-1/size checked by candidate static verifier'
    result = {'schema': 1, 'manifest_url': MANIFEST,
              'manifest_sha256_observed': hashlib.sha256(manifest_raw).hexdigest(),
              'fabric_metadata': [FABRIC + x for x in ('game', 'intermediary', 'yarn', 'loader')],
              'scope': 'stable 1.14 through 1.21.10; excludes snapshots and 1.21.11',
              'caveat': 'Mappings and metadata are not proof that an artifact loads or renders.',
              'versions': rows}
    target = ROOT / 'docs/legacy-version-inventory.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {len(rows)} versions to {target}')


if __name__ == '__main__':
    main()
