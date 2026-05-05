"""Build metadiscourse marker file for lexinspect Phase 4.

Hyland (2005) 10-category framework. Hedges category uses the HLTCHKUST
verbatim mirror of Hyland's Appendix A (105 items). The other 9 categories
are a curated reference subset drawn from canonical, widely-reproduced
examples in the academic-writing literature — not the full appendix.

Markers are stored lowercased. Multi-word markers use single-space tokens.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA_OUT = Path("/Users/quangnguyendang/webapps/lexinspect/src/lexinspect/data")
TMP = Path("/tmp/lex4")


def _load_hedges() -> list[str]:
    out: list[str] = []
    for line in (TMP / "hedges.txt").read_text().splitlines():
        ln = line.strip()
        if not ln or ln.startswith("#"):
            continue
        out.append(ln.lower())
    return sorted(set(out))


# Curated reference subsets for the other 9 categories.
# Drawn from canonical Hyland 2005 reproductions widely cited in the L2
# writing literature; not Hyland's full Appendix A.
BOOSTERS = [
    "actually", "always", "believe", "beyond doubt", "certain", "certainly",
    "clear", "clearly", "conclude", "conclusively", "decidedly", "definite",
    "definitely", "demonstrate", "demonstrates", "establish", "established",
    "evidently", "find", "found", "in fact", "indeed", "indisputable",
    "indisputably", "must", "never", "no doubt", "obvious", "obviously",
    "of course", "particularly", "prove", "proven", "proves", "really",
    "show", "shows", "shown", "sure", "surely", "think", "true", "truly",
    "undeniable", "undeniably", "undoubtedly", "well-known", "without doubt",
]

ATTITUDE_MARKERS = [
    "agree", "amazingly", "appropriate", "appropriately", "astonishing",
    "astonishingly", "correctly", "curious", "curiously", "desirable",
    "disappointing", "disappointingly", "dramatic", "dramatically",
    "essential", "even", "expected", "expectedly", "fortunate", "fortunately",
    "hopefully", "important", "importantly", "inappropriate", "inappropriately",
    "interesting", "interestingly", "ironically", "must", "noteworthy",
    "preferable", "preferably", "prefer", "preferred", "regrettably",
    "remarkable", "remarkably", "shocked", "shocking", "shockingly",
    "striking", "strikingly", "surprised", "surprising", "surprisingly",
    "unbelievable", "unbelievably", "unexpected", "unexpectedly",
    "unfortunate", "unfortunately", "usual", "usually",
]

ENGAGEMENT_MARKERS = [
    "by the way", "consider", "imagine", "incidentally", "let us", "let's",
    "look", "note", "note that", "notice", "notice that", "one's",
    "our", "ours", "ourselves", "picture", "recall", "see", "the reader",
    "think about", "think of", "us", "we", "you", "you can see",
    "you may", "you might", "you must", "you should", "you will",
    "your", "yours",
]

SELF_MENTIONS = [
    "i", "me", "my", "mine", "myself",
    "we", "us", "our", "ours", "ourselves",
    "the author", "the authors", "the writer", "the writers",
    "the researcher", "the researchers", "the present author",
    "the present writer", "the present study", "this paper",
    "this study", "this article", "this thesis",
]

TRANSITIONS = [
    "accordingly", "additionally", "again", "also", "although",
    "and", "as a consequence", "as a result", "at the same time",
    "because", "besides", "but", "by contrast", "by the same token",
    "consequently", "conversely", "equally", "even though", "for",
    "for example", "for instance", "further", "furthermore", "hence",
    "however", "in addition", "in contrast", "in fact",
    "in other words", "in particular", "in spite of", "in the same way",
    "indeed", "instead", "likewise", "meanwhile", "moreover", "namely",
    "nevertheless", "nonetheless", "now", "on the contrary",
    "on the other hand", "or", "rather", "similarly", "since", "so",
    "specifically", "still", "subsequently", "such as", "then",
    "therefore", "though", "thus", "to be sure", "whereas", "while", "yet",
]

FRAME_MARKERS = [
    "all in all", "as a final point", "as mentioned earlier",
    "at this point", "at this stage", "by far", "finally", "first",
    "first of all", "firstly", "for one thing", "i argue", "i mean",
    "i propose", "i suggest", "i want to", "in conclusion", "in short",
    "in sum", "in summary", "lastly", "let me", "my aim",
    "my goal", "my intention", "my purpose", "next", "on the whole",
    "overall", "second", "secondly", "so far", "the aim", "the goal",
    "the purpose", "third", "thirdly", "thus far", "to begin",
    "to conclude", "to start with", "to sum up", "to summarize",
    "to summarise", "we argue", "we propose", "we suggest", "we want to",
]

ENDOPHORIC_MARKERS = [
    "above", "as discussed earlier", "as noted above", "as shown above",
    "as we have seen", "below", "earlier", "example", "examples",
    "figure", "figures", "given above", "in chapter", "in part",
    "in section", "in the chapter", "in the next section",
    "in the previous section", "in the section", "later",
    "next chapter", "next section", "noted above", "page",
    "previous chapter", "previously stated", "see", "see above",
    "see below", "see chapter", "see figure", "see section", "see table",
    "shown below", "shown earlier", "table", "tables", "the above",
    "the example", "the figure", "the table",
]

EVIDENTIALS = [
    "according to", "argues", "argues that", "as", "as far as",
    "as noted by", "asserts", "asserts that", "based on", "believes",
    "believes that", "cited", "cited in", "claim", "claims",
    "claims that", "concludes", "concludes that", "contends", "demonstrates",
    "demonstrates that", "discusses", "found that", "indicates",
    "indicates that", "maintains", "maintains that", "mentions",
    "notes", "notes that", "observes", "observes that", "points out",
    "proposes", "proposes that", "puts it", "puts it as",
    "quoted", "quoted by", "quoted in", "remarks", "reports",
    "reports that", "shows", "shows that", "states", "states that",
    "stresses", "studies show", "suggests", "suggests that", "writes",
]

CODE_GLOSSES = [
    "called", "defined as", "e.g.", "especially", "for example",
    "for instance", "i.e.", "in fact", "in other words", "in particular",
    "indeed", "known as", "meaning", "meaning that", "namely",
    "or", "particularly", "put another way", "put differently",
    "say", "specifically", "such as", "that is", "that is to say",
    "this means", "this means that", "to put it another way",
    "to put it differently", "viz.", "what i mean is", "which is to say",
    "which means", "which means that",
]


CATEGORIES = {
    "interactive": {
        "transitions": TRANSITIONS,
        "frame_markers": FRAME_MARKERS,
        "endophoric_markers": ENDOPHORIC_MARKERS,
        "evidentials": EVIDENTIALS,
        "code_glosses": CODE_GLOSSES,
    },
    "interactional": {
        "hedges": _load_hedges(),
        "boosters": BOOSTERS,
        "attitude_markers": ATTITUDE_MARKERS,
        "engagement_markers": ENGAGEMENT_MARKERS,
        "self_mentions": SELF_MENTIONS,
    },
}


def _normalize(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        norm = re.sub(r"\s+", " ", it.lower()).strip()
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return sorted(out)


def build() -> None:
    categories = {
        dim: {cat: _normalize(items) for cat, items in cats.items()}
        for dim, cats in CATEGORIES.items()
    }
    counts = {
        dim: {cat: len(items) for cat, items in cats.items()}
        for dim, cats in categories.items()
    }
    total = sum(len(items) for cats in categories.values() for items in cats.values())
    out = {
        "source": (
            "Hyland, K. (2005). Metadiscourse: Exploring Interaction in Writing. "
            "Continuum. Hedges category from HLTCHKUST/framing-bias-metric verbatim "
            "mirror of Hyland 2005 Appendix A; remaining 9 categories are a curated "
            "reference subset drawn from canonical reproductions in the L2 academic-"
            "writing literature."
        ),
        "version": "Hyland 10-category curated subset",
        "license": (
            "Code: MIT. The marker lists are factual lexical inventories; the "
            "10-category taxonomy is Hyland's intellectual contribution — cite "
            "Hyland (2005) in any output. Hedges category is a verbatim mirror "
            "of Hyland 2005 Appendix A from HLTCHKUST/framing-bias-metric (no "
            "stated licence; treated as research/educational use)."
        ),
        "marker_count": total,
        "category_counts": counts,
        "categories": categories,
    }
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "metadiscourse.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"Metadiscourse: {total} markers across 10 categories")
    for dim, cats in counts.items():
        print(f"  {dim}: {sum(cats.values())} ({cats})")


if __name__ == "__main__":
    build()
