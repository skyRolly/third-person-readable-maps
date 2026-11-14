"""Record actual target properties and separate proposed 1.0.0 artifacts."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
HERE = Path(__file__).resolve().parent


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True)


def properties(text):
    return dict(line.split('=', 1) for line in text.splitlines()
                if '=' in line and not line.startswith('#'))


def main():
    builds = json.loads((ROOT / 'docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups']
    refs = json.loads((ROOT / 'docs/source-head-transition-2026-11-13.json').read_text())['groups']
    candidates = json.loads((ROOT / 'docs/legacy-candidate-evidence.json').read_text())['groups']
    runtime = json.loads((ROOT / 'docs/runtime-smoke-verifier-followup-2026-11-13/index.json').read_text())['versions']
    manifest = json.loads((ROOT / 'docs/legacy-dry-run-1.0.0-2026-11-14/release-manifest.json').read_text())
    groups = {row['id']: row for row in manifest['groups']}
    prs = {'1.21.11': 31, '26.1-26.2': 32, '26.3': 33}
    rows = {}
    for group, entry in sorted(groups.items()):
        target = 'mc/' + group
        ref = 'refs/remotes/origin/' + target
        target_head = git(ROOT, 'rev-parse', ref).strip()
        actual = properties(git(ROOT, 'show', target_head + ':gradle.properties'))
        if group in candidates:
            repo = WORKSPACE / ('tprm-legacy-' + ('1.14' if group == '1.14-1.14.4' else group))
            number = int(candidates[group]['pull_request'].rstrip('/').split('/')[-1])
            status = 'placeholder target; intended port remains unmerged'
        else:
            repo = WORKSPACE / ('tprm-review-' + group)
            number = prs[group]
            status = 'integrated maintenance target; 1.0.0 proposal remains unmerged'
        head = refs[group]['new_head']
        proposed = properties(git(repo, 'show', head + ':gradle.properties'))
        assert proposed['mod_version'] == '1.0.0' and entry['source_commit'] == head
        assert entry['sha256'] == builds[group]['sha256']
        assert all(runtime[v]['source_commit'] == head and runtime[v]['artifact_sha256'] == entry['sha256']
                   for v in entry['minecraft'])
        rows[group] = {'target_branch': target, 'target_head': target_head,
                       'target_mod_version': actual['mod_version'],
                       'target_minecraft_version': actual['minecraft_version'], 'target_status': status,
                       'proposed_head': head, 'proposed_mod_version': proposed['mod_version'],
                       'pull_request': 'https://github.com/skyRolly/third-person-readable-maps/pull/' + str(number),
                       'artifact': entry['artifact'], 'sha256': entry['sha256'],
                       'advertised_versions': entry['minecraft'], 'local_world_observations': len(entry['minecraft'])}
    data = {'schema': 1, 'observed_on': '2026-11-14',
            'note': 'Remote targets are observations, not proposed PR results; no target was modified by this inventory.',
            'groups': rows}
    (HERE / 'index.json').write_text(json.dumps(data, indent=2) + '\n')
    lines = ['# 1.0.0 version consistency — 2026-11-14', '',
             'The table distinguishes actual remote target properties from unmerged proposed heads. Every proposed artifact is 1.0.0; its hash was checked in the candidate rehearsal and its declared versions completed local-world startup and short walking observations. Full graphical acceptance, security dispositions and integration remain open.', '',
             '| Target/group | Current remote Mod / Minecraft property | Proposed Mod | Proposed artifact SHA-256 | Local-world smoke |',
             '|---|---|---|---|---|']
    for group, row in rows.items():
        lines.append(f"| [{group}]({row['pull_request']}) | {row['target_mod_version']} / {row['target_minecraft_version']} | {row['proposed_mod_version']} | `{row['sha256']}` | {row['local_world_observations']}/{len(row['advertised_versions'])} |")
    lines += ['', 'The ten legacy targets are placeholders containing the 1.21.11 baseline, not integrated legacy ports. The three existing maintenance targets are integrated at 0.0.2. The proposed 1.0.0 heads and expected post-integration versions are not current target states. See the [source and artifact index](index.json), [48-version matrix](../compatibility-1.0.0-validation.md), and [release gates](../release-readiness-1.0.0.md).', '', 'No 1.0.0 tag, draft release or public release was created.']
    (HERE / 'README.md').write_text('\n'.join(lines) + '\n')
    print('Recorded current and proposed versions for', len(rows), 'groups')


if __name__ == '__main__':
    main()
