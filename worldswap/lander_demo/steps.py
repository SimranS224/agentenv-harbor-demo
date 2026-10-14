import asyncio,json,tempfile,hashlib
from pathlib import Path
from agent_env.task_step.task_step import TaskStep
from agent_env.entity_refs import EntityRef
from agent_env.artifact.artifacts.file import FileArtifact
from .environment import PhysicsWorld
from .verify import verify
from .util import ROOT

class Base(TaskStep):
 entity_refs=()
 @classmethod
 def from_dict(cls,d):return cls(**cls._base_from_dict(d))
 def to_dict(self):return super().to_dict()

class Fly(Base):
 type='fly_controller'
 entity_refs=(EntityRef.artifact('controller_id',version_field='controller_version'),)
 def __init__(self,id,version,controller_id,controller_version=1,**kw):
  super().__init__(id,version,**kw);self.controller_id=controller_id;self.controller_version=controller_version
 @classmethod
 def from_dict(cls,d):return cls(**cls._base_from_dict(d),controller_id=d['controller_id'],controller_version=d['controller_version'])
 def to_dict(self):return {**super().to_dict(),'controller_id':self.controller_id,'controller_version':self.controller_version}
 async def execute(self,context):
  deployed=context.deployed_envs[0];env=await PhysicsWorld.from_deployed_env(deployed)
  a=FileArtifact.get(self.controller_id,self.controller_version)
  try:
   with tempfile.TemporaryDirectory() as td:
    path=Path(td)/'controller.py';path.write_bytes(a.load())
    original=await asyncio.to_thread(env.fly)
    repaired=await asyncio.to_thread(env.fly,path)
    context.metadata['flights']={'world':env.world,'original':original,'repaired':repaired,'env_id':env.id,'env_version':env.version,'env_instance_id':deployed.instance_id,'controller_id':a.id,'controller_version':a.version,'controller_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  finally:await env.close()
  return context

class Grade(Base):
 type='grade_landing'
 async def execute(self,context):
  d=context.metadata['flights'];d['verifier_sha256']=hashlib.sha256((ROOT/'lander_demo/verify.py').read_bytes()).hexdigest();d['grades']={key:verify(d['world'],d[key]) for key in ('original','repaired')}
  context.metadata.setdefault('verifications',{})['safe_landing']={'score':int(d['grades']['repaired']['passed']),'results':[d['grades']['repaired']]}
  return context

class Collect(Base):
 type='collect_landing'
 async def execute(self,context):
  d=context.metadata['flights'];d['task_instance_id']=context.instance_id
  name=context.instance_id.rsplit('/',1)[-1]
  path=ROOT/'artifacts'/name;path.mkdir(parents=True,exist_ok=True)
  content=json.dumps(d,indent=2).encode();(path/'flight.json').write_bytes(content)
  a=await asyncio.to_thread(FileArtifact.put_bytes,'worldswap-flights/'+name,description='Recorded landing trajectories',filename='flight.json',content=content,content_type='application/json')
  context.metadata['flight_artifact']={'id':a.id,'version':a.version}
  print(d['world']['name'],d['grades'],'artifact',a.id,flush=True)
  return context
