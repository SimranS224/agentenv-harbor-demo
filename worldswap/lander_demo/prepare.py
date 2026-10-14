"""One bounded no-key coding attempt, independent of the reusable landing task."""
import uuid,json,difflib
from pathlib import Path
from .util import ROOT,build,cmd,digest
from .codex_agent import preflight,run_codex

def prepare(mode='controls'):
 if mode=='codex':preflight()
 image=build();out=ROOT/'artifacts'/('repair-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
 name='ae-worldswap-code-'+uuid.uuid4().hex[:8]
 cmd(['docker','run','-d','--name',name,'--network','none','--memory','256m','--cpus','1','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges',image])
 before=(ROOT/'engine/controller.py').read_text()
 try:
  cmd(['docker','cp',str(ROOT/'worlds'),name+':/app/worlds'])
  cmd(['docker','exec',name,'chmod','-R','a+rwX','/app/src'])
  if mode=='codex':
   def execute(command,timeout):
    p=cmd(['docker','exec','--user','65534:65534','-w','/app',name,'timeout','-s','KILL',str(max(1,int(timeout))),'sh','-c',command],check=False,timeout=timeout+3)
    return {'exit_code':p.returncode,'stdout':p.stdout[:10000],'stderr':p.stderr[:2000]}
   agent=run_codex((ROOT/'task/instruction.md').read_text(),execute,out/'trace.jsonl',timeout=60)
   cmd(['docker','stop','-t','1',name]);cmd(['docker','start',name])
   cmd(['docker','cp',name+':/app/src/controller.py',str(out/'controller.py')])
  else:
   source=before.replace("(target_vx - s['vx']) * 2.5,","(target_vx - s['vx']) * 2.5 - s['wind'],").replace("80 + (target_vy","s['gravity'] + (target_vy")
   (out/'controller.py').write_text(source);agent={'model':None,'status':'scripted reference'}
 finally:cmd(['docker','rm','-f',name],check=False)
 after=(out/'controller.py').read_text()
 (out/'repair.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='before/controller.py',tofile='after/controller.py')))
 (out/'agent.json').write_text(json.dumps(agent,indent=2));(ROOT/'artifacts/latest-controller.txt').write_text(str(out/'controller.py'))
 print('Controller:',out/'controller.py',flush=True)
if __name__=='__main__':
 import sys
 prepare(sys.argv[1] if len(sys.argv)>1 else 'controls')
