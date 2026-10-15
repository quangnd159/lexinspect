"""One-shot: parse CoxheadAWL.xml into JSON keyed by sublist."""

import json
import re
import xml.etree.ElementTree as ET

tree = ET.parse("/tmp/awl.xml")
root = tree.getroot()

sublists: dict[int, list[dict]] = {i: [] for i in range(1, 11)}
all_forms: dict[str, dict] = {}
unparseable = []

for fam in root.findall("FAMILY"):
    head = fam.get("HEADWORD", "").strip().lower()
    tags = fam.get("TAGS", "")
    # Match the canonical Coxhead sublist (ignore the AR re-bands)
    m = re.search(r"Coxhead AWL Sublist (\d+)", tags)
    if not m:
        unparseable.append((head, tags))
        continue
    sub = int(m.group(1))
    forms = sorted({(w.text or "").strip().lower() for w in fam.findall("WORD") if w.text})
    forms = [f for f in forms if f]
    entry = {"headword": head, "sublist": sub, "forms": forms}
    sublists[sub].append(entry)
    for f in forms:
        all_forms[f] = entry  # last writer wins; AWL families don't significantly overlap

families = []
for sub in range(1, 11):
    families.extend(sorted(sublists[sub], key=lambda e: e["headword"]))

out = {
    "source": "Coxhead, A. (2000). A new academic word list. TESOL Quarterly, 34(2), 213–238.",
    "version": "Coxhead AWL (2000)",
    "headword_count": len(families),
    "sublist_counts": {sub: len(sublists[sub]) for sub in range(1, 11)},
    "families": families,
}

with open("/Users/quangnguyendang/webapps/lexinspect/src/lexinspect/data/awl.json", "w") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"Wrote {len(families)} families across 10 sublists")
print(f"Per-sublist: {out['sublist_counts']}")
print(f"Total inflected forms indexed: {len(all_forms)}")
if unparseable:
    print(f"Skipped {len(unparseable)} entries with non-Coxhead tags")
