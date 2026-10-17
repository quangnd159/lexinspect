"""Run one detector configuration on a round's archived texts and write its full hit frame.

Invoked by `run` as a separate process per configuration, inside the uv
environment of the checkout being measured:

    uv run --project CHECKOUT python -I .../fixcheck/worker.py \\
        --texts ROUND_DIR --config NAME --families-module lexinspect._fix_families \\
        --enable MD-A,MD-B --out RUN_DIR

One process per configuration, so no family toggle, cache or lazily built
rule table can leak from one configuration into another. The configuration's
families are enabled with the toggle interface `only(families)` of
`--families-module` (only([]) = 0.3.3 behaviour); `--families-module none`
runs the checkout as it is (the pinned 0.3.3 commit). `--import-root DIR`
puts DIR first on sys.path before lexinspect is imported, so that a pinned
source tree (an archive of src/ at the baseline commit) runs in this
environment. `python -I` ignores PYTHONPATH, which is why this is an option.
The worker stops unless lexinspect is then imported from inside DIR.

For every text the archived bytes are checked against texts.jsonl's SHA-256,
lexinspect runs exactly as build.py's run_lexinspect does
(pipeline.run_all(text, modules=["metadiscourse", "phrase"])), and the run
stops unless Analysis.text equals the archived bytes. Every hit is written
(no sampling) with the judgement payload exactly as labellers see it, built
with build.py's own functions: context (build.context_for), marker (the hit's
surface) and claimed object (build.claimed_for with build.phrase_lookup(), i.e.
category and dimension, or PHRASE expression, sense, example and every other
listed sense). The payload hash is SHA-256 of its canonical JSON.

Hit identity. claim_key = canonical JSON of [source identity (source_id),
normalised-text SHA-256, module, span start, span end, claim], where claim is
{"category"} for metadiscourse and {"expression", "rank", "sense"} for PHRASE.
hit_id = "<config>:" + first 16 hex digits of sha256(claim_key + "#" + k),
k = the hit's occurrence index among identical claim keys in emission order.

Head token (audit r1 B4). Each row also records `head_span`, the character
offsets of the syntactic root of the hit's span (spaCy's Span.root of
doc.char_span(start, end, alignment_mode="expand")). The crosswalk's span
resolution rule uses it. It is not part of the payload or the claim key.

PHRASE lookup digest (audit r1 S3). `phrase_lookup_sha256` hashes the full
canonical content of every rank of build.phrase_lookup() (expression, sense,
example, variants and every other field) together with the sibling lists;
`phrase_inventory_sha256` separately hashes the packaged data file
lexinspect/data/phrase.json that the lookup reads.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import platform
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build  # noqa: E402

from fixcheck.common import (  # noqa: E402
    canonical_json,
    payload_sha256,
    read_jsonl,
    sha256_file,
    sha256_text,
    write_json,
)
from fixcheck.ledger import FAMILIES  # noqa: E402

MODULES_RUN = ["metadiscourse", "phrase"]


def claim_of(h: dict[str, Any]) -> dict[str, Any]:
    if h["module"] == "metadiscourse":
        return {"category": h["category"]}
    return {"expression": h["phrase"], "rank": h["rank"], "sense": h.get("sense")}


def claim_key(source_id: str, text_sha: str, module: str, span: list[int], claim: dict) -> str:
    return canonical_json([source_id, text_sha, module, int(span[0]), int(span[1]), claim])


def lookup_digest(by_rank: dict, siblings: dict) -> str:
    """SHA-256 of the complete canonical PHRASE lookup: every rank's full entry and siblings."""
    return sha256_text(
        canonical_json(
            {
                "by_rank": {str(k): by_rank[k] for k in sorted(by_rank)},
                "siblings": {str(k): siblings[k] for k in sorted(siblings)},
            }
        )
    )


def head_span(doc: Any, span: list[int]) -> list[int] | None:
    """Character offsets of the root token of the hit's span, or None if spaCy has no span."""
    if doc is None:
        return None
    sp = doc.char_span(int(span[0]), int(span[1]), alignment_mode="expand")
    if sp is None or len(sp) == 0:
        return None
    root = sp.root
    return [root.idx, root.idx + len(root.text)]


def hit_rows(
    config: str,
    text: dict[str, Any],
    raw: dict[str, list[dict[str, Any]]],
    analysis_tuple: Any,
    by_rank: dict,
    siblings: dict,
) -> list[dict[str, Any]]:
    """Rows for one text: every hit, its claim key, payload and payload hash."""
    rows = []
    occ: dict[str, int] = {}
    for module in MODULES_RUN:
        for h0 in raw[module]:
            h = {"module": module, "text_id": text["text_id"], **h0}
            claim = claim_of(h)
            ck = claim_key(text["source_id"], text["text_sha256"], module, h["span"], claim)
            k = occ.get(ck, 0)
            occ[ck] = k + 1
            ctx, sent_span = build.context_for(h, analysis_tuple)
            doc = getattr(analysis_tuple[0], "doc", None)
            payload = {
                "module": module,
                "context": ctx,
                "marker": h["surface"],
                "claimed": build.claimed_for(h, by_rank, siblings),
            }
            rows.append(
                {
                    "hit_id": f"{config}:{sha256_text(ck + '#' + str(k))[:16]}",
                    "config": config,
                    "module": module,
                    "text_id": text["text_id"],
                    "source_id": text["source_id"],
                    "text_sha256": text["text_sha256"],
                    "register": text["register"],
                    "span": [int(h["span"][0]), int(h["span"][1])],
                    "head_span": head_span(doc, h["span"]),
                    "token_index": h["token_index"],
                    "surface": h["surface"],
                    "sentence_span": sent_span,
                    "claim": claim,
                    "claim_key": ck,
                    "occurrence": k,
                    "raw": h0,
                    "payload": payload,
                    "payload_sha256": payload_sha256(payload),
                }
            )
    return rows


def families_context(module_name: str, enable: list[str]):
    if module_name == "none":
        if enable:
            raise SystemExit("--families-module none cannot enable families")
        return contextlib.nullcontext(), None
    fam = importlib.import_module(module_name)
    if tuple(fam.FAMILIES) != FAMILIES:
        raise SystemExit(f"{module_name}.FAMILIES {tuple(fam.FAMILIES)} != ledger {FAMILIES}")
    unknown = sorted(set(enable) - set(FAMILIES))
    if unknown:
        raise SystemExit(f"unknown families {unknown}")
    return fam.only(list(enable)), fam


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--texts", type=Path, required=True, help="round dir (texts.jsonl, texts/)")
    ap.add_argument("--config", required=True)
    ap.add_argument("--families-module", default="lexinspect._fix_families")
    ap.add_argument("--enable", default="", help="comma-separated families to enable")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--import-root", type=Path, help="source tree to import lexinspect from")
    args = ap.parse_args(argv)
    enable = [f for f in args.enable.split(",") if f]
    root = None
    if args.import_root is not None:
        root = args.import_root.resolve()
        if "lexinspect" in sys.modules:
            raise SystemExit("lexinspect was imported before --import-root could take effect")
        sys.path.insert(0, str(root))

    import lexinspect
    from lexinspect import pipeline

    if root is not None and not Path(lexinspect.__file__).resolve().is_relative_to(root):
        raise SystemExit(f"lexinspect imported from {lexinspect.__file__}, not from {root}")

    texts = read_jsonl(args.texts / "texts.jsonl")
    ctx, fam = families_context(args.families_module, enable)
    rows: list[dict[str, Any]] = []
    with ctx:
        enabled_now = [f for f in FAMILIES if fam.enabled(f)] if fam is not None else None
        if fam is not None and enabled_now != [f for f in FAMILIES if f in enable]:
            raise SystemExit(f"toggle state {enabled_now} != requested {enable}")
        by_rank, siblings = build.phrase_lookup()
        lookup_sha = lookup_digest(by_rank, siblings)
        from importlib import resources

        inventory_sha = sha256_text(
            resources.files("lexinspect.data").joinpath("phrase.json").read_text(encoding="utf-8")
        )
        poly = sorted(build.polysemous_ranks())
        for t in texts:
            p = args.texts / "texts" / f"{t['text_id']}.txt"
            text = p.read_text(encoding="utf-8")
            if sha256_text(text) != t["text_sha256"]:
                raise SystemExit(f"{p}: bytes differ from texts.jsonl's text_sha256")
            a, res = pipeline.run_all(text, modules=MODULES_RUN)
            if a.text != text:
                raise SystemExit(f"{t['text_id']}: Analysis.text differs from the archived bytes")
            sents = list(a.doc.sents)
            analysis_tuple = (a, sents, [s.start for s in sents])
            raw = {m: res[m]["hits"] for m in MODULES_RUN}
            rows += hit_rows(args.config, t, raw, analysis_tuple, by_rank, siblings)
    args.out.mkdir(parents=True, exist_ok=True)
    hits_path = args.out / f"{args.config}.hits.jsonl"
    with hits_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    try:
        from lexinspect._nlp import get_nlp

        nlp_meta = {k: get_nlp().meta.get(k) for k in ("name", "version", "spacy_version")}
    except Exception as e:  # noqa: BLE001 - recorded, not fatal
        nlp_meta = {"error": repr(e)}
    import spacy

    meta = {
        "config": args.config,
        "families_module": args.families_module,
        "families_module_file": getattr(fam, "__file__", None),
        "families_module_sha256": sha256_file(Path(fam.__file__)) if fam is not None else None,
        "enabled": enable,
        "enabled_reported_by_module": enabled_now,
        "lexinspect_version": getattr(lexinspect, "__version__", None),
        "lexinspect_file": lexinspect.__file__,
        "import_root": None if root is None else str(root),
        "python": platform.python_version(),
        "spacy": spacy.__version__,
        "spacy_model": nlp_meta,
        "phrase_lookup_sha256": lookup_sha,
        "phrase_lookup_digest": "worker.lookup_digest: full canonical by-rank entries + siblings",
        "phrase_inventory_sha256": inventory_sha,
        "polysemous_ranks": poly,
        "n_texts": len(texts),
        "texts_jsonl_sha256": sha256_file(args.texts / "texts.jsonl"),
        "n_hits": {m: sum(r["module"] == m for r in rows) for m in MODULES_RUN},
        "hits_sha256": sha256_file(hits_path),
        "pipeline_call": "lexinspect.pipeline.run_all(text, modules=['metadiscourse', 'phrase'])",
    }
    write_json(args.out / f"{args.config}.meta.json", meta)
    print(f"{args.config}: {meta['n_hits']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
