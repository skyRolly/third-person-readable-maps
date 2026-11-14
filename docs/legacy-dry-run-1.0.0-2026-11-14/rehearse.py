from pathlib import Path
import copy,json,os,shutil,subprocess,sys,tempfile

coord=Path('/workspace/tprm-legacy-coordination')
sys.path.insert(0,str(coord/'scripts'))
import release,release_github
out=Path(os.environ.get('TPRM_REHEARSAL_DIR','/workspace/.tprm-dryrun/rehearsal-20261114'))
assert not out.exists(), 'preserve previous rehearsal if present'
out.mkdir(parents=True)
cfg=json.loads(Path('/workspace/.tprm-dryrun/expanded-config.json').read_text())
evidence_path=Path(os.environ.get('TPRM_REHEARSAL_EVIDENCE',str(coord/'docs/legacy-candidate-evidence.json')))
artifact_root=os.environ.get('TPRM_REHEARSAL_ARTIFACTS')
legacy=json.loads(evidence_path.read_text())['groups']
coordinator=subprocess.check_output(['git','rev-parse','HEAD'],cwd=coord,text=True).strip()
changes=['Prepare the coordinated 1.0.0 mod version and readable-map corrections']
heads={}
for group in cfg['groups']:
    if group in legacy:
        root=Path('/workspace')/('tprm-legacy-'+('1.14' if group=='1.14-1.14.4' else group))
        branch='candidate/mc-'+group
        assert legacy[group]['versions']==cfg['groups'][group]['minecraft']
    else:
        root=Path('/workspace/tprm-review-'+group)
        branch='maintenance/mc-'+group+'-1.0.0'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if group in legacy:assert sha==legacy[group]['candidate_head']
    heads[group]=(branch,sha)
    dest=out/'artifacts'/group;dest.mkdir(parents=True)
    jar=(Path(artifact_root)/group if artifact_root else root/'build/libs')/f'third-person-readable-maps-1.0.0-mc{group}.jar'
    shutil.copyfile(jar,dest/jar.name)
plan={'schema':1,'version':'1.0.0','release_date':'2026-11-14','changes':changes,
      'known_limitations':['Non-publishing candidate rehearsal; runtime, security, review and administrative gates remain open'],
      'groups':{g:{'source_branch':b,'commit':s,'verified_changes':changes,'runtime_evidence':{}} for g,(b,s) in heads.items()}}
config_file=out/'candidate-compatibility.json';plan_file=out/'candidate-plan.json'
config_file.write_text(json.dumps(cfg,indent=2)+'\n');plan_file.write_text(json.dumps(plan,indent=2)+'\n')
cfg,plan=release.load_plan(plan_file,candidate=True,config_path=config_file)
assert len(cfg['groups'])==13 and len({v for x in cfg['groups'].values() for v in x['minecraft']})==48
(out/'candidate-matrix.json').write_text(json.dumps(release.matrix(cfg,plan),indent=2)+'\n')
release.verify_sources(cfg,plan)
release.aggregate(cfg,plan,out/'artifacts',out/'bundle',candidate=True,coordinator_sha=coordinator)
subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=out/'bundle',check=True)
checks={}
with tempfile.TemporaryDirectory(prefix='tprm-negative-rehearsal-') as tmp:
    tmp=Path(tmp)
    def reject(name,fn):
        try:fn()
        except (release.Invalid,ValueError,OSError) as exc:
            checks[name]=str(exc);print('REJECTED',name,str(exc),flush=True)
        else:raise RuntimeError(name+' was accepted')
    def check_plan(name,data,candidate=True):
        path=tmp/(name+'.json');path.write_text(json.dumps(data));release.load_plan(path,candidate=candidate,config_path=config_file)
    bad=copy.deepcopy(plan);bad['groups'].pop('1.14-1.14.4')
    reject('missing-group',lambda:check_plan('missing',bad))
    bad=copy.deepcopy(plan);bad['version']='0.0.2'
    reject('wrong-mod-version',lambda:check_plan('wrong-version',bad))
    bad=copy.deepcopy(plan);bad['groups']['1.14-1.14.4']['source_branch']='candidate/mc-1.21.11'
    reject('wrong-candidate-source',lambda:check_plan('wrong-source',bad))
    bad=copy.deepcopy(plan)
    for group in bad['groups']:bad['groups'][group]['source_branch']=cfg['groups'][group]['branch']
    reject('missing-strict-runtime-evidence',lambda:check_plan('missing-runtime',bad,False))
    reject('candidate-publication',lambda:release_github.verified_files(cfg,plan,out/'bundle',coordinator))
    artifacts=tmp/'artifacts';shutil.copytree(out/'artifacts',artifacts)
    group='1.14-1.14.4';original=next((artifacts/group).glob('*.jar'))
    shutil.copyfile(original,original.with_name('duplicate.jar'))
    reject('duplicate-artifact',lambda:release.aggregate(cfg,plan,artifacts,tmp/'duplicate-output',True,coordinator))
    original=(out/'artifacts'/group/next((out/'artifacts'/group).glob('*.jar')).name)
    wrong=copy.deepcopy(cfg['groups'][group]);wrong['minecraft']=['1.14.4']
    reject('wrong-game-metadata',lambda:release.inspect_jar(original,'1.0.0',group,wrong))
    wrong=copy.deepcopy(cfg['groups'][group]);wrong['namespace']='official'
    reject('wrong-namespace',lambda:release.inspect_jar(original,'1.0.0',group,wrong))
    mixed=tmp/original.name
    shutil.copyfile('/workspace/.tprm-dryrun/bundle-expanded/third-person-readable-maps-0.0.2-mc1.14-1.14.4.jar',mixed)
    reject('mixed-0.0.2-and-1.0.0-artifacts',lambda:release.inspect_jar(mixed,'1.0.0',group,cfg['groups'][group]))
    classifier=tmp/'third-person-readable-maps-1.0.0-mcWRONG.jar'
    shutil.copyfile(original,classifier)
    reject('wrong-artifact-classifier',lambda:release.inspect_jar(classifier,'1.0.0',group,cfg['groups'][group]))
    badcfg=copy.deepcopy(cfg);badcfg['groups'][group]['minecraft'].append(badcfg['groups'][group]['minecraft'][0])
    badcfg_path=tmp/'duplicate-game-version.json';badcfg_path.write_text(json.dumps(badcfg))
    reject('duplicate-game-version',lambda:release.load_plan(plan_file,candidate=True,config_path=badcfg_path))
    badcfg=copy.deepcopy(cfg);badcfg['groups']['1.15-1.16.5']['minecraft'].append('1.14')
    badcfg_path=tmp/'overlapping-game-version.json';badcfg_path.write_text(json.dumps(badcfg))
    reject('overlapping-game-version',lambda:release.load_plan(plan_file,candidate=True,config_path=badcfg_path))
    p=subprocess.run(['python3',str(coord/'scripts/release.py'),'validate','--plan',str(plan_file),
                      '--candidate-config',str(config_file)],capture_output=True,text=True)
    assert p.returncode!=0 and '--candidate-config requires --candidate' in (p.stdout+p.stderr)
    checks['strict-rejects-candidate-config']='strict CLI rejected the candidate-only configuration'
    print('REJECTED strict-rejects-candidate-config',flush=True)
    different=tmp/'changed-bundle';shutil.copytree(out/'bundle',different)
    target=next(different.glob('*.jar'));target.write_bytes(target.read_bytes()+b'changed')
    p=subprocess.run(['sha256sum','--check','SHA256SUMS'],cwd=different,capture_output=True,text=True)
    assert p.returncode!=0
    checks['changed-artifact-after-checksum']='sha256sum --check rejected modified bundle artifact'
    print('REJECTED changed-artifact-after-checksum',flush=True)
    bad=copy.deepcopy(plan);bad['groups']['1.14-1.14.4']['commit']='f'*40
    reject('wrong-remote-source-commit',lambda:release.verify_sources(cfg,bad))
(out/'negative-controls.json').write_text(json.dumps(checks,indent=2)+'\n')
print('REHEARSAL COMPLETE',len(cfg['groups']),'groups; 48 versions; coordinator',coordinator,flush=True)
