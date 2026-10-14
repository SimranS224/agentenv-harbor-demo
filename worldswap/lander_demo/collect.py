import json,hashlib
from pathlib import Path
from agent_env.task.task import Task
from .util import ROOT,digest

def collect():
 reg=json.loads((ROOT/'artifacts/registry.json').read_text());task=Task.get(reg['task_id'],reg['task_version'])
 current=hashlib.sha256(json.dumps(task.to_dict(),sort_keys=True).encode()).hexdigest()
 assert current==reg['task_sha256'],'Stored task changed'
 rows=[]
 for p in sorted((ROOT/'artifacts/contexts'/reg['batch']).glob('*.json')):
  c=json.loads(p.read_text())
  if not c.get('metadata',{}).get('flight_artifact'):continue
  d=c['metadata']['flights']
  assert d['controller_id']==reg['controller_id'] and d['controller_version']==reg['controller_version']
  assert d['controller_sha256']==reg['controller_sha256']
  assert d['verifier_sha256']==reg['verifier_sha256']
  expected=next(e for e in reg['environments'] if e['id']==d['env_id'])
  assert d['env_version']==expected['version'] and d['world']==expected['world']
  inst=Task.get_instance(c['instance_id']);assert inst.task_version==reg['task_version']
  d['task_version']=inst.task_version;rows.append(d)
 assert len(rows)==3 and len({r['env_id'] for r in rows})==3
 agent_path=Path((ROOT/'artifacts/latest-controller.txt').read_text()).parent/'agent.json'
 agent=json.loads(agent_path.read_text())
 agent.pop('thread_id',None);agent.pop('turn_id',None)
 report={'coding_agent':agent,'registry':reg,'task_unchanged':True,'flights':rows}
 (ROOT/'artifacts/comparison.json').write_text(json.dumps(report,indent=2))
 print('PROVEN: one stored task version, one controller artifact, one verifier, three registered environment IDs.')
if __name__=='__main__':collect()
