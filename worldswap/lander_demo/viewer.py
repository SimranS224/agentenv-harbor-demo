import json
from pathlib import Path
from .util import ROOT

def render(report,out):
    text=(ROOT/'lander_demo/viewer.html').read_text()
    Path(out).write_text(text.replace('__DATA__',json.dumps(report).replace('<','\\u003c')))
if __name__=='__main__':
    render(json.loads((ROOT/'artifacts/comparison.json').read_text()),ROOT/'artifacts/index.html')
