"""Append page-id and renamed-title aliases from the 2026-10-21 Wikipedia lookup.

Reads exclusions_v1_before_pageids.jsonl and pageid_lookup/lookup.json; writes
exclusions.jsonl = the v1 records unchanged, then a comment and one plain line
per alias (read_exclusions accepts both forms)."""
import json
from pathlib import Path

E = Path(__file__).resolve().parents[1]
v1 = (E / "exclusions_v1_before_pageids.jsonl").read_text(encoding="utf-8")
look = json.loads((E / "pageid_lookup" / "lookup.json").read_text(encoding="utf-8"))
recs = [json.loads(x) for x in v1.splitlines() if x.strip()]
have = {r["source_id"] for r in recs if str(r.get("source_id", "")).startswith("pageid:")}
titles = {t for r in recs for t in r.get("all_titles", []) + [r.get("title") or ""]}
lines = []
for t, v in sorted(look["results"].items()):
    pid = f"pageid:{v['pageid']}"
    if pid not in have:
        lines.append(pid)
    if v["resolved_title"] not in titles:
        lines.append(v["resolved_title"])
lines = sorted(set(lines))
head = (
    f"# aliases from the English Wikipedia page-id lookup of {look['queried']} "
    f"({look['n_titles']} title-only records): page ids, and current titles of renamed pages"
)
(E / "exclusions.jsonl").write_text(v1.rstrip("\n") + "\n" + head + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
print(len(lines), "alias lines")
