// Tiny DOM helpers shared by every renderer. No framework, no build step — the
// rendering surface is small enough that vanilla JS stays readable as long as
// the helpers are well-named and one-purpose.

const $ = (id) => document.getElementById(id);

/**
 * Build a DOM element. Attributes:
 *   - `class`     -> className
 *   - `html`      -> innerHTML (use sparingly)
 *   - everything else -> setAttribute
 * Children can be a single string/Node or an array; strings become text nodes.
 */
/**
 * A row of pill spans built from text nodes.
 *
 * Several of these lists echo the user's own tokens back — off-list words,
 * excluded digits — and the old code interpolated them into an `html:` string.
 * `el()` assigns `html` straight to innerHTML, so a token like `<img
 * src=x onerror=...>` would execute. It's the user's own text in the user's own
 * browser, so the blast radius is themselves, but there's no reason to hand the
 * DOM a string when a text node says exactly what we mean.
 */
function pills(items, style) {
  const frag = document.createDocumentFragment();
  items.forEach((t) => {
    const attrs = { class: 'pill' };
    if (style) attrs.style = style;
    frag.appendChild(el('span', attrs, String(t)));
  });
  return frag;
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === 'class') e.className = v;
    else if (k === 'html') e.innerHTML = v;
    else e.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  });
  return e;
}

/** Format a number for display: dashes for null/undefined, integers as-is, floats to 3dp. */
function fmtNum(v) {
  if (v == null) return '—';
  if (typeof v !== 'number') return String(v);
  return Number.isInteger(v) ? v.toString() : v.toFixed(3);
}

/** Two-column key/value table for a flat object. */
function kvTable(obj, formatter = String) {
  const tbl = el('table', { class: 'kv' });
  Object.entries(obj || {}).forEach(([k, v]) => {
    const tr = el('tr', {}, [el('td', {}, k), el('td', {}, formatter(v))]);
    tbl.appendChild(tr);
  });
  return tbl;
}

/**
 * Horizontal bar chart from a {label: count} distribution, normalised against
 * `total`. Sorted highest count first. Used by the POS tagger, AWL sublists,
 * BNC/COCA bands, NGSL split, and metadiscourse categories.
 */
function barChart(dist, total) {
  const container = el('div', { class: 'bar-chart' });
  const sorted = Object.entries(dist).sort((a, b) => b[1] - a[1]);
  sorted.forEach(([label, n]) => {
    const pct = total ? (n / total) * 100 : 0;
    const row = el('div', { class: 'bar-row' });
    row.appendChild(el('div', { class: 'lbl' }, label));
    const track = el('div', { class: 'bar-track' });
    const fill = el('div', { class: 'bar-fill' });
    fill.style.width = `${pct}%`;
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el('div', { class: 'num' }, `${n} · ${pct.toFixed(1)}%`));
    container.appendChild(row);
  });
  return container;
}
