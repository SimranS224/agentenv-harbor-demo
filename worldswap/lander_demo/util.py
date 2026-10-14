import subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def cmd(args,check=True,timeout=120,input=None):
 p=subprocess.run(args,text=True,input=input,capture_output=True,timeout=timeout)
 if check and p.returncode:raise RuntimeError(p.stderr[-2500:])
 return p
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def build():
 tag='ae-worldswap:'+hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'engine').iterdir()) if p.is_file())).hexdigest()[:12]
 existing=cmd(['docker','image','inspect',tag,'--format','{{.Id}}'],check=False)
 if existing.returncode==0:return existing.stdout.strip()
 p=cmd(['docker','build','-t',tag,str(ROOT/'engine')],timeout=240)
 return cmd(['docker','image','inspect',tag,'--format','{{.Id}}']).stdout.strip()
