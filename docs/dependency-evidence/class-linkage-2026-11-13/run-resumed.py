from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json,os,shutil,subprocess,tempfile

workspace=Path('/workspace')
coord=workspace/'tprm-legacy-coordination'
output=workspace/'.tprm-dryrun/class-linkage-security'
audit_start=Path('/tmp/tprm-class-audit-start').stat().st_mtime_ns
output.mkdir(parents=True,exist_ok=True)
legacy=['1.14-1.14.4','1.15-1.16.5','1.17-1.19.2','1.19.3','1.19.4-1.20.4',
        '1.20.5-1.20.6','1.21-1.21.1','1.21.2-1.21.3','1.21.4-1.21.8','1.21.9-1.21.10']
integrated={'1.21.11':'177f5708727ae4c152091d185536aaa734063280',
            '26.1-26.2':'453cf35695cf07be4072f77895cdbafbed617870',
            '26.3':'226b1de7dd4e7c2a75ec35eef1697434462e4f54'}
env={**os.environ,'JAVA_HOME':'/workspace/.toolchains/jdk25','JAVA_HOME_25_X64':'/workspace/.toolchains/jdk25',
     'JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts '
     '-Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080',
     'GITHUB_DEPENDENCY_GRAPH_ENABLED':'true','GITHUB_DEPENDENCY_GRAPH_JOB_ID':'local-20261113-verifier-followup'}
init='/tmp/tprm-graph-init/gradle-actions.github-dependency-graph.init.gradle'
evidence_path=Path('/tmp/tprm-class-followup-candidate-evidence.json')
evidence=json.loads(evidence_path.read_text())['groups']
only=set(filter(None,os.environ.get('TPRM_AUDIT_GROUPS','').split(',')))
jobs=[]
for group in legacy+list(integrated):
    if only and group not in only:continue
    candidate=group in legacy
    repo=workspace/(('tprm-legacy-'+('1.14' if group=='1.14-1.14.4' else group)) if candidate else ('tprm-review-'+group))
    branch=('candidate/mc-' if candidate else 'mc/')+group
    sha=evidence[group]['candidate_head'] if candidate else integrated[group]
    jobs.append((group,candidate,repo,branch,sha))

def audit(group,candidate,repo,branch,sha,snapshot):
    report=output/(group+'-osv.json');log=output/(group+'-audit.log')
    if report.exists():
        existing=json.loads(report.read_text())
        if existing.get('source_sha')==sha and existing.get('status') not in (None,'incomplete'):
            print('ALREADY AUDITED',group,sha,flush=True)
            return 0
    if candidate:
        cmd=['python3','scripts/audit_candidate_dependencies.py','audit','--snapshot',str(snapshot),'--source',str(repo),
             '--group',group,'--branch',branch,'--source-sha',sha,'--output',str(report),'--evidence',str(evidence_path)]
    else:
        cmd=['python3','scripts/audit_dependencies.py','--snapshot',str(snapshot),'--branch',branch,
             '--source-sha',sha,'--output',str(report)]
    with log.open('w') as file:p=subprocess.run(cmd,cwd=coord,stdout=file,stderr=subprocess.STDOUT)
    print('AUDIT',group,'exit',p.returncode,'details',log,flush=True)
    return p.returncode

with ThreadPoolExecutor(max_workers=2) as pool:
    futures=[]
    for group,candidate,repo,branch,sha in jobs:
        snapshot=output/(group+'-snapshot.json')
        if group=='1.14-1.14.4' and not snapshot.exists():
            seed=Path('/tmp/tprm-graph-report-114/local-candidate-114.json')
            if seed.exists() and json.loads(seed.read_text()).get('sha')==sha:
                shutil.copyfile(seed,snapshot)
        if not snapshot.exists():
            if shutil.disk_usage(workspace).free < 190*1024*1024:
                print('STOP: insufficient free disk before',group,flush=True);break
            print('SNAPSHOT',group,sha,flush=True)
            with tempfile.TemporaryDirectory(prefix='tprm-audit-source-',dir='/tmp') as temp:
                temp=Path(temp);src=temp/'source';src.mkdir();out=temp/'reports';out.mkdir()
                archive=temp/'source.tar'
                # Documentation screenshots are not Gradle inputs and can be
                # very large; all other tracked source/build files come from
                # the exact commit being audited.
                names=subprocess.check_output(['git','ls-tree','--name-only',sha],cwd=repo,text=True).splitlines()
                names=[name for name in names if name not in ('docs','.github')]
                subprocess.run(['git','archive','--format=tar','--output',str(archive),sha,'--',*names],cwd=repo,check=True)
                subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True)
                archive.unlink()
                settings={**env,'GITHUB_DEPENDENCY_GRAPH_JOB_CORRELATOR':'snapshot',
                    'GITHUB_DEPENDENCY_GRAPH_REF':'refs/heads/'+branch,'GITHUB_DEPENDENCY_GRAPH_SHA':sha,
                    'GITHUB_DEPENDENCY_GRAPH_WORKSPACE':str(src),'DEPENDENCY_GRAPH_REPORT_DIR':str(out)}
                cmd=['./gradlew','--no-daemon','--console=plain','-I',init,'--refresh-dependencies',
                     ':ForceDependencyResolutionPlugin_resolveAllDependencies']
                log=output/(group+'-snapshot.log')
                with log.open('w') as file:p=subprocess.run(cmd,cwd=src,env=settings,stdout=file,stderr=subprocess.STDOUT)
                generated=out/'snapshot.json'
                if p.returncode or not generated.exists():
                    print('SNAPSHOT FAILED',group,'exit',p.returncode,'details',log,flush=True);continue
                raw=json.loads(generated.read_text())
                if raw.get('sha')!=sha or raw.get('ref')!='refs/heads/'+branch:
                    print('SNAPSHOT IDENTITY MISMATCH',group,flush=True);continue
                shutil.copyfile(generated,snapshot)
                props=dict(line.split('=',1) for line in (src/'gradle.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
            # Only re-downloadable Loom inputs, not source, test worlds, or results.
            cache=Path('/home/agent/.gradle/caches/fabric-loom')/props['minecraft_version']
            for name in ('minecraft-client.jar','minecraft-merged.jar','minecraft-server.jar','minecraft-extracted_server.jar'):
                p=cache/name
                if p.is_file() and p.stat().st_mtime_ns>audit_start:p.unlink()
            maven=Path('/home/agent/.gradle/caches/fabric-loom/minecraftMaven/net/minecraft')
            for kind in ('minecraft-merged','minecraft-merged-intermediary'):
                for p in (maven/kind).glob(props['minecraft_version']+'-*/*.jar*'):
                    if p.is_file() and p.stat().st_mtime_ns>audit_start:p.unlink()
        data=json.loads(snapshot.read_text())
        if data.get('sha')!=sha or data.get('ref')!='refs/heads/'+branch:
            print('STALE SNAPSHOT',group,flush=True);continue
        futures.append(pool.submit(audit,group,candidate,repo,branch,sha,snapshot))
    for f in futures:f.result()
print('Finished available source-bound snapshots and OSV audits',flush=True)
