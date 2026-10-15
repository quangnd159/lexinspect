// The analysis pane: tabs, and one renderer per tab. Panels are built lazily
// on first open, so the first paint after Analyse only builds the overview.

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'readability', label: 'Readability' },
  { id: 'vocabulary', label: 'Vocabulary' },
  { id: 'phrase', label: 'Phrases', lens: 'phrase' },
  { id: 'md', label: 'Metadiscourse', lens: 'md' },
  { id: 'spelling', label: 'Spelling', lens: 'spelling' },
  { id: 'diversity', label: 'Diversity' },
  { id: 'statistics', label: 'Statistics' },
];
const VOCAB_SUBS = [
  { id: 'cefr', label: 'CEFR' },
  { id: 'bnc', label: 'Frequency' },
  { id: 'ngsl', label: 'NGSL / NAWL' },
  { id: 'awl', label: 'AWL' },
];
const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

// ---- shared pieces -----------------------------------------------------------

function about(key) {
  const info = SECTION_INFO[key];
  if (!info) return null;
  return h('details', { class: 'about' },
    h('summary', {}, 'About this measure'),
    h('div', { class: 'about-body' },
      h('p', { html: info.about }),
      info.caveats.length ? h('ul', {}, info.caveats.map((c) => h('li', { html: c }))) : null));
}

function stat(label, value, sub) {
  return h('div', { class: 'stat' }, h('span', { class: 'stat-label' }, label), h('span', { class: 'stat-value' }, value), sub ? h('span', { class: 'stat-sub' }, sub) : null);
}

function callout(kind, title, items) {
  return h('div', { class: `callout ${kind}`, role: kind === 'warn' ? 'note' : null },
    h('b', {}, title), items?.length ? h('ul', {}, items.map((t) => h('li', {}, t))) : null);
}

/** Word chips; clicking one flashes its occurrences in the reader. */
function chips(list, { lens, limit = 40, label = (x) => x.word, count = (x) => x.count, spans } = {}) {
  const wrap = h('div', { class: 'chips' });
  const make = (x) =>
    h('button', { type: 'button', class: 'chip', onclick: () => Reader.flash(spans ? spans(x) : spansOfWord(label(x)), lens) },
      label(x), count(x) > 1 ? h('span', { class: 'chip-n' }, `×${count(x)}`) : null);
  list.slice(0, limit).forEach((x) => wrap.appendChild(make(x)));
  if (list.length > limit) {
    const more = h('button', { type: 'button', class: 'chip more' }, `+${list.length - limit} more`);
    more.addEventListener('click', () => {
      list.slice(limit).forEach((x) => wrap.insertBefore(make(x), more));
      more.remove();
    });
    wrap.appendChild(more);
  }
  if (!list.length) wrap.appendChild(h('span', { class: 'muted' }, 'None'));
  return wrap;
}

let CURRENT = null; // the response being shown

const asName = (x) => x.word.charAt(0).toUpperCase() + x.word.slice(1);

function spansOfWord(word, keep = () => true) {
  const { rows } = CURRENT.results.profile;
  const text = CURRENT.input.normalised_text ?? CURRENT.submitted;
  const w = word.toLowerCase().replace(/’/g, "'");
  const out = [];
  for (const r of rows) if (keep(r) && text.slice(r[0], r[1]).toLowerCase().replace(/’/g, "'") === w) out.push([r[0], r[1]]);
  return out;
}

/** Stacked horizontal bar from [{key, value, label}] with a legend underneath. */
function stack(parts, { lens, total } = {}) {
  const sum = total ?? parts.reduce((s, p) => s + p.value, 0);
  const bar = h('div', { class: 'stack', role: 'img', 'aria-label': parts.map((p) => `${p.label} ${pct((p.value / sum) * 100)}`).join(', ') });
  const keys = h('div', { class: 'stack-keys' });
  parts.forEach((p) => {
    if (!p.value) return;
    const share = sum ? (p.value / sum) * 100 : 0;
    bar.appendChild(h('span', { class: `seg ${lens}-${p.key}`, style: { flexGrow: String(p.value) }, title: `${p.label}: ${pct(share)}` }));
    keys.appendChild(
      h('button', { type: 'button', class: 'stack-key', onclick: lens && p.focus !== false ? () => Reader.focus(lens, p.key) : null, disabled: !lens || p.focus === false },
        h('i', { class: `sw ${lens}-${p.key}` }), p.label, h('b', {}, pct(share, share < 10 ? 1 : 0))));
  });
  return h('div', { class: 'stack-wrap' }, bar, keys);
}

// ---- overview ------------------------------------------------------------------

function bandFor(perBand, threshold) {
  for (const [band, v] of Object.entries(perBand)) if (v.cumulative_coverage_with_supplementary_pct >= threshold) return Number(band);
  return null;
}

function b2plus(cefr) {
  return ['B2', 'C1', 'C2'].reduce((s, l) => s + cefr.per_level[l].coverage_pct, 0);
}

function renderOverview(r, go) {
  const rd = r.readability;
  const grade = rd.scores.text_standard;
  const ease = rd.scores.flesch_reading_ease;
  const easeLabel = EASE_BANDS.find(([lo]) => ease >= lo)[1];
  const b95 = bandFor(r.bnc_coca.per_band, 95);
  const b98 = bandFor(r.bnc_coca.per_band, 98);
  const div = r.diversity.scores;
  const md = r.metadiscourse;
  const e = r.errors;
  const issues = e.counts.errors_total;

  const card = (tab, sub, title, value, unit, detail, extra) =>
    h('button', { type: 'button', class: 'card', onclick: () => go(tab, sub) },
      h('span', { class: 'card-title' }, title),
      h('span', { class: 'card-value' }, value, unit ? h('small', {}, unit) : null),
      h('span', { class: 'card-detail' }, detail),
      extra || null);

  const levelBar = h('span', { class: 'mini-levels', 'aria-hidden': 'true' },
    LEVELS.map((l) => h('i', { class: `cefr-${l}`, style: { flexGrow: String(r.cefr.per_level[l].tokens || 0) } })));

  const head = h('div', { class: 'ov-head' },
    stat('Words', num(rd.counts.words)),
    stat('Sentences', num(rd.counts.sentences)),
    stat('Reading time', duration(rd.counts.reading_time_seconds)),
    stat('Words per sentence', num(rd.averages.words_per_sentence, 1)));

  const cards = h('div', { class: 'cards' },
    card('readability', null, 'Readability', grade == null ? '–' : num(grade, 1), 'grade',
      `${gradeLabel(grade)} · Flesch ${num(ease)} (${easeLabel.toLowerCase()})`,
      rd.reliability.reliable ? null : h('span', { class: 'card-flag' }, 'Short text: indicative only')),
    card('vocabulary', 'cefr', 'Vocabulary level', r.cefr.highest_level_present ?? '–', 'highest',
      `${pct(b2plus(r.cefr))} of words at B2 or above`, levelBar),
    card('vocabulary', 'bnc', 'Vocabulary needed', b95 ? `${b95}K` : '25K+', 'for 95%',
      b98 ? `${b98}K families for 98% coverage` : `98% not reached: ${plural(r.bnc_coca.counts.off_list_tokens, 'word')} in no list`),
    card('diversity', null, 'Lexical diversity', div.mtld == null ? '–' : num(div.mtld, 0), 'MTLD',
      div.vocd_d == null ? 'Needs at least 50 words for vocd-D' : `vocd-D ${num(div.vocd_d, 0)}`),
    card('vocabulary', 'awl', 'Academic words', pct(r.awl.coverage_pct), 'AWL',
      `${plural(r.awl.counts.awl_families, 'family', 'families')} · NAWL ${pct(r.ngsl.coverage_pct.nawl)}`),
    card('phrase', null, 'Phrases', num(r.phrase.counts.total_hits), null,
      `${num(r.phrase.counts.hits_per_1000_words, 0)} per 1,000 words · ${plural(r.phrase.counts.unique_phrases, 'expression')}`),
    card('md', null, 'Metadiscourse', num(md.density_per_1000, 0), 'per 1k',
      `${plural(md.per_category.hedges.hits, 'hedge')} · ${plural(md.per_category.boosters.hits, 'booster')}`),
    card('spelling', null, 'Spelling', issues ? num(issues) : 'Clean', issues ? (issues === 1 ? 'issue' : 'issues') : null,
      issues
        ? `${plural(e.counts.unique_errors, 'distinct word')}${e.counts.variant_mismatches ? ` · ${num(e.counts.variant_mismatches)} ${e.variant === 'gb' ? 'US' : 'UK'} spellings` : ''}`
        : e.counts.variant_mismatches
          ? `${num(e.counts.variant_mismatches)} ${e.variant === 'gb' ? 'US' : 'UK'} spellings in ${e.variant === 'gb' ? 'UK' : 'US'} mode`
          : `Checked as ${e.variant === 'gb' ? 'British' : 'American'} English`));

  return h('div', {}, head, cards);
}

// ---- readability -----------------------------------------------------------------

// Grade equivalents used by the headline median (readability._dale_chall_grade
// and _flesch_grade): the midpoint of each published band.
function daleGradeNum(raw) {
  for (const [ceil, g] of [[5, 4], [6, 5.5], [7, 7.5], [8, 9.5], [9, 11.5], [10, 14]]) if (raw < ceil) return g;
  return 16;
}
function fleschGradeNum(fre) {
  for (const [floor, g] of [[90, 5], [80, 6], [70, 7], [60, 8.5], [50, 11], [30, 14]]) if (fre >= floor) return g;
  return 16;
}

function daleGrade(raw) {
  for (const [ceil, g] of [[5, '4 and below'], [6, '5–6'], [7, '7–8'], [8, '9–10'], [9, '11–12'], [10, '13–15']]) if (raw < ceil) return g;
  return '16+';
}

function renderReadability(r) {
  const rd = r.readability;
  const s = rd.scores;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, s.text_standard == null ? '–' : num(s.text_standard, 1)),
    h('div', { class: 'hero-text' }, h('b', {}, `Grade ${s.text_standard == null ? '–' : num(s.text_standard, 1)} · ${gradeLabel(s.text_standard)}`),
      h('span', {}, 'Median of the eight formulas below. Roughly the reader age minus five.'))));
  if (!rd.reliability.reliable) out.appendChild(callout('warn', 'Read these scores with care', rd.reliability.notes));

  out.appendChild(h('div', { class: 'sub-h' }, 'Each formula’s grade, on one scale: longer bars mean harder text'));
  const list = h('div', { class: 'rows' });
  for (const f of FORMULAS) {
    const v = s[f.key];
    let value;
    let bar;
    let sub;
    if (f.kind === 'ease') {
      value = num(v, 0);
      bar = meter(fleschGradeNum(v), 20, 'grade');
      sub = EASE_BANDS.find(([lo]) => v >= lo)[1];
    } else if (f.kind === 'dale') {
      value = num(v, 1);
      bar = meter(daleGradeNum(v), 20, 'grade');
      sub = `grade ${daleGrade(v)}`;
    } else {
      value = num(v, 1);
      bar = meter(v, 20, 'grade');
      sub = gradeLabel(v).toLowerCase();
    }
    list.appendChild(h('div', { class: 'row' },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, f.name), h('span', { class: 'row-note' }, f.note)),
      h('div', { class: 'row-viz' }, bar),
      h('div', { class: 'row-val' }, h('b', {}, value), h('span', {}, sub))));
  }
  out.appendChild(list);

  const c = rd.counts;
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('Syllables', num(c.syllables), `${num(rd.averages.syllables_per_word, 2)} per word`),
    stat('Polysyllables', num(c.polysyllable_words), '3+ syllables'),
    stat('Long words', num(c.long_words), '7+ letters'),
    stat('Unfamiliar', num(c.difficult_words), 'not on Dale–Chall list'),
    stat('Characters', num(c.characters), `${num(rd.averages.characters_per_word, 1)} per word`),
    stat('Reading time', duration(c.reading_time_seconds), '238 words per minute')));
  out.appendChild(about('readability'));
  return out;
}

// ---- vocabulary --------------------------------------------------------------------

function renderCefr(r, ctx) {
  const c = r.cefr;
  const out = h('div', {});
  const n = c.counts.content_tokens;
  out.appendChild(stack([
    ...LEVELS.map((l) => ({ key: l, label: l, value: c.per_level[l].tokens })),
    { key: 'off', label: 'Not listed', value: c.counts.off_list_tokens },
    { key: 'proper', label: 'Names', value: c.counts.proper_noun_tokens },
  ], { lens: 'cefr', total: n }));

  out.appendChild(h('div', { class: 'stats-grid' },
    stat('Highest level', c.highest_level_present ?? '–'),
    stat('B2 and above', pct(b2plus(c))),
    stat('Level for 95% coverage', c.estimated_level_95th ?? 'beyond C2', 'names counted as known'),
    stat('On the lists', pct(c.coverage_pct), `${num(c.counts.on_list_tokens)} of ${num(n)} words`)));

  for (const l of [...LEVELS].reverse()) {
    const words = c.words_by_level[l];
    if (!words.length) continue;
    out.appendChild(h('div', { class: 'level' },
      h('button', { type: 'button', class: 'level-head', onclick: () => Reader.focus('cefr', l) },
        h('span', { class: `badge cefr-${l}` }, l),
        h('span', {}, `${plural(c.per_level[l].tokens, 'word')} · ${pct(c.per_level[l].coverage_pct)}`)),
      chips(words, { lens: 'cefr', limit: l === 'A1' ? 24 : 40, spans: (x) => spansOfWord(x.word, (row) => row[2] === l) })));
  }
  if (c.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge cefr-off' }, '?'), 'Not on the CEFR lists'), chips(c.off_list, { lens: 'cefr' })));
  if (c.proper_nouns.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge cefr-proper' }, 'N'), 'Names'), chips(c.proper_nouns, { lens: 'cefr', label: asName })));
  if (c.counts.pos_fallback_tokens) {
    out.appendChild(h('p', { class: 'fine' }, `${plural(c.counts.pos_fallback_tokens, 'word')} used in a part of speech the lists don't give a level for; their lowest listed level was used.`));
  }
  if (ctx.cefrLevelAvailable) out.appendChild(cefrClassifier(ctx));
  out.appendChild(about('cefr'));
  return out;
}

function cefrClassifier(ctx) {
  const box = h('div', { class: 'callout' }, h('b', {}, 'Text-level estimate'),
    h('p', {}, 'A ModernBERT classifier trained on the UniversalCEFR corpus predicts one level for the whole text. It is an estimate, not a placement.'));
  const btn = h('button', { type: 'button', class: 'btn small' }, 'Run classifier');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Running…';
    try {
      const res = await ctx.cefrLevel();
      box.replaceChildren(h('b', {}, `Estimated level: ${res.level ?? res.predicted_level ?? '–'}`), h('p', {}, 'Combine with the vocabulary profile and readability before reporting a level.'));
    } catch (err) {
      btn.disabled = false;
      btn.textContent = 'Run classifier';
      toast(err.message);
    }
  });
  box.appendChild(btn);
  return box;
}

function renderBnc(r) {
  const b = r.bnc_coca;
  const n = b.counts.content_tokens;
  const out = h('div', {});
  const bands = Object.entries(b.per_band).map(([k, v]) => ({ band: Number(k), ...v }));
  const used = bands.filter((x) => x.tokens);
  const bucket = (lo, hi) => bands.filter((x) => x.band >= lo && x.band <= hi).reduce((s, x) => s + x.tokens, 0);
  out.appendChild(stack([
    { key: 'k1', label: '1K', value: bucket(1, 1) },
    { key: 'k2', label: '2K', value: bucket(2, 2) },
    { key: 'k3', label: '3K', value: bucket(3, 3) },
    { key: 'k4', label: '4–5K', value: bucket(4, 5) },
    { key: 'k6', label: '6–9K', value: bucket(6, 9) },
    { key: 'k10', label: '10K+', value: bucket(10, 25) },
    { key: 'supp', label: 'Supplementary', value: b.counts.supplementary_tokens },
    { key: 'proper', label: 'Names', value: b.counts.proper_noun_tokens },
    { key: 'off', label: 'Off-list', value: b.counts.off_list_tokens },
  ], { lens: 'bnc', total: n }));

  const b95 = bandFor(b.per_band, 95);
  const b98 = bandFor(b.per_band, 98);
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('95% coverage', b95 ? `${b95}K` : '25K+', 'adequate comprehension'),
    stat('98% coverage', b98 ? `${b98}K` : '25K+', 'comfortable reading'),
    stat('In 25 bands', pct(b.coverage_pct), `${pct(b.coverage_with_supplementary_pct)} with names and supplementary`),
    stat('Off-list', num(b.counts.off_list_tokens), 'words in no list')));

  // Coverage curve, one bar per band up to the last band used. The axis starts
  // near the 1K value rather than at 0: the decisions (95%, 98%) are made in the
  // top few points, which a 0–100 axis flattens into one line.
  // The floor drops in steps of 10 when the 1K band alone covers less than 70%.
  const first = b.per_band['1']?.cumulative_coverage_with_supplementary_pct ?? 100;
  const FLOOR = Math.max(0, Math.min(70, Math.floor((first - 4) / 10) * 10));
  const y = (v) => Math.max(0, Math.min(1, (v - FLOOR) / (100 - FLOOR)));
  const last = Math.max(3, ...used.map((x) => x.band));
  const curve = h('div', { class: 'curve', role: 'img', 'aria-label': 'Cumulative coverage by band' });
  let prev = b.counts.content_tokens ? ((b.counts.supplementary_tokens + b.counts.proper_noun_tokens) / n) * 100 : 0;
  bands.filter((x) => x.band <= last).forEach((x) => {
    const cum = x.cumulative_coverage_with_supplementary_pct;
    curve.appendChild(h('div', { class: 'curve-col', title: `${x.band}K: ${num(x.tokens)} words (${pct(x.coverage_pct)}); cumulative ${pct(cum)}` },
      h('span', { class: 'curve-track' },
        h('span', { class: 'curve-bar', style: { height: `${y(cum) * 100}%` } }),
        h('span', { class: 'curve-own', style: { bottom: `${y(prev) * 100}%`, height: `${(y(cum) - y(prev)) * 100}%` } })),
      h('span', { class: 'curve-label' }, String(x.band))));
    prev = cum;
  });
  out.appendChild(h('div', { class: 'curve-wrap' },
    h('div', { class: 'curve-lines' }, h('span', { style: { '--y': y(95) } }, '95%'), h('span', { style: { '--y': y(98) } }, '98%')),
    curve,
    h('div', { class: 'curve-axis' }, `Cumulative coverage by band (thousand word families), axis from ${FLOOR}% to 100%. The dark slice is each band’s share; names and supplementary lists count as known.`)));

  if (b.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, 'Off-list words'), chips(b.off_list, { lens: 'bnc' })));
  if (b.proper_nouns.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, 'Names'), chips(b.proper_nouns, { lens: 'bnc', label: asName })));
  const supp = Object.entries(b.supplementary);
  if (supp.length) {
    const names = { proper_names: 'proper names', marginal_words: 'marginal words', transparent_compounds: 'transparent compounds', acronyms: 'acronyms', abbreviations: 'abbreviations' };
    out.appendChild(h('p', { class: 'fine' }, 'Supplementary lists: ', supp.map(([k, v]) => `${num(v)} ${names[k] ?? k.replace(/_/g, ' ')}`).join(', '), '.'));
  }
  out.appendChild(about('bnc'));
  return out;
}

function renderNgsl(r) {
  const g = r.ngsl;
  const out = h('div', {});
  out.appendChild(stack([
    { key: 'ngsl', label: 'NGSL', value: g.counts.ngsl_tokens },
    { key: 'nawl', label: 'NAWL', value: g.counts.nawl_tokens },
    { key: 'proper', label: 'Names', value: g.counts.proper_noun_tokens },
    { key: 'off', label: 'Off-list', value: g.counts.off_list_tokens },
  ], { lens: 'ngsl', total: g.counts.content_tokens }));
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('NGSL', pct(g.coverage_pct.ngsl), `${plural(g.counts.ngsl_lemmas, 'lemma')}`),
    stat('NAWL', pct(g.coverage_pct.nawl), `${plural(g.counts.nawl_lemmas, 'lemma')}`),
    stat('Together', pct(g.coverage_pct.ngsl_plus_nawl)),
    stat('Off-list', pct(g.coverage_pct.off_list))));
  if (g.nawl_words?.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge ngsl-nawl' }, 'NAWL'), 'Academic words'), chips(g.nawl_words, { lens: 'ngsl' })));
  if (g.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, 'Off-list words'), chips(g.off_list, { lens: 'ngsl' })));
  out.appendChild(about('ngsl'));
  return out;
}

function renderAwl(r) {
  const a = r.awl;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, pct(a.coverage_pct)),
    h('div', { class: 'hero-text' }, h('b', {}, `${plural(a.counts.awl_tokens, 'word')} from ${plural(a.counts.awl_families, 'family', 'families')}`),
      h('span', {}, 'Academic prose typically runs near 10%, fiction 1–2%.'))));
  const rows = h('div', { class: 'rows compact' });
  const max = Math.max(1, ...Object.values(a.per_sublist).map((x) => x.tokens));
  for (const [s, v] of Object.entries(a.per_sublist)) {
    rows.appendChild(h('div', { class: `row${v.tokens ? '' : ' dim'}` },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, `Sublist ${s}`)),
      h('div', { class: 'row-viz' }, meter(v.tokens, max, 'awl')),
      h('div', { class: 'row-val' }, h('b', {}, num(v.tokens)), h('span', {}, plural(v.families, 'family', 'families')))));
  }
  out.appendChild(rows);
  if (a.families_detail.length) {
    out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, 'Families found'),
      chips(a.families_detail, {
        lens: 'awl',
        limit: 60,
        label: (x) => x.headword,
        count: (x) => x.tokens,
        spans: (x) => x.spans,
      })));
  }
  out.appendChild(about('awl'));
  return out;
}

function renderVocabulary(r, ctx, sub) {
  const out = h('div', {});
  const nav = h('div', { class: 'subnav segmented', role: 'tablist' });
  const body = h('div', {});
  const renderers = { cefr: renderCefr, bnc: renderBnc, ngsl: renderNgsl, awl: renderAwl };
  const cache = {};
  const select = (id, { fromLens = false } = {}) => {
    nav.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.sub === id)));
    cache[id] ??= renderers[id](r, ctx);
    body.replaceChildren(cache[id]);
    out.dataset.sub = id;
    if (!fromLens) Reader.setLens(id);
  };
  VOCAB_SUBS.forEach((s) => nav.appendChild(h('button', { type: 'button', role: 'radio', dataset: { sub: s.id }, onclick: () => select(s.id) }, s.label)));
  out.append(nav, body);
  out.selectSub = select;
  select(sub || 'cefr', { fromLens: true });
  return out;
}

// ---- phrases -------------------------------------------------------------------------

function renderPhrases(r) {
  const p = r.phrase;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('Expressions', num(p.counts.total_hits), plural(p.counts.unique_phrases, 'distinct one')),
    stat('Per 1,000 words', num(p.counts.hits_per_1000_words, 1))));
  if (p.counts.total_hits) {
    out.appendChild(h('div', { class: 'sub-h' }, 'By frequency band (K1 most common, K5 least)'));
    out.appendChild(stack([1, 2, 3, 4, 5].map((k) => ({ key: String(k), label: `K${k}`, value: p.hits_per_k_band[k] })), { lens: 'phrase' }));
  }

  const groups = new Map();
  for (const x of p.hits) {
    const key = `${x.rank}`;
    if (!groups.has(key)) groups.set(key, { ...x, spans: [], surfaces: new Set(), also: new Set() });
    const g = groups.get(key);
    g.spans.push(x.span);
    g.surfaces.add(x.surface.toLowerCase());
    (x.also_possible || []).forEach((a) => g.also.add(a));
  }
  const list = h('div', { class: 'rows' });
  [...groups.values()]
    .sort((a, b) => b.spans.length - a.spans.length || a.k_band - b.k_band || a.rank - b.rank)
    .forEach((g) => {
      list.appendChild(h('button', { type: 'button', class: 'row clickable', onclick: () => Reader.flash(g.spans, 'phrase') },
        h('div', { class: 'row-main' },
          h('span', { class: 'row-name' }, h('span', { class: `badge phrase-${g.k_band}` }, `K${g.k_band}`), ' ', g.phrase.replace(/\s*\(.*?\)\s*/g, ' ').trim().toLowerCase()),
          h('span', { class: 'row-note' },
            g.sense ? `${g.sense.toLowerCase()} · ` : '',
            [...g.surfaces].map((s) => `“${s}”`).join(', '),
            g.also.size ? ` · could also be ${[...g.also].map((a) => a.toLowerCase()).join(', ')}` : '')),
        h('div', { class: 'row-val' }, h('b', {}, `×${g.spans.length}`))));
    });
  if (!groups.size) list.appendChild(h('p', { class: 'muted' }, 'No PHRASE-list expressions in this text.'));
  out.appendChild(list);
  out.appendChild(about('phrase'));
  return out;
}

// ---- metadiscourse -----------------------------------------------------------------

function renderMetadiscourse(r) {
  const m = r.metadiscourse;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('Markers', num(m.counts.total_hits), `${num(m.density_per_1000, 0)} per 1,000 words`),
    stat('Interactive', num(m.per_dimension.interactive.hits), `${num(m.per_dimension.interactive.density_per_1000, 0)} per 1,000`),
    stat('Interactional', num(m.per_dimension.interactional.hits), `${num(m.per_dimension.interactional.density_per_1000, 0)} per 1,000`)));

  for (const dim of ['interactive', 'interactional']) {
    const section = h('div', { class: 'md-dim' }, h('button', { type: 'button', class: 'md-dim-head', onclick: () => Reader.focus('md', dim === 'interactive' ? 'ia' : 'il') },
      h('i', { class: `sw md-${dim === 'interactive' ? 'ia' : 'il'}` }), dim === 'interactive' ? 'Interactive: guiding the reader through the text' : 'Interactional: engaging the reader'));
    const rows = h('div', { class: 'rows compact' });
    const max = Math.max(1, ...Object.values(m.per_category).map((c) => c.hits));
    for (const [cat, v] of Object.entries(m.per_category)) {
      if (v.dimension !== dim) continue;
      const hits = m.hits.filter((x) => x.category === cat);
      const markers = new Map();
      hits.forEach((x) => markers.set(x.surface.toLowerCase(), (markers.get(x.surface.toLowerCase()) || 0) + 1));
      const info = MD_CATEGORIES[cat] || { label: cat, note: '', eg: '' };
      rows.appendChild(h('button', { type: 'button', class: `row clickable${v.hits ? '' : ' dim'}`, disabled: !v.hits, onclick: () => Reader.flash(hits.map((x) => x.span), 'md') },
        h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, info.label),
          h('span', { class: 'row-note' }, v.hits ? [...markers].map(([w, c]) => (c > 1 ? `${w} ×${c}` : w)).join(', ') : `${info.note}: ${info.eg}`)),
        h('div', { class: 'row-viz' }, meter(v.hits, max, `md-${dim === 'interactive' ? 'ia' : 'il'}`)),
        h('div', { class: 'row-val' }, h('b', {}, num(v.hits)), h('span', {}, `${num(v.density_per_1000, 1)}/1k`))));
    }
    section.appendChild(rows);
    out.appendChild(section);
  }
  out.appendChild(about('metadiscourse'));
  return out;
}

// ---- spelling ----------------------------------------------------------------------------

function renderSpelling(r, ctx) {
  const e = r.errors;
  const out = h('div', {});
  const variantNames = { gb: 'British', us: 'American' };
  const toggle = h('div', { class: 'segmented', role: 'radiogroup', 'aria-label': 'Spelling variety' },
    ['gb', 'us'].map((v) => h('button', { type: 'button', role: 'radio', 'aria-checked': String(e.variant === v), onclick: () => v !== e.variant && ctx.setVariant(v) }, v === 'gb' ? 'UK' : 'US')));
  out.appendChild(h('div', { class: 'spell-head' }, h('span', {}, `Checked as ${variantNames[e.variant]} English`), toggle));

  const item = (x, kind) =>
    h('div', { class: `fix ${kind}` },
      h('button', { type: 'button', class: 'fix-word', onclick: () => Reader.flash(x.spans, 'spelling'), title: 'Show in text' }, x.surface, x.count > 1 ? h('span', { class: 'chip-n' }, `×${x.count}`) : null),
      h('span', { class: 'fix-arrow', 'aria-hidden': 'true' }, x.suggestions?.length ? '→' : ''),
      h('span', { class: 'fix-sugs' },
        x.suggestions?.length
          ? x.suggestions.map((s) => h('button', { type: 'button', class: 'sug', title: `Replace ${x.count > 1 ? `all ${x.count}` : ''} with “${s}” and re-analyse`, onclick: () => ctx.applyFix(x.spans, s) }, s))
          : h('span', { class: 'muted' }, kind === 'name' ? 'probably a name' : 'no suggestion')));

  if (!e.errors.length && !e.variant_mismatches.length) {
    out.appendChild(h('div', { class: 'empty-ok' }, h('b', {}, 'No spelling errors found.'), h('span', {}, `${num(e.counts.tokens_checked)} words checked against the ${variantNames[e.variant]} dictionary.`)));
  }
  if (e.errors.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, `Possible misspellings · ${num(e.counts.errors_total)}`));
    out.appendChild(h('div', { class: 'fixes' }, e.errors.map((x) => item(x, 'err'))));
  }
  if (e.variant_mismatches.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, `${e.variant === 'gb' ? 'American' : 'British'} spellings · ${num(e.counts.variant_mismatches)}`));
    out.appendChild(h('div', { class: 'fixes' }, e.variant_mismatches.map((x) => item(x, 'var'))));
  }
  if (e.unknown_names.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, `Not in the dictionary, probably names · ${num(e.counts.unknown_names)}`));
    out.appendChild(h('div', { class: 'fixes' }, e.unknown_names.map((x) => item(x, 'name'))));
  }
  if (e.errors.length) out.appendChild(h('p', { class: 'fine' }, `${num(e.rates.errors_per_100_words, 1)} errors per 100 words.`));
  out.appendChild(about('spelling'));
  return out;
}

// ---- diversity ------------------------------------------------------------------------------

function renderDiversity(r) {
  const d = r.diversity;
  const s = d.scores;
  const out = h('div', {});
  const bands = d.references?.vocd_d_bands || [];
  const hero = h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, s.mtld == null ? '–' : num(s.mtld, 0)),
    h('div', { class: 'hero-text' }, h('b', {}, 'MTLD'),
      h('span', {}, s.mtld == null ? 'Needs at least 50 words.' : `${num(d.counts.types)} different words in ${num(d.counts.tokens)}.`)));
  out.appendChild(hero);

  if (s.vocd_d != null && bands.length) {
    const max = Math.max(130, s.vocd_d + 10);
    const scale = h('div', { class: 'ref-scale' });
    bands.forEach((b, i) => scale.appendChild(h('span', { class: `ref-band b${i}`, style: { '--l': b.min / max, '--w': (b.max - b.min) / max }, title: `${b.name}: ${b.min}–${b.max}` })));
    scale.appendChild(h('span', { class: 'ref-marker', style: { '--l': s.vocd_d / max } }, h('b', {}, num(s.vocd_d, 0))));
    const where = { below: 'below this range', within: 'within this range', above: 'above this range' };
    const keys = h('div', { class: 'ref-keys' }, bands.map((b, i) =>
      h('div', { class: 'ref-key' }, h('i', { class: `sw ref-sw b${i}` }),
        h('span', { class: 'ref-key-name' }, b.name, h('span', { class: 'muted' }, ` · D ${b.min}–${b.max}`)),
        h('b', { class: `pos-${b.position}` }, where[b.position] ?? b.position))));
    out.appendChild(h('div', { class: 'ref' }, h('div', { class: 'ref-title' }, `vocd-D ${num(s.vocd_d, 1)} against published ranges`), scale, keys,
      h('div', { class: 'fine' }, 'Ranges from Durán, Malvern, Richards & Chipere (2004), Applied Linguistics 25/2.')));
  }

  const rows = h('div', { class: 'rows' });
  for (const m of DIVERSITY) {
    const v = s[m.key];
    rows.appendChild(h('div', { class: 'row' },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, m.name, m.ref ? h('span', { class: 'ref-cite' }, ` ${m.ref}`) : null), h('span', { class: 'row-note' }, m.note)),
      h('div', { class: 'row-val' }, h('b', {}, v == null ? '–' : num(v, m.d)), v == null ? h('span', {}, 'text too short') : null)));
  }
  out.appendChild(rows);
  out.appendChild(about('diversity'));
  return out;
}

// ---- statistics ------------------------------------------------------------------------------

function renderStatistics(r) {
  const st = r.statistics;
  const tg = r.tagger;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('Words', num(st.counts.tokens_excluding_numbers), `${num(st.counts.excluded_numeric_tokens)} numbers excluded`),
    stat('Different words', num(st.counts.unique_types_excluding_numbers), `TTR ${num(st.averages.type_token_ratio, 2)}`),
    stat('Sentences', num(st.counts.sentences), `${num(st.averages.tokens_per_sentence, 1)} words each`),
    stat('Syllables', num(st.counts.syllables), `${num(st.averages.syllables_per_word, 2)} per word`),
    stat('Polysyllabic', pct(st.averages.polysyllable_pct), `${num(st.counts.polysyllable_words)} words`),
    stat('Characters', num(st.counts.characters_with_spaces), `${num(st.counts.characters_without_spaces)} without spaces`),
    stat('Verbal elements', num(tg.summary.total_verbal_elements), `${num(tg.summary.verbal_elements_per_sentence, 1)} per sentence`),
    stat('Noun elements', num(tg.summary.total_noun_elements), `${num(tg.summary.noun_elements_per_sentence, 1)} per sentence`)));

  const dist = Object.entries(tg.upos_distribution).filter(([k]) => k !== 'PUNCT' && k !== 'SPACE');
  const total = dist.reduce((s, [, v]) => s + v, 0);
  const max = Math.max(1, ...dist.map(([, v]) => v));
  const rows = h('div', { class: 'rows compact' });
  dist.forEach(([k, v]) => rows.appendChild(h('div', { class: 'row' },
    h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, UPOS[k] || k)),
    h('div', { class: 'row-viz' }, meter(v, max, 'pos')),
    h('div', { class: 'row-val' }, h('b', {}, num(v)), h('span', {}, pct((v / total) * 100))))));
  out.appendChild(h('h3', { class: 'sub-h' }, 'Parts of speech'));
  out.appendChild(rows);
  if (st.excluded_digits?.length) out.appendChild(h('p', { class: 'fine' }, `Numbers excluded from word types: ${st.excluded_digits.slice(0, 20).join(', ')}${st.excluded_digits.length > 20 ? '…' : ''}`));
  out.appendChild(about('statistics'));
  return out;
}

// ---- tabs ----------------------------------------------------------------------------------------

const Panels = (() => {
  const tabsEl = $('tabs');
  const panelsEl = $('panels');
  const indicator = $('tabIndicator');
  let built = {};
  let active = 'overview';
  let ctx = null;
  let data = null;

  const LENS_TO_TAB = { cefr: ['vocabulary', 'cefr'], bnc: ['vocabulary', 'bnc'], ngsl: ['vocabulary', 'ngsl'], awl: ['vocabulary', 'awl'], phrase: ['phrase'], md: ['md'], spelling: ['spelling'] };

  function moveIndicator(btn, animate) {
    if (!btn) return;
    indicator.classList.toggle('no-anim', !animate);
    indicator.style.transform = `translateX(${btn.offsetLeft}px) scaleX(${btn.offsetWidth / 100})`;
    indicator.style.opacity = '1';
  }

  function build(id, sub) {
    const r = data.results;
    const go = (tab, s) => open(tab, { sub: s, syncLens: true, focus: true });
    switch (id) {
      case 'overview': return renderOverview(r, go);
      case 'readability': return renderReadability(r);
      case 'vocabulary': return renderVocabulary(r, ctx, sub);
      case 'phrase': return renderPhrases(r);
      case 'md': return renderMetadiscourse(r);
      case 'spelling': return renderSpelling(r, ctx);
      case 'diversity': return renderDiversity(r);
      case 'statistics': return renderStatistics(r);
    }
  }

  function open(id, { sub = null, syncLens = true, animate = true, focus = false } = {}) {
    active = id;
    tabsEl.querySelectorAll('.tab').forEach((b) => {
      const on = b.dataset.tab === id;
      b.setAttribute('aria-selected', String(on));
      b.tabIndex = on ? 0 : -1;
      if (on) {
        moveIndicator(b, animate);
        if (b.offsetLeft < tabsEl.scrollLeft || b.offsetLeft + b.offsetWidth > tabsEl.scrollLeft + tabsEl.clientWidth) tabsEl.scrollLeft = b.offsetLeft - 12;
      }
    });
    if (!built[id]) {
      const panel = h('div', { class: 'panel', role: 'tabpanel', id: `panel-${id}`, dataset: { tab: id } });
      panel.appendChild(build(id, sub));
      panelsEl.appendChild(panel);
      built[id] = panel;
      panel.classList.add('fresh');
      setTimeout(() => panel.classList.remove('fresh'), 900);
    } else if (id === 'vocabulary' && sub) {
      built[id].firstChild.selectSub(sub, { fromLens: !syncLens });
    }
    Object.values(built).forEach((p) => p.classList.toggle('active', p === built[id]));
    if (syncLens) {
      const tab = TABS.find((t) => t.id === id);
      if (tab?.lens) Reader.setLens(tab.lens);
      if (id === 'vocabulary') Reader.setLens(sub || built[id].firstChild.dataset.sub);
    }
    if (focus && window.matchMedia('(max-width: 899px)').matches) built[id].scrollIntoView({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }

  tabsEl.addEventListener('keydown', (e) => {
    const i = TABS.findIndex((t) => t.id === active);
    let j = null;
    if (e.key === 'ArrowRight') j = (i + 1) % TABS.length;
    if (e.key === 'ArrowLeft') j = (i - 1 + TABS.length) % TABS.length;
    if (e.key === 'Home') j = 0;
    if (e.key === 'End') j = TABS.length - 1;
    if (j == null) return;
    e.preventDefault();
    open(TABS[j].id, { animate: false });
    tabsEl.querySelector(`[data-tab="${TABS[j].id}"]`).focus();
  });
  function updateFade() {
    tabsEl.classList.toggle('overflow', tabsEl.scrollWidth > tabsEl.clientWidth + 1);
    tabsEl.classList.toggle('at-end', tabsEl.scrollLeft + tabsEl.clientWidth >= tabsEl.scrollWidth - 2);
  }
  tabsEl.addEventListener('scroll', updateFade, { passive: true });
  window.addEventListener('resize', () => {
    moveIndicator(tabsEl.querySelector('.tab[aria-selected="true"]'), false);
    updateFade();
  });

  return {
    render(d, context, { keepTab = false } = {}) {
      data = d;
      CURRENT = d;
      ctx = context;
      const prev = keepTab ? active : 'overview';
      const prevSub = built.vocabulary?.firstChild?.dataset.sub;
      built = {};
      panelsEl.replaceChildren();
      tabsEl.querySelectorAll('.tab').forEach((t) => t.remove());
      TABS.forEach((t) => tabsEl.appendChild(h('button', { type: 'button', role: 'tab', class: 'tab', dataset: { tab: t.id }, 'aria-controls': `panel-${t.id}`, onclick: () => open(t.id) }, t.label)));
      requestAnimationFrame(() => {
        open(prev, { sub: prevSub, syncLens: false, animate: false });
        updateFade();
      });
    },
    /** The reader's lens changed by the user: follow it. */
    followLens(lens) {
      const target = LENS_TO_TAB[lens];
      if (target) open(target[0], { sub: target[1], syncLens: false });
    },
  };
})();
