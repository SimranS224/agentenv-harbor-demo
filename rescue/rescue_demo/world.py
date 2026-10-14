"""Deterministic environment events and an independent route verifier."""
import heapq
import copy


def episodes():
    m = [[1] * 23 for _ in range(15)]
    for y in range(15):
        m[y][11] = 0
    for y in (4, 10):
        m[y][11] = 1
    for x0, x1 in ((3, 8), (15, 20)):
        for y in (2, 3, 11, 12):
            for x in range(x0, x1):
                m[y][x] = 0
    wet = copy.deepcopy(m)
    for y in range(0, 8):
        for x in range(12, 23):
            if wet[y][x]: wet[y][x] = 7
    start, goal = [2, 7], [20, 7]
    def event(id, title, detail, matrix, blocked):
        return dict(id=id,title=title,detail=detail,matrix=matrix,start=start,goal=goal,blocked=blocked)
    return [event('clear','01 / All clear','The static test is green. Both bridges are open.',m,[]),
            event('bridge','02 / Bridge closed','The north bridge closes after delivery one. Same process. Same destination.',m,[[11,4]]),
            event('flood','03 / Flood warning','North bridge reopens. Floodwater makes the north bank 7× more costly.',wet,[]),
            event('sealed','04 / No safe route','Both bridges close. The correct answer is to stop dispatching.',m,[[11,4],[11,10]]),
            event('reopen','05 / Roads reopen','Closures expire. A safe route must become available again.',m,[])]


def optimum(e):
    m=e['matrix']; closed={tuple(c) for c in e['blocked']}
    s=tuple(e['start']); g=tuple(e['goal']); q=[(0,s)]; dist={s:0}
    while q:
        d,p=heapq.heappop(q)
        if d!=dist[p]:continue
        if p==g:return d
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            x,y=p[0]+dx,p[1]+dy; n=(x,y)
            if 0<=y<len(m) and 0<=x<len(m[0]) and m[y][x]>0 and n not in closed:
                nd=d+m[y][x]
                if nd<dist.get(n,float('inf')):dist[n]=nd;heapq.heappush(q,(nd,n))
    return None


def grade(e,path):
    best=optimum(e)
    if not path:return dict(ok=best is None,cost=None,optimal=best,reason='Safe stop' if best is None else 'No route returned')
    closed={tuple(c) for c in e['blocked']}; m=e['matrix']; cost=0
    if path[0]!=e['start'] or path[-1]!=e['goal']:return dict(ok=False,cost=None,optimal=best,reason='Wrong destination')
    for i,(x,y) in enumerate(path):
        if not (0<=y<len(m) and 0<=x<len(m[0])) or not m[y][x] or (x,y) in closed:
            return dict(ok=False,cost=None,optimal=best,reason='Route enters a closure',collision=[x,y])
        if i:
            a,b=path[i-1]
            if abs(a-x)+abs(b-y)!=1:return dict(ok=False,cost=None,optimal=best,reason='Invalid movement')
            cost+=m[y][x]
    return dict(ok=cost==best,cost=cost,optimal=best,reason='Optimal delivery' if cost==best else 'Avoidable flood exposure')
