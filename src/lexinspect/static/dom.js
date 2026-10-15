// DOM and formatting helpers shared by every other script. No framework and no
// build step: the page is small enough that a 20-line `h()` keeps it readable.
//
// User text never goes through innerHTML. `h()` turns strings into text nodes;
// the only markup path is the `html` attribute, and it is fed exclusively from
// constants in copy.js. CSP `script-src 'self'` backs that up.

const $ = (id) => document.getElementById(id);

/** h('div', {class: 'x', onclick: fn}, child, [children], 'text') */
function h(tag, attrs, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
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

const nf0 = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Format a number; `d` = fraction digits. Null renders as an en dash. */
function num(v, d = 0) {
  if (v == null || Number.isNaN(v)) return '–';
  return (d === 0 ? nf0 : d === 1 ? nf1 : nf2).format(v);
}

function pct(v, d = 1) {
  return v == null ? '–' : `${num(v, d)}%`;
}

function plural(n, one, many = one + 's') {
  return `${num(n)} ${n === 1 ? one : many}`;
}

function duration(seconds) {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s ? `${m} min ${s} s` : `${m} min`;
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
  const t = $('toast');
  t.textContent = message;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}

/** A horizontal meter: value in [0, max]. */
function meter(value, max, cls = '') {
  const frac = Math.max(0, Math.min(1, (value || 0) / max));
  return h('span', { class: `bar ${cls}`, style: { '--v': frac } }, h('span', { class: 'bar-fill' }));
}
