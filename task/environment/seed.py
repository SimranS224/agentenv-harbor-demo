from pathlib import Path

p = Path('/app/src/requests/structures.py')
s = p.read_text()
original = 'return self._store[key.lower()][1]'
assert s.count(original) == 1
p.write_text(s.replace(original, 'return self._store[key][1]'))
