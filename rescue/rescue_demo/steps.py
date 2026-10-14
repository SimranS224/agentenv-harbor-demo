import asyncio,json
from pathlib import Path
from agent_env.task_step.task_step import TaskStep
from agent_env.artifact.artifacts.file import FileArtifact
from .workflow import repair,simulate
from .replay import render

class Base(TaskStep):
    entity_refs=()
    @classmethod
    def from_dict(cls,data):return cls(**cls._base_from_dict(data))
    def to_dict(self):return super().to_dict()

async def save(path,run):
    path=Path(path)
    a=await asyncio.to_thread(FileArtifact.put_bytes,'@local/rescue/'+run+'/'+path.name,
        description='Rescue simulation evidence',filename=path.name,content=path.read_bytes(),
        content_type='text/html' if path.suffix=='.html' else 'application/json' if path.suffix=='.json' else 'text/plain')
    return {'id':a.id,'version':a.version,'filename':path.name}

class Repair(Base):
    type='rescue_repair'
    async def execute(self,context):
        result=await asyncio.to_thread(repair)
        context.metadata['rescue']=result
        context.metadata['patch']=await save(Path(result['directory'])/'repair.patch',Path(result['directory']).name)
        return context

class Simulate(Base):
    type='rescue_simulate'
    async def execute(self,context):
        report=await asyncio.to_thread(simulate,context.metadata['rescue'])
        context.metadata['rescue_scores']=report['score']
        context.metadata.setdefault('verifications',{})['changing_world']={'score':report['score']['repaired'],'results':report['lanes']['repaired']}
        context.metadata['evidence']=await save(Path(report['directory'])/'results.json',Path(report['directory']).name)
        return context

class Replay(Base):
    type='rescue_replay'
    async def execute(self,context):
        out=Path(context.metadata['rescue']['directory'])
        report=json.loads((out/'results.json').read_text())
        await asyncio.to_thread(render,report,out/'index.html')
        context.metadata['replay']=await save(out/'index.html',out.name)
        print('Replay:',out/'index.html',flush=True)
        return context
