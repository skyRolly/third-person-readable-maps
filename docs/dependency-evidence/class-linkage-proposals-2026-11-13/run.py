from pathlib import Path
import json,os,shutil,subprocess,tempfile

coord=Path('/workspace/tprm-legacy-coordination')
out=Path('/workspace/.tprm-dryrun/class-linkage-proposal-security')
audit_start=Path('/tmp/tprm-class-audit-start').stat().st_mtime_ns
out.mkdir(parents=True,exist_ok=True)
env={**os.environ,'JAVA_HOME':'/workspace/.toolchains/jdk25','JAVA_HOME_25_X64':'/workspace/.toolchains/jdk25',
     'JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts '
     '-Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080',
     'GITHUB_DEPENDENCY_GRAPH_ENABLED':'true','GITHUB_DEPENDENCY_GRAPH_JOB_ID':'local-20261113-verifier-followup'}
init='/tmp/tprm-graph-init/gradle-actions.github-dependency-graph.init.gradle'
for group in ('1.21.11','26.1-26.2','26.3'):
    repo=Path('/workspace/tprm-review-'+group)
    branch='maintenance/mc-'+group+'-1.0.0'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    snap=out/(group+'-snapshot.json');report=out/(group+'-osv.json')
    if not snap.exists():
        if shutil.disk_usage('/workspace').free<220*1024*1024:raise RuntimeError('Insufficient disk before '+group)
        print('SNAPSHOT proposal',group,sha,flush=True)
        with tempfile.TemporaryDirectory(prefix='tprm-proposal-audit-',dir='/tmp') as temp:
            tmp=Path(temp);src=tmp/'source';src.mkdir();reports=tmp/'reports';reports.mkdir();archive=tmp/'source.tar'
            names=subprocess.check_output(['git','ls-tree','--name-only',sha],cwd=repo,text=True).splitlines()
            names=[n for n in names if n not in ('docs','.github')]
            subprocess.run(['git','archive','--format=tar','--output',str(archive),sha,'--',*names],cwd=repo,check=True)
            subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True);archive.unlink()
            settings={**env,'GITHUB_DEPENDENCY_GRAPH_JOB_CORRELATOR':'snapshot',
                      'GITHUB_DEPENDENCY_GRAPH_REF':'refs/heads/'+branch,'GITHUB_DEPENDENCY_GRAPH_SHA':sha,
                      'GITHUB_DEPENDENCY_GRAPH_WORKSPACE':str(src),'DEPENDENCY_GRAPH_REPORT_DIR':str(reports)}
            log=Path('/tmp/tprm-class-proposal-snapshot-'+group+'.log')
            with log.open('w') as file:
                p=subprocess.run(['./gradlew','--no-daemon','--console=plain','-I',init,'--refresh-dependencies',
                                  ':ForceDependencyResolutionPlugin_resolveAllDependencies'],cwd=src,env=settings,
                                 stdout=file,stderr=subprocess.STDOUT)
            if p.returncode or not (reports/'snapshot.json').exists():
                print('SNAPSHOT FAILED',group,p.returncode,'see',log,flush=True);continue
            data=json.loads((reports/'snapshot.json').read_text())
            assert data['ref']=='refs/heads/'+branch and data['sha']==sha
            shutil.copyfile(reports/'snapshot.json',snap)
            props=dict(line.split('=',1) for line in (src/'gradle.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
        cache=Path('/home/agent/.gradle/caches/fabric-loom')/props['minecraft_version']
        for name in ('minecraft-client.jar','minecraft-merged.jar','minecraft-server.jar','minecraft-extracted_server.jar'):
            p=cache/name
            if p.is_file() and p.stat().st_mtime_ns>audit_start:p.unlink()
        maven=Path('/home/agent/.gradle/caches/fabric-loom/minecraftMaven/net/minecraft')
        for kind in ('minecraft-merged','minecraft-merged-intermediary','minecraft-merged-deobf'):
            for p in (maven/kind).glob(props['minecraft_version']+'*/*.jar*'):
                if p.is_file() and p.stat().st_mtime_ns>audit_start:p.unlink()
    data=json.loads(snap.read_text());assert data['ref']=='refs/heads/'+branch and data['sha']==sha
    if not report.exists():
        log=Path('/tmp/tprm-class-proposal-audit-'+group+'.log')
        with log.open('w') as file:
            p=subprocess.run(['python3','scripts/audit_maintenance_proposal.py','--snapshot',str(snap),'--source',str(repo),
                              '--group',group,'--branch',branch,'--source-sha',sha,'--output',str(report)],
                             cwd=coord,stdout=file,stderr=subprocess.STDOUT)
        print('AUDIT proposal',group,'exit',p.returncode,'see',log,flush=True)
    else:print('Existing source-bound proposal report',group,flush=True)
print('Finished maintenance proposal scans',flush=True)
