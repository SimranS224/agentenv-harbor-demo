"""Register independent envs, a controller artifact, and ONE parameterized task."""
import json,hashlib,uuid
from pathlib import Path
from agent_env.task.task import Task
from agent_env.task_step.registry import get_task_step_registry
from agent_env.artifact.artifacts.file import FileArtifact
from .environment import PhysicsWorld
from .util import ROOT,build,digest
TASK_ID='worldswap-land-probe'
CONTROLLER_ID='worldswap-controller'

def register(controller):
 image=build();envs=[]
 for path in sorted((ROOT/'worlds').glob('*.json')):
  world=json.loads(path.read_text());id='worldswap-'+world['slug']
  try:
   env=PhysicsWorld.get(id)
   if env.world!=world or env.image!=image:env=PhysicsWorld.put(id=id,world=world,image=image)
  except Exception as err:
   if type(err).__name__!='NotFoundError':raise
   env=PhysicsWorld.put(id=id,world=world,image=image)
  envs.append({'id':env.id,'version':env.version,'world':world,'definition_sha256':hashlib.sha256(json.dumps(env.to_dict(),sort_keys=True).encode()).hexdigest()})
 a=FileArtifact.put_bytes(CONTROLLER_ID,description='One landing controller reused across worlds',filename='controller.py',content=Path(controller).read_bytes(),content_type='text/x-python')
 task_rows=[{'id':'world','type':'deploy_env','env_id':'<world_id>','env_version':None,'ttl_seconds':300},
 {'id':'fly','type':'fly_controller','controller_id':a.id,'controller_version':a.version,'depends_on':['world']},
 {'id':'grade','type':'grade_landing','depends_on':['fly']},
 {'id':'collect','type':'collect_landing','depends_on':['grade']}]
 registry=get_task_step_registry();task=Task.put(id=TASK_ID,steps=[registry[r['type']].from_dict(r) for r in task_rows])
 record={'batch':uuid.uuid4().hex[:8],'task_id':task.id,'task_version':task.version,'task_sha256':hashlib.sha256(json.dumps(task.to_dict(),sort_keys=True).encode()).hexdigest(),'task_definition':task.to_dict(),'controller_id':a.id,'controller_version':a.version,'controller_sha256':digest(controller),'verifier_sha256':digest(ROOT/'lander_demo/verify.py'),'environments':envs}
 (ROOT/'artifacts').mkdir(exist_ok=True);(ROOT/'artifacts/registry.json').write_text(json.dumps(record,indent=2))
 for e in envs:
  (ROOT/'artifacts'/('seed-'+e['world']['slug']+'.json')).write_text(json.dumps({'metadata':{'seed':{'world_id':e['id']}}}))
 print(json.dumps({k:v for k,v in record.items() if k not in ('task_definition','environments')},indent=2))
if __name__=='__main__':
 import sys
 register(sys.argv[1])
