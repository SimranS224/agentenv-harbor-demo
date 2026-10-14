import json
from pathlib import Path

def render(report,path):
    public={k:report[k] for k in ['episodes','lanes','static_test','score','mode']}
    public['model']=report['agent'].get('model')
    data=json.dumps(public).replace('<','\\u003c')
    template=Path(__file__).with_name('replay.html').read_text()
    Path(path).write_text(template.replace('__DATA__',data))
