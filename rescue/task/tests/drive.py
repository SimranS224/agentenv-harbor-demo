"""Requests share one Python process: resetting it would hide the bug."""
import json,sys,copy
from pathfinding.rescue import plan_route
world=json.load(sys.stdin); results=[]
for e in world:
    original=copy.deepcopy(e['matrix'])
    try:
        path=plan_route(e['matrix'],e['start'],e['goal'],e['blocked'])
        results.append({'path':[list(p) for p in path], 'input_unchanged':e['matrix']==original})
    except Exception as err:
        results.append({'path':[], 'error':str(err), 'input_unchanged':e['matrix']==original})
print(json.dumps(results))
