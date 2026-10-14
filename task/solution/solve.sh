#!/bin/sh
set -eu
python - <<'PY'
from pathlib import Path
p = Path('/app/src/requests/structures.py')
s = p.read_text()
broken = 'return self._store[key][1]'
assert s.count(broken) == 1, 'Expected fresh seeded regression'
p.write_text(s.replace(broken, 'return self._store[key.lower()][1]'))
PY
