// Many texts: a queue of analyses run one or two at a time, and a table that
// fills in as they finish. Each text goes through the same /v1/analyze as the
// main page; the table reads the same numbers, and the CSV writes the same
// columns as a single-text summary export, so batch rows stack with them.
//
// The table is in the interface language; the CSV stays English research data
// (export.js), including the names given to pasted texts.

const MAX_TEXTS = 100;
const CONCURRENCY = 2;
let LIMIT_BYTES = 50_000;

const state = {
  items: [], // {id, name, paste?, text, status, data, error, variant}
  variant: store.get('lexinspect:variant', 'gb') === 'us' ? 'us' : 'gb',
  sort: { key: null, dir: 1 },
  running: 0,
  seq: 0,
};

const encoder = new TextEncoder();

document.querySelector('.toplinks').appendChild(I18n.picker());
fitTopbar();

/** A size in kilobytes, in the locale's unit style ("12.3 kB", "12,3 ko"). */
function kb(bytes, d = 1) {
  return new Intl.NumberFormat(I18n.intl, { style: 'unit', unit: 'kilobyte', unitDisplay: 'short', minimumFractionDigits: d, maximumFractionDigits: d }).format(bytes / 1000);
}

/** A message for a failed API request, from its HTTP status and error code (api.py, _human.py). 0 = no response. */
function apiMessage(status, code = '') {
  if (status === 413 || code === 'text_too_large') return t('This text is too long: the limit is {limit}. Analyse it in parts.', { limit: kb(LIMIT_BYTES, 0) });
  if (status === 429) return t('Too many analyses in a short time. Wait a minute and try again.');
  if (code === 'challenge_unavailable') return t('The human check is unavailable at the moment. Try again in a minute.');
  if (status === 403 || code === 'challenge_required' || code === 'challenge_failed') return t('The human check didn’t go through. Try again.');
  if (status === 422 || code === 'invalid_request') return t('This text couldn’t be read. Paste it in again as plain text.');
  if (!status || status >= 500) return t('A temporary problem stopped the analysis. Try again in a moment.');
  return t('The analysis failed (error {status}). Try again.', { status });
}

// Row errors are kept as functions so they follow a change of language; an
// Error from another module (files.js, human.js) keeps its own text.
const errorText = (item) => (typeof item.error === 'function' ? item.error() : item.error);

/** The name shown for a text: its file name, or "Text 3: The first words…" for a pasted one. */
function displayName(item) {
  return item.paste ? t('Text {n}: {start}', { n: num(item.paste.n), start: `⁨${item.paste.start}⁩` }) : item.name;
}

// ---- adding texts ------------------------------------------------------------------

async function addFiles(files) {
  const list = [...files];
  for (const file of list) {
    if (state.items.length >= MAX_TEXTS) {
      toast(t('Up to {count} texts at a time. The rest weren’t added.', { count: num(MAX_TEXTS) }));
      break;
    }
    try {
      add(file.name, await Files.read(file));
    } catch (err) {
      state.items.push({ id: ++state.seq, name: file.name, text: '', status: 'error', error: err instanceof Files.FileError ? err.message : () => t('This file couldn’t be read.') });
    }
  }
  pump();
  render();
}

function add(name, text, paste = null) {
  const body = text.trim();
  const bytes = encoder.encode(body).length;
  const item = { id: ++state.seq, name, paste, text: body, status: 'queued' };
  if (!body) Object.assign(item, { status: 'error', error: () => t('This file has no text.') });
  else if (bytes > LIMIT_BYTES) Object.assign(item, { status: 'error', error: () => t('This text is {size}; the limit is {limit} per text.', { size: kb(bytes), limit: kb(LIMIT_BYTES, 0) }) });
  state.items.push(item);
}

// ---- running -------------------------------------------------------------------------

async function analyseItem(item, attempt = 0) {
  item.status = 'running';
  const variant = state.variant;
  render();
  try {
    const res = await Human.fetch('/v1/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: item.text, variant, source: 'web-batch' }),
    });
    if (res.status === 429 && attempt < 4) {
      // Rate limited: back off and try again, so a long batch finishes on its own.
      await new Promise((r) => setTimeout(r, 4000 * (attempt + 1)));
      return analyseItem(item, attempt + 1);
    }
    if (!res.ok) {
      let code = '';
      try {
        const j = await res.json();
        code = j.detail?.error || j.error || '';
      } catch {}
      const status = res.status;
      throw Object.assign(new Error(apiMessage(status, code)), { again: () => apiMessage(status, code) });
    }
    const data = await res.json();
    data.submitted = item.text;
    item.data = data;
    // The spelling variety changed while this text was out: analyse it again.
    item.status = variant === state.variant ? 'done' : 'queued';
  } catch (err) {
    item.status = 'error';
    // fetch() rejects with a TypeError when the network fails.
    item.error = err instanceof TypeError ? () => apiMessage(0) : err.again ?? (err.message || (() => t('This text couldn’t be analysed.')));
  }
}

function pump() {
  while (state.running < CONCURRENCY) {
    const next = state.items.find((x) => x.status === 'queued');
    if (!next) break;
    state.running++;
    analyseItem(next).finally(() => {
      state.running--;
      // Start the next one first, so a rendering problem can never stall the queue.
      pump();
      render();
    });
  }
}

// ---- table ---------------------------------------------------------------------------

const LEVEL_RANK = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };

function columns() {
  const target = Prefs.target;
  const band = (v) => (v == null ? '25K+' : `${v}K`);
  return [
    { key: 'words', label: t('Words'), get: (r) => r.readability.counts.words, fmt: (v) => num(v) },
    {
      key: 'level', label: t('Level estimate'), title: t('Estimated CEFR level of a reading text, with its likely range'),
      get: (r) => (r.level?.applicable ? LEVEL_RANK[r.level.level] : null),
      show: (r) => (r.level?.applicable ? (r.level.range.length > 1 ? t('{level} ({low}–{high})', { level: r.level.level, low: r.level.range[0], high: r.level.range[r.level.range.length - 1] }) : r.level.level) : '–'),
    },
    { key: 'grade', label: t('Grade'), title: t('Median of eight readability formulas, as a US school grade'), get: (r) => r.readability.scores.text_standard, fmt: (v) => num(v, 1) },
    target
      ? { key: 'known', label: t('Words ≤ {level}', { level: target }), title: t('Share of words at {level} or below on the CEFR lists, counting names as known', { level: target }), get: (r) => Insights.knownAt(r, target), fmt: (v) => pct(v), tone: (v) => (v >= 98 ? 'good' : v >= 95 ? 'ok' : 'warn') }
      : { key: 'b2', label: t('B2+ words'), title: t('Share of words at B2, C1 or C2'), get: (r) => ['B2', 'C1', 'C2'].reduce((s, l) => s + r.cefr.per_level[l].coverage_pct, 0), fmt: (v) => pct(v) },
    { key: 'k95', label: t('{pct} coverage', { pct: pct(95, 0) }), title: t('BNC/COCA word families a reader needs to know {pct} of the words', { pct: pct(95, 0) }), get: (r) => Insights.bandAt(r.bnc_coca.per_band, 95), fmt: band },
    { key: 'k95p', label: t('With phrases'), title: t('The same, counting PHRASE List expressions as single units'), get: (r) => Insights.bandAt(r.phrase.integrated_profile.per_band, 95), fmt: band },
    { key: 'phr', label: t('Phrases per {count}', { count: num(1000) }), title: t('PHRASE List expressions per {count} words', { count: num(1000) }), get: (r) => r.phrase.counts.hits_per_1000_words, fmt: (v) => num(v, 1) },
    { key: 'mlt', label: 'MLT', title: t('Mean length of T-unit, in words (Lu 2010)'), get: (r) => r.syntax?.indices?.mlt, fmt: (v) => num(v, 1) },
    { key: 'mtld', label: 'MTLD', title: t('Lexical diversity (McCarthy & Jarvis 2010)'), get: (r) => r.diversity.scores.mtld, fmt: (v) => num(v, 0) },
    { key: 'awl', label: 'AWL', title: t('Share of words on Coxhead’s Academic Word List'), get: (r) => r.awl.coverage_pct, fmt: (v) => pct(v) },
    { key: 'err', label: t('Spelling'), title: t('Possible misspellings'), get: (r) => r.errors.counts.errors_total, fmt: (v) => num(v) },
  ];
}

function sorted(cols) {
  const { key, dir } = state.sort;
  if (!key) return state.items;
  const c = cols.find((x) => x.key === key);
  const val = (x) => (x.status === 'done' ? (key === 'name' ? displayName(x).toLowerCase() : c.get(x.data.results)) : null);
  return [...state.items].sort((a, b) => {
    const va = val(a);
    const vb = val(b);
    if (va == null && vb == null) return a.id - b.id;
    if (va == null) return 1;
    if (vb == null) return -1;
    return (va > vb ? 1 : va < vb ? -1 : 0) * dir;
  });
}

async function openItem(item) {
  const url = await Share.link(item.text, { variant: state.variant, target: Prefs.target, path: '/' });
  window.open(url, '_blank', 'noopener');
}

function progress() {
  const done = state.items.filter((x) => x.status === 'done').length;
  const failed = state.items.filter((x) => x.status === 'error').length;
  const total = state.items.length;
  if (total - done - failed) return tn(total, 'Analysing… {done} of {n} text done', 'Analysing… {done} of {n} texts done', { done: num(done) });
  const ok = tn(done, '{n} text analysed.', '{n} texts analysed.');
  return failed ? `${ok} ${tn(failed, '{n} couldn’t be analysed.', '{n} couldn’t be analysed.')}` : ok;
}

function renderTable() {
  const table = $('batchTable');
  const cols = columns();
  // The readers' level swaps a column: a sort on one that is gone starts over.
  if (state.sort.key && state.sort.key !== 'name' && !cols.some((c) => c.key === state.sort.key)) state.sort = { key: null, dir: 1 };
  const has = state.items.length > 0;
  $('batchResults').hidden = !has;
  $('batchProgress').textContent = progress();
  $('batchCsv').disabled = !state.items.some((x) => x.status === 'done');

  const sortBtn = (key, label, title) => {
    const on = state.sort.key === key;
    return h('th', { scope: 'col', 'aria-sort': on ? (state.sort.dir > 0 ? 'ascending' : 'descending') : 'none' },
      h('button', { type: 'button', class: 'th-sort', title: title || null, onclick: () => {
        state.sort = { key, dir: on ? -state.sort.dir : key === 'name' ? 1 : -1 };
        render();
      } }, label, h('span', { class: 'th-caret', 'aria-hidden': 'true' }, on ? icon(state.sort.dir > 0 ? 'arrow-up' : 'arrow-down', { size: 14 }) : null)));
  };
  const head = h('thead', {}, h('tr', {}, sortBtn('name', t('Text')), cols.map((c) => sortBtn(c.key, c.label, c.title)), h('th', { scope: 'col' }, h('span', { class: 'sr-only' }, t('Actions')))));
  const body = h('tbody', {});
  for (const item of sorted(cols)) {
    const r = item.data?.results;
    const name = displayName(item);
    const cells = cols.map((c) => {
      if (item.status !== 'done') return h('td', { class: 'num' }, '');
      const v = c.get(r);
      const text = c.show ? c.show(r) : v == null ? '–' : c.fmt(v);
      const why = c.key === 'level' && !r.level?.applicable ? t('Too short for a level estimate') : null;
      return h('td', { class: `num${c.tone && v != null ? ` tone-${c.tone(v)}` : ''}`, title: why }, text);
    });
    const status = item.status === 'error'
      ? h('span', { class: 'batch-err' }, errorText(item))
      : item.status === 'done' ? null : h('span', { class: 'batch-wait' }, item.status === 'running' ? t('Analysing…') : t('Waiting'));
    body.appendChild(h('tr', { class: `st-${item.status}` },
      h('th', { scope: 'row', class: 'batch-name' }, h('span', { class: 'batch-file', dir: 'auto' }, name), status),
      item.status === 'error' ? h('td', { colspan: String(cols.length) }) : cells,
      h('td', { class: 'batch-act' },
        item.status === 'done' ? h('button', { type: 'button', class: 'link-btn', onclick: () => openItem(item) }, t('Open'), icon('arrow-up-right', { size: 14 })) : null,
        h('button', { type: 'button', class: 'icon-btn', 'aria-label': t('Remove {name}', { name }), title: t('Remove'), onclick: () => {
          state.items = state.items.filter((x) => x !== item);
          render();
        } }, icon('x')))));
  }
  table.replaceChildren(head, body);
}

/** Redraw the table. A failure here is logged, never thrown into the queue. */
function render() {
  try {
    renderTable();
  } catch (err) {
    console.error(err);
  }
}

// ---- controls ----------------------------------------------------------------------

function renderTarget() {
  const wrap = $('batchTarget');
  const group = h('div', { class: 'segmented small', role: 'radiogroup', 'aria-label': t('Readers’ CEFR level') });
  for (const [v, text] of [['', t('Any')], ...Prefs.TARGETS.map((l) => [l, l])]) {
    group.appendChild(h('button', { type: 'button', role: 'radio', 'aria-checked': String((Prefs.target ?? '') === v), onclick: () => Prefs.setTarget(v || null) }, text));
  }
  wrap.replaceChildren(h('span', { class: 'target-label' }, t('Readers')), group);
}
Prefs.onChange(() => {
  renderTarget();
  render();
});
I18n.onChange(() => {
  renderTarget();
  render();
});

function setVariantUi() {
  document.querySelectorAll('#batchVariant [data-variant]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.variant === state.variant)));
}
$('batchVariant').addEventListener('click', (e) => {
  const b = e.target.closest('[data-variant]');
  if (!b || b.dataset.variant === state.variant) return;
  state.variant = b.dataset.variant;
  store.set('lexinspect:variant', state.variant);
  setVariantUi();
  // Spelling depends on the variety: analyse everything again. Texts in
  // flight re-queue themselves when they return (analyseItem).
  for (const x of state.items) if (x.status === 'done') x.status = 'queued';
  pump();
  render();
});

const input = $('batchFiles');
input.accept = Files.ACCEPT;
$('batchPick').addEventListener('click', () => input.click());
input.addEventListener('change', () => {
  addFiles(input.files);
  input.value = '';
});

const drop = $('batchDrop');
let depth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
document.addEventListener('dragenter', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  depth++;
  drop.classList.add('dragging');
});
document.addEventListener('dragover', (e) => hasFiles(e) && e.preventDefault());
document.addEventListener('dragleave', (e) => {
  if (!hasFiles(e)) return;
  if (--depth <= 0) {
    depth = 0;
    drop.classList.remove('dragging');
  }
});
document.addEventListener('drop', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  depth = 0;
  drop.classList.remove('dragging');
  addFiles(e.dataTransfer.files);
});

$('batchPasteBtn').addEventListener('click', () => {
  $('batchPaste').hidden = false;
  $('batchText').focus();
});
$('batchPasteCancel').addEventListener('click', () => ($('batchPaste').hidden = true));
$('batchPasteGo').addEventListener('click', () => {
  const parts = $('batchText').value.split(/^\s*-{3,}\s*$/m).map((x) => x.trim()).filter(Boolean);
  if (!parts.length) return toast(t('Paste some text first'));
  const start = state.items.length;
  parts.slice(0, MAX_TEXTS - start).forEach((part, i) => {
    const n = start + i + 1;
    const opening = `${part.slice(0, 40).replace(/\s+/g, ' ')}${part.length > 40 ? '…' : ''}`;
    // `name` is the English form the CSV keeps; the table shows displayName().
    add(`Text ${n}: ${opening}`, part, { n, start: opening });
  });
  if (parts.length > MAX_TEXTS - start) toast(t('Up to {count} texts at a time. The rest weren’t added.', { count: num(MAX_TEXTS) }));
  $('batchText').value = '';
  $('batchPaste').hidden = true;
  pump();
  render();
});

$('batchClear').addEventListener('click', () => {
  state.items = state.items.filter((x) => x.status === 'running');
  render();
});

$('batchCsv').addEventListener('click', async () => {
  const done = state.items.filter((x) => x.status === 'done');
  const rows = [];
  for (const x of done) rows.push({ d: x.data, m: await Export.meta(x.data), name: x.name });
  const stamp = new Date().toISOString().slice(0, 10);
  const blob = new Blob([Export.summaryCsvMany(rows)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = h('a', { href: url, download: `lexinspect-batch-${stamp}.csv` });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(tn(done.length, 'Downloaded {n} text as CSV', 'Downloaded {n} texts as CSV'));
});

// ---- boot ------------------------------------------------------------------------------

fetch('/v1/schema')
  .then((r) => r.json())
  .then((s) => {
    if (s.limits?.max_text_bytes) LIMIT_BYTES = s.limits.max_text_bytes;
    Human.configure(s.turnstile_site_key);
  }, () => Human.configure(null));
setVariantUi();
renderTarget();
render();
