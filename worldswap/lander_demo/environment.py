"""A registered AgentEnv environment type backed by a disposable physics container."""
import json,uuid,tempfile,os
from agent_env.env.env import Env,DeployedEnv
from agent_env.env.store import get_env_instance_store
from .util import cmd

class PhysicsWorld(Env):
 type='landing_physics'
 description='Pymunk landing world with its own versioned physical parameters'
 def __init__(self,id,version,world,image,metadata=None):
  super().__init__(id,version,metadata);self.world=world;self.image=image;self.container=None
 def to_dict(self):return {**super().to_dict(),'world':self.world,'image':self.image}
 @classmethod
 def from_dict(cls,d):return cls(d['id'],d.get('version'),d['world'],d['image'],d.get('metadata'))
 async def deploy(self,ttl_seconds=300,**kwargs):
  self.container='ae-worldswap-'+uuid.uuid4().hex[:10]
  cmd(['docker','run','-d','--name',self.container,'--network','none','--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges',self.image])
  try:
   with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
    json.dump(self.world,f);f.flush();os.chmod(f.name,0o644);cmd(['docker','cp',f.name,self.container+':/app/world.json'])
   d=DeployedEnv(env_id=self.id,env_version=self.version,metadata={'container':self.container,'world':self.world,'engine_image':self.image})
   deployed=get_env_instance_store().create_instance(d,ttl_seconds)
   self._instance_id=deployed.instance_id
   return deployed
  except BaseException:
   await self.close();raise
 @classmethod
 async def from_deployed_env(cls,d):
  env=cls.get(d.env_id,d.env_version);env.container=d.metadata['container'];env._instance_id=d.instance_id;return env
 def fly(self,controller_path=None):
  path='/app/src/controller.py'
  if controller_path:
   cmd(['docker','cp',str(controller_path),self.container+':/app/candidate.py']);path='/app/candidate.py'
  p=cmd(['docker','exec','--user','65534:65534',self.container,'timeout','20','python','/app/simulate.py','/app/world.json',path],timeout=25)
  return json.loads(p.stdout)
 async def close(self):
  if self.container:cmd(['docker','rm','-f',self.container],check=False);self.container=None
