"""One verifier for every environment; candidate cannot write the score."""
def verify(world,flight):
    c=flight.get('contact')
    if c is None:return {'passed':False,'reason':'Did not reach the pad','error':round(abs(flight['final']['x']-world['pad_x']),2)}
    error=abs(c['x']-world['pad_x']);safe=error<=12 and abs(c['vx'])<=8 and abs(c['vy'])<=12 and c['t']<=45
    return {'passed':safe,'reason':'Safe landing' if safe else 'Unsafe touchdown','error':round(error,2),'speed':round((c['vx']**2+c['vy']**2)**.5,2),'time':c['t']}
