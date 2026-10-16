"""Study 3, step 1: assemble the comparison texts.

Builds ~300 openly licensed English texts of 100-1,000 words into
`.cache/validation/study3/texts/` (gitignored) with a `manifest.jsonl` that
records each text's source, licence, URL, selection details and SHA-256.

Sources (all selections are seeded, SEED below):

- Project Gutenberg (public domain in the US): 100 passages from a fixed list
  of books spanning fiction, children's books, essays, science, philosophy,
  history and practical writing. Each passage starts at a seeded random
  paragraph in the middle 80% of the book and runs whole paragraphs up to a
  seeded random target length.
- Simple English Wikipedia and English Wikipedia (CC BY-SA 4.0): 50 topics
  sampled from Simple Wikipedia's "Very good articles" and "Good articles",
  each paired with the English Wikipedia article it links to. Text is the
  article's prose paragraphs (no headings, lists, tables or reference marks)
  from the start, whole paragraphs up to 1,000 words. Each article is fetched
  at a pinned revision, recorded in `wikipedia_selection.json` next to this
  script, so a rerun reads the same revisions.
- ELLIPSE corpus (Crossley et al. 2023; CC BY-NC-SA 4.0): 100 essays by
  English-language learners in grades 8-12, sampled from the public training
  split among essays of 100-1,000 words.

Texts are never committed. Run with `python -I` (downloaded data is untrusted).
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation" / "study3"
RAW = CACHE / "raw"
TEXTS = CACHE / "texts"
SELECTION = Path(__file__).resolve().parent / "wikipedia_selection.json"

SEED = 20261016
UA = "lexinspect-validation/0.3 (https://github.com/quangnd159/lexinspect; research use)"
MIN_WORDS, MAX_WORDS = 100, 1000

N_GUTENBERG = 100
N_WIKI_TOPICS = 50
N_ELLIPSE = 100

# Fixed candidate list: (Gutenberg ebook id, short title, genre). Chosen for
# genre spread before any text was seen; passages are then sampled with SEED.
GUTENBERG_BOOKS: list[tuple[int, str, str]] = [
    (1342, "Pride and Prejudice", "fiction"),
    (84, "Frankenstein", "fiction"),
    (1661, "The Adventures of Sherlock Holmes", "fiction"),
    (2701, "Moby Dick", "fiction"),
    (98, "A Tale of Two Cities", "fiction"),
    (345, "Dracula", "fiction"),
    (35, "The Time Machine", "fiction"),
    (36, "The War of the Worlds", "fiction"),
    (1400, "Great Expectations", "fiction"),
    (25344, "The Scarlet Letter", "fiction"),
    (11, "Alice's Adventures in Wonderland", "children"),
    (74, "The Adventures of Tom Sawyer", "children"),
    (16, "Peter Pan", "children"),
    (55, "The Wonderful Wizard of Oz", "children"),
    (45, "Anne of Green Gables", "children"),
    (205, "Walden", "essay"),
    (147, "Common Sense", "essay"),
    (2680, "Meditations", "philosophy"),
    (5827, "The Problems of Philosophy", "philosophy"),
    (1497, "The Republic", "philosophy"),
    (2009, "On the Origin of Species", "science"),
    (30155, "Relativity: The Special and General Theory", "science"),
    (14474, "The Chemical History of a Candle", "science"),
    (3300, "The Wealth of Nations", "economics"),
    (1404, "The Federalist Papers", "politics"),
    (20203, "Autobiography of Benjamin Franklin", "memoir"),
    (23, "Narrative of the Life of Frederick Douglass", "memoir"),
    (408, "The Souls of Black Folk", "essay"),
    (10136, "The Book of Household Management", "practical"),
    (37134, "The Elements of Style", "practical"),
]


def get(url: str, *, cache: Path | None = None, binary: bool = False):
    if cache is not None and cache.exists():
        data = cache.read_bytes()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 3:
                    raise
                print(f"  retry {url}: {e}", file=sys.stderr)
                time.sleep(2 + 3 * attempt)
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(data)
        time.sleep(0.5)
    return data if binary else data.decode("utf-8", errors="replace")


def n_words(text: str) -> int:
    return len(text.split())


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def take_paragraphs(paras: list[str], start: int, target: int) -> str | None:
    """Whole paragraphs from `start` until `target` words; never over MAX_WORDS."""
    out: list[str] = []
    total = 0
    for p in paras[start:]:
        w = n_words(p)
        if total + w > MAX_WORDS:
            if total >= MIN_WORDS:
                break
            # A single overlong paragraph: cut at the last sentence end that fits.
            room = MAX_WORDS - total
            words = p.split()
            cut = " ".join(words[:room])
            m = list(re.finditer(r"[.!?][\"'”’)]?(?=\s|$)", cut))
            if not m:
                return None
            p = cut[: m[-1].end()]
            w = n_words(p)
        out.append(p)
        total += w
        if total >= target:
            break
    return "\n\n".join(out) if total >= MIN_WORDS else None


# --- Project Gutenberg -------------------------------------------------------


def gutenberg_paragraphs(raw: str) -> list[str]:
    raw = raw.replace("\r\n", "\n")
    start = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*\n", raw)
    end = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", raw)
    body = raw[start.end() if start else 0 : end.start() if end else len(raw)]
    paras = []
    for block in re.split(r"\n\s*\n", body):
        lines = [ln.strip() for ln in block.strip().split("\n")]
        p = " ".join(ln for ln in lines if ln)
        p = re.sub(r"_(?=\S)([^_]+?)_", r"\1", p)  # PG italics markup: _word_
        p = re.sub(r"\[(Illustration|Footnote)[^\]]*\]", "", p).strip()
        p = re.sub(r"\s+", " ", p)
        # Prose only: long enough, ends like a sentence, not a shouted heading.
        if n_words(p) < 15 or p.upper() == p or not re.search(r"[.!?][\"'”’)]?$", p):
            continue
        paras.append(p)
    return paras


def build_gutenberg(rng: random.Random) -> list[dict]:
    books = {}
    for ebook, title, genre in GUTENBERG_BOOKS:
        url = f"https://www.gutenberg.org/cache/epub/{ebook}/pg{ebook}.txt"
        try:
            raw = get(url, cache=RAW / "gutenberg" / f"pg{ebook}.txt")
        except Exception as e:  # noqa: BLE001
            print(f"  skip Gutenberg {ebook}: {e}", file=sys.stderr)
            continue
        paras = gutenberg_paragraphs(raw)
        if len(paras) < 20:
            print(f"  skip Gutenberg {ebook}: only {len(paras)} prose paragraphs", file=sys.stderr)
            continue
        books[ebook] = (title, genre, paras, sha(raw), url)
    ids = sorted(books)
    out: list[dict] = []
    used: set[tuple[int, int]] = set()
    tries = 0
    while len(out) < N_GUTENBERG and tries < 10_000:
        tries += 1
        ebook = rng.choice(ids)
        title, genre, paras, raw_sha, url = books[ebook]
        lo, hi = int(len(paras) * 0.1), int(len(paras) * 0.9)
        start = rng.randrange(lo, max(lo + 1, hi))
        target = rng.randint(MIN_WORDS, MAX_WORDS)
        if any(e == ebook and abs(s - start) < 15 for e, s in used):
            continue
        text = take_paragraphs(paras, start, target)
        if text is None:
            continue
        used.add((ebook, start))
        out.append(
            {
                "id": f"pg{ebook}-p{start:05d}",
                "source": "Project Gutenberg",
                "genre": genre,
                "title": title,
                "licence": "Public domain in the USA (Project Gutenberg); PG header/licence removed",
                "url": url,
                "raw_sha256": raw_sha,
                "selection": {"start_paragraph": start, "target_words": target},
                "text": text,
            }
        )
    return out


# --- Wikipedia ---------------------------------------------------------------


def api(host: str, **params) -> dict:
    params = {"format": "json", "formatversion": "2", **params}
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    return json.loads(get(url))


class _ProseParagraphs(HTMLParser):
    """Text of top-level <p> elements; skips references, styles, maths, tables."""

    SKIP_TAGS = {"style", "script", "sup", "table", "math", "figure", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paras: list[str] = []
        self._in_p = 0
        self._skip = 0
        self._stack: list[bool] = []
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class") or ""
        skip = (
            tag in self.SKIP_TAGS
            or "mwe-math" in cls
            or "reference" in cls
            or "noprint" in cls
            or "IPA" in cls
        )
        if tag in ("br", "img", "wbr", "meta", "link", "hr"):
            return
        self._stack.append(skip)
        if skip:
            self._skip += 1
        if tag == "p" and not self._skip:
            self._in_p += 1
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("br", "img", "wbr", "meta", "link", "hr"):
            return
        if tag == "p" and self._in_p and not self._skip:
            self._in_p -= 1
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            text = re.sub(r"\[(\d+|[a-z]|citation needed|note \d+)\]", "", text)
            text = re.sub(r"\s+([,.;:])", r"\1", text)
            if text:
                self.paras.append(text)
        if self._stack and self._stack.pop():
            self._skip -= 1

    def handle_data(self, data):
        if self._in_p and not self._skip:
            self._buf.append(data)


def wiki_text(host: str, revid: int) -> str:
    data = api(host, action="parse", oldid=revid, prop="text", disableeditsection=1)
    parser = _ProseParagraphs()
    parser.feed(data["parse"]["text"])
    paras = [p for p in parser.paras if n_words(p) >= 8]
    return take_paragraphs(paras, 0, MAX_WORDS) or ""


def wiki_selection(rng: random.Random) -> list[dict]:
    if SELECTION.exists():
        return json.loads(SELECTION.read_text("utf-8"))["topics"]
    titles: list[str] = []
    for cat in ("Category:Very good articles", "Category:Good articles"):
        cont: dict = {}
        while True:
            d = api(
                "simple.wikipedia.org",
                action="query",
                list="categorymembers",
                cmtitle=cat,
                cmnamespace=0,
                cmlimit=500,
                **cont,
            )
            titles += [m["title"] for m in d["query"]["categorymembers"]]
            if "continue" not in d:
                break
            cont = d["continue"]
    titles = sorted(set(titles))
    rng.shuffle(titles)
    topics: list[dict] = []
    for t in titles:
        if len(topics) >= N_WIKI_TOPICS:
            break
        d = api(
            "simple.wikipedia.org",
            action="query",
            titles=t,
            prop="langlinks|revisions",
            lllang="en",
            rvprop="ids|timestamp",
        )
        page = d["query"]["pages"][0]
        if not page.get("langlinks"):
            continue
        en_title = page["langlinks"][0]["title"]
        e = api(
            "en.wikipedia.org",
            action="query",
            titles=en_title,
            prop="revisions",
            rvprop="ids|timestamp",
            redirects=1,
        )
        epage = e["query"]["pages"][0]
        if "revisions" not in epage:
            continue
        topics.append(
            {
                "simple_title": page["title"],
                "simple_revid": page["revisions"][0]["revid"],
                "simple_timestamp": page["revisions"][0]["timestamp"],
                "en_title": epage["title"],
                "en_revid": epage["revisions"][0]["revid"],
                "en_timestamp": epage["revisions"][0]["timestamp"],
            }
        )
    SELECTION.write_text(
        json.dumps(
            {
                "seed": SEED,
                "pool": "Simple English Wikipedia: Category:Very good articles + Category:Good articles",
                "pool_size": len(titles),
                "topics": topics,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    return topics


def build_wikipedia(rng: random.Random) -> list[dict]:
    out: list[dict] = []
    for i, t in enumerate(wiki_selection(rng)):
        for variety, host, title, revid in (
            ("simple", "simple.wikipedia.org", t["simple_title"], t["simple_revid"]),
            ("en", "en.wikipedia.org", t["en_title"], t["en_revid"]),
        ):
            cache = RAW / "wikipedia" / f"{variety}-{revid}.txt"
            if cache.exists():
                text = cache.read_text("utf-8")
            else:
                text = wiki_text(host, revid)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(text, "utf-8")
            if n_words(text) < MIN_WORDS:
                print(f"  skip {variety} {title}: {n_words(text)} words", file=sys.stderr)
                continue
            out.append(
                {
                    "id": f"wiki-{variety}-{i:03d}",
                    "source": "Simple English Wikipedia"
                    if variety == "simple"
                    else "English Wikipedia",
                    "genre": f"encyclopedia-{variety}",
                    "title": title,
                    "licence": "CC BY-SA 4.0 (Wikipedia contributors)",
                    "url": f"https://{host}/w/index.php?oldid={revid}",
                    "selection": {"topic_index": i, "revid": revid},
                    "text": text,
                }
            )
    return out


# --- ELLIPSE -----------------------------------------------------------------

ELLIPSE_URL = (
    "https://raw.githubusercontent.com/scrosseye/ELLIPSE-Corpus/main/ELLIPSE_Final_github_train.csv"
)


def build_ellipse(rng: random.Random) -> list[dict]:
    raw = get(ELLIPSE_URL, cache=RAW / "ellipse" / "ELLIPSE_Final_github_train.csv")
    csv.field_size_limit(10**8)
    rows = list(csv.DictReader(raw.splitlines(keepends=True)))
    pool = []
    for r in rows:
        text = r["full_text"].replace("\r\n", "\n").strip()
        if MIN_WORDS <= n_words(text) <= MAX_WORDS:
            pool.append((r["text_id_kaggle"], text, r))
    pool.sort(key=lambda x: x[0])
    picks = rng.sample(pool, N_ELLIPSE)
    out = []
    for tid, text, r in picks:
        out.append(
            {
                "id": f"ellipse-{tid}",
                "source": "ELLIPSE corpus (train split)",
                "genre": "learner-essay",
                "title": f"ELLIPSE {tid} (grade {r['grade']}, prompt: {r['prompt']})",
                "licence": "CC BY-NC-SA 4.0 (Crossley et al. 2023)",
                "url": ELLIPSE_URL,
                "selection": {"pool_size": len(pool), "overall_score": r["Overall"]},
                "text": text,
            }
        )
    return out


def main() -> None:
    TEXTS.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    print("Gutenberg ...", file=sys.stderr)
    items += build_gutenberg(random.Random(SEED))
    print("Wikipedia ...", file=sys.stderr)
    items += build_wikipedia(random.Random(SEED + 1))
    print("ELLIPSE ...", file=sys.stderr)
    items += build_ellipse(random.Random(SEED + 2))
    for old in TEXTS.glob("*.txt"):
        old.unlink()
    with (CACHE / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for it in items:
            text = it.pop("text")
            (TEXTS / f"{it['id']}.txt").write_text(text, "utf-8")
            it["words_whitespace"] = n_words(text)
            it["sha256"] = sha(text)
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    by_src: dict[str, int] = {}
    for it in items:
        by_src[it["source"]] = by_src.get(it["source"], 0) + 1
    print(json.dumps({"n": len(items), "by_source": by_src}, indent=1), file=sys.stderr)


if __name__ == "__main__":
    main()
