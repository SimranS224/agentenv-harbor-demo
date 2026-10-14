"""Social video frames drawn from the actual recorded physics trajectories."""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from .util import ROOT
F=Path('/System/Library/Fonts/Supplemental')
def font(n,b=False):
 p=F/('Arial Bold.ttf' if b else 'Arial.ttf')
 if not p.exists():p=Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if b else 'DejaVuSans.ttf')
 return ImageFont.truetype(str(p),n)
def rgb(h):return tuple(int(h[i:i+2],16) for i in (1,3,5))
def frame(D,t):
 im=Image.new('RGB',(1440,960),'#090f1c');p=ImageDraw.Draw(im);R=D['registry']
 def txt(x,y,s,n=18,col='#edf4f7',b=False):p.text((x,y),s,font=font(n,b),fill=col)
 txt(42,30,'AGENTENV  /  THE WORLD-SWAP EXPERIMENT',15,'#89a6be',True)
 txt(38,72,'One task. Three worlds.',70,'#eaf2f8',True)
 txt(42,163,'One coding-agent repair. Swap the environment. Keep the task and verifier.',23,'#a1b4c7')
 p.rounded_rectangle((42,218,1398,278),radius=12,fill='#132033',outline='#2c4053')
 txt(61,237,f'TASK {R["task_id"]} @ {R["task_version"]}  ·  UNCHANGED',17,'#b5f4cb',True)
 txt(725,239,'CONTROLLER '+R['controller_sha256'][:10]+'   VERIFIER '+R['verifier_sha256'][:10],15,'#a5bdcf')
 palettes={'earth':['#103455','#7baac0','#345d65','#294c43'],'moon':['#080f25','#303954','#626e83','#363f54'],'mars':['#301b2c','#b47557','#994f41','#713a32']}
 for col,slug in enumerate(['earth','moon','mars']):
  f=next(f for f in D['flights'] if f['world']['slug']==slug);w=f['world'];ox=42+col*458;oy=382;W=438;H=350;pal=palettes[slug]
  p.rounded_rectangle((ox,308,ox+W,831),radius=16,fill='#111d2e',outline='#2b3d52')
  txt(ox+20,325,w['name'],28,'#f1f6f7',True);txt(ox+20,360,w['description'],12,'#9fb5c9')
  a,b=map(rgb,pal[:2])
  for y in range(H):
   c=tuple(round(a[k]+(b[k]-a[k])*y/H) for k in range(3));p.line((ox,oy+y,ox+W,oy+y),fill=c)
  for i in range(55):
   x=(i*97+23)%W;y=(i*43+19)%200;p.ellipse((ox+x,oy+y,ox+x+1,oy+y+1),fill='#aac7d3')
  x,y=ox+350,oy+53;r=24 if slug=='moon' else 17
  p.ellipse((x-r,y-r,x+r,y+r),fill='#82b5c4' if slug=='moon' else '#eacaa0')
  if slug=='moon':p.ellipse((x-8,y-19,x+7,y+19),fill='#3b7c80')
  for layer,base,amp,color in [(0,260,17,pal[2]),(1,305,8,pal[3])]:
   pts=[(ox,oy+H)]+[(ox+x,oy+base+math.sin(x*.025+layer)*amp+math.cos(x*.059)*5) for x in range(0,W+20,20)]+[(ox+W,oy+H)]
   p.polygon(pts,fill=color)
  for i in range(12):
   x=ox+(i*71+11)%W;y=oy+324+i%3*9;p.ellipse((x-6,y-2,x+6,y+2),outline='#798899' if slug=='moon' else '#aa8870')
  if slug=='mars':
   for i in range(13):
    x=ox+((i*41+t*17)%400);y=oy+150+i*10;p.line((x,y,x+25,y-2),fill='#bc9478')
  def xy(q):return (ox+20+q['x']*.64,oy+317-q['y']*.85)
  px,py=xy({'x':w['pad_x'],'y':w['pad_y']});p.rounded_rectangle((px-28,py+8,px+28,py+14),radius=2,fill='#233d43');p.line((px-25,py+7,px+25,py+7),fill='#c0f3cf',width=2);p.text((px,py+30),'PAD',font=font(10,True),fill='#c4e7d6',anchor='mm')
  for lane in ['original','repaired']:
   frames=f[lane]['frames'];idx=min(len(frames)-1,int(t*10));q=frames[idx];green=lane=='repaired';color='#b5f4cb' if green else '#e49b89';pts=[xy(q) for q in frames[:idx+1:2]]
   if len(pts)>1:
    if green:p.line(pts,fill=color,width=2)
    else:
     for j in range(0,len(pts)-1,3):p.line(pts[j:j+2],fill=color,width=1)
   x,y=xy(q)
   if q['thrust']>5 and idx<len(frames)-1:p.polygon([(x-4,y+8),(x,y+18+q['thrust']/15+math.sin(t*33)*2),(x+4,y+8)],fill='#ecc477' if green else '#b77761')
   p.line([(x-7,y+3),(x-12,y+12),(x-16,y+12)],fill=color,width=2);p.line([(x+7,y+3),(x+12,y+12),(x+16,y+12)],fill=color,width=2)
   p.rounded_rectangle((x-8,y-12,x+8,y+9),radius=5,fill='#e8f2f3' if green else '#c28b7d');p.rounded_rectangle((x-5,y-9,x+5,y-1),radius=3,fill='#234151');p.rounded_rectangle((x-11,y+1,x+11,y+6),radius=2,fill=color)
  txt(ox+16,oy+13,f'g {w["gravity"]}   wind +{w["wind"]}',12,'#c6dbe4')
  txt(ox+20,751,'ORIGINAL',11,'#9bb2c6');txt(ox+20,772,'Landed' if f['grades']['original']['passed'] else 'Still hovering',18,'#e79d8a',True)
  txt(ox+228,751,'REPAIRED',11,'#9bb2c6');txt(ox+228,772,f'Land: {f["grades"]["repaired"]["time"]:.1f}s',18,'#b5f4cb',True)
  txt(ox+20,807,f'ENV {f["env_id"]} @ {f["env_version"]}',11,'#829fb9')
 txt(42,854,'— Original Earth-tuned code',16,'#e49b89');txt(320,854,'— One repaired controller across all worlds',16,'#b5f4cb');txt(1190,854,f'{min(t,45):04.1f} / 45s',17,'#a9bdce')
 txt(42,901,'Three native environment records. One stored task version. Same controller bytes and verifier.',19,'#e2edf2',True)
 txt(42,936,'Recorded Pymunk simulation · Illustrative physics · One no-key Codex repair · Independent environment reuse, not a Harbor benchmark',12,'#768fa6')
 return im
if __name__=='__main__':
 d=json.loads((ROOT/'artifacts/comparison.json').read_text());out=ROOT/'artifacts/frames';out.mkdir(exist_ok=True)
 frame(d,31).save(ROOT/'artifacts/showcase.png')
 for i in range(240):frame(d,min(45,i/10*2)).save(out/f'{i:04d}.png')
