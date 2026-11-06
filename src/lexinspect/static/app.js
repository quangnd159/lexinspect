// Entry point: the editor, the request, and the wiring between the reader and
// the analysis pane.

const workspace = $('workspace');
const textarea = $('text');
const analyseBtn = $('analyseBtn');
const editorMsg = $('editorMsg');

let LIMIT_BYTES = 50_000;
let CEFR_LEVEL_AVAILABLE = false;
let variant = store.get('lexinspect:variant', 'gb') === 'us' ? 'us' : 'gb';
let last = null; // last successful response
let inflight = null;

const encoder = new TextEncoder();
const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

document.querySelector('.toplinks').appendChild(I18n.picker());
fitTopbar();

/** A size in kilobytes, in the locale's unit style ("12.3 kB", "12,3 ko"). */
function kb(bytes, d = 1) {
  return new Intl.NumberFormat(I18n.intl, { style: 'unit', unit: 'kilobyte', unitDisplay: 'short', minimumFractionDigits: d, maximumFractionDigits: d }).format(bytes / 1000);
}

/** A file name or other English label inside a translated sentence, isolated for right-to-left text. */
const isolate = (s) => `\u2068${s}\u2069`;

/** Labels and rich text this script sets, in the interface language. */
function renderStatic() {
  $('analyseKbd').textContent = isMac ? '⌘↵' : t('Ctrl ↵');
  setLoading(analyseBtn.dataset.state === 'loading');
  $('introSources').replaceChildren(...tr('Every list and formula is the published one, with its source and licence on the <a>Sources</a> page.', {}, { a: (s) => h('a', { href: '/licences' }, s) }));
  $('introCli').replaceChildren(...tr('Run the same analysis yourself with the <code>lexinspect</code> command-line tool or Python package.', {}, { code: (s) => h('code', {}, s) }));
}

// ---- editor ------------------------------------------------------------------

function updateMeter() {
  const value = textarea.value;
  const words = (value.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu) || []).length;
  const bytes = encoder.encode(value).length;
  $('liveWords').textContent = tn(words, '{n} word', '{n} words');
  $('liveSize').textContent = t('{size} of {limit}', { size: kb(bytes, bytes ? 1 : 0), limit: kb(LIMIT_BYTES, 0) });
  const m = $('meter');
  m.classList.toggle('near', bytes > LIMIT_BYTES * 0.9 && bytes <= LIMIT_BYTES);
  m.classList.toggle('over', bytes > LIMIT_BYTES);
  return { words, bytes };
}

let saveTimer;
textarea.addEventListener('input', () => {
  updateMeter();
  setMessage('');
  markStale();
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => store.set('lexinspect:draft', textarea.value), 400);
});

textarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    analyse();
  }
});

function markStale() {
  if (last) $('results').classList.toggle('stale', textarea.value.trim() !== last.submitted);
}

// The message under the editor. A function is kept and called again when the
// language changes; a plain string (from another module) stays as it is.
let message = null;
function setMessage(text, kind = 'error') {
  message = text || null;
  editorMsg.textContent = typeof text === 'function' ? text() : text;
  editorMsg.dataset.kind = text ? kind : '';
}

function setVariantUi() {
  document.querySelectorAll('#variant [data-variant]').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.variant === variant)));
}

$('variant').addEventListener('click', (e) => {
  const b = e.target.closest('[data-variant]');
  if (!b) return;
  setVariant(b.dataset.variant, { rerun: false });
});

function setVariant(v, { rerun = true } = {}) {
  variant = v;
  store.set('lexinspect:variant', v);
  setVariantUi();
  if (rerun && last) analyse({ keepTab: true, text: last.submitted });
}

// ---- samples menu ----------------------------------------------------------------

const samplesBtn = $('samplesBtn');
const samplesMenu = $('samplesMenu');

function renderSamples() {
  samplesMenu.replaceChildren(
    ...SAMPLES.map((s) =>
      h('button', { type: 'button', role: 'menuitem', class: 'menu-item', onclick: () => useSample(s) },
        h('span', { class: 'menu-label' }, t(s.label)), h('span', { class: 'menu-note' }, t(s.note)))
    )
  );
}
renderSamples();

function toggleMenu(open) {
  const isOpen = !samplesMenu.hidden && samplesMenu.classList.contains('open');
  open ??= !isOpen;
  samplesBtn.setAttribute('aria-expanded', String(open));
  if (open) {
    samplesMenu.hidden = false;
    requestAnimationFrame(() => samplesMenu.classList.add('open'));
  } else {
    samplesMenu.classList.remove('open');
    samplesMenu.hidden = true;
  }
}

samplesBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  toggleMenu();
  if (!samplesMenu.hidden) samplesMenu.querySelector('.menu-item')?.focus({ preventScroll: true });
});
document.addEventListener('click', (e) => !samplesMenu.hidden && !samplesMenu.contains(e.target) && toggleMenu(false));
document.addEventListener('keydown', (e) => {
  if (samplesMenu.hidden) return;
  const items = [...samplesMenu.querySelectorAll('.menu-item')];
  const i = items.indexOf(document.activeElement);
  if (e.key === 'Escape') {
    toggleMenu(false);
    samplesBtn.focus();
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    items[(i + 1) % items.length].focus();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    items[(i - 1 + items.length) % items.length].focus();
  }
});

function useSample(s) {
  toggleMenu(false);
  textarea.value = s.text;
  updateMeter();
  store.set('lexinspect:draft', s.text);
  analyse();
}

// ---- files -------------------------------------------------------------------------

const fileInput = $('fileInput');
fileInput.accept = Files.ACCEPT;
$('openBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) openFile(fileInput.files[0]);
  fileInput.value = '';
});

async function openFile(file) {
  setMessage('');
  try {
    const text = await Files.read(file);
    textarea.value = text;
    store.set('lexinspect:draft', text);
    const { bytes } = updateMeter();
    if (bytes > LIMIT_BYTES) {
      setMode('edit');
      setMessage(() => t('{file} has {size} of text; the limit is {limit}. Cut what you don’t need, or analyse it in parts.', { file: quoted(file.name), size: kb(bytes), limit: kb(LIMIT_BYTES, 0) }));
      return;
    }
    analyse();
  } catch (err) {
    setMode('edit');
    setMessage(err instanceof Files.FileError ? err.message : () => t('{file} couldn’t be read. Paste the text in instead.', { file: quoted(file.name) }));
  }
}

// The whole editor is a drop target. dragenter/leave fire for every child, so
// count them rather than trusting the last event.
const editorEl = $('editor');
let dragDepth = 0;
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files');
editorEl.addEventListener('dragenter', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth++;
  editorEl.classList.add('dragging');
});
editorEl.addEventListener('dragover', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});
editorEl.addEventListener('dragleave', (e) => {
  if (!hasFiles(e)) return;
  if (--dragDepth <= 0) {
    dragDepth = 0;
    editorEl.classList.remove('dragging');
  }
});
editorEl.addEventListener('drop', (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault();
  dragDepth = 0;
  editorEl.classList.remove('dragging');
  const file = e.dataTransfer.files[0];
  if (file) openFile(file);
});
// A file dropped anywhere else would navigate away from the page.
window.addEventListener('dragover', (e) => hasFiles(e) && e.preventDefault());
window.addEventListener('drop', (e) => hasFiles(e) && !editorEl.contains(e.target) && e.preventDefault());

// ---- modes -----------------------------------------------------------------------

function setMode(mode) {
  workspace.dataset.mode = mode;
  $('editor').hidden = mode !== 'edit';
  $('reader').hidden = mode !== 'read';
  if (mode === 'edit') {
    Reader.hide();
    textarea.focus({ preventScroll: true });
  }
}

$('editBtn').addEventListener('click', () => setMode('edit'));

// ---- analysis --------------------------------------------------------------------

function setLoading(on) {
  analyseBtn.dataset.state = on ? 'loading' : '';
  analyseBtn.setAttribute('aria-busy', String(on));
  analyseBtn.querySelector('.btn-label').textContent = on ? t('Analysing') : t('Analyse');
}

/** While a request is in flight, edits to the analysed text wait (adapt.js and panels read ctx.busy). */
function setBusy(on) {
  if (on) document.body.dataset.busy = 'true';
  else delete document.body.dataset.busy;
  $('results').setAttribute('aria-busy', String(on));
}

// The API counts offsets in Unicode code points (Python strings); JavaScript
// strings index UTF-16 units. They differ only after a character outside the
// Basic Multilingual Plane (most emoji), so convert only when there is one.
function toUtf16Offsets(data) {
  const text = data.input?.normalised_text ?? data.submitted;
  if (!/[\uD800-\uDFFF]/.test(text)) return;
  const map = [];
  let u = 0;
  for (const ch of text) {
    map.push(u);
    u += ch.length;
  }
  map.push(u);
  const fix = (i) => (Number.isInteger(i) && i >= 0 && i < map.length ? map[i] : i);
  const isPair = (p) => Array.isArray(p) && p.length === 2 && p.every(Number.isInteger);
  const walk = (x) => {
    if (Array.isArray(x)) return x.forEach(walk);
    if (!x || typeof x !== 'object') return;
    for (const [k, v] of Object.entries(x)) {
      if (k === 'span' && isPair(v)) x[k] = v.map(fix);
      else if (k === 'spans' && Array.isArray(v) && v.every(isPair)) x[k] = v.map((p) => p.map(fix));
      else walk(v);
    }
  };
  walk(data.results);
  // The token profile is a table: [start, end, …] per row.
  const prof = data.results?.profile;
  if (prof?.columns && Array.isArray(prof.rows)) {
    const cols = ['start', 'end'].map((c) => prof.columns.indexOf(c)).filter((i) => i >= 0);
    for (const row of prof.rows) for (const i of cols) row[i] = fix(row[i]);
  }
}

async function analyse({ keepTab = false, text = null, openTab = null, openLens = null } = {}) {
  const body = (text ?? textarea.value).trim();
  if (!body) {
    setMode('edit');
    setMessage(() => t('Paste or type some text first.'), 'info');
    textarea.focus();
    return;
  }
  const bytes = encoder.encode(body).length;
  if (bytes > LIMIT_BYTES) {
    setMode('edit');
    const words = Math.round(LIMIT_BYTES / 6.2 / 100) * 100;
    setMessage(() => tn(words, 'This text is {size}; the limit is {limit}, about {n} word. Analyse it in parts.', 'This text is {size}; the limit is {limit}, about {n} words. Analyse it in parts.', { size: kb(bytes), limit: kb(LIMIT_BYTES, 0) }));
    return;
  }

  inflight?.abort();
  const ctl = new AbortController();
  inflight = ctl;
  // What the editor held when the request went out: if the user types while
  // it runs, the response mustn't overwrite their text.
  const sent = textarea.value;
  const fromEditor = sent.trim() === body;
  setLoading(true);
  setBusy(true);
  setMessage('');
  try {
    const res = await Human.fetch('/v1/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: body, variant, source: 'web' }),
      signal: ctl.signal,
    });
    if (!res.ok) throw await requestError(res);
    const data = await res.json();
    data.submitted = body;
    toUtf16Offsets(data);
    // A revision of the text on screen (most of its words shared) is compared
    // with the version before it; an unrelated text starts afresh.
    if (last && last.submitted !== body && Metrics.overlap(last.submitted, body) >= 0.6) {
      data.previous = last.previous && Metrics.overlap(last.previous.submitted, body) >= 0.6 ? last.previous : { submitted: last.submitted, results: last.results };
      data.changes = Metrics.changes(data.previous.results, data.results, { target: Prefs.target });
    }
    last = data;
    Export.meta(data); // hash the text now so Cmd/Ctrl+P can show it
    show(data, keepTab, { openTab, openLens, keepEditor: !fromEditor || textarea.value !== sent });
  } catch (err) {
    if (err.name === 'AbortError') return;
    setMode('edit');
    // fetch() rejects with a TypeError when the network fails.
    setMessage(err instanceof TypeError ? () => apiMessage(0) : err.again ?? (err.message || (() => t('Something went wrong. Try again.'))));
  } finally {
    if (inflight === ctl) {
      inflight = null;
      setLoading(false);
      setBusy(false);
    }
  }
}

/** A message for a failed API request, from its HTTP status and error code (api.py, _human.py). 0 = no response. */
function apiMessage(status, code = '', limit = LIMIT_BYTES) {
  if (status === 413 || code === 'text_too_large') return t('This text is too long: the limit is {limit}. Analyse it in parts.', { limit: kb(limit, 0) });
  if (status === 429) return t('Too many analyses in a short time. Wait a minute and try again.');
  if (code === 'challenge_unavailable') return t('The human check is unavailable at the moment. Try again in a minute.');
  if (status === 403 || code === 'challenge_required' || code === 'challenge_failed') return t('The human check didn’t go through. Try again.');
  if (status === 422 || code === 'invalid_request') return t('This text couldn’t be read. Paste it in again as plain text.');
  if (!status || status >= 500) return t('A temporary problem stopped the analysis. Try again in a moment.');
  return t('The analysis failed (error {status}). Try again.', { status });
}

/** An Error for a failed response; `again()` rebuilds its message in the current language. */
async function requestError(res) {
  let code = '';
  let limit = LIMIT_BYTES;
  try {
    const j = await res.json();
    code = j.detail?.error || j.error || '';
    if (j.detail?.limit_bytes) limit = j.detail.limit_bytes;
  } catch {}
  const again = () => apiMessage(res.status, code, limit);
  return Object.assign(new Error(again()), { again });
}

const ctx = {
  setVariant: (v) => setVariant(v),
  /** True while an analysis is running: edits to the analysed text are ignored until it returns. */
  get busy() {
    return inflight != null;
  },
  /** Stop comparing with the earlier version: the current one becomes the baseline. */
  dropComparison() {
    if (!last) return;
    delete last.previous;
    delete last.changes;
    Panels.retarget();
  },
  applyFix(spans, replacement) {
    ctx.applyEdits(
      spans.map((span) => ({ span, text: replacement })),
      tn(spans.length, 'Replaced with {word}', 'Replaced {n} occurrences with {word}', { word: quoted(replacement) })
    );
  },
  /** Apply [{span, text}] to the analysed text (right to left, so spans stay valid) and re-analyse.
   *  Ignored while a request is in flight: its spans would no longer match. Returns whether it applied. */
  applyEdits(edits, message) {
    if (ctx.busy || !last) return false;
    const base = last.input.normalised_text ?? last.submitted;
    let out = base;
    [...edits].sort((a, b) => b.span[0] - a.span[0]).forEach(({ span: [a, b], text }) => (out = out.slice(0, a) + text + out.slice(b)));
    textarea.value = out;
    store.set('lexinspect:draft', out);
    updateMeter();
    if (message) toast(message);
    analyse({ keepTab: true, text: out });
    return true;
  },
  copyWordList(items, target) {
    // Tab-separated data for a spreadsheet: English headers, like the other exports.
    const lines = ['word\tlevel\tcount', ...items.map((x) => `${x.occurrences[0]?.surface?.toLowerCase() ?? x.lemma}\t${x.level || 'not listed'}\t${x.count}`)];
    copy(lines.join('\n'), tn(items.length, 'Copied {n} word above {level}', 'Copied {n} words above {level}', { level: target }));
  },
  get cefrLevelAvailable() {
    return CEFR_LEVEL_AVAILABLE;
  },
  async cefrLevel() {
    const res = await Human.fetch('/v1/cefr-level', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: last.submitted, source: 'web' }),
    });
    if (!res.ok) throw await requestError(res);
    return (await res.json()).result;
  },
};

/** Put an analysis on screen. `keepEditor`: the user changed the text while it ran, so keep their
 *  text and the editor open, and mark the results as out of date. */
function show(data, keepTab, { openTab = null, openLens = null, keepEditor = false } = {}) {
  const first = workspace.dataset.hasResults !== 'true';
  workspace.dataset.hasResults = 'true';
  $('results').hidden = false;
  $('intro').hidden = true;
  if (keepEditor) {
    markStale();
  } else {
    $('results').classList.remove('stale');
    if (textarea.value.trim() !== data.submitted) textarea.value = data.submitted;
    setMode('read');
  }
  Reader.load(data);
  Panels.render(data, ctx, { keepTab, openTab, openLens });
  if (first) {
    workspace.classList.remove('entered');
    void workspace.offsetWidth;
    workspace.classList.add('entered');
  }
  if (!keepTab && window.matchMedia('(max-width: 899px)').matches) {
    $('reader').scrollIntoView({ block: 'start', behavior: 'auto' });
  }
}

Reader.onLensChange((lens) => Panels.followLens(lens));
Prefs.onChange(() => {
  if (last?.previous) last.changes = Metrics.changes(last.previous.results, last.results, { target: Prefs.target });
  Reader.retarget();
  Panels.retarget();
});
analyseBtn.addEventListener('click', () => analyse());

// ---- export ----------------------------------------------------------------------
// Built from `last` in the browser (export.js); nothing is re-sent.

const exportBtn = $('exportBtn');
const exportMenu = $('exportMenu');

function toggleExport(open) {
  open ??= exportMenu.hidden;
  exportBtn.setAttribute('aria-expanded', String(open));
  if (open) {
    exportMenu.hidden = false;
    requestAnimationFrame(() => exportMenu.classList.add('open'));
  } else {
    exportMenu.classList.remove('open');
    exportMenu.hidden = true;
  }
}

exportBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  toggleExport();
  if (!exportMenu.hidden) exportMenu.querySelector('.menu-item')?.focus({ preventScroll: true });
});
document.addEventListener('click', (e) => !exportMenu.hidden && !exportMenu.contains(e.target) && toggleExport(false));
exportMenu.addEventListener('keydown', (e) => {
  const items = [...exportMenu.querySelectorAll('.menu-item')];
  const i = items.indexOf(document.activeElement);
  const go = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key];
  if (e.key === 'Escape' || e.key === 'Tab') {
    if (e.key === 'Escape') e.preventDefault();
    toggleExport(false);
    exportBtn.focus();
  } else if (go != null) {
    e.preventDefault();
    items[(go + items.length) % items.length].focus();
  }
});

function save(data, name, type) {
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
  const a = h('a', { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast(t('Downloaded {file}', { file: isolate(name) }));
}

async function copy(text, done) {
  try {
    await navigator.clipboard.writeText(text);
    toast(done);
  } catch {
    toast(t('Couldn’t copy to the clipboard. Use a download instead.'));
  }
}

function buildReport(m) {
  $('report').replaceChildren(Export.report(last, m));
  document.body.classList.add('print-report');
}

const EXPORTS = {
  link: async () => {
    if (!Share.supported()) return toast(t('This browser can’t make share links. Try a current version of Chrome, Edge, Firefox or Safari.'));
    const url = await Share.link(last.submitted, { variant, target: Prefs.target, tab: Panels.active, lens: Reader.lens });
    copy(url, url.length > 8000 ? t('Link copied. It’s long because the text is inside it.') : t('Link copied'));
  },
  summary: async (m) => copy(Export.summaryText(last, m), t('Summary copied')),
  print: async (m) => {
    buildReport(m);
    window.print();
  },
  xlsx: async (m) => save(await Export.xlsx(last, m), Export.filename(last, m, '', 'xlsx')),
  'summary-csv': async (m) => save(Export.summaryCsv(last, m), Export.filename(last, m, 'summary', 'csv'), 'text/csv;charset=utf-8'),
  'words-csv': async (m) => save(Export.wordsCsv(last, m), Export.filename(last, m, 'words', 'csv'), 'text/csv;charset=utf-8'),
  json: async (m) => save(Export.json(last), Export.filename(last, m, '', 'json'), 'application/json'),
  'copy-json': async () => copy(Export.json(last), t('JSON copied')),
  cite: async (m) => copy(Export.citationText(last, m), t('Citation copied')),
};

exportMenu.addEventListener('click', async (e) => {
  const item = e.target.closest('[data-export]');
  if (!item || !last) return;
  toggleExport(false);
  exportBtn.focus({ preventScroll: true });
  try {
    await EXPORTS[item.dataset.export](await Export.meta(last));
  } catch (err) {
    console.error(err);
    toast(t('The export failed. Please report it on GitHub.'));
  }
});

// Cmd/Ctrl+P prints the report too, once there is an analysis to print. The
// report is rebuilt each time so its timestamp is the print time.
window.addEventListener('beforeprint', () => {
  if (last && !document.body.classList.contains('print-report')) {
    $('report').replaceChildren(Export.report(last, Export.metaNow(last)));
    document.body.classList.add('print-report');
  }
});
window.addEventListener('afterprint', () => document.body.classList.remove('print-report'));

// ---- boot ------------------------------------------------------------------------

fetch('/v1/schema')
  .then((r) => r.json())
  .then((s) => {
    if (s.limits?.max_text_bytes) LIMIT_BYTES = s.limits.max_text_bytes;
    CEFR_LEVEL_AVAILABLE = !!s.optional_available?.cefr_level;
    Human.configure(s.turnstile_site_key);
    $('versionMeta').textContent = `lexinspect ${s.version}`;
    updateMeter();
  }, () => Human.configure(null));

setVariantUi();
textarea.value = store.get('lexinspect:draft', '');
renderStatic();
updateMeter();
setMode('edit');

// A new interface language: redo everything this script put on screen. The
// reader and the analysis panels rebuild themselves (reader.js, panels.js),
// keeping the open tab, lens and scroll, so nothing here re-renders them.
I18n.onChange(() => {
  renderStatic();
  renderSamples();
  updateMeter();
  if (typeof message === 'function') editorMsg.textContent = message();
});

// A shared link opens its text and analyses it straight away. The fragment is
// cleared afterwards so the address bar doesn't hold a stale copy once the
// text is edited; the draft store keeps it across reloads.
Share.read().then(
  (shared) => {
    if (!shared) return;
    Share.clear();
    textarea.value = shared.text;
    store.set('lexinspect:draft', shared.text);
    updateMeter();
    if (shared.variant !== variant) setVariant(shared.variant, { rerun: false });
    if (shared.target) Prefs.setTarget(shared.target, { silent: true });
    analyse({ openTab: shared.tab, openLens: shared.lens });
  },
  () => {
    Share.clear();
    // share.js throws English text; say the same in the interface language.
    setMessage(() => (Share.supported()
      ? t('This link is incomplete or damaged, so its text can’t be read. Ask for it to be sent again.')
      : t('This browser can’t open shared links. Try a current version of Chrome, Edge, Firefox or Safari.')));
  }
);
