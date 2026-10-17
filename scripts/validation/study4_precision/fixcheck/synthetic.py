"""SYNTHETIC labels for the dry run only (never for a real check).

Two scenarios over a round's assignment:
- "random": analyse.make_dummy_labels (latent truth per item id, P(correct) .8,
  per-labeller flips and UNSURE), plus injected faults: B misses 1% of items, A
  has a few invalid records (WRONG_CATEGORY naming the claimed category / a
  WRONG_SENSE_LISTED naming no listed sense) and B a few conflicting
  duplicates; the adjudicator answers every assigned item with 10% UNSURE, so
  some references stay unresolved.
- retry: the single registered retry answers two thirds of each role's retry
  manifest (synthetic valid labels); the rest stay missing and become
  non-votes.
- "favourable": the generator peeks at the unblinded key (allowed only because
  it is synthetic): payloads sampled in a REMOVED frame are wrong
  (NOT_METADISCOURSE / NOT_THE_EXPRESSION), everything else CORRECT, with a few
  UNSURE; built to exercise the pass path.
"""

from __future__ import annotations

import json
import random
from typing import Any

import analyse


def _wrong(module: str) -> tuple[str, None]:
    return (
        ("NOT_METADISCOURSE", None) if module == "metadiscourse" else ("NOT_THE_EXPRESSION", None)
    )


def _unsure(module: str) -> dict[str, Any]:
    first = "NOT_METADISCOURSE" if module == "metadiscourse" else "NOT_THE_EXPRESSION"
    return {"label": "UNSURE", "alt_category": None, "note": f"CORRECT or {first}: synthetic"}


def random_primaries(key: list[dict[str, Any]], items: dict[str, dict[str, Any]], seed: int):
    rows = [{"id": k["id"], "module": k["module"], "category": k["category"]} for k in key]
    a = analyse.make_dummy_labels(rows, items, seed + 1)
    b = analyse.make_dummy_labels(rows, items, seed + 2)
    r = random.Random(seed)
    lines_a = [json.dumps(x) for x in a]
    # A: invalid records on a few items.
    for i, x in enumerate(a[:200]):
        it = items[x["id"]]
        if it["module"] == "metadiscourse" and i % 40 == 0:
            bad = {
                "id": x["id"],
                "label": "WRONG_CATEGORY",
                "alt_category": it["claimed"]["category"],
                "note": None,
            }
            lines_a[i] = json.dumps(bad)
        if it["module"] == "phrase" and i % 50 == 1:
            bad = {
                "id": x["id"],
                "label": "WRONG_SENSE_LISTED",
                "alt_category": "NO SUCH SENSE",
                "note": None,
            }
            lines_a[i] = json.dumps(bad)
    # B: 1% missing, a few conflicting duplicates.
    keep = [x for x in b if r.random() >= 0.01]
    lines_b = [json.dumps(x) for x in keep]
    for x in keep[:3]:
        other = dict(
            x,
            label="CORRECT" if x["label"] != "CORRECT" else _wrong(items[x["id"]]["module"])[0],
            alt_category=None,
        )
        lines_b.append(json.dumps(other))
    return lines_a, lines_b


def random_adjudicator(ids: list[str], items: dict[str, dict[str, Any]], seed: int) -> list[str]:
    rows = [
        {"id": i, "module": items[i]["module"], "category": items[i]["claimed"].get("category")}
        for i in ids
    ]
    labs = analyse.make_dummy_labels(rows, items, seed + 3, p_unsure=0.10)
    return [json.dumps(x) for x in labs]


def favourable(
    key: list[dict[str, Any]], seed: int
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    r = random.Random(seed)
    removed = {
        k["id"]
        for k in key
        if any(
            mb["frame"].endswith("|affected|REMOVED") and mb["role"] == "sampled"
            for mb in k["memberships"]
        )
    }
    a, b, truth = [], [], {}
    for k in key:
        lab, alt = _wrong(k["module"]) if k["id"] in removed else ("CORRECT", None)
        truth[k["id"]] = {"id": k["id"], "label": lab, "alt_category": alt, "note": None}
        ra = dict(truth[k["id"]])
        rb = dict(truth[k["id"]])
        if r.random() < 0.01:
            ra = {"id": k["id"], **_unsure(k["module"])}
        a.append(json.dumps(ra))
        b.append(json.dumps(rb))
    return a, b, truth


def favourable_adjudicator(ids: list[str], truth: dict[str, dict[str, Any]]) -> list[str]:
    return [json.dumps(truth[i]) for i in ids]


def retry_answers(ids: list[str], items: dict[str, dict[str, Any]], seed: int) -> list[str]:
    """Valid synthetic retry labels for two thirds of the manifest ids; the rest stay missing."""
    keep = [i for k, i in enumerate(sorted(ids)) if k % 3 != 2]
    rows = [
        {"id": i, "module": items[i]["module"], "category": items[i]["claimed"].get("category")}
        for i in keep
    ]
    return [json.dumps(x) for x in analyse.make_dummy_labels(rows, items, seed, p_unsure=0.0)]
