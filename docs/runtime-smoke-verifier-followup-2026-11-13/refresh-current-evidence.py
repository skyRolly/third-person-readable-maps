"""Refresh the proposed candidate inventory from retained, source-bound evidence."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs'
HISTORY = DOCS / 'historical-verifier-followup-2026-11-13'
current = json.loads((HISTORY / 'legacy-candidate-evidence.json').read_text())
inventory = json.loads((HISTORY / 'legacy-version-inventory.json').read_text())
refs = json.loads((DOCS / 'source-head-transition-2026-11-13.json').read_text())['groups']
builds = json.loads((DOCS / 'builds-verifier-followup-2026-11-13/index.json').read_text())['groups']
runtime = json.loads((DOCS / 'runtime-smoke-verifier-followup-2026-11-13/index.json').read_text())['versions']
manifest = json.loads((DOCS / 'legacy-dry-run-1.0.0/release-manifest.json').read_text())
manifest_groups = {group['id']: group for group in manifest['groups']}
negatives = json.loads((DOCS / 'negative-verifier-followup-2026-11-13/index.json').read_text())
current['observed_on'] = '2026-11-13'
current['static_checks_observed_on'] = '2026-11-13'
current['previous_1.0.0_evidence'] = 'docs/historical-verifier-followup-2026-11-13/legacy-candidate-evidence.json'
by_version = {}
for group, entry in current['groups'].items():
    ref, build, proposed = refs[group], builds[group], manifest_groups[group]
    assert build['source_commit'] == ref['new_head'] == proposed['source_commit']
    assert build['sha256'] == proposed['sha256'] and entry['versions'] == proposed['minecraft']
    entry.update(source_commit=ref['new_head'], candidate_head=ref['new_head'], sha256=build['sha256'],
                 static_linkage='PASS: exact-head hosted CI and instruction-aware checks on every declared version; verifier limits remain',
                 client_startup='NOT RUN: no new-source installed-client observation recorded for this version',
                 graphical='NOT RUN: full graphical acceptance of the current 1.0.0 artifact remains required')
    entry['limitations'] = ['Static verification is not a complete JVM bytecode verifier or graphical acceptance',
                            'Independent human visual acceptance, hardware-GPU and multiplayer testing remain outstanding',
                            'Candidate has not been integrated or admitted to strict release configuration',
                            'Security findings and administrative approval gates remain unresolved',
                            'Earlier map-ID and rendering-state probes retain their previous source identities']
    group_negatives = [row for row in negatives.values() if row['group'] == group]
    entry['negative'] = ('; '.join(row['group'] + ' on ' + row['unsupported_version'] +
                                  ' rejected (exit ' + str(row['exit_code']) + '): ' + row['tail'][-1]
                                  for row in group_negatives) if group_negatives else
                         'See the current adjacent-version negative-control index; no new case is claimed for this group')
    entry['per_version'] = {}
    for version in entry['versions']:
        row = runtime.get(version)
        if row:
            assert row['group'] == group and row['source_commit'] == ref['new_head'] and row['artifact_sha256'] == build['sha256']
            movement = json.loads((DOCS / 'runtime-smoke-verifier-followup-2026-11-13' / version / 'movement.json').read_text())
            entry['per_version'][version] = {
                'client_startup': 'PASS: installed 1.0.0 JAR joined a local world using Fabric 0.20.1, the required Java runtime, and Linux Xorg/Mesa software rendering',
                'graphical': 'PARTIAL: automated walking screenshots captured; independent visual assessment and full graphical acceptance NOT RUN',
                'movement_diagnostic': f"Local walking distance {movement['horizontal_distance']:.2f} blocks; evidence retained in docs/runtime-smoke-verifier-followup-2026-11-13/{version}/",
                'movement_observed_on': row['observed_on']}
        by_version[version] = (group, entry, entry['per_version'].get(version, {}))
(DOCS / 'legacy-candidate-evidence.json').write_text(json.dumps(current, indent=2) + '\n')
for row in inventory['versions']:
    group, entry, specific = by_version[row['minecraft']]
    for key in ('static_linkage', 'client_startup', 'graphical'):
        row[key] = specific.get(key, entry[key])
    row['fabric_loader_runtime_verification'] = ('PARTIAL: installed 1.0.0 JAR joined a Linux local world; full runtime acceptance NOT RUN'
        if row['client_startup'].startswith('PASS') else 'NOT RUN: no recorded installed-client startup on the advanced source head')
    for key in ('movement', 'lighting', 'movement_diagnostic'):
        row.pop(key, None)
    if 'movement_diagnostic' in specific:
        row['movement_diagnostic'] = specific['movement_diagnostic']
inventory['caveat'] = 'Version metadata and static linkage do not establish full runtime or graphical acceptance or integrated support. Earlier 1.0.0 and historical 0.0.2 evidence retain their original source identities.'
(DOCS / 'legacy-version-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
lines = ['# Legacy stable-version inventory', '',
         'The current proposed version is **1.0.0**. The [machine-readable inventory](legacy-version-inventory.json) records Mojang metadata and current source-bound status. The prior [1.0.0 snapshot](historical-verifier-followup-2026-11-13/) and [0.0.2 evidence](historical-0.0.2-2026-11-05/) remain historical. Candidate ports are not integrated.', '',
         '| Minecraft | Group | Java | Static 1.0.0 | Installed 1.0.0 | Graphical 1.0.0 |', '|---|---|---:|---|---|---|']
for row in inventory['versions']:
    group, entry, specific = by_version[row['minecraft']]
    startup = 'PASS (local world)' if row['client_startup'].startswith('PASS') else 'NOT RUN'
    visual = 'PARTIAL diagnostic' if row['graphical'].startswith('PARTIAL') else 'NOT RUN'
    lines.append(f"| {row['minecraft']} | {group} | {row['java']['majorVersion']} | PASS | {startup} | {visual} |")
lines += ['', 'Static checks do not establish complete JVM linkage or graphical acceptance. See the [review handoff](legacy-review-handoff.md) for current source heads and limitations.']
(DOCS / 'legacy-version-inventory.md').write_text('\n'.join(lines) + '\n')
lines = ['# Legacy candidate review handoff', '',
         'All ten proposed legacy implementations remain draft PRs against placeholder `mc/*` branches. They are not integrated or release-ready. The coordinated proposed mod version is **1.0.0**; actual integrated branches remain 0.0.2 pending their separate reviewed PRs. No coordinated release has been published.', '',
         'All 42 legacy versions passed instruction-aware verification on the advanced proposed heads, with remaining JVM limits in the [review matrix](review-resolution-1.0.0.md). The [current per-version inventory](legacy-version-inventory.md), [candidate evidence](legacy-candidate-evidence.json), [prior 1.0.0 snapshot](historical-verifier-followup-2026-11-13/) and [historical 0.0.2 evidence](historical-0.0.2-2026-11-05/) retain separate identities.', '',
         '| Group | Draft PR | Proposed source HEAD | 1.0.0 JAR SHA-256 | New-head installed coverage |', '|---|---|---|---|---|']
for group, entry in sorted(current['groups'].items()):
    starts = sum(row.get('client_startup', '').startswith('PASS') for row in entry['per_version'].values())
    lines.append(f"| {group} | [PR]({entry['pull_request']}) | `{entry['candidate_head']}` | `{entry['sha256']}` | {starts}/{len(entry['versions'])} partial local-world evidence |")
lines += ['', 'Earlier controlled map-ID and 1.14 texture/lighting probes are retained with their prior source heads. All 19 component-era game codecs converted the tested malformed numeric values to zero in the [isolated codec sweep](dependency-evidence/component-mapid-codec-2026-11-13/); a [1.21.11 local-world probe](component-map-id-item-loading-2026-11-13/host-inventory-attempt/) also observed the item-loading path. Other paths and a bounded remedy remain open. Historical candidate/no-mod [foreground comparisons](foreground-comparisons-2026-11-13/) did not reproduce the large shape, but the original conditions were not reproduced and its cause remains unresolved.', '',
          'Do not activate Dependabot for a placeholder. Candidate dependency monitoring must stay source-pinned; activation, authoritative release admission, runtime acceptance, security dispositions and independent approvals are separate gates. See the [48-version matrix](compatibility-1.0.0-validation.md), [PR handoff](pr-integration-handoff-1.0.0.md) and [release gates](release-readiness-1.0.0.md).']
(DOCS / 'legacy-review-handoff.md').write_text('\n'.join(lines) + '\n')
lines = ['# Proposed 1.0.0 compatibility and validation matrix', '',
         'This non-publishing matrix describes proposed heads, not integrated legacy support or a release claim. All 13 product heads passed hosted Linux and Windows checks; clean local JAR hashes are recorded below. New-head installed-client evidence is partial, and earlier source-bound observations remain [historical](runtime-smoke-1.0.0/).', '',
         '| Minecraft | Group | 1.0.0 artifact SHA-256 | Static | Installed startup | Graphical evidence | Remaining |', '|---|---|---|---|---|---|---|']
for group in manifest['groups']:
    for version in group['minecraft']:
        observed = version in runtime
        if observed:
            assert runtime[version]['source_commit'] == group['source_commit'] and runtime[version]['artifact_sha256'] == group['sha256']
        remaining = ('Full visual, hardware-GPU, multiplayer and independent review' if observed else
                     'New-head startup, full visual, hardware-GPU, multiplayer and independent review')
        lines.append(f"| {version} | {group['id']} | `{group['sha256']}` | PASS | {'PASS (local world)' if observed else 'NOT RUN'} | {'PARTIAL diagnostic' if observed else 'NOT RUN'} | {remaining} |")
lines += ['', 'The [new-head runtime index](runtime-smoke-verifier-followup-2026-11-13/) records exactly which local observations are complete. The [review matrix](review-resolution-1.0.0.md) records verifier limits, the component-era malformed-ID boundary and the unresolved foreground-shape investigation.']
(DOCS / 'compatibility-1.0.0-validation.md').write_text('\n'.join(lines) + '\n')
print('Refreshed', len(current['groups']), 'candidate source pins and', len(inventory['versions']), 'legacy-version rows')
