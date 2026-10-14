"""Pymunk rigid-body integration. Units are illustrative, not planetary SI units."""
import importlib.util,json,math,sys
import pymunk

def simulate(world,controller):
    space=pymunk.Space();space.gravity=(world['wind'],-world['gravity'])
    body=pymunk.Body(1,float('inf'));body.position=tuple(world['start'])
    shape=pymunk.Poly.create_box(body,(16,22));space.add(body,shape)
    dt=1/60;frames=[];status='timeout';impact=None
    for i in range(2700):
        s=dict(world,x=body.position.x,y=body.position.y,vx=body.velocity.x,vy=body.velocity.y)
        ax,thrust=map(float,controller(s))
        if not all(math.isfinite(v) for v in (ax,thrust)):raise ValueError('Non-finite actuator output')
        ax=max(-world['max_lateral'],min(world['max_lateral'],ax));thrust=max(0,min(world['max_thrust'],thrust))
        body.force=(ax,thrust);space.step(dt)
        f=dict(t=round((i+1)*dt,3),x=round(body.position.x,3),y=round(body.position.y,3),vx=round(body.velocity.x,3),vy=round(body.velocity.y,3),thrust=round(thrust,2),lateral=round(ax,2))
        if i%6==0:frames.append(f)
        if body.position.y<=world['pad_y']:
            impact=f;status='contact';frames.append(f);break
        if not(-1000<body.position.x<1800 and -100<body.position.y<1800):status='out_of_bounds';frames.append(f);break
    return dict(frames=frames,status=status,contact=impact,final=frames[-1],engine='pymunk '+pymunk.version)

if __name__=='__main__':
    spec=importlib.util.spec_from_file_location('candidate',sys.argv[2]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    print(json.dumps(simulate(json.load(open(sys.argv[1])),module.control)))
