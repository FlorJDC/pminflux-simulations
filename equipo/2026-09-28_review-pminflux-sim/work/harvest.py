# -*- coding: utf-8 -*-
"""Append a ```claims block (from a report file) to state.json. Usage: harvest.py <report.md> <round> <source>"""
import io, json, re, sys
rep, rnd, src = sys.argv[1], int(sys.argv[2]), sys.argv[3]
text = io.open(rep, encoding="utf-8").read()
blocks = re.findall(r"```claims\s*(\[.*?\])\s*```", text, re.S)
if not blocks:
    sys.exit("no claims block in " + rep)
items = json.loads(blocks[-1])
sp = "equipo/2026-09-28_review-pminflux-sim/state.json"
st = json.load(io.open(sp, encoding="utf-8"))
seen = {(c["text"], c["status"]) for c in st["claims"]}
new = [dict(status=i["status"], text=i["text"], round=rnd, source=src) for i in items if (i["text"], i["status"]) not in seen]
st["claims"].extend(new)
io.open(sp, "w", encoding="utf-8", newline="\n").write(json.dumps(st, indent=1, ensure_ascii=False))
from collections import Counter
print(len(new), "claims harvested:", dict(Counter(i["status"] for i in new)))
