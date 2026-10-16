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
$('analyseKbd').textContent = isMac ? '⌘↵' : 'Ctrl ↵';

// ---- editor ------------------------------------------------------------------

function updateMeter() {
  const t = textarea.value;
  const words = (t.match(/[\p{L}\p{N}]+(?:['’\-][\p{L}\p{N}]+)*/gu) || []).length;
  const bytes = encoder.encode(t).length;
  $('liveWords').textContent = num(words);
  $('liveSize').textContent = bytes < 1000 ? `${bytes} B` : `${num(bytes / 1000, 1)} KB`;
  const m = $('meter');
  m.classList.toggle('near', bytes > LIMIT_BYTES * 0.9 && bytes <= LIMIT_BYTES);
  m.classList.toggle('over', bytes > LIMIT_BYTES);
  return { words, bytes };
}

let saveTimer;
textarea.addEventListener('input', () => {
  updateMeter();
  setMessage('');
  if (last) $('results').classList.toggle('stale', textarea.value.trim() !== last.submitted);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => store.set('lexinspect:draft', textarea.value), 400);
});

textarea.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    e.preventDefault();
    analyse();
  }
});

function setMessage(text, kind = 'error') {
  editorMsg.textContent = text;
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

SAMPLES.forEach((s) =>
  samplesMenu.appendChild(
    h('button', { type: 'button', role: 'menuitem', class: 'menu-item', onclick: () => useSample(s) },
      h('span', { class: 'menu-label' }, s.label), h('span', { class: 'menu-note' }, s.note))
  )
);

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
  analyseBtn.querySelector('.btn-label').textContent = on ? 'Analysing' : 'Analyse';
}

async function analyse({ keepTab = false, text = null } = {}) {
  const body = (text ?? textarea.value).trim();
  if (!body) {
    setMode('edit');
    setMessage('Paste or type some text first.', 'info');
    textarea.focus();
    return;
  }
  const bytes = encoder.encode(body).length;
  if (bytes > LIMIT_BYTES) {
    setMode('edit');
    setMessage(`That’s ${num(bytes / 1000, 1)} KB; the limit is ${num(LIMIT_BYTES / 1000)} KB (about ${num(Math.round(LIMIT_BYTES / 6.2 / 100) * 100)} words). Analyse it in parts.`);
    return;
  }

  inflight?.abort();
  const ctl = new AbortController();
  inflight = ctl;
  setLoading(true);
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
    last = data;
    show(data, keepTab);
  } catch (err) {
    if (err.name === 'AbortError') return;
    setMode('edit');
    setMessage(err.message || 'Something went wrong. Try again.');
  } finally {
    if (inflight === ctl) {
      inflight = null;
      setLoading(false);
    }
  }
}

async function requestError(res) {
  let detail = '';
  let code = '';
  try {
    const j = await res.json();
    code = j.detail?.error || '';
    detail = j.detail?.detail || j.detail || j.error || '';
    if (typeof detail !== 'string') detail = '';
  } catch {}
  if (res.status === 403) return new Error('The human check didn’t go through. Try again.');
  if (res.status === 413) return new Error(detail || 'The text is too long. Analyse it in parts.');
  if (res.status === 429) return new Error('Too many analyses in a short time. Wait a minute and try again.');
  if (code === 'challenge_unavailable') return new Error(detail);
  if (res.status >= 500) return new Error('The analyser had a problem with this text. Try again; if it keeps failing, please report it on GitHub.');
  return new Error(detail || `Request failed (${res.status}).`);
}

const ctx = {
  setVariant: (v) => setVariant(v),
  applyFix(spans, replacement) {
    const base = last.input.normalised_text ?? last.submitted;
    let out = base;
    [...spans].sort((a, b) => b[0] - a[0]).forEach(([a, b]) => (out = out.slice(0, a) + replacement + out.slice(b)));
    textarea.value = out;
    store.set('lexinspect:draft', out);
    updateMeter();
    toast(spans.length > 1 ? `Replaced ${spans.length} occurrences with “${replacement}”` : `Replaced with “${replacement}”`);
    analyse({ keepTab: true, text: out });
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

function show(data, keepTab) {
  const first = workspace.dataset.hasResults !== 'true';
  workspace.dataset.hasResults = 'true';
  $('results').hidden = false;
  $('results').classList.remove('stale');
  $('intro').hidden = true;
  if (textarea.value.trim() !== data.submitted) textarea.value = data.submitted;
  setMode('read');
  Reader.load(data);
  Panels.render(data, ctx, { keepTab });
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
analyseBtn.addEventListener('click', () => analyse());

// ---- export ----------------------------------------------------------------------

function exportable() {
  const { submitted, ...rest } = last;
  return JSON.stringify(rest, null, 2);
}

$('copyJson').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(exportable());
    toast('Analysis JSON copied');
  } catch {
    toast('Copy failed; use Download instead');
  }
});

$('downloadJson').addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([exportable()], { type: 'application/json' }));
  const a = h('a', { href: url, download: 'lexinspect-analysis.json' });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

// ---- boot ------------------------------------------------------------------------

fetch('/v1/schema')
  .then((r) => r.json())
  .then((s) => {
    if (s.limits?.max_text_bytes) LIMIT_BYTES = s.limits.max_text_bytes;
    CEFR_LEVEL_AVAILABLE = !!s.optional_available?.cefr_level;
    Human.configure(s.turnstile_site_key);
    $('liveLimit').textContent = `${num(LIMIT_BYTES / 1000)} KB`;
    $('versionMeta').textContent = `lexinspect ${s.version}`;
    updateMeter();
  }, () => Human.configure(null));

setVariantUi();
textarea.value = store.get('lexinspect:draft', '');
updateMeter();
setMode('edit');
