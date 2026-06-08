#!/usr/bin/env python3
import json, sys
from pathlib import Path
c, path = sys.argv[1], Path(sys.argv[2])
o=f=0
if path.exists():
  for l in path.read_text().splitlines():
    if not l.strip(): continue
    d=json.loads(l)
    if (d.get('ts') or '') < c: continue
    if d.get('success'): o+=1
    else: f+=1
print(sys.argv[3], o, 'ok', f, 'fail')