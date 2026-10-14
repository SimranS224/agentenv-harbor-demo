"""Render recorded route coordinates, never invented agent actions."""
import json,sys,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
F=Path('/System/Library/Fonts/Supplemental')
def font(n,bold=False):return ImageFont.truetype(str(F/('Arial Bold.ttf' if bold else 'Arial.ttf')),n)
C={'bg':'#f2f0e7','ink':'#152b32','muted':'#637c7d','red':'#cd5837','green':'#1b716e'}
def frame(d,stage,progress):
 im=Image.new('RGB',(1440,900),C['bg']);p=ImageDraw.Draw(im)
 def text(pos,s,n=18,c='ink',bold=False):p.text(pos,s,font=font(n,bold),fill=C.get(c,c))
 text((48,28),'AGENTENV  /  COUNTERFACTUAL DELIVERY LAB',15,'muted',True)
 text((44,68),'Green tests. Stranded robot.',61,'ink',True)
 text((48,149),'Same destination. Same events. One repaired planner.',22,'muted')
 e=d['episodes'][stage]
 p.rounded_rectangle((48,203,1392,274),radius=13,fill=C['ink'])
 text((70,216),e['title'].upper(),24,'#ffffff',True)
 text((70,247),e['detail'],15,'#bbcacc')
 for k,ox in [('original',48),('repaired',736)]:
  r=d['lanes'][k][stage]
  p.rounded_rectangle((ox,298,ox+656,803),radius=17,fill='#fffdf7',outline='#d3dcd1')
  text((ox+20,314),'ORIGINAL PLANNER' if k=='original' else 'AGENT-REPAIRED PLANNER',21,'ink',True)
  text((ox+20,343),'Static smoke test: PASS',15,'muted')
  s=25; mx=ox+40;my=385
  def xy(v):return (mx+v[0]*s+s//2,my+v[1]*s+s//2)
  for y,row in enumerate(e['matrix']):
   for x,v in enumerate(row):
    color=('#8bbad0' if x==11 else '#62775e') if not v else '#eed181' if v>1 else '#edf0e5'
    if x==11 and v:color='#9dc777'
    X,Y=mx+x*s,my+y*s;p.rounded_rectangle((X,Y,X+s-2,Y+s-2),radius=3,fill=color)
    if not v and x!=11:p.rounded_rectangle((X+4,Y+3,X+18,Y+15),radius=2,fill='#8a9c7e')
  for v in e['blocked']:
   x,y=xy(v);p.rounded_rectangle((x-12,y-12,x+11,y+11),radius=3,fill=C['red']);p.line((x-6,y-6,x+6,y+6),fill='white',width=2);p.line((x+6,y-6,x-6,y+6),fill='white',width=2)
  route=r['path'];col=C['green'] if r['ok'] else C['red'];pts=[xy(v) for v in route]
  if pts:
   p.line(pts,fill=col,width=3)
   end=len(pts)-1
   if r.get('collision'):end=route.index(r['collision'])
   index=min(end,int(progress*(len(pts)+7)))
   x,y=pts[index];p.ellipse((x-10,y-10,x+10,y+10),fill=col,outline='#fffdf7',width=3);p.rounded_rectangle((x-4,y-3,x+4,y+3),radius=2,fill='white')
   if r.get('collision') and index==end:p.ellipse((x-18,y-18,x+18,y+18),outline=col,width=2)
  for v,label in [(e['start'],'DEPOT'),(e['goal'],'HOSPITAL')]:
   x,y=xy(v);p.ellipse((x-4,y-4,x+4,y+4),fill=C['ink']);p.text((x,y+18),label,font=font(11,True),fill=C['ink'],anchor='mt')
  text((ox+20,771),r['reason'].upper(),17,col,True)
  score=sum(v['ok'] for v in d['lanes'][k]);p.text((ox+636,320),f'{score}/5',font=font(27,True),fill=col,anchor='rt')
 text((48,827),'REPAIR  →  PERSIST PATCH  →  CHANGE WORLD  →  GRADE + SAVE REPLAY',18,'ink',True)
 model=d['agent'].get('model') or 'scripted reference control'
 text((48,864),f'Recorded {model} run · Synthetic integration in python-pathfinding · Custom simulation orchestrated by AgentEnv',14,'muted')
 for i in range(5):p.rounded_rectangle((1190+i*40,834,1220+i*40,840),radius=3,fill=C['red'] if i==stage else '#cbd4c8')
 return im
if __name__=='__main__':
 src=Path(sys.argv[1]);d=json.loads((src/'results.json').read_text());out=src/'frames';out.mkdir(exist_ok=True)
 frame(d,1,1).save(src/'showcase.png')
 for stage in range(5):
  for j in range(40):frame(d,stage,j/31).save(out/f'{stage*40+j:04d}.png')
 print(src/'showcase.png')
