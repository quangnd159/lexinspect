"""Build the maintainer's labelling page for Study 4's maintainer sample.

    uv run python -I scripts/validation/study4_precision/human_page.py \
        [--dir .cache/validation/study4] [--out PAGE.html]
        [--second-pass PASS1_VALIDATED.jsonl | --practice IDS.txt]

Writes `<dir>/human_labelling.html` (or --out): a self-contained page that shows
the maintainer-sample items one at a time, blind (no model labels, no source),
with the guidelines alongside, scrolled to the claimed category's section (or
Part B for PHRASE items) as a lookup aid. Items follow the maintainer role's
order in orders.json if present, else items.jsonl order.

Label rules enforced on save, matching analyse.py's validation:
- the alternative-category selector starts empty and must be chosen; it never
  offers the claimed category;
- EXTERNAL_CONNECTIVE is offered only for claimed `transitions`;
- WRONG_SENSE_LISTED is offered only when the item has other listed senses and
  needs one of them chosen; WRONG_SENSE_UNLISTED needs a gloss of 1-6 words,
  stored in capitals, that is not a listed sense or the claimed entry;
- alt_category is null for every other label;
- notes are at most 25 words; UNSURE needs a note of the form
  "READING or READING: reason" naming at least two distinct readings, each a
  label of the module or (metadiscourse) a category key;
- every exported record has id, label, alt_category and note.
Labels are kept in the browser's local storage and exported as
`maintainer_<labelled>of<total>.jsonl`; export warns if items are unlabelled.
The page stays in the gitignored cache because PHRASE items quote the PHRASE
List.

Second pass (pre-specified, before unblinding): --second-pass takes the
validated first-pass file written by

    uv run python scripts/validation/study4_precision/analyse.py \
        --validate-pass1 maintainer_RAW.jsonl \
        [--pass1-retry maintainer_retry_RAW.jsonl --manifest DIR/retry_maintainer.jsonl] \
        --validated-out maintainer_pass1_validated.jsonl \
        --validation-log maintainer_pass1_validation.json

(the validator-accepted records only, one per id, sorted; see analyse.py). A
file that has any invalid record (bad note or alternative, missing keys,
conflicting duplicates, unknown or unassigned ids, malformed lines), or valid
records not in that validated form (such as a raw page export), is refused and
the page is not built: the message names the validation command, because
labels are never corrected by hand. The assignment is analyse.second_pass_ids
of the validated file, the same assignment the analysis uses. Valid first-pass
items that are missing never become second-pass items. The page holds the
assigned items in the maintainer order, equally blind (no model labels), each
with the maintainer's own first-pass note; the same label rules apply (UNSURE
stays allowed). The SHA-256 of the validated file is shown on the page and
written into every exported record (`pass1_sha256`); analyse.py requires it on
every record and checks it against --maintainer, which must be the same file.
Labels use a separate local-storage key and export as
`maintainer_pass2_<k>of<n>.jsonl`.
Written to `<dir>/human_labelling_pass2.html` by default. If the first pass has
no UNSURE labels there is nothing to do: the command prints "No second-pass
items: your first pass had no UNSURE labels", writes no page, and exits 0.

Practice (--practice IDS.txt): a page of the listed items, which must not be in
the maintainer sample, under a "PRACTICE — not counted" banner, with its own
local-storage key and a `PRACTICE_not_counted_*.jsonl` export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyse as A  # noqa: E402

NO_SECOND_PASS = "No second-pass items: your first pass had no UNSURE labels"
ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "validation" / "study4"
GUIDE = ROOT / "docs" / "validation" / "study4-guidelines.md"


def sample_ids(d: Path) -> list[str]:
    orders = d / "orders.json"
    if orders.exists():
        return json.loads(orders.read_text())["roles"]["maintainer"]["order"]
    key = [json.loads(x) for x in (d / "key.jsonl").read_text().splitlines() if x.strip()]
    if any("in_maintainer_sample" in r for r in key):
        return sorted(r["id"] for r in key if r.get("in_maintainer_sample"))
    return (d / "human_sample_ids.txt").read_text().split()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", type=Path, default=CACHE)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--guide", type=Path, default=GUIDE)
    ap.add_argument(
        "--second-pass",
        type=Path,
        metavar="PASS1",
        help="build the second-pass page from the validated first-pass file "
        "(analyse.py --validate-pass1; its UNSURE items only)",
    )
    ap.add_argument(
        "--practice",
        type=Path,
        metavar="IDS",
        help="practice page of these item ids (not in the maintainer sample; not counted)",
    )
    args = ap.parse_args(argv)
    if args.second_pass and args.practice:
        ap.error("--second-pass and --practice are exclusive")
    wanted = sample_ids(args.dir)
    by_id = {
        it["id"]: it
        for it in (
            json.loads(line)
            for line in (args.dir / "items.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    prior: dict[str, str | None] = {}
    pass1_sha = ""
    mode = "pass1"
    if args.second_pass:
        mode = "pass2"
        assigned, prior, pass1_sha = second_pass_assignment(args.second_pass, by_id, wanted)
        if not assigned:
            print(NO_SECOND_PASS)
            return
        wanted = [i for i in wanted if i in set(assigned)]
    elif args.practice:
        mode = "practice"
        ids = args.practice.read_text(encoding="utf-8").split()
        clash = sorted(set(ids) & set(wanted))
        if clash:
            raise SystemExit(f"practice ids in the maintainer sample: {clash}")
        wanted = ids
    default = {
        "pass1": "human_labelling.html",
        "pass2": "human_labelling_pass2.html",
        "practice": "practice_labelling.html",
    }[mode]
    out = args.out or args.dir / default
    missing = [i for i in wanted if i not in by_id]
    assert not missing, f"{len(missing)} maintainer-sample ids missing from items.jsonl"
    sample = [by_id[i] for i in wanted]
    guide = args.guide.read_text(encoding="utf-8")
    pass_no = {"pass1": 1, "pass2": 2, "practice": 0}[mode]
    stamp = hashlib.sha256(
        (json.dumps([sample, prior, pass_no, pass1_sha], sort_keys=True) + guide).encode("utf-8")
    ).hexdigest()[:12]

    def js(v: object) -> str:
        return json.dumps(v, ensure_ascii=False).replace("</", "<\\/")

    html = (
        TEMPLATE.replace("__ITEMS__", js(sample))
        .replace("__GUIDE__", js(guide))
        .replace("__PRIOR__", js(prior))
        .replace("__PASS__", str(pass_no))
        .replace("__PASS1SHA__", pass1_sha)
        .replace("__STAMP__", stamp)
    )
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({mode}, {len(sample)} items, stamp {stamp})")


def second_pass_assignment(
    path: Path, items: dict[str, dict], sample: list[str]
) -> tuple[list[str], dict[str, str | None], str]:
    """The analyser's assignment: analyse.second_pass_ids of the validated first pass.

    Returns (ids, {id: first-pass note}, SHA-256 of the file). A file that is not a
    validated first-pass file (analyse.py --validate-pass1) stops the build with the
    list of problems; nothing is repaired or skipped here."""
    problems = A.validated_form_problems(path, items, sample)
    if problems:
        raise SystemExit(
            f"{path}: not a validated first-pass file:\n  "
            + "\n  ".join(problems)
            + "\nDo not edit or relabel records by hand. Build the validated file from the raw "
            "export (and the single retry export, if any) with\n"
            "  uv run python scripts/validation/study4_precision/analyse.py --validate-pass1 RAW "
            "[--pass1-retry RETRY --manifest RETRY_MANIFEST] --validated-out VALIDATED "
            "--validation-log LOG\n"
            "and pass VALIDATED here and as --maintainer in the analysis."
        )
    pass1 = A.load_labels(path, items, sample, A.MAINTAINER)
    ids = A.second_pass_ids(pass1)
    return ids, {i: pass1.labels[i].get("note") for i in ids}, A.file_sha256(path)


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Study 4: maintainer labelling</title>
<style>
  :root { --ink:#1d1d1f; --muted:#6e6e73; --line:#d2d2d7; --accent:#0b57d0; --bg:#fbfbfd; }
  * { box-sizing: border-box; }
  body { margin:0; font:16px/1.5 system-ui, -apple-system, sans-serif; color:var(--ink); background:var(--bg); }
  main { display:grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); height:100vh; }
  #work { padding:28px 36px; overflow:auto; border-right:1px solid var(--line); }
  #guide { padding:20px 28px; overflow:auto; font-size:14px; background:#fff; }
  #guide pre { white-space:pre-wrap; font:13px/1.5 ui-monospace, Menlo, monospace; }
  .bar { display:flex; justify-content:space-between; align-items:center; color:var(--muted); font-size:14px; }
  .progress { height:4px; background:var(--line); border-radius:2px; margin:8px 0 24px; }
  .progress > div { height:100%; background:var(--accent); border-radius:2px; }
  .ctx { font:19px/1.65 Georgia, serif; background:#fff; border:1px solid var(--line); border-radius:10px; padding:20px 22px; }
  mark { background:#fff1a8; padding:1px 3px; border-radius:3px; font-weight:600; }
  .claim { margin:20px 0; padding:14px 18px; border-left:4px solid var(--accent); background:#eef3fd; border-radius:0 8px 8px 0; }
  .claim small { color:var(--muted); display:block; }
  .prior { margin:-8px 0 16px; padding:10px 14px; background:#fff7e0; border-radius:8px; display:none; }
  .labels { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:18px 0; }
  button { font:inherit; padding:12px 14px; border:1px solid var(--line); border-radius:8px; background:#fff; cursor:pointer; text-align:left; }
  button:hover { border-color:var(--accent); }
  button.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  button kbd { float:right; opacity:.6; font-size:12px; }
  label { display:block; font-size:14px; color:var(--muted); margin-top:12px; }
  input, select { font:inherit; width:100%; padding:8px 10px; border:1px solid var(--line); border-radius:6px; margin-top:4px; }
  .nav { display:flex; gap:10px; margin-top:22px; }
  .nav button { text-align:center; flex:1; }
  .warn { color:#b3261e; font-size:14px; min-height:1.5em; margin-top:10px; }
  .done { font-size:14px; color:var(--muted); }
</style>
</head>
<body>
<div id="banner" style="display:none; background:#b3261e; color:#fff; font:700 20px/1.4 system-ui; text-align:center; padding:10px;">PRACTICE — not counted</div>
<main>
  <section id="work">
    <div class="bar"><span id="pos"></span><span>Study 4 maintainer labels<span id="passtag"></span> · <code>__STAMP__</code></span></div>
    <div class="progress"><div id="prog"></div></div>
    <div class="ctx" id="ctx"></div>
    <div class="claim" id="claim"></div>
    <div class="prior" id="prior"></div>
    <div class="labels" id="labels"></div>
    <div id="altwrap">
      <label for="alt" id="altlab">Actual category</label>
      <select id="altsel"></select>
      <input id="alt" placeholder="Short gloss of the actual sense, in capitals, e.g. FROM INSIDE">
    </div>
    <label for="note">Note (optional, at most 25 words; with UNSURE required: "CORRECT or NOT_METADISCOURSE: reason")</label>
    <input id="note" maxlength="400">
    <div class="warn" id="warn"></div>
    <div class="nav">
      <button id="prev">← Previous</button>
      <button id="next">Save and next →</button>
    </div>
    <p class="done" id="done"></p>
    <div class="nav">
      <button id="export">Export labels (.jsonl)</button>
    </div>
    <p class="done">Keys: 1–5 choose a label, Enter saves and moves on, ← goes back. Progress is saved in this browser automatically.</p>
  </section>
  <section id="guide"><pre id="guidetext"></pre></section>
</main>
<script>
const ITEMS = __ITEMS__;
const GUIDE = __GUIDE__;
const PASS = __PASS__;
const PRIOR = __PRIOR__;
const PASS1_SHA = "__PASS1SHA__";
const KEY = PASS === 2 ? "study4-maintainer-pass2-__STAMP__"
  : PASS === 0 ? "study4-PRACTICE-not-counted-__STAMP__" : "study4-maintainer-__STAMP__";
const EXPORT_PREFIX = PASS === 2 ? "maintainer_pass2_" : PASS === 0 ? "PRACTICE_not_counted_" : "maintainer_";
const CATS = ["transitions","frame_markers","endophoric_markers","evidentials","code_glosses",
  "hedges","boosters","attitude_markers","engagement_markers","self_mentions"];
const ALL_LABELS = {
  metadiscourse: ["CORRECT","WRONG_CATEGORY","EXTERNAL_CONNECTIVE","NOT_METADISCOURSE","UNSURE"],
  phrase: ["CORRECT","WRONG_SENSE_LISTED","WRONG_SENSE_UNLISTED","NOT_THE_EXPRESSION","UNSURE"],
};
// Same normalisation as analyse.norm_sense: straight quotes, collapsed whitespace, case-folded.
function normSense(s) {
  return String(s).replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, " ").trim().toLowerCase();
}
function words(s) { return String(s).trim().split(/\s+/).filter(Boolean).length; }
// Same rule as analyse.unsure_readings.
function unsureProblem(note, module) {
  if (!note || !note.trim()) return "With UNSURE, name the readings: e.g. CORRECT or NOT_METADISCOURSE: reason.";
  const m = /^\s*([^:]+):\s*\S/.exec(note);
  if (!m) return "Start the note with the readings joined by 'or', then a colon, then the reason.";
  const readings = m[1].trim().split(/\s+or\s+/).map(r => r.trim());
  const allowed = ALL_LABELS[module].concat(module === "metadiscourse" ? CATS : []);
  const bad = readings.filter(r => !allowed.includes(r));
  if (bad.length) return `Not a label${module === "metadiscourse" ? " or category key" : ""}: ${bad.join(", ")}.`;
  if (new Set(readings).size < 2) return "Name at least two different readings.";
  return null;
}
function others(it) { return (it.claimed.other_senses_in_list || []).map(o => o.expression); }
function labelsFor(it) {
  return ALL_LABELS[it.module].filter(l =>
    (l !== "EXTERNAL_CONNECTIVE" || it.claimed.category === "transitions") &&
    (l !== "WRONG_SENSE_LISTED" || others(it).length > 0));
}
const store = JSON.parse(localStorage.getItem(KEY) || "{}");
let i = Math.max(0, ITEMS.findIndex(it => !store[it.id]));
if (i < 0 || !ITEMS.some(it => !store[it.id])) i = 0;
let chosen = null;
const $ = id => document.getElementById(id);
$("guidetext").textContent = GUIDE;

function fillSelect(it) {
  const opts = it.module === "metadiscourse" ? CATS.filter(c => c !== it.claimed.category) : others(it);
  $("altsel").innerHTML = `<option value="">— choose —</option>` +
    opts.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
  $("altsel").value = "";
}

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

function scrollGuide(it) {
  const pre = $("guidetext");
  const needle = it.module === "phrase" ? "## Part B." : "#### `" + it.claimed.category + "`";
  const idx = GUIDE.indexOf(needle);
  if (idx < 0) return;
  const ratio = idx / GUIDE.length;
  $("guide").scrollTop = ratio * pre.scrollHeight - 10;
}

function render() {
  const it = ITEMS[i];
  const saved = store[it.id];
  chosen = saved ? saved.label : null;
  $("pos").textContent = `Item ${i + 1} of ${ITEMS.length}`;
  if (PASS === 2) {
    $("passtag").textContent = ` (second pass: your first-pass UNSURE items; first-pass file SHA-256 ${PASS1_SHA.slice(0, 16)}…)`;
    $("prior").style.display = "block";
    $("prior").innerHTML = `<small>Your first-pass note (UNSURE):</small> ${esc(PRIOR[it.id] || "(none)")}`;
  }
  const n = ITEMS.filter(x => store[x.id]).length;
  $("prog").style.width = (100 * n / ITEMS.length) + "%";
  $("done").textContent = `${n} of ${ITEMS.length} labelled.`;
  $("ctx").innerHTML = esc(it.context).replace(/⟦(.*?)⟧/, "<mark>$1</mark>");
  if (it.module === "metadiscourse") {
    $("claim").innerHTML = `<small>lexinspect says this is metadiscourse:</small><b>${it.claimed.category}</b> (${it.claimed.dimension})`;
  } else {
    const c = it.claimed;
    const others = (c.other_senses_in_list || []).map(o => `${esc(o.expression)}: <i>${esc(o.example || "")}</i>`).join("<br>");
    $("claim").innerHTML = `<small>lexinspect says this is the PHRASE List entry:</small><b>${esc(c.expression)}</b>` + (c.sense ? ` <small>sense: ${esc(c.sense)}</small>` : "")
      + `<br><small>List example:</small><i>${esc(c.example || "")}</i>`
      + (others ? `<br><small>Other entries with the same wording:</small>${others}` : "");
  }
  $("labels").innerHTML = labelsFor(it).map((l, k) =>
    `<button data-l="${l}" class="${l === chosen ? "on" : ""}">${l}<kbd>${k + 1}</kbd></button>`).join("");
  $("labels").querySelectorAll("button").forEach(b => b.onclick = () => choose(b.dataset.l));
  $("note").value = saved?.note || "";
  fillSelect(it);
  $("alt").value = saved?.label === "WRONG_SENSE_UNLISTED" ? (saved.alt_category || "") : "";
  if (saved && (saved.label === "WRONG_CATEGORY" || saved.label === "WRONG_SENSE_LISTED")) $("altsel").value = saved.alt_category;
  $("warn").textContent = "";
  showAlt();
  scrollGuide(it);
}

function showAlt() {
  const sel = chosen === "WRONG_CATEGORY" || chosen === "WRONG_SENSE_LISTED";
  const txt = chosen === "WRONG_SENSE_UNLISTED";
  $("altwrap").style.display = sel || txt ? "" : "none";
  $("altsel").style.display = sel ? "" : "none";
  $("alt").style.display = txt ? "" : "none";
  $("altlab").textContent = chosen === "WRONG_CATEGORY" ? "Actual category (required)"
    : chosen === "WRONG_SENSE_LISTED" ? "Which listed sense (required)" : "Gloss of the actual sense (required)";
}

function choose(l) {
  chosen = l;
  $("labels").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.l === l));
  showAlt();
}

function save() {
  const it = ITEMS[i];
  if (!chosen) { $("warn").textContent = "Choose a label first."; return false; }
  let alt = null;
  if (!labelsFor(it).includes(chosen)) { $("warn").textContent = "That label is not available for this item."; return false; }
  if (chosen === "WRONG_CATEGORY" || chosen === "WRONG_SENSE_LISTED") {
    alt = $("altsel").value;
    if (!alt) { $("warn").textContent = chosen === "WRONG_CATEGORY" ? "Choose the actual category." : "Choose the listed sense."; return false; }
  }
  if (chosen === "WRONG_SENSE_UNLISTED") {
    alt = $("alt").value.replace(/\s+/g, " ").trim().toUpperCase();
    if (!alt) { $("warn").textContent = "Give a short gloss of the actual sense."; return false; }
    if (words(alt) > 6) { $("warn").textContent = "Keep the gloss to six words or fewer."; return false; }
    if (others(it).concat([it.claimed.expression]).some(o => normSense(o) === normSense(alt))) {
      $("warn").textContent = "That is a listed sense: use WRONG_SENSE_LISTED (or CORRECT)."; return false;
    }
  }
  const note = $("note").value.trim() || null;
  if (note && words(note) > 25) { $("warn").textContent = "Keep the note to 25 words or fewer."; return false; }
  if (chosen === "UNSURE") {
    const problem = unsureProblem(note, it.module);
    if (problem) { $("warn").textContent = problem; return false; }
  }
  store[it.id] = { id: it.id, label: chosen, alt_category: alt, note, labelled_at: new Date().toISOString() };
  if (PASS === 2) store[it.id].pass1_sha256 = PASS1_SHA;
  localStorage.setItem(KEY, JSON.stringify(store));
  return true;
}

$("next").onclick = () => { if (save()) { if (i < ITEMS.length - 1) i++; render(); } };
$("prev").onclick = () => { if (i > 0) i--; render(); };
$("export").onclick = () => {
  const done = ITEMS.filter(it => store[it.id]);
  if (done.length < ITEMS.length &&
      !confirm(`Only ${done.length} of ${ITEMS.length} items are labelled. ` +
               `${ITEMS.length - done.length} will count as missing if you submit this file. Export anyway?`)) return;
  const lines = done.map(it => JSON.stringify(store[it.id])).join("\n") + "\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines], { type: "application/jsonl" }));
  a.download = EXPORT_PREFIX + `${done.length}of${ITEMS.length}.jsonl`;
  a.click();
};
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") {
    if (e.key === "Enter") $("next").click();
    return;
  }
  const opts = labelsFor(ITEMS[i]);
  if (e.key >= "1" && e.key <= String(opts.length)) choose(opts[+e.key - 1]);
  else if (e.key === "Enter") $("next").click();
  else if (e.key === "ArrowLeft") $("prev").click();
});
if (PASS === 0) {
  $("banner").style.display = "block";
  $("passtag").textContent = " — PRACTICE, not counted";
}
if (ITEMS.length === 0) {
  $("work").innerHTML = "<p>No items on this page.</p>";
} else {
  render();
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
