import subprocess,json,uuid,hashlib,difflib,os
from pathlib import Path
from .world import episodes,grade
from .codex_agent import preflight,run_codex
ROOT=Path(__file__).resolve().parents[1]

def cmd(args,check=True,timeout=120,input=None):
    p=subprocess.run(args,input=input,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode:raise RuntimeError(p.stderr[-2000:])
    return p

def container(image):
    name='ae-rescue-'+uuid.uuid4().hex[:10]
    cmd(['docker','run','-d','--name',name,'--network','none','--memory','256m','--memory-swap','256m','--cpus','1','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges',image])
    return name

def repair():
    mode=os.environ.get('RESCUE_MODE','controls')
    if mode=='codex':preflight()
    identity=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'task/environment').iterdir()))).hexdigest()
    out=ROOT/'artifacts'/('run-'+uuid.uuid4().hex[:10]);out.mkdir(parents=True)
    image='ae-rescue:'+identity[:12]
    built=cmd(['docker','build','-t',image,str(ROOT/'task/environment')],timeout=240)
    (out/'build.log').write_text(built.stdout+built.stderr)
    name=container(image)
    before=(ROOT/'task/environment/rescue.py').read_text()
    try:
        cmd(['docker','exec',name,'chmod','-R','a+rwX','/app/src'])
        if mode=='codex':
            def execute(command,timeout):
                p=cmd(['docker','exec','--user','65534:65534','-w','/app',name,'timeout','-s','KILL',str(max(1,int(timeout))),'sh','-c',command],check=False,timeout=timeout+3)
                return dict(exit_code=p.returncode,stdout=p.stdout[:10000],stderr=p.stderr[:2000])
            agent=run_codex((ROOT/'task/instruction.md').read_text(),execute,out/'trace.jsonl',timeout=60)
        else:
            # Reference control: removing caching preserves upstream A* semantics.
            fixed=before.replace('    if key in _cache:\n        return list(_cache[key])\n','')
            (out/'oracle.py').write_text(fixed)
            cmd(['docker','cp',str(out/'oracle.py'),name+':/app/src/pathfinding/rescue.py'])
            agent={'model':None,'status':'scripted-control','billing':'No model calls'}
        cmd(['docker','stop','-t','1',name]);cmd(['docker','start',name])
        cmd(['docker','cp',name+':/app/src/pathfinding',str(out/'candidate')])
    finally:cmd(['docker','rm','-f',name],check=False)
    after=(out/'candidate/rescue.py').read_text()
    (out/'repair.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='before/pathfinding/rescue.py',tofile='after/pathfinding/rescue.py')))
    result=dict(directory=str(out),image=image,task_hash=identity,mode=mode,agent=agent)
    (out/'repair.json').write_text(json.dumps(result,indent=2))
    return result

def simulate(repair_result):
    out=Path(repair_result['directory']);world=episodes(); report={**repair_result,'episodes':world,'lanes':{}}
    for label in ('original','repaired'):
        name=container(repair_result['image'])
        try:
            if label=='repaired':cmd(['docker','cp',str(out/'candidate')+'/.',name+':/app/src/pathfinding'])
            cmd(['docker','cp',str(ROOT/'task/tests/drive.py'),name+':/drive.py'])
            p=cmd(['docker','exec','-i','--user','65534:65534',name,'python','/drive.py'],input=json.dumps(world),timeout=20)
            paths=json.loads(p.stdout)
            assert len(paths)==len(world)
            report['lanes'][label]=[{**r,**grade(e,r['path'])} for e,r in zip(world,paths)]
            for r in report['lanes'][label]:r['ok']=r['ok'] and r['input_unchanged'] and not r.get('error')
        finally:cmd(['docker','rm','-f',name],check=False)
    report['static_test']={k:v[0]['ok'] for k,v in report['lanes'].items()}
    report['score']={k:sum(r['ok'] for r in v)/len(v) for k,v in report['lanes'].items()}
    # No inference calls here: both lanes execute code against identical events.
    (out/'results.json').write_text(json.dumps(report,indent=2))
    print('Static:',report['static_test'],'Changing world:',report['score'],flush=True)
    return report
