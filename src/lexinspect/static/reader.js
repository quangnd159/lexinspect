// The reader: the analysed text, with every finding highlighted in place.
//
// The text is cut at every span boundary from every module (profile tokens,
// phrases, metadiscourse, spelling), and each piece becomes one <span> carrying
// data attributes for everything it belongs to. Switching lens then only
// changes `data-lens` on the container; CSS decides what is coloured, so a lens
// switch is a single attribute write and the colours can cross-fade.

// Labels are N_ strings, translated where shown; codes (A1, 1K, NGSL) are
// shown as they are.
const LENSES = [
  { id: 'adapt', label: N_('Adapt') },
  { id: 'spelling', label: N_('Spelling') },
  { id: 'cefr', label: N_('CEFR') },
  { id: 'bnc', label: N_('Frequency') },
  { id: 'awl', label: N_('Academic') },
  { id: 'ngsl', label: N_('NGSL') },
  { id: 'phrase', label: N_('Phrases') },
  { id: 'md', label: N_('Metadiscourse') },
  { id: 'sent', label: N_('Sentences'), needs: 'syntax' },
];

const CEFR_ORDER = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

function sentenceBucket(words) {
  if (words <= 15) return 's1';
  if (words <= 25) return 's2';
  if (words <= 35) return 's3';
  return 's4';
}

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

// Legend definitions: [key, label, flags] in display order. Keys match the
// data-* values written on segments. A label is an N_ message unless the item
// says `code` (shown as is); `plain` keys have no colour in the text, so they
// get no swatch.
const CODE = { code: true };
const LEGENDS = {
  spelling: { attr: 'e', items: [['err', N_('Spelling error')], ['var', null], ['name', N_('Unknown name')]] },
  cefr: { attr: 'c', items: [...CEFR_ORDER.map((l) => [l, l, CODE]), ['off', N_('Not listed')], ['proper', N_('Proper noun')]] },
  bnc: { attr: 'b', items: [['k1', '1K', CODE], ['k2', '2K', CODE], ['k3', '3K', CODE], ['k4', '4–5K', CODE], ['k6', '6–9K', CODE], ['k10', '10K+', CODE], ['supp', N_('Supplementary')], ['off', N_('Off-list')], ['proper', N_('Proper noun')]] },
  awl: { attr: 'a', items: [['1', N_('Sublists 1–3')], ['4', N_('Sublists 4–6')], ['7', N_('Sublists 7–10')]] },
  ngsl: { attr: 'n', items: [['ngsl', 'NGSL', CODE], ['nawl', 'NAWL', CODE], ['off', N_('Off-list')], ['proper', N_('Proper noun')]] },
  phrase: { attr: 'k', items: [['1', '1K', CODE], ['2', '2K', CODE], ['3', '3K', CODE], ['4', '4K', CODE], ['5', '5K', CODE]] },
  md: { attr: 'd', items: [['ia', N_('Interactive')], ['il', N_('Interactional')]] },
  sent: { attr: 'sl', items: [['s1', N_('Up to 15 words'), { plain: true }], ['s2', N_('16–25 words'), { plain: true }], ['s3', N_('26–35 words')], ['s4', N_('Over 35 words')]] },
};

/** The Adapt lens's keys depend on the readers' level: every level above it. */
function adaptLegend() {
  const target = Prefs.target;
  const from = target ? CEFR_ORDER.indexOf(target) + 1 : 6;
  return { attr: 'c', items: [...CEFR_ORDER.slice(from).map((l) => [l, l, CODE]), ['off', N_('Not listed')]], above: true };
}
const legendFor = (id) => (id === 'adapt' ? adaptLegend() : LEGENDS[id]);

const Reader = (() => {
  const doc = $('doc');
  const legend = $('legend');
  const lensBar = $('lenses');
  const pop = $('popover');
  // The analysed text is English whatever the interface language.
  doc.lang = 'en';
  doc.dir = 'ltr';
  // View toggles, not tabs: there are no tab panels to switch between.
  lensBar.setAttribute('role', 'group');

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
    const sents = (r.syntax?.sentences ?? []).slice().sort((a, b) => a.span[0] - b.span[0]);
    // Simpler-word suggestions by token start, for the Adapt lens's card.
    const alt = new Map();
    for (const item of r.alternatives?.items ?? []) for (const o of item.occurrences) alt.set(o.span[0], item);
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
    for (const list of [phrases, md, errs, sents]) list.forEach((x) => (cuts.add(x.span[0]), cuts.add(x.span[1])));
    const points = [...cuts].filter((p) => p >= 0 && p <= text.length).sort((a, b) => a - b);

    // Sweep: each layer is sorted and non-overlapping, so one pointer each.
    const ptr = { t: 0, p: 0, m: 0, e: 0, s: 0 };
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
      const tok = cover(rows, 't', a, (row) => row);
      const p = cover(phrases, 'p', a, (x) => x.span);
      const m = cover(md, 'm', a, (x) => x.span);
      const er = cover(errs, 'e', a, (x) => x.span);
      const si = cover(sents, 's', a, (x) => x.span);
      if (tok < 0 && p < 0 && m < 0 && er < 0) {
        if (si < 0) {
          frag.appendChild(document.createTextNode(piece));
          continue;
        }
        // Space and punctuation inside a sentence: shaded with it, never hovered.
        const g = document.createElement('span');
        g.className = 'g';
        g.textContent = piece;
        g.dataset.si = si;
        g.dataset.sl = sentenceBucket(sents[si].words);
        frag.appendChild(g);
        segs.push({ a, b, el: g });
        continue;
      }
      const s = document.createElement('span');
      s.className = 's';
      s.textContent = piece;
      const ds = s.dataset;
      if (si >= 0) {
        ds.si = si;
        ds.sl = sentenceBucket(sents[si].words);
      }
      if (tok >= 0) {
        const row = rows[tok];
        ds.t = tok;
        ds.c = row[2] ?? 'off';
        ds.b = bncBucket(row[3]);
        if (row[4] != null) ds.a = row[4] <= 3 ? '1' : row[4] <= 6 ? '4' : '7';
        ds.n = row[5] ?? 'off';
        if (row[2] !== 'proper') ds.cr = row[2] == null ? 7 : CEFR_ORDER.indexOf(row[2]) + 1;
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
    state = { text, rows, phrases, md, errs, sents, alt, segs, r };
    markAbove();
    focusKey = null;
    doc.classList.remove('focusing');
  }

  /** Flag every token above the readers' level for the Adapt lens. */
  function markAbove() {
    if (!state) return;
    const rank = Prefs.target ? CEFR_ORDER.indexOf(Prefs.target) + 1 : 6;
    for (const { el } of state.segs) {
      const cr = el.dataset.cr;
      el.classList.toggle('above', cr != null && Number(cr) > rank);
    }
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
    else if (id === 'sent') state.sents.forEach((x) => bump(sentenceBucket(x.words)));
    else if (id === 'adapt') {
      const from = Prefs.target ? CEFR_ORDER.indexOf(Prefs.target) + 1 : 6;
      rows.forEach((r) => {
        if (r[2] === 'proper') return;
        const rank = r[2] == null ? 7 : CEFR_ORDER.indexOf(r[2]) + 1;
        if (rank > from) bump(r[2] ?? 'off');
      });
    }
    return out;
  }

  const updateLensFade = edgeFade(lensBar);

  const lensLabel = (l) => (l.id === 'adapt' && Prefs.target ? t('Above {level}', { level: Prefs.target }) : t(l.label));

  function renderLensBar() {
    requestAnimationFrame(updateLensFade);
    lensBar.replaceChildren(
      ...LENSES.filter((l) => !l.needs || state?.r[l.needs]).map((l) =>
        h('button', {
          type: 'button',
          class: 'lens',
          'aria-pressed': String(l.id === lens),
          dataset: { lens: l.id },
          onclick: () => setLens(l.id, { fromUser: true }),
        }, lensLabel(l))
      )
    );
  }

  function keyLabel(k, label, flags) {
    if (flags?.code) return label;
    // The spelling variety not being checked against, named for this text.
    if (lens === 'spelling' && k === 'var') return state.r.errors?.variant === 'gb' ? t('American spelling') : t('British spelling');
    return t(label);
  }

  function emptyLegend() {
    switch (lens) {
      case 'spelling': return t('No spelling issues found.');
      case 'phrase': return t('No PHRASE List expressions found.');
      case 'md': return t('No metadiscourse markers found.');
      case 'awl': return t('No Academic Word List words found.');
      case 'adapt': return t('Every word on the CEFR lists is at {level} or below.', { level: Prefs.target });
      default: return '';
    }
  }

  function renderLegend() {
    const def = legendFor(lens);
    if (!def) return legend.replaceChildren();
    if (lens === 'adapt' && !Prefs.target) {
      legend.replaceChildren(h('span', { class: 'legend-empty' }, t('Choose the readers’ level in Adapt to highlight the words above it.')));
      return;
    }
    const c = counts(lens);
    const total = Object.values(c).reduce((x, y) => x + y, 0);
    const items = def.items
      .filter(([k]) => c[k])
      .map(([k, label, flags]) =>
        h('button', {
          type: 'button',
          class: flags?.plain ? 'key plain' : 'key',
          'aria-pressed': String(focusKey === k),
          dataset: { lens, k },
          onclick: () => focus(focusKey === k ? null : k),
        }, flags?.plain ? null : h('i', { class: 'sw', 'aria-hidden': 'true' }), keyLabel(k, label, flags), h('span', { class: 'key-n' }, num(c[k])))
      );
    if (!items.length) {
      legend.replaceChildren(h('span', { class: 'legend-empty' }, emptyLegend()));
      return;
    }
    legend.replaceChildren(...items, total ? h('span', { class: 'legend-hint' }, t('Select a key to isolate it')) : null);
  }

  function setLens(id, { fromUser = false } = {}) {
    if (!state) return;
    lens = id;
    doc.dataset.lens = id;
    focus(null, { silent: true });
    lensBar.querySelectorAll('.lens').forEach((b) => {
      const on = b.dataset.lens === id;
      b.setAttribute('aria-pressed', String(on));
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
    const def = legendFor(lens);
    doc.classList.toggle('focusing', key != null);
    if (state) {
      const attr = def?.attr;
      for (const { el } of state.segs) el.classList.toggle('hit', key != null && el.dataset[attr] === key && (!def.above || el.classList.contains('above')));
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

  /** One row of the card: a label, then its value. */
  const popRow = (lensId, label, value, cls = '') =>
    h('div', { class: `pop-row ${cls}`.trim(), 'data-lens-row': lensId }, h('span', {}, label), value);
  /** English from the text or the word lists, inside the card. */
  const enB = (...children) => h('b', { lang: 'en', dir: 'ltr' }, ...children);

  function cardFor(el) {
    const ds = el.dataset;
    const { rows, phrases, md, r } = state;
    const lines = [];
    const word = ds.t != null ? state.text.slice(rows[ds.t][0], rows[ds.t][1]) : el.textContent;
    const head = h('div', { class: 'pop-head' }, en(word, 'pop-word'));
    if (ds.e) {
      const list = { err: r.errors.errors, var: r.errors.variant_mismatches, name: r.errors.unknown_names }[ds.e];
      const item = list[ds.ei];
      const label = {
        err: t('Possible misspelling'),
        var: r.errors.variant === 'gb' ? t('American spelling') : t('British spelling'),
        name: t('Not in the dictionary; perhaps a name'),
      }[ds.e];
      lines.push(popRow('spelling', label, item.suggestions?.length ? enB(item.suggestions.slice(0, 3).join(', ')) : null, `pop-${ds.e}`));
    }
    if (ds.t != null) {
      const row = rows[ds.t];
      const cefr = row[2] == null ? t('Not listed') : row[2] === 'proper' ? t('Proper noun') : row[2];
      const bnc = row[3] == null ? t('Off-list') : row[3] === 'proper' ? t('Proper noun') : row[3] === 'supplementary' ? t('Supplementary') : t('{band} band', { band: `${row[3]}K` });
      const ngsl = row[5] == null ? t('Off-list') : row[5] === 'proper' ? t('Proper noun') : row[5].toUpperCase();
      lines.push(popRow('cefr', 'CEFR', h('b', {}, cefr)));
      lines.push(popRow('bnc', 'BNC/COCA', h('b', {}, bnc)));
      if (row[4] != null) lines.push(popRow('awl', 'AWL', h('b', {}, t('Sublist {sublist}', { sublist: num(row[4]) }))));
      lines.push(popRow('ngsl', 'NGSL', h('b', {}, ngsl)));
    }
    if (ds.p != null) {
      const x = phrases[ds.p];
      const e = r.phrase.expressions?.find((y) => y.rank === x.rank);
      const sense = senseLabel(x);
      const band = `${x.k_band}K`;
      lines.push(h('div', { class: 'pop-row pop-block', 'data-lens-row': 'phrase' },
        h('span', {}, e?.word_band != null
          ? t('PHRASE List, {band}; its rarest word is {wordBand}', { band, wordBand: `${e.word_band}K` })
          : t('PHRASE List, {band}', { band })),
        enB(phraseName(x), sense ? h('em', {}, ` ${sense}`) : null),
        e ? h('span', { class: 'ratings' }, PHRASE_REGISTERS.map((reg) => ratingDots(reg, e.register[reg.key]))) : null));
    }
    if (ds.m != null) {
      const x = md[ds.m];
      const cat = MD_CATEGORIES[x.category];
      lines.push(popRow('md', x.dimension === 'interactive' ? t('Interactive') : t('Interactional'), h('b', {}, cat ? t(cat.label) : x.category), 'pop-block'));
    }
    if (ds.t != null && state.alt.has(rows[ds.t][0])) {
      const item = state.alt.get(rows[ds.t][0]);
      const target = Prefs.target;
      const opts = item.suggestions.filter((x) => !target || CEFR_ORDER.indexOf(x.level) <= CEFR_ORDER.indexOf(target));
      if (opts.length && (!target || el.classList.contains('above'))) {
        const occ = item.occurrences.find((o) => o.span[0] === rows[ds.t][0]);
        lines.push(popRow('adapt', target ? t('Simpler words at {level} or below', { level: target }) : t('Simpler words'),
          enB(opts.slice(0, 4).map((x) => occ?.replacements?.[x.word] ?? x.word).join(', ')), 'pop-block'));
      }
    }
    if (ds.si != null && lens === 'sent') {
      const x = state.sents[ds.si];
      const facts = [tn(x.words, '{n} word', '{n} words'), tn(x.clauses, '{n} clause', '{n} clauses')];
      if (x.passive) facts.push(tn(x.passive, '{n} passive clause', '{n} passive clauses'));
      lines.push(popRow('sent', t('Sentence {number}', { number: num(Number(ds.si) + 1) }), h('b', {}, facts.join(' · '))));
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
    // clientWidth, not innerWidth: the card must clear the scrollbar too.
    left = Math.max(8, Math.min(left, document.documentElement.clientWidth - pw - 8));
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

  const hoverable = (node) => node instanceof Element && node.closest('.s');

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

  // Language change: relabel the lens buttons, the legend and an open card.
  // The text itself carries no interface language.
  I18n.onChange(() => {
    if (!state) return;
    renderLensBar();
    renderLegend();
    if (current) {
      pop.replaceChildren(...cardFor(current));
      place(current);
    }
  });

  return {
    load(data) {
      hide();
      build(data);
      renderLensBar();
      setLens(lens === 'none' ? (data.results.errors?.counts.errors_total ? 'spelling' : Prefs.target ? 'adapt' : 'cefr') : lens);
    },
    setLens,
    /** The readers' level changed: re-mark and relabel. */
    retarget() {
      if (!state) return;
      markAbove();
      renderLensBar();
      setLens(lens);
    },
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
