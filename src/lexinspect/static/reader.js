// The reader: the analysed text, with every finding highlighted in place.
//
// The text is cut at every span boundary from every module (profile tokens,
// phrases, metadiscourse, spelling), and each piece becomes one <span> carrying
// data attributes for everything it belongs to. Switching lens then only
// changes `data-lens` on the container; CSS decides what is coloured, so a lens
// switch is a single attribute write and the colours can cross-fade.

const LENSES = [
  { id: 'spelling', label: 'Spelling' },
  { id: 'cefr', label: 'CEFR' },
  { id: 'bnc', label: 'Frequency' },
  { id: 'awl', label: 'Academic' },
  { id: 'ngsl', label: 'NGSL' },
  { id: 'phrase', label: 'Phrases' },
  { id: 'md', label: 'Metadiscourse' },
];

function bncBucket(b) {
  if (b == null) return 'off';
  if (typeof b === 'string') return b === 'proper' ? 'proper' : 'supp';
  if (b <= 1) return 'k1';
  if (b === 2) return 'k2';
  if (b === 3) return 'k3';
  if (b <= 5) return 'k4';
  if (b <= 9) return 'k6';
  return 'k10';
}

// Legend definitions: key -> label, in display order. Keys match the data-*
// values written on segments.
const LEGENDS = {
  spelling: { attr: 'e', items: [['err', 'Spelling error'], ['var', 'Other variety'], ['name', 'Unknown name']] },
  cefr: { attr: 'c', items: [['A1', 'A1'], ['A2', 'A2'], ['B1', 'B1'], ['B2', 'B2'], ['C1', 'C1'], ['C2', 'C2'], ['off', 'Not listed'], ['proper', 'Name']] },
  bnc: { attr: 'b', items: [['k1', '1K'], ['k2', '2K'], ['k3', '3K'], ['k4', '4–5K'], ['k6', '6–9K'], ['k10', '10K+'], ['supp', 'Supplementary'], ['off', 'Off-list'], ['proper', 'Name']] },
  awl: { attr: 'a', items: [['1', 'Sublist 1–3'], ['4', '4–6'], ['7', '7–10']] },
  ngsl: { attr: 'n', items: [['ngsl', 'NGSL'], ['nawl', 'NAWL'], ['off', 'Off-list'], ['proper', 'Name']] },
  phrase: { attr: 'k', items: [['1', 'K1'], ['2', 'K2'], ['3', 'K3'], ['4', 'K4'], ['5', 'K5']] },
  md: { attr: 'd', items: [['ia', 'Interactive'], ['il', 'Interactional']] },
};

const Reader = (() => {
  const doc = $('doc');
  const legend = $('legend');
  const lensBar = $('lenses');
  const pop = $('popover');

  let state = null; // {text, profile, phrases, md, errs, segs}
  let lens = 'none';
  let focusKey = null;
  let onLens = () => {};

  // ---- building ------------------------------------------------------------

  function build(data) {
    const r = data.results;
    const text = data.input.normalised_text ?? data.submitted;
    const rows = r.profile?.rows ?? [];
    const phrases = (r.phrase?.hits ?? []).slice().sort((a, b) => a.span[0] - b.span[0]);
    const md = (r.metadiscourse?.hits ?? []).slice().sort((a, b) => a.span[0] - b.span[0]);
    const errs = [];
    const e = r.errors;
    if (e) {
      for (const [kind, list] of [['err', e.errors], ['var', e.variant_mismatches], ['name', e.unknown_names]]) {
        list.forEach((item, idx) => item.spans.forEach((sp) => errs.push({ span: sp, kind, idx })));
      }
      errs.sort((a, b) => a.span[0] - b.span[0]);
    }

    // Every boundary from every layer.
    const cuts = new Set([0, text.length]);
    rows.forEach((row) => (cuts.add(row[0]), cuts.add(row[1])));
    for (const list of [phrases, md, errs]) list.forEach((x) => (cuts.add(x.span[0]), cuts.add(x.span[1])));
    const points = [...cuts].filter((p) => p >= 0 && p <= text.length).sort((a, b) => a - b);

    // Sweep: each layer is sorted and non-overlapping, so one pointer each.
    const ptr = { t: 0, p: 0, m: 0, e: 0 };
    const cover = (list, key, a, spanOf) => {
      while (ptr[key] < list.length && spanOf(list[ptr[key]])[1] <= a) ptr[key]++;
      const x = list[ptr[key]];
      return x && spanOf(x)[0] <= a ? ptr[key] : -1;
    };

    const frag = document.createDocumentFragment();
    const segs = [];
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      if (a === b) continue;
      const piece = text.slice(a, b);
      const t = cover(rows, 't', a, (row) => row);
      const p = cover(phrases, 'p', a, (x) => x.span);
      const m = cover(md, 'm', a, (x) => x.span);
      const er = cover(errs, 'e', a, (x) => x.span);
      if (t < 0 && p < 0 && m < 0 && er < 0) {
        frag.appendChild(document.createTextNode(piece));
        continue;
      }
      const s = document.createElement('span');
      s.className = 's';
      s.textContent = piece;
      const ds = s.dataset;
      if (t >= 0) {
        const row = rows[t];
        ds.t = t;
        ds.c = row[2] ?? 'off';
        ds.b = bncBucket(row[3]);
        if (row[4] != null) ds.a = row[4] <= 3 ? '1' : row[4] <= 6 ? '4' : '7';
        ds.n = row[5] ?? 'off';
      }
      if (p >= 0) {
        ds.p = p;
        ds.k = phrases[p].k_band;
        if (phrases[p].span[0] === a) s.classList.add('p0');
        if (phrases[p].span[1] === b) s.classList.add('p1');
      }
      if (m >= 0) {
        ds.m = m;
        ds.d = md[m].dimension === 'interactive' ? 'ia' : 'il';
        ds.mc = md[m].category;
        if (md[m].span[0] === a) s.classList.add('m0');
        if (md[m].span[1] === b) s.classList.add('m1');
      }
      if (er >= 0) {
        ds.e = errs[er].kind;
        ds.ei = errs[er].idx;
      }
      frag.appendChild(s);
      segs.push({ a, b, el: s });
    }
    doc.replaceChildren(frag);
    state = { text, rows, phrases, md, errs, segs, r };
    focusKey = null;
    doc.classList.remove('focusing');
  }

  // ---- lenses & legend -------------------------------------------------------

  function counts(id) {
    const out = {};
    const bump = (k) => (out[k] = (out[k] || 0) + 1);
    const { rows, phrases, md, errs } = state;
    if (id === 'cefr') rows.forEach((r) => bump(r[2] ?? 'off'));
    else if (id === 'bnc') rows.forEach((r) => bump(bncBucket(r[3])));
    else if (id === 'awl') rows.forEach((r) => r[4] != null && bump(r[4] <= 3 ? '1' : r[4] <= 6 ? '4' : '7'));
    else if (id === 'ngsl') rows.forEach((r) => bump(r[5] ?? 'off'));
    else if (id === 'phrase') phrases.forEach((x) => bump(String(x.k_band)));
    else if (id === 'md') md.forEach((x) => bump(x.dimension === 'interactive' ? 'ia' : 'il'));
    else if (id === 'spelling') errs.forEach((x) => bump(x.kind));
    return out;
  }

  function updateLensFade() {
    lensBar.classList.toggle('overflow', lensBar.scrollWidth > lensBar.clientWidth + 1);
    lensBar.classList.toggle('at-end', lensBar.scrollLeft + lensBar.clientWidth >= lensBar.scrollWidth - 2);
  }
  lensBar.addEventListener('scroll', updateLensFade, { passive: true });
  window.addEventListener('resize', updateLensFade);

  function renderLensBar() {
    requestAnimationFrame(updateLensFade);
    lensBar.replaceChildren(
      ...LENSES.map((l) =>
        h('button', {
          type: 'button',
          role: 'tab',
          class: 'lens',
          'aria-selected': String(l.id === lens),
          dataset: { lens: l.id },
          onclick: () => setLens(l.id, { fromUser: true }),
        }, l.label)
      )
    );
  }

  function renderLegend() {
    const def = LEGENDS[lens];
    if (!def) return legend.replaceChildren();
    const c = counts(lens);
    const total = Object.values(c).reduce((x, y) => x + y, 0);
    const items = def.items
      .filter(([k]) => c[k])
      .map(([k, label]) =>
        h('button', {
          type: 'button',
          class: 'key',
          'aria-pressed': String(focusKey === k),
          dataset: { lens, k },
          onclick: () => focus(focusKey === k ? null : k),
        }, h('i', { class: 'sw', 'aria-hidden': 'true' }), label, h('span', { class: 'key-n' }, num(c[k])))
      );
    if (!items.length) {
      const empty = { spelling: 'No spelling issues found.', phrase: 'No PHRASE-list expressions found.', md: 'No metadiscourse markers found.', awl: 'No Academic Word List words found.' }[lens];
      legend.replaceChildren(h('span', { class: 'legend-empty' }, empty || ''));
      return;
    }
    legend.replaceChildren(...items, total ? h('span', { class: 'legend-hint' }, 'Select a key to isolate it') : null);
  }

  function setLens(id, { fromUser = false } = {}) {
    if (!state) return;
    lens = id;
    doc.dataset.lens = id;
    focus(null, { silent: true });
    lensBar.querySelectorAll('.lens').forEach((b) => {
      const on = b.dataset.lens === id;
      b.setAttribute('aria-selected', String(on));
      // Horizontal only: scrollIntoView would also scroll the page to the bar.
      if (on && (b.offsetLeft < lensBar.scrollLeft || b.offsetLeft + b.offsetWidth > lensBar.scrollLeft + lensBar.clientWidth)) {
        lensBar.scrollLeft = b.offsetLeft - 12;
      }
    });
    renderLegend();
    if (fromUser) onLens(id);
  }

  /** Isolate one legend key: everything else in this lens is un-highlighted. */
  function focus(key, { silent = false } = {}) {
    focusKey = key;
    const def = LEGENDS[lens];
    doc.classList.toggle('focusing', key != null);
    if (state) {
      const attr = def?.attr;
      for (const { el } of state.segs) el.classList.toggle('hit', key != null && el.dataset[attr] === key);
    }
    if (!silent) renderLegend();
    if (key != null && !silent) {
      const first = state.segs.find((s) => s.el.classList.contains('hit'));
      if (first) scrollToEl(first.el);
    }
  }

  // ---- jump & flash ------------------------------------------------------------

  function segsIn(span) {
    const { segs } = state;
    let lo = 0;
    let hi = segs.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (segs[mid].b <= span[0]) lo = mid + 1;
      else hi = mid;
    }
    const out = [];
    for (let i = lo; i < segs.length && segs[i].a < span[1]; i++) out.push(segs[i].el);
    return out;
  }

  function scrollToEl(el) {
    const r = el.getBoundingClientRect();
    if (r.top > 96 && r.bottom < window.innerHeight - 48) return;
    el.scrollIntoView({ block: 'center', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }

  /** Scroll to the first span and pulse every span given. */
  function flash(spans, lensId) {
    if (!state || !spans.length) return;
    if (lensId && lensId !== lens) setLens(lensId);
    const els = spans.flatMap(segsIn);
    if (!els.length) return;
    scrollToEl(els[0]);
    els.forEach((el) => {
      el.classList.remove('flash');
      void el.offsetWidth; // restart the animation if it is already running
      el.classList.add('flash');
    });
    setTimeout(() => els.forEach((el) => el.classList.remove('flash')), 1400);
  }

  // ---- popover -------------------------------------------------------------------

  let showTimer = 0;
  let hideTimer = 0;
  let lastHidden = 0;
  let current = null;

  function cardFor(el) {
    const ds = el.dataset;
    const { rows, phrases, md, r } = state;
    const lines = [];
    const word = ds.t != null ? state.text.slice(rows[ds.t][0], rows[ds.t][1]) : el.textContent;
    const head = h('div', { class: 'pop-head' }, h('span', { class: 'pop-word' }, word));
    if (ds.e) {
      const list = { err: r.errors.errors, var: r.errors.variant_mismatches, name: r.errors.unknown_names }[ds.e];
      const item = list[ds.ei];
      const label = { err: 'Possible misspelling', var: r.errors.variant === 'gb' ? 'American spelling' : 'British spelling', name: 'Not in dictionary (name?)' }[ds.e];
      lines.push(h('div', { class: `pop-row pop-${ds.e}`, 'data-lens-row': 'spelling' }, h('span', {}, label),
        item.suggestions?.length ? h('b', {}, item.suggestions.slice(0, 3).join(', ')) : null));
    }
    if (ds.t != null) {
      const row = rows[ds.t];
      const cefr = row[2] == null ? 'not listed' : row[2] === 'proper' ? 'name' : row[2];
      const bnc = row[3] == null ? 'off-list' : row[3] === 'proper' ? 'name' : row[3] === 'supplementary' ? 'supplementary' : `${row[3]}K band`;
      const ngsl = row[5] == null ? 'off-list' : row[5] === 'proper' ? 'name' : row[5].toUpperCase();
      lines.push(h('div', { class: 'pop-row', 'data-lens-row': 'cefr' }, h('span', {}, 'CEFR'), h('b', {}, cefr)));
      lines.push(h('div', { class: 'pop-row', 'data-lens-row': 'bnc' }, h('span', {}, 'BNC/COCA'), h('b', {}, bnc)));
      if (row[4] != null) lines.push(h('div', { class: 'pop-row', 'data-lens-row': 'awl' }, h('span', {}, 'AWL'), h('b', {}, `sublist ${row[4]}`)));
      lines.push(h('div', { class: 'pop-row', 'data-lens-row': 'ngsl' }, h('span', {}, 'NGSL'), h('b', {}, ngsl)));
    }
    if (ds.p != null) {
      const x = phrases[ds.p];
      const e = r.phrase.expressions?.find((y) => y.rank === x.rank);
      const sense = senseLabel(x);
      lines.push(h('div', { class: 'pop-row pop-block', 'data-lens-row': 'phrase' },
        h('span', {}, `Phrase · K${x.k_band}`, e?.word_band != null ? ` · its words ${e.word_band}K` : ''),
        h('b', {}, phraseName(x), sense ? h('em', {}, ` ${sense}`) : null),
        e ? h('span', { class: 'ratings' }, PHRASE_REGISTERS.map((reg) => ratingDots(reg, e.register[reg.key]))) : null));
    }
    if (ds.m != null) {
      const x = md[ds.m];
      lines.push(h('div', { class: 'pop-row pop-block', 'data-lens-row': 'md' }, h('span', {}, x.dimension === 'interactive' ? 'Interactive' : 'Interactional'),
        h('b', {}, MD_CATEGORIES[x.category]?.label ?? x.category)));
    }
    lines.forEach((l) => l.dataset.lensRow === lens && l.classList.add('current'));
    return [head, ...lines];
  }

  function place(el) {
    const rects = el.getClientRects();
    const rect = rects[0] || el.getBoundingClientRect();
    pop.hidden = false;
    const pw = pop.offsetWidth;
    const ph = pop.offsetHeight;
    const gap = 8;
    const above = rect.top - ph - gap > 8;
    const top = above ? rect.top - ph - gap : rect.bottom + gap;
    let left = rect.left + rect.width / 2 - pw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    const originX = rect.left + rect.width / 2 - left;
    pop.style.left = `${Math.round(left + window.scrollX)}px`;
    pop.style.top = `${Math.round(top + window.scrollY)}px`;
    pop.style.setProperty('--ox', `${originX}px`);
    pop.dataset.side = above ? 'top' : 'bottom';
  }

  function show(el, instant) {
    current?.classList.remove('hover');
    current = el;
    el.classList.add('hover');
    pop.replaceChildren(...cardFor(el));
    place(el);
    pop.classList.toggle('instant', instant);
    requestAnimationFrame(() => pop.classList.add('open'));
  }

  function hide() {
    clearTimeout(showTimer);
    if (!current) return;
    current.classList.remove('hover');
    current = null;
    lastHidden = performance.now();
    pop.classList.remove('open');
    pop.hidden = true;
  }

  const hoverable = (t) => t instanceof Element && t.closest('.s');

  doc.addEventListener('pointerover', (e) => {
    if (e.pointerType === 'touch') return;
    const el = hoverable(e.target);
    if (!el || el === current) return;
    clearTimeout(hideTimer);
    clearTimeout(showTimer);
    // First card waits, so sweeping the mouse across the text doesn't flicker;
    // once one is open, the next opens at once and without animation.
    const warm = current || performance.now() - lastHidden < 400;
    if (warm) show(el, true);
    else showTimer = setTimeout(() => show(el, false), 320);
  });
  doc.addEventListener('pointerout', (e) => {
    if (e.pointerType === 'touch') return;
    if (hoverable(e.relatedTarget)) return;
    clearTimeout(showTimer);
    hideTimer = setTimeout(hide, 80);
  });
  doc.addEventListener('click', (e) => {
    const el = hoverable(e.target);
    if (!el) return hide();
    if (el === current) return hide();
    show(el, false);
  });
  document.addEventListener('keydown', (e) => e.key === 'Escape' && hide());
  window.addEventListener('scroll', () => current && hide(), { passive: true });
  window.addEventListener('resize', hide);

  return {
    load(data) {
      hide();
      build(data);
      renderLensBar();
      setLens(lens === 'none' ? (data.results.errors?.counts.errors_total ? 'spelling' : 'cefr') : lens);
    },
    setLens,
    get lens() {
      return lens;
    },
    focus(lensId, key) {
      if (lensId !== lens) setLens(lensId);
      focus(focusKey === key ? null : key);
    },
    flash,
    onLensChange(fn) {
      onLens = fn;
    },
    hide,
  };
})();
