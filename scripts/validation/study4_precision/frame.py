"""Study 4: the sampling frame (every hit), summarised per sub-stratum and register.

analyse.py needs exact domain populations: N_h for every sub-stratum and the
number of hits of each register in it. Those come from the full hit
population, never from the sample. build.py writes `frame.json`; for a set
built before frame.json existed, reconstruct it from hits.jsonl, texts.jsonl
and the manifest's design (and check it against the key):

    uv run python scripts/validation/study4_precision/frame.py \\
        --dir .cache/validation/study4 --out .cache/validation/study4_scratch/frame.json

PHRASE strata need the list-level multi-sense flag (build.polysemous_ranks),
so lexinspect's PHRASE list must be importable; use the source of the version
that built the set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def md_substratum(hit: dict[str, Any], design_md: dict[str, Any]) -> str:
    cat = hit["category"]
    own = design_md[cat]["substrata"]
    sub = f"marker={hit['marker']}"
    return f"{cat}|{sub if sub in own else 'rest'}"


def phrase_substratum(hit: dict[str, Any], design_ph: dict[str, Any], poly: set[int]) -> str:
    multi = bool(hit.get("also_possible")) or hit["rank"] in poly
    stratum = f"K{hit['k_band']}-{'multi' if multi else 'single'}"
    own = design_ph[stratum]["substrata"]
    sub = f"marker={hit['phrase']}"
    return f"{stratum}|{sub if sub in own else 'rest'}"


def build_frame(
    hits: list[dict[str, Any]],
    register_of: dict[str, str],
    design: dict[str, Any],
    poly: set[int],
) -> dict[str, Any]:
    counts: dict[str, dict[str, Counter]] = {
        "metadiscourse": defaultdict(Counter),
        "phrase": defaultdict(Counter),
    }
    for h in hits:
        if h["module"] == "metadiscourse":
            sub = md_substratum(h, design["metadiscourse"])
        else:
            sub = phrase_substratum(h, design["phrase"], poly)
        counts[h["module"]][sub][register_of[h["text_id"]]] += 1
    out: dict[str, Any] = {"modules": {}}
    for mod, subs in counts.items():
        out["modules"][mod] = {
            sub: {"N": sum(c.values()), "by_register": dict(sorted(c.items()))}
            for sub, c in sorted(subs.items())
        }
    # Cross-check against the design's recorded N per sub-stratum.
    problems = []
    for mod, strata in design.items():
        for stratum, d in strata.items():
            for sub, s in d["substrata"].items():
                got = out["modules"][mod].get(f"{stratum}|{sub}", {}).get("N")
                if got != s["N"]:
                    problems.append(f"{mod} {stratum}|{sub}: frame N {got} != design N {s['N']}")
    out["checks"] = {"design_N_match": not problems, "problems": problems}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    import build

    hits = [json.loads(x) for x in (args.dir / "hits.jsonl").read_text().splitlines() if x.strip()]
    texts = [
        json.loads(x) for x in (args.dir / "texts.jsonl").read_text().splitlines() if x.strip()
    ]
    design = json.loads((args.dir / "manifest.json").read_text())["design"]["strata"]
    frame = build_frame(
        hits, {t["text_id"]: t["register"] for t in texts}, design, build.polysemous_ranks()
    )
    frame["source"] = {
        "hits_sha256": hashlib.sha256((args.dir / "hits.jsonl").read_bytes()).hexdigest(),
        "n_hits": len(hits),
    }
    if not frame["checks"]["design_N_match"]:
        raise SystemExit(
            "frame does not match the design:\n" + "\n".join(frame["checks"]["problems"])
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(frame, indent=1, ensure_ascii=False))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
