// DOM and formatting helpers shared by every other script. No framework and no
// build step: the page is small enough that a 20-line `h()` keeps it readable.
//
// Nothing goes through innerHTML: `h()` turns strings into text nodes, and
// rich messages are built as nodes by tr() (i18n.js). CSP `script-src 'self'`
// backs that up.

const $ = (id) => document.getElementById(id);

/** Keep the top bar on one line whatever the interface language. When the
 *  links don't fit beside the wordmark, data-fit="1" shrinks the language menu
 *  to its icon (always so on phones) and data-fit="2" also drops the wordmark's
 *  name (styles.css). Rechecked when the bar resizes, the language changes or
 *  the fonts arrive. Only the bar is observed: fitting resizes the links, and
 *  observing them would loop. */
function fitTopbar() {
  const bar = document.querySelector('.topbar');
  if (!bar) return;
  const phone = matchMedia('(max-width: 480px)');
  const fit = () => {
    for (const level of [phone.matches ? 1 : 0, 1, 2]) {
      if (level) bar.dataset.fit = level;
      else delete bar.dataset.fit;
      if (bar.scrollWidth <= bar.clientWidth) return;
    }
  };
  fit();
  if (window.ResizeObserver) new ResizeObserver(fit).observe(bar);
  else addEventListener('resize', fit);
  I18n.onChange(fit);
  document.fonts?.ready.then(fit);
}

// When the system switches between light and dark, every colour changes at
// once instead of each control fading on its own (styles.css turns transitions
// off while data-theme-switching is set).
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  const root = document.documentElement;
  root.setAttribute('data-theme-switching', '');
  requestAnimationFrame(() => requestAnimationFrame(() => root.removeAttribute('data-theme-switching')));
});

/** A row that scrolls sideways fades at its trailing edge while more is hidden
 *  there (.overflow in styles.css) and stops fading once scrolled to the end
 *  (.at-end). scrollLeft runs negative on right-to-left pages, hence abs().
 *  Returns the update, for callers whose content changes without a resize. */
function edgeFade(el) {
  const update = () => {
    el.classList.toggle('overflow', el.scrollWidth > el.clientWidth + 1);
    el.classList.toggle('at-end', Math.abs(el.scrollLeft) + el.clientWidth >= el.scrollWidth - 2);
  };
  el.addEventListener('scroll', update, { passive: true });
  if (window.ResizeObserver) new ResizeObserver(update).observe(el);
  else addEventListener('resize', update);
  return update;
}

/** h('div', {class: 'x', onclick: fn}, child, [children], 'text') */
function h(tag, attrs, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'style' && typeof v === 'object') {
      // Custom properties need setProperty; Object.assign silently drops `--x` keys.
      for (const [prop, val] of Object.entries(v)) {
        if (prop.startsWith('--')) e.style.setProperty(prop, String(val));
        else e.style[prop] = val;
      }
    }
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'dataset') Object.assign(e.dataset, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  append(e, children);
  return e;
}

function append(parent, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    parent.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return parent;
}

// Number formats follow the interface language (Western digits throughout;
// see I18n.intl). Rebuilt when the language changes.
const NF = new Map();
function nf(key, opts) {
  const k = `${I18n.intl}|${key}`;
  if (!NF.has(k)) NF.set(k, new Intl.NumberFormat(I18n.intl, opts));
  return NF.get(k);
}

/** Format a number; `d` = fraction digits. Null renders as an en dash. */
function num(v, d = 0) {
  if (v == null || Number.isNaN(v)) return '–';
  return nf(`n${d}`, { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
}

/** A percentage given as 0–100, in the locale's own percent style (12.5%, 12,5 %, %12,5). */
function pct(v, d = 1) {
  if (v == null || Number.isNaN(v)) return '–';
  return nf(`p${d}`, { style: 'percent', minimumFractionDigits: d, maximumFractionDigits: d }).format(v / 100);
}

/** "3 words": English-only helper kept for code that hasn't moved to tn(). */
function plural(n, one, many = one + 's') {
  return `${num(n)} ${n === 1 ? one : many}`;
}

/** A duration in the locale's short unit style: "35 s", "2 min 5 s". */
function duration(seconds) {
  const unit = (v, u) => nf(`u-${u}`, { style: 'unit', unit: u, unitDisplay: 'short' }).format(v);
  if (seconds < 60) return unit(Math.max(1, Math.round(seconds)), 'second');
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s ? `${unit(m, 'minute')} ${unit(s, 'second')}` : unit(m, 'minute');
}

/** "a, b and c" in the interface language. */
function listOf(items, type = 'conjunction') {
  return new Intl.ListFormat(I18n.intl, { style: 'long', type }).format(items.map(String));
}

/** A quoted English word or phrase, with the interface language's quotation
 *  marks. Wrapped in Unicode isolates so it keeps its order in right-to-left text. */
function quoted(s) {
  return t('“{text}”', { text: `\u2068${s}\u2069` });
}

/** An English word or phrase from the text, as a node inside translated copy. */
function en(s, cls) {
  return h('span', { lang: 'en', dir: 'ltr', class: cls ?? null }, s);
}

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** localStorage that never throws (private windows, blocked storage). */
const store = {
  get(k, fallback = null) {
    try {
      const v = localStorage.getItem(k);
      return v == null ? fallback : v;
    } catch {
      return fallback;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, v);
    } catch {}
  },
};

let toastTimer;
function toast(message) {
  const el = $('toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
}

/** A horizontal meter: value in [0, max]. */
function meter(value, max, cls = '') {
  const frac = Math.max(0, Math.min(1, (value || 0) / max));
  return h('span', { class: `bar ${cls}`, style: { '--v': frac } }, h('span', { class: 'bar-fill' }));
}

/** Settings that outlive one analysis: the readers' CEFR level a text is meant for. */
const Prefs = (() => {
  const TARGETS = ['A1', 'A2', 'B1', 'B2', 'C1'];
  const stored = store.get('lexinspect:target', '');
  let target = TARGETS.includes(stored) ? stored : null;
  const listeners = new Set();
  return {
    TARGETS,
    get target() {
      return target;
    },
    setTarget(v, { silent = false } = {}) {
      const next = TARGETS.includes(v) ? v : null;
      if (next === target) return;
      target = next;
      store.set('lexinspect:target', next ?? '');
      if (!silent) listeners.forEach((fn) => fn(next));
    },
    onChange(fn) {
      listeners.add(fn);
    },
  };
})();
