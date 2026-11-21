from pathlib import Path
import json,os,shutil,subprocess,tempfile
coord=Path('/workspace/tprm-legacy-coordination');workspace=coord.parent;out=workspace/'.tprm-dryrun/wrapper-hardening-proposal-audits-20261114';heads=json.loads(Path('/tmp/tprm-current-hardening-heads.json').read_text());init='/tmp/tprm-graph-init/gradle-actions.github-dependency-graph.init.gradle';assert Path(init).is_file()
env={**os.environ,'JAVA_HOME':'/workspace/.toolchains/jdk25','JAVA_HOME_25_X64':'/workspace/.toolchains/jdk25','JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts -Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080','GITHUB_DEPENDENCY_GRAPH_ENABLED':'true','GITHUB_DEPENDENCY_GRAPH_JOB_ID':'local-20261114-final-proposal'}
for group in ('1.21.11','26.1-26.2','26.3'):
 h=heads[group];repo=Path(h['worktree']);sha=h['new_head'];branch=h['branch'];assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==sha
 if shutil.disk_usage(workspace).free<280*1024*1024:raise RuntimeError('insufficient disk before '+group)
 print('RESOLVE',group,sha,flush=True)
 with tempfile.TemporaryDirectory(prefix='tprm-final-proposal-',dir='/tmp') as temp:
  temp=Path(temp);src=temp/'source';src.mkdir();reports=temp/'reports';reports.mkdir();archive=temp/'source.tar';names=subprocess.check_output(['git','ls-tree','--name-only',sha],cwd=repo,text=True).splitlines();names=[n for n in names if n not in ('docs','.github')];subprocess.run(['git','archive','--format=tar','--output',str(archive),sha,'--',*names],cwd=repo,check=True);subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True);archive.unlink()
  subprocess.run(['python3',str(coord/'scripts/verify_gradle_wrapper.py'),'--root',str(src)],check=True)
  e={**env,'GITHUB_DEPENDENCY_GRAPH_JOB_CORRELATOR':'snapshot','GITHUB_DEPENDENCY_GRAPH_REF':'refs/heads/'+branch,'GITHUB_DEPENDENCY_GRAPH_SHA':sha,'GITHUB_DEPENDENCY_GRAPH_WORKSPACE':str(src),'DEPENDENCY_GRAPH_REPORT_DIR':str(reports)}
  with (out/(group+'-local-snapshot.log')).open('w') as log:p=subprocess.run(['./gradlew','--no-daemon','--console=plain','-I',init,':ForceDependencyResolutionPlugin_resolveAllDependencies'],cwd=src,env=e,stdout=log,stderr=subprocess.STDOUT)
  if p.returncode:raise RuntimeError('resolution failed '+group)
  snap=reports/'snapshot.json';d=json.loads(snap.read_text());assert d['sha']==sha and d['ref']=='refs/heads/'+branch;shutil.copyfile(snap,out/(group+'-local-snapshot.json'))
  props=dict(line.split('=',1) for line in (src/'gradle.properties').read_text().splitlines() if '=' in line and not line.startswith('#'))
 cache=Path('/home/agent/.gradle/caches/fabric-loom');version=props['minecraft_version']
 for generated in [cache/version,*((cache/'minecraftMaven/net/minecraft').glob('minecraft-*'+'/'+version+'-*'))]:
  if generated.is_dir():shutil.rmtree(generated)
 print('RESOLVED',group,flush=True)
 print('AUDIT',group,flush=True)
 with (out/(group+'-proposal-audit.log')).open('w') as log:p=subprocess.run(['python3','scripts/audit_maintenance_proposal.py','--snapshot',str(out/(group+'-local-snapshot.json')),'--source',str(repo),'--group',group,'--branch',branch,'--source-sha',sha,'--output',str(out/(group+'-proposal-report.json'))],cwd=coord,stdout=log,stderr=subprocess.STDOUT)
 report=json.loads((out/(group+'-proposal-report.json')).read_text());print('RESULT',group,'exit',p.returncode,'status',report['status'],'matches',len(report.get('matches',[])),flush=True)
 if p.returncode!=1 or report['status']!='complete-unreviewed-maintenance-proposal':raise RuntimeError('unexpected audit outcome '+group)
print('COMPLETE final unmerged maintenance proposals',flush=True)
