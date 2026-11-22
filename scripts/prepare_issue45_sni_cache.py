#!/usr/bin/env python3
"""Acquire six pinned Mojang Netty JARs into a new SHA-1-keyed cache.

Downloads are restricted to the source-bound Mojang URLs and are verified
before writing. The separate SNI CLI can then inspect the cache offline.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import BadZipFile

import inspect_issue45_netty_ipfilter_high as ipfilter
import inspect_issue45_sni_high as sni
from release import require, unique_object


def prepare_cache(output, catalog, known, scan, inventory, fetch):
    root = output.resolve()
    require(not root.exists(), 'refusing to replace an existing cache')
    require(len(catalog) == 6 and len({row['sha1'] for row in catalog}) == 6 and
            set(known) == {row['sha1'] for row in catalog}, 'Netty cache catalog coverage differs')
    prior = {row['sha1']: row for row in scan['runtime_classpath_scan']['all_artifacts']}
    require(len(prior) == len(scan['runtime_classpath_scan']['all_artifacts']), 'duplicate runtime artifact')
    root.mkdir(parents=True, exist_ok=False)
    try:
        for library in catalog:
            identifier, version = library['sha1'], library['version']
            require(isinstance(identifier, str) and re.fullmatch(r'[a-f0-9]{40}', identifier) and
                    sni.affected_version(version), 'invalid Netty cache artifact identity')
            coordinate = 'io.netty:netty-handler:' + version
            matches = [row for row in inventory['netty_artifacts'] if row['coordinate'] == coordinate and
                       row['sha1'] == identifier and row['sha256'] == library['sha256']]
            require(len(matches) == 1, 'missing source-bound Mojang Netty artifact')
            artifact = matches[0]
            url = ('https://libraries.minecraft.net/io/netty/netty-handler/' + version +
                   '/netty-handler-' + version + '.jar')
            source = prior.get(identifier)
            require(source is not None and artifact['url'] == url and artifact['size'] == source['size_bytes'] and
                    source['sha256'] == library['sha256'] and coordinate in source['coordinates'],
                    'Mojang Netty source URL, size or identity differs')
            raw = fetch(url, artifact['size'])
            require(len(raw) == artifact['size'], 'downloaded Netty library size differs')
            sni.verify_known_cached_library(raw, library, known[identifier])
            path = (root / identifier).resolve()
            require(path.is_relative_to(root), 'Netty cache artifact path escapes root')
            with path.open('xb') as stream:
                stream.write(raw)
    except Exception:
        shutil.rmtree(root)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        _, priority, critical, scan, mod = sni.load_inputs()
        high = next(row for row in priority['advisories'] if row['advisory_id'] == sni.HIGH)
        catalog, _, _ = sni.bind_occurrences(high, critical, scan, mod)
        known = sni.known_hit_inventory(catalog)
        ref = scan['source_provenance']['netty_artifact_inventory']
        inventory = json.loads(sni.read(sni.ROOT, ref['path'], ref['sha256']), object_pairs_hook=unique_object)
        prepare_cache(args.output, catalog, known, scan, inventory, ipfilter.download_mojang_library)
        print('Prepared six independently verified Netty JARs for offline cache inspection')
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, BadZipFile) as exc:
        print('Netty cache acquisition incomplete: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
