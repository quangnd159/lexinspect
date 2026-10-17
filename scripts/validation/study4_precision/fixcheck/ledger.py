"""The round-1 candidate ledger as code: families, modules, J, a, component identities.

Source: .cache/validation/study4_fix040/CANDIDATE_LEDGER.md (F = 12, all
module-specific; rule lists as revised after implementation audit r1, which
removed PH-03, PH-07, PH-08 and SX-03; verify.ledger_check compares them with
the ledger file) and the protocol's "Error budget": J = 4(F + 5) one-sided
components = 2 rounds x 2 modules x (F family-removal upper bounds + 1
complete-candidate removal upper bound + 2 loss-total upper bounds + 2
baseline-success lower bounds). a = .05 / J for every component; unused
allocation is never recycled.

Identities: R{round}.{module}.{family|COMPLETE}.{removal|loss_STRICT|loss_INV|
success_STRICT|success_INV}. INV is the module's inventory outcome: LENIENT
(metadiscourse) or LIST_LENIENT (PHRASE).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# The finalised ledger lives at the tracked freeze location (maintainer Addendum item 2;
# audit r2 S5); the DRAFT working copy stays under .cache and serves dry runs only.
LEDGER_MD = (
    Path(__file__).resolve().parents[4] / "docs/validation/study4-fix040/CANDIDATE_LEDGER.md"
)
LEDGER_COMPONENTS = LEDGER_MD.parent / "ledger_components.json"
DRAFT_LEDGER_MD = (
    Path(__file__).resolve().parents[4] / ".cache/validation/study4_fix040/CANDIDATE_LEDGER.md"
)
FAMILIES: tuple[str, ...] = (
    "MD-A",
    "MD-B",
    "MD-C",
    "MD-D",
    "MD-E",
    "MD-F",
    "MD-G",
    "MD-H",
    "MD-I",
    "PH-A",
    "PH-B",
    "PH-C",
)
FAMILY_MODULE = {f: ("metadiscourse" if f.startswith("MD-") else "phrase") for f in FAMILIES}
FAMILY_RULES = {
    "MD-A": ("MD-01", "MD-02", "MD-03", "MD-05", "MD-06", "MD-25"),
    "MD-B": ("MD-04",),
    "MD-C": ("MD-07", "MD-08", "MD-09", "MD-10", "MD-11", "MD-12", "MD-30"),
    "MD-D": ("MD-13", "MD-14", "MD-15", "MD-21"),
    "MD-E": ("MD-16", "MD-17", "MD-18", "MD-19"),
    "MD-F": ("MD-20", "MD-22", "MD-23", "MD-24", "MD-26", "MD-27", "MD-28"),
    "MD-G": ("MD-29", "MD-31"),
    "MD-H": ("MD-32",),
    "MD-I": ("SX-01",),
    "PH-A": ("PH-01", "PH-02"),
    "PH-B": ("PH-04", "PH-05", "PH-06", "PH-09", "PH-11", "PH-12"),
    "PH-C": ("PH-10", "PH-13"),
}
MODULES: tuple[str, ...] = ("metadiscourse", "phrase")
ROUNDS: tuple[int, ...] = (1, 2)
F = len(FAMILIES)
J = 4 * (F + 5)
TOTAL_ALPHA = 0.05
A = TOTAL_ALPHA / J  # per-component one-sided level
REMOVAL_TOLERANCE = 0.15
CUMULATIVE_TOLERANCE = 0.05
INV = {"metadiscourse": "LENIENT", "phrase": "LIST_LENIENT"}
GATED_OUTCOMES = {m: ("STRICT", INV[m]) for m in MODULES}
DIAGNOSTIC_OUTCOMES = {"metadiscourse": ("CONNECTIVE",), "phrase": ("PHRASAL",)}
COMPLETE = "COMPLETE"
BASELINE = "BASELINE"
COMPONENT_KINDS = ("removal", "loss_STRICT", "loss_INV", "success_STRICT", "success_INV")


def component_id(rnd: int, module: str, who: str, kind: str) -> str:
    return f"R{rnd}.{module}.{who}.{kind}"


def ledger_components() -> list[dict[str, Any]]:
    """All J component identities with their reserved applicability (before any data)."""
    out = []
    for rnd in ROUNDS:
        for module in MODULES:
            for fam in FAMILIES:
                if rnd == 2:
                    app = "reserved_round_2"
                elif FAMILY_MODULE[fam] == module:
                    app = "applicable_if_frame_nonempty"
                else:
                    app = "reserved_other_module_not_applicable_unless_frame_nonempty"
                out.append(
                    {
                        "id": component_id(rnd, module, fam, "removal"),
                        "round": rnd,
                        "module": module,
                        "who": fam,
                        "kind": "removal",
                        "bound": "upper",
                        "alpha": A,
                        "applicability": app,
                    }
                )
            for kind in COMPONENT_KINDS:
                out.append(
                    {
                        "id": component_id(rnd, module, COMPLETE, kind),
                        "round": rnd,
                        "module": module,
                        "who": COMPLETE,
                        "kind": kind,
                        "bound": "lower" if kind.startswith("success") else "upper",
                        "outcome": None
                        if kind == "removal"
                        else (INV[module] if kind.endswith("INV") else "STRICT"),
                        "alpha": A,
                        "applicability": "reserved_round_2"
                        if rnd == 2
                        else ("applicable_if_frame_nonempty" if kind == "removal" else "required"),
                    }
                )
    return out


def ledger_document() -> dict[str, Any]:
    comps = ledger_components()
    return {
        "ledger": "Study 4 fix-check candidate ledger, round 1 (lexinspect 0.4.0 candidate)",
        "source": ".cache/validation/study4_fix040/CANDIDATE_LEDGER.md",
        "F": F,
        "J": J,
        "J_formula": "4(F + 5)",
        "total_alpha": TOTAL_ALPHA,
        "a": A,
        "families": [
            {"family": f, "module": FAMILY_MODULE[f], "rules": list(FAMILY_RULES[f])}
            for f in FAMILIES
        ],
        "order": "each family alone against the 0.3.3 baseline (prerequisites: none); "
        "COMPLETE enables all twelve",
        "inventory_outcome": INV,
        "tolerances": {"removal": REMOVAL_TOLERANCE, "cumulative": CUMULATIVE_TOLERANCE},
        "n_components": len(comps),
        "components": comps,
    }
