from pathlib import Path
import json,runpy,sys,traceback
repo,jar,version,output=sys.argv[1:5]
sys.path.insert(0,str(Path(repo)/'scripts'))
import jvm_linkage as jvm
original=jvm.validate_use;events=[];calls=0
def traced(use,caller,lookup):
 global calls
 result=original(use,caller,lookup);calls+=1
 resolved=jvm.resolve_member(use['owner'],use['kind'],use['name'],use['descriptor'],lookup)
 if resolved:
  declared,_,member=resolved
  if member['access'] & 4:
   events.append({'caller':caller,'owner':use['owner'],'declared':declared,'kind':use['kind'],
                  'name':use['name'],'descriptor':use['descriptor'],'operation':use['operation'],
                  'same_package':caller.rpartition('/')[0]==declared.rpartition('/')[0],
                  'static':bool(member['access'] & 8)})
 return result
jvm.validate_use=traced
sys.argv=[str(Path(repo)/'scripts/verify_supported_apis.py'),'--jar',jar,'--versions',version]
code=1
try:
 try:runpy.run_path(sys.argv[0],run_name='__main__');code=0
 except SystemExit as exc:code=exc.code if isinstance(exc.code,int) else 1
except BaseException:
 traceback.print_exc();code=1
unique={json.dumps(e,sort_keys=True) for e in events}
Path(output).write_text(json.dumps({'version':version,'exit_code':code,'validated_uses':calls,'protected_uses':[json.loads(e) for e in sorted(unique)]},indent=2)+'\n')
sys.exit(code)
