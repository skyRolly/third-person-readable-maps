from pathlib import Path
from zipfile import ZipFile
import hashlib,json,os,shutil,subprocess,tempfile

workspace=Path('/workspace');refs=json.loads((workspace/'.minecraft-test-class-linkage-heads.json').read_text())
out=workspace/'.tprm-dryrun/class-linkage-builds';out.mkdir(parents=True,exist_ok=True)
result_file=out/'index.json'; results=json.loads(result_file.read_text()) if result_file.exists() else {}
env={**os.environ,'JAVA_HOME':'/workspace/.toolchains/jdk25','JAVA_HOME_25_X64':'/workspace/.toolchains/jdk25',
     'JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/etc/ssl/certs/java/cacerts '
     '-Dhttps.proxyHost=proxy -Dhttps.proxyPort=8080 -Dhttp.proxyHost=proxy -Dhttp.proxyPort=8080'}
for group,ref in refs.items():
    repo=workspace/('tprm-review-'+group if group in ('1.21.11','26.1-26.2','26.3') else 'tprm-legacy-'+('1.14' if group=='1.14-1.14.4' else group))
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==ref['new_head']
    if group in results:
        existing=out/group/results[group]['artifact']
        assert results[group]['source_commit']==ref['new_head'] and hashlib.sha256(existing.read_bytes()).hexdigest()==results[group]['sha256']
        print('ALREADY BUILT',group,flush=True); continue
    if shutil.disk_usage(workspace).free < 300*1024*1024:raise RuntimeError('Insufficient free space before '+group)
    print('BUILD',group,ref['new_head'],flush=True)
    with tempfile.TemporaryDirectory(prefix='tprm-class-build-',dir='/tmp') as temp:
        temp=Path(temp);src=temp/'source';src.mkdir();archive=temp/'source.tar'
        names=subprocess.check_output(['git','ls-tree','--name-only',ref['new_head']],cwd=repo,text=True).splitlines()
        names=[name for name in names if name not in ('docs','.github')]
        subprocess.run(['git','archive','--format=tar','--output',str(archive),ref['new_head'],'--',*names],cwd=repo,check=True)
        subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True);archive.unlink()
        log=out/(group+'-build.log')
        with log.open('w') as file:
            p=subprocess.run(['./gradlew','--no-daemon','--console=plain','clean','build'],cwd=src,env=env,stdout=file,stderr=subprocess.STDOUT)
        if p.returncode:
            print('BUILD FAILED',group,log.read_text(errors='replace')[-3000:],flush=True)
            raise SystemExit(p.returncode)
        name='third-person-readable-maps-1.0.0-mc'+group+'.jar';jar=src/'build/libs'/name
        assert jar.is_file(),name
        with ZipFile(jar) as z:
            metadata=json.loads(z.read('fabric.mod.json'))
            assert metadata['version']=='1.0.0' and metadata['id']=='thirdpersonreadablemaps'
        digest=hashlib.sha256(jar.read_bytes()).hexdigest();target=out/group;target.mkdir(exist_ok=True)
        shutil.copyfile(jar,target/name)
        results[group]={'source_commit':ref['new_head'],'branch':ref['branch'],'artifact':name,'sha256':digest,
                        'same_as_previous':digest==ref['artifact_sha256_before_rebuild'],
                        'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
        result_file.write_text(json.dumps(results,indent=2)+'\n')
        print('BUILT',group,digest,'same-as-previous',results[group]['same_as_previous'],flush=True)
print('Built',len(results),'exact committed source heads',flush=True)
