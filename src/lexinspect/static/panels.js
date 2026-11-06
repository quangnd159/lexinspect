// The analysis pane: tabs, and one renderer per tab. Panels are built lazily
// on first open, so the first paint after Analyse only builds the overview.
// Everything is rebuilt when the interface language changes (see Panels).

const TABS = [
  { id: 'overview', label: N_('Overview') },
  { id: 'adapt', label: N_('Adapt'), lens: 'adapt' },
  { id: 'vocabulary', label: N_('Vocabulary') },
  { id: 'phrase', label: N_('Phrases'), lens: 'phrase' },
  { id: 'sentences', label: N_('Sentences'), lens: 'sent', needs: 'syntax' },
  { id: 'readability', label: N_('Readability') },
  { id: 'md', label: N_('Metadiscourse'), lens: 'md' },
  { id: 'spelling', label: N_('Spelling'), lens: 'spelling' },
  { id: 'statistics', label: N_('Statistics') },
];
const VOCAB_SUBS = [
  { id: 'cefr', label: N_('CEFR'), lens: 'cefr' },
  { id: 'bnc', label: N_('Frequency'), lens: 'bnc' },
  { id: 'ngsl', label: N_('NGSL / NAWL'), lens: 'ngsl' },
  { id: 'awl', label: N_('AWL'), lens: 'awl' },
  { id: 'diversity', label: N_('Diversity') },
];

// ---- shared pieces -----------------------------------------------------------

/** Separate labels on one line: "12 hedges · 3 boosters". */
const dot = (...parts) => parts.filter(Boolean).join(' · ');

/** Whole sentences side by side in one paragraph; Japanese and Chinese run them on without a space. */
const sentences = (...parts) => parts.filter(Boolean).join(['ja', 'zh-CN'].includes(I18n.locale) ? '' : ' ');

/** A band code: 3 → "3K"; none → "25K+". */
const bandCode = (v) => (v ? `${v}K` : '25K+');

// Markup allowed in copy.js texts: bold, and italics for English example words.
const RICH = { b: (s) => h('b', {}, s), i: (s) => h('i', { lang: 'en' }, s) };
const rich = (text) => tr(text, null, RICH);

function about(key) {
  const info = SECTION_INFO[key];
  if (!info) return null;
  return h('details', { class: 'about' },
    h('summary', {}, icon('chevron-right', { size: 14 }), t('About this measure')),
    h('div', { class: 'about-body' },
      h('p', {}, rich(info.about)),
      info.caveats.length ? h('ul', {}, info.caveats.map((c) => h('li', {}, rich(c)))) : null));
}

function stat(label, value, sub) {
  return h('div', { class: 'stat' }, h('span', { class: 'stat-label' }, label), h('span', { class: 'stat-value' }, value), sub ? h('span', { class: 'stat-sub' }, sub) : null);
}

function callout(kind, title, items) {
  return h('div', { class: `callout ${kind}`, role: kind === 'warn' ? 'note' : null },
    h('b', {}, title), items?.length ? h('ul', {}, items.map((item) => h('li', {}, item))) : null);
}

/** Radio-group keys (WAI-ARIA): arrows and Home/End move and select, and only
 *  the checked radio is in the tab order. Works on radios added later too. */
function radioKeys(group) {
  const radios = () => [...group.querySelectorAll('[role="radio"]')].filter((b) => !b.disabled);
  const sync = () => {
    const all = radios();
    const on = all.find((b) => b.getAttribute('aria-checked') === 'true') ?? all[0];
    all.forEach((b) => (b.tabIndex = b === on ? 0 : -1));
  };
  group.addEventListener('keydown', (e) => {
    const all = radios();
    const i = all.indexOf(document.activeElement);
    if (i < 0) return;
    const rtl = getComputedStyle(group).direction === 'rtl';
    const next = rtl ? 'ArrowLeft' : 'ArrowRight';
    const prev = rtl ? 'ArrowRight' : 'ArrowLeft';
    let j = null;
    if (e.key === next || e.key === 'ArrowDown') j = (i + 1) % all.length;
    else if (e.key === prev || e.key === 'ArrowUp') j = (i - 1 + all.length) % all.length;
    else if (e.key === 'Home') j = 0;
    else if (e.key === 'End') j = all.length - 1;
    if (j == null) return;
    e.preventDefault();
    all[j].focus();
    if (all[j].getAttribute('aria-checked') !== 'true') all[j].click();
  });
  new MutationObserver(sync).observe(group, { subtree: true, childList: true, attributes: true, attributeFilter: ['aria-checked', 'disabled'] });
  sync();
  return group;
}

/** Word chips; clicking one flashes its occurrences in the reader. */
function chips(list, { lens, limit = 40, label = (x) => x.word, count = (x) => x.count, spans } = {}) {
  const wrap = h('div', { class: 'chips' });
  const make = (x) =>
    h('button', { type: 'button', class: 'chip', onclick: () => Reader.flash(spans ? spans(x) : spansOfWord(label(x)), lens) },
      en(label(x)), count(x) > 1 ? h('span', { class: 'chip-n' }, `×${num(count(x))}`) : null);
  list.slice(0, limit).forEach((x) => wrap.appendChild(make(x)));
  if (list.length > limit) {
    const more = h('button', { type: 'button', class: 'chip more' }, tn(list.length - limit, '+{n} more', '+{n} more'));
    more.addEventListener('click', () => {
      list.slice(limit).forEach((x) => wrap.insertBefore(make(x), more));
      more.remove();
    });
    wrap.appendChild(more);
  }
  if (!list.length) wrap.appendChild(h('span', { class: 'muted' }, t('None')));
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

/** "B1: 12%", for legends, tooltips and accessible names. */
const share = (label, value) => t('{label}: {pct}', { label, pct: value });

/** Stacked horizontal bar from [{key, value, label}] with a legend underneath. */
function stack(parts, { lens, total } = {}) {
  const sum = total ?? parts.reduce((s, p) => s + p.value, 0);
  const bar = h('div', { class: 'stack', role: 'img', 'aria-label': listOf(parts.map((p) => share(p.label, pct((p.value / sum) * 100))), 'unit') });
  const keys = h('div', { class: 'stack-keys' });
  parts.forEach((p) => {
    if (!p.value) return;
    const part = sum ? (p.value / sum) * 100 : 0;
    bar.appendChild(h('span', { class: `seg ${lens}-${p.key}`, style: { flexGrow: String(p.value) }, title: share(p.label, pct(part)) }));
    keys.appendChild(
      h('button', { type: 'button', class: 'stack-key', onclick: lens && p.focus !== false ? () => Reader.focus(lens, p.key) : null, disabled: !lens || p.focus === false },
        h('i', { class: `sw ${lens}-${p.key}` }), p.label, h('b', {}, pct(part, part < 10 ? 1 : 0))));
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

/** "Readers' level" picker: one control, used wherever a target matters. */
function targetPicker(label = t('Readers')) {
  const wrap = h('div', { class: 'target-picker' });
  const group = h('div', { class: 'segmented small', role: 'radiogroup', 'aria-label': t('Readers’ CEFR level') });
  const opts = [['', t('Any')], ...Prefs.TARGETS.map((l) => [l, l])];
  for (const [v, text] of opts) {
    group.appendChild(h('button', {
      type: 'button',
      role: 'radio',
      'aria-checked': String((Prefs.target ?? '') === v),
      title: v ? t('Profile this text for {level} readers', { level: v }) : t('No target level'),
      onclick: () => Prefs.setTarget(v || null),
    }, text));
  }
  radioKeys(group);
  wrap.append(h('span', { class: 'target-label' }, label), group);
  return wrap;
}

// The level model's features (level.py FEATURES), named so each reads in the
// middle of a sentence. `vars` fill placeholders; numbers are formatted at use.
const LEVEL_FEATURES = {
  ...Object.fromEntries(['A1', 'A2', 'B1', 'B2', 'C1'].map((lv) => [`cefr_above_${lv}_pct`,
    { label: N_('the share of words above {level} (CEFR-J and Octanove)'), vars: { level: lv }, unit: '%' }])),
  cefr_off_list_pct: { label: N_('the share of words not on the CEFR lists'), unit: '%' },
  cefr_proper_noun_pct: { label: N_('the share of names'), unit: '%' },
  ...Object.fromEntries([1, 2, 3, 4, 5, 10].map((k) => [`bnc_beyond_${k}k_pct`,
    { label: N_('the share of words beyond the first {families} BNC/COCA word families'), vars: { families: k * 1000 }, unit: '%' }])),
  bnc_off_list_pct: { label: N_('the share of words on no BNC/COCA list'), unit: '%' },
  ...Object.fromEntries([1, 2, 3, 4, 5, 10].map((k) => [`phrase_beyond_${k}k_pct`,
    { label: N_('the share of words beyond the first {families} word families when PHRASE List expressions count as units'), vars: { families: k * 1000 }, unit: '%' }])),
  words_per_sentence: { label: N_('the average sentence length'), unit: 'words' },
  syllables_per_word: { label: N_('the average word length in syllables'), unit: 'syllables' },
  characters_per_word: { label: N_('the average word length in letters'), unit: 'letters' },
  polysyllable_pct: { label: N_('the share of words with three or more syllables'), unit: '%' },
  dale_chall_difficult_pct: { label: N_('the share of words not on the Dale–Chall list of familiar words'), unit: '%' },
  mtld: { label: N_('the variety of words (MTLD)'), unit: '', d: 1 },
  mattr: { label: N_('the variety of words (MATTR)'), unit: '', d: 3 },
  awl_pct: { label: N_('the share of words from the Academic Word List'), unit: '%' },
  outside_ngsl_pct: { label: N_('the share of words outside the New General Service List'), unit: '%' },
  outside_ngsl_nawl_pct: { label: N_('the share of words outside both the NGSL and the New Academic Word List'), unit: '%' },
  ngsl_off_list_pct: { label: N_('the share of words on neither the NGSL nor the NAWL (names excluded)'), unit: '%' },
};
const LEVEL_MIN_WORDS = 100; // level.py: the model's min_words
const LEVEL_MODULES = ['readability', 'diversity', 'awl', 'bnc_coca', 'ngsl', 'phrase', 'cefr'];

function featureName(key, fallback) {
  const f = LEVEL_FEATURES[key];
  if (!f) return fallback ?? key;
  const vars = Object.fromEntries(Object.entries(f.vars ?? {}).map(([k, v]) => [k, typeof v === 'number' ? num(v) : v]));
  return t(f.label, vars);
}

function featureValue(key, v) {
  const f = LEVEL_FEATURES[key];
  const value = num(v, f?.d ?? 1);
  switch (f?.unit) {
    case '%': return pct(v, 1);
    case 'words': return t('{value} words', { value });
    case 'syllables': return t('{value} syllables', { value });
    case 'letters': return t('{value} letters', { value });
    default: return value;
  }
}

/** One reason for the estimate, from a contribution's feature, value and direction. */
function contributionText(c) {
  const measure = featureName(c.feature, c.label);
  const up = c.direction === 'up';
  if (c.value == null) {
    return up
      ? t('The model had no value for {measure} and used the training median, which raises the estimate.', { measure })
      : t('The model had no value for {measure} and used the training median, which lowers the estimate.', { measure });
  }
  const vars = { measure, value: featureValue(c.feature, c.value), typical: featureValue(c.feature, c.typical) };
  const high = c.value > c.typical;
  if (up) {
    return high
      ? t('The estimate goes up because {measure} is higher than in a typical training passage ({value}, against {typical}).', vars)
      : t('The estimate goes up because {measure} is lower than in a typical training passage ({value}, against {typical}).', vars);
  }
  return high
    ? t('The estimate goes down because {measure} is higher than in a typical training passage ({value}, against {typical}).', vars)
    : t('The estimate goes down because {measure} is lower than in a typical training passage ({value}, against {typical}).', vars);
}

function confidenceText(conf, range) {
  if (conf.label === 'high') return t('Most of the probability ({pct}) is on one level.', { pct: pct(conf.top_probability * 100, 0) });
  if (conf.label === 'moderate') return t('The text sits between two adjacent levels.');
  return tn(range?.length ?? 3, 'The probability is spread over {n} level, so treat the level as a rough guide.', 'The probability is spread over {n} levels, so treat the level as a rough guide.');
}

function levelNotApplicable(r) {
  if (LEVEL_MODULES.some((m) => !r[m])) return t('Not available for this text.');
  const words = r.readability.counts.words;
  if (words < LEVEL_MIN_WORDS) {
    return tn(words, 'This text has {n} word. The estimate needs at least {min} words: in shorter texts, one or two words decide the level.', 'This text has {n} words. The estimate needs at least {min} words: in shorter texts, one or two words decide the level.', { min: num(LEVEL_MIN_WORDS) });
  }
  return t('This text has too few different words to compare with graded reading passages.');
}

function levelEstimate(r) {
  const L = r.level;
  if (!L) return null;
  if (!L.applicable) {
    return h('div', { class: 'level-card muted-card' },
      h('span', { class: 'card-title' }, t('Estimated reading level')),
      h('span', { class: 'level-na' }, levelNotApplicable(r)));
  }
  const p = L.probabilities;
  const max = Math.max(...LEVELS.map((l) => p[l]));
  const probs = h('div', { class: 'level-probs', role: 'img', 'aria-label': t('Probability by level: {list}', { list: listOf(LEVELS.map((l) => share(l, pct(p[l] * 100, 0))), 'unit') }) },
    LEVELS.map((l) => h('div', { class: `lp${L.range?.includes(l) ? ' in' : ''}${l === L.level ? ' top' : ''}`, title: share(l, pct(p[l] * 100, 0)) },
      h('span', { class: 'lp-bar' }, h('span', { class: 'lp-fill', style: { '--v': max ? p[l] / max : 0 } })),
      h('span', { class: 'lp-label' }, l))));
  const range = L.range?.length > 1 ? `${L.range[0]}–${L.range[L.range.length - 1]}` : null;
  const top = pct(p[L.level] * 100, 0);
  const why = (L.contributions || []).slice(0, 2).map(contributionText);
  const ev = L.evaluation;
  const conf = L.confidence;
  const beyond = conf?.beyond_training_features ?? [];
  return h('div', { class: 'level-card' },
    h('div', { class: 'level-main' },
      h('span', { class: 'card-title' }, t('Estimated reading level')),
      h('span', { class: 'level-value' }, range ?? L.level,
        h('small', {}, range ? t('most likely {level} ({pct})', { level: L.level, pct: top }) : t('{pct} likely', { pct: top })))),
    probs,
    why.length ? h('ul', { class: 'level-why' }, why.map((line) => h('li', {}, line))) : null,
    h('details', { class: 'about level-about' },
      h('summary', {}, icon('chevron-right', { size: 14 }), t('How accurate is this?')),
      h('div', { class: 'about-body' },
        ev?.held_out_within_one != null
          ? h('p', {}, t('On {texts} exam and graded reading passages left out of training (5-fold cross-validation), the estimate was within one level of the published level {within} of the time and exactly right {exact} of the time. Its range contained the published level {range} of the time.', {
            texts: num(ev.n_texts),
            within: pct(ev.held_out_within_one * 100, 0),
            exact: pct(ev.held_out_exact * 100, 0),
            range: pct(ev.range_contains_true_level * 100, 0),
          }))
          : null,
        ev?.cross_dataset_within_one_worst != null
          ? h('p', {}, t('Trained on one collection and tested on the other, it was within one level {pct} of the time at worst.', { pct: pct(ev.cross_dataset_within_one_worst * 100, 0) }))
          : null,
        beyond.length
          ? h('p', {}, sentences(
            confidenceText(conf, L.range),
            t('On {measures}, this text goes beyond almost every training passage, so the estimate is an extrapolation.', { measures: listOf(beyond.map((k) => featureName(k))) })))
          : null,
        h('p', {}, t('Calibrated on Cambridge English exam passages and ELG-CEFR-EN graded texts. It describes reading material written or chosen for learners; don’t use it to grade a learner’s writing.')))));
}

function insightList(r, go) {
  const items = Insights.compute(r, {
    target: Prefs.target,
    go,
    flash: (spans, lens) => Reader.flash(spans, lens),
    spansOfWord,
  });
  if (!items.length) return null;
  return h('section', { class: 'insights', 'aria-label': t('What stands out') },
    h('h3', { class: 'sub-h' }, t('What stands out')),
    h('ul', {}, items.map((x) =>
      h('li', { class: `insight ${x.tone}` },
        h('span', { class: 'insight-dot', 'aria-hidden': 'true' }),
        h('div', { class: 'insight-body' },
          h('b', {}, x.title),
          h('p', {}, x.body),
          x.action ? h('button', { type: 'button', class: 'link-btn', onclick: x.action.run }, x.action.label, icon('arrow-right', { size: 14 })) : null)))));
}

/** What changed since the previous version of this text. */
function changesStrip(changes, ctx) {
  if (!changes?.length) return null;
  const rows = changes.slice(0, 8).map((c) => {
    const vars = { before: Metrics.format(c, c.before, c.beforeText), after: Metrics.format(c, c.after, c.afterText) };
    const spoken = c.dir === 'easier' ? t('From {before} to {after}, easier.', vars) : c.dir === 'harder' ? t('From {before} to {after}, harder.', vars) : t('From {before} to {after}.', vars);
    return h('div', { class: `chg ${c.dir ?? ''}` },
      h('span', { class: 'chg-label' }, c.label),
      h('span', { class: 'chg-vals', 'aria-hidden': 'true' },
        h('span', { class: 'chg-before' }, vars.before),
        h('span', { class: 'chg-arrow' }, icon('arrow-right', { size: 12 })),
        h('b', {}, vars.after),
        c.dir ? h('span', { class: 'chg-arrow chg-dir' }, c.dir === 'easier' ? t('easier') : t('harder')) : null),
      h('span', { class: 'sr-only' }, spoken));
  });
  return h('section', { class: 'changes', 'aria-label': t('Since the original version') },
    h('div', { class: 'changes-head' },
      h('h3', { class: 'sub-h' }, t('Since the original version')),
      h('span', { class: 'changes-key', 'aria-hidden': 'true' }, h('i', { class: 'easier' }), t('easier'), h('i', { class: 'harder' }), t('harder')),
      h('button', { type: 'button', class: 'link-btn', onclick: () => ctx.dropComparison(), title: t('Compare later edits with this version instead') }, t('Reset'))),
    h('div', { class: 'chg-grid' }, rows));
}

function spellingCard(e, card) {
  const issues = e.counts.errors_total;
  const mismatches = e.counts.variant_mismatches;
  const gb = e.variant === 'gb';
  const checked = gb ? t('Checked as British English') : t('Checked as American English');
  // Spellings of the other variety: "US spellings" when checking as British.
  const other = (n) => (gb ? tn(n, '{n} US spelling', '{n} US spellings') : tn(n, '{n} UK spelling', '{n} UK spellings'));
  if (issues) {
    return card('spelling', null, t('Spelling'), num(issues), tn(issues, 'issue', 'issues'),
      dot(tn(e.counts.unique_errors, '{n} distinct word', '{n} distinct words'), mismatches ? other(mismatches) : null));
  }
  if (mismatches) {
    return card('spelling', null, t('Spelling'), num(mismatches), gb ? tn(mismatches, 'US spelling', 'US spellings') : tn(mismatches, 'UK spelling', 'UK spellings'),
      gb ? t('No misspellings · checked as British English') : t('No misspellings · checked as American English'));
  }
  return card('spelling', null, t('Spelling'), t('Clean'), null, checked);
}

function renderOverview(r, go, ctx) {
  const rd = r.readability;
  const grade = rd.scores.text_standard;
  const ease = rd.scores.flesch_reading_ease;
  const easeLabel = t(EASE_BANDS.find(([lo]) => ease >= lo)[1]);
  const b95 = bandFor(r.bnc_coca.per_band, 95);
  const b98 = bandFor(r.bnc_coca.per_band, 98);
  const ip = r.phrase?.integrated_profile;
  const p95 = ip?.counts.phrase_tokens ? bandFor(ip.per_band, 95) : b95;
  const div = r.diversity.scores;
  const md = r.metadiscourse;
  const target = Prefs.target;
  const pct95 = pct(95, 0);
  const pct98 = pct(98, 0);

  const card = (tab, sub, title, value, unit, detail, extra) =>
    h('button', { type: 'button', class: 'card', onclick: () => go(tab, sub) },
      h('span', { class: 'card-title' }, title),
      h('span', { class: 'card-value' }, value, unit ? h('small', {}, unit) : null),
      h('span', { class: 'card-detail' }, detail),
      extra || null);

  const levelBar = h('span', { class: 'mini-levels', 'aria-hidden': 'true' },
    LEVELS.map((l) => h('i', { class: `cefr-${l}`, style: { flexGrow: String(r.cefr.per_level[l].tokens || 0) } })));

  const head = h('div', { class: 'ov-head' },
    stat(t('Words'), num(rd.counts.words)),
    stat(t('Sentences'), num(rd.counts.sentences)),
    stat(t('Reading time'), duration(rd.counts.reading_time_seconds)),
    stat(t('Words per sentence'), num(rd.averages.words_per_sentence, 1)));

  // Vocabulary for the readers' level, or the B2+ share when none is set.
  const known = target ? Insights.knownAt(r, target) : null;
  const fit = target ? Insights.fit(known) : null;
  const vocabCard = target
    ? card('adapt', null, t('Words for {level} readers', { level: target }), pct(known), null,
      fit ? dot(fit.label, t('{pct} above {level} or not listed', { pct: pct(Math.max(0, 100 - known)), level: target })) : '', levelBar)
    : card('vocabulary', 'cefr', t('Vocabulary level'), r.cefr.highest_level_present ?? '–', t('highest'), t('{pct} of words at B2 or above', { pct: pct(b2plus(r.cefr)) }), levelBar);
  if (fit) vocabCard.classList.add(`fit-${fit.key}`);

  const syn = r.syntax;
  const longest = syn?.sentences?.length ? syn.sentences.reduce((a, b) => (b.words > a.words ? b : a)) : null;
  const hits = r.phrase.counts.total_hits;

  let bncDetail;
  if (p95 && b95 && p95 !== b95) bncDetail = dot(t('{band} counting phrases', { band: bandCode(p95) }), b98 ? t('{band} for {pct}', { band: bandCode(b98), pct: pct98 }) : t('{pct} not reached', { pct: pct98 }));
  else if (b98) bncDetail = t('{band} word families for {pct} coverage', { band: bandCode(b98), pct: pct98 });
  else bncDetail = tn(r.bnc_coca.counts.off_list_tokens, '{pct} not reached: {n} word on no list', '{pct} not reached: {n} words on no list', { pct: pct98 });

  const cards = h('div', { class: 'cards' },
    card('readability', null, t('Readability'), grade == null ? '–' : num(grade, 1), t('grade'),
      t('{school} · Flesch {score} ({band})', { school: gradeLabel(grade), score: num(ease), band: easeLabel }),
      rd.reliability.reliable ? null : h('span', { class: 'card-flag' }, t('Short text: indicative only'))),
    vocabCard,
    card('vocabulary', 'bnc', t('Vocabulary needed'), bandCode(b95), t('for {pct}', { pct: pct95 }), bncDetail),
    card('phrase', null, t('Phrases'), num(hits), tn(hits, 'expression', 'expressions'),
      hits ? t('{count} per 1,000 words · from the PHRASE List', { count: num(r.phrase.counts.hits_per_1000_words, 0) }) : t('None from the PHRASE List')),
    syn?.indices
      ? card('sentences', null, t('Sentences'), num(syn.indices.mlt, 1), t('words per T-unit'),
        dot(t('{count} clauses per sentence', { count: num(syn.indices.c_s, 2) }), longest ? tn(longest.words, 'longest {n} word', 'longest {n} words') : null))
      : null,
    card('vocabulary', 'diversity', t('Lexical diversity'), div.mtld == null ? '–' : num(div.mtld, 0), 'MTLD',
      div.vocd_d == null ? t('vocd-D needs more than 50 words, not counting numbers') : `vocd-D ${num(div.vocd_d, 0)}`),
    card('vocabulary', 'awl', t('Academic words'), pct(r.awl.coverage_pct), 'AWL',
      dot(tn(r.awl.counts.awl_families, '{n} family', '{n} families'), 'NAWL ' + pct(r.ngsl.coverage_pct.nawl))),
    card('md', null, t('Metadiscourse'), num(md.density_per_1000, 0), t('per 1,000 words'),
      dot(tn(md.per_category.hedges.hits, '{n} hedge', '{n} hedges'), tn(md.per_category.boosters.hits, '{n} booster', '{n} boosters'))),
    spellingCard(r.errors, card));

  return h('div', {},
    h('div', { class: 'ov-top' }, head, targetPicker()),
    changesStrip(CURRENT.changes, ctx),
    levelEstimate(r),
    insightList(r, go),
    h('h3', { class: 'sub-h' }, t('Profile')),
    cards);
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

/** The Dale–Chall grade band for a raw score. */
function daleGrade(raw) {
  if (raw < 5) return t('grade 4 or below');
  for (const [ceil, from, to] of [[6, 5, 6], [7, 7, 8], [8, 9, 10], [9, 11, 12], [10, 13, 15]]) if (raw < ceil) return t('grades {from}–{to}', { from: num(from), to: num(to) });
  return t('grade 16 or above');
}

/** Why the scores of a short text are fragile (readability.py's notes, composed here). */
function readabilityNotes(c) {
  if (!c.words) return [t('There are no words to measure.')];
  const notes = [];
  if (c.words < 100) {
    notes.push(tn(c.words, 'Only {n} word. The formulas were fitted on passages of {min} words or more; in a text this short, one long word or sentence moves every score.', 'Only {n} words. The formulas were fitted on passages of {min} words or more; in a text this short, one long word or sentence moves every score.', { min: num(100) }));
  }
  if (c.sentences < 30) {
    notes.push(tn(c.sentences, 'SMOG was normed on samples of {min} sentences. This text has {n} sentence, so its SMOG score is extrapolated.', 'SMOG was normed on samples of {min} sentences. This text has {n} sentences, so its SMOG score is extrapolated.', { min: num(30) }));
  }
  return notes;
}

function renderReadability(r) {
  const rd = r.readability;
  const s = rd.scores;
  const out = h('div', {});
  const grade = s.text_standard == null ? '–' : num(s.text_standard, 1);
  out.appendChild(h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, grade),
    h('div', { class: 'hero-text' }, h('b', {}, t('Grade {grade} · {school}', { grade, school: gradeLabel(s.text_standard) })),
      h('span', {}, t('The median of the eight formulas. Roughly the reader’s age minus five.')))));
  if (!rd.reliability.reliable) out.appendChild(callout('warn', t('Read these scores with care'), readabilityNotes(rd.counts)));
  out.appendChild(callout('info', t('A rough guide, not a measurement'), [
    t('These formulas use surface features such as word and sentence length. Against teachers’ rankings of 4,724 school texts, they explain about a quarter to a third of the differences in difficulty (Crossley et al. 2023).'),
    t('They were normed on US native-speaker readers, and the evidence for language learners is thinner. For learners, check the vocabulary profile too.'),
  ]));

  out.appendChild(h('h3', { class: 'sub-h' }, t('Each formula’s grade, on one scale: longer bars mean harder text')));
  const list = h('div', { class: 'rows' });
  for (const f of FORMULAS) {
    const v = s[f.key];
    let value;
    let bar;
    let sub;
    if (f.kind === 'ease') {
      value = num(v, 0);
      bar = meter(fleschGradeNum(v), 20, 'grade');
      sub = t(EASE_BANDS.find(([lo]) => v >= lo)[1]);
    } else if (f.kind === 'dale') {
      value = num(v, 1);
      bar = meter(daleGradeNum(v), 20, 'grade');
      sub = daleGrade(v);
    } else {
      value = num(v, 1);
      bar = meter(v, 20, 'grade');
      sub = gradeLabel(v);
    }
    list.appendChild(h('div', { class: 'row' },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, t(f.name)), h('span', { class: 'row-note' }, t(f.note))),
      h('div', { class: 'row-viz' }, bar),
      h('div', { class: 'row-val' }, h('b', {}, value), h('span', {}, sub))));
  }
  out.appendChild(list);

  const c = rd.counts;
  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Syllables'), num(c.syllables), t('{count} per word', { count: num(rd.averages.syllables_per_word, 2) })),
    stat(t('Polysyllables'), num(c.polysyllable_words), t('three or more syllables')),
    stat(t('Long words'), num(c.long_words), t('seven or more letters')),
    stat(t('Unfamiliar words'), num(c.difficult_words), t('not on the Dale–Chall list')),
    stat(t('Characters'), num(c.characters), t('{count} per word', { count: num(rd.averages.characters_per_word, 1) })),
    stat(t('Reading time'), duration(c.reading_time_seconds), t('at {count} words per minute', { count: num(238) }))));
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
    { key: 'off', label: t('Not listed'), value: c.counts.off_list_tokens },
    { key: 'proper', label: t('Names'), value: c.counts.proper_noun_tokens },
  ], { lens: 'cefr', total: n }));

  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Highest level'), c.highest_level_present ?? '–'),
    stat(t('B2 and above'), pct(b2plus(c))),
    c.estimate_reliability && !c.estimate_reliability.reliable
      ? stat(t('Level for 95% coverage'), '–', t('needs at least 50 words'))
      : stat(t('Level for 95% coverage'), c.estimated_level_95th ?? t('beyond the C2 lists'), t('a rough guide: within one level for most graded reading texts, and not a proficiency rating')),
    stat(t('On the lists'), pct(c.coverage_pct), tn(n, '{count} of {n} word', '{count} of {n} words', { count: num(c.counts.on_list_tokens) }))));

  for (const l of [...LEVELS].reverse()) {
    const words = c.words_by_level[l];
    if (!words.length) continue;
    out.appendChild(h('div', { class: 'level' },
      h('button', { type: 'button', class: 'level-head', onclick: () => Reader.focus('cefr', l) },
        h('span', { class: `badge cefr-${l}` }, l),
        h('span', {}, tn(c.per_level[l].tokens, '{n} word · {pct}', '{n} words · {pct}', { pct: pct(c.per_level[l].coverage_pct) }))),
      chips(words, { lens: 'cefr', limit: l === 'A1' ? 24 : 40, spans: (x) => spansOfWord(x.word, (row) => row[2] === l) })));
  }
  if (c.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge cefr-off', 'aria-hidden': 'true' }, '?'), t('Not on the CEFR lists')), chips(c.off_list, { lens: 'cefr' })));
  if (c.proper_nouns.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge cefr-proper', 'aria-hidden': 'true' }, 'N'), t('Names')), chips(c.proper_nouns, { lens: 'cefr', label: asName })));
  if (c.counts.pos_fallback_tokens) {
    out.appendChild(h('p', { class: 'fine' }, tn(c.counts.pos_fallback_tokens, '{n} word is used as a part of speech the lists give no level for; its lowest listed level was used.', '{n} words are used as parts of speech the lists give no level for; their lowest listed level was used.')));
  }
  if (ctx.cefrLevelAvailable) out.appendChild(cefrClassifier(ctx));
  out.appendChild(about('cefr'));
  return out;
}

function cefrClassifier(ctx) {
  const box = h('div', { class: 'callout' }, h('b', {}, t('Text-level estimate')),
    h('p', {}, t('Experimental. A ModernBERT classifier trained on the UniversalCEFR corpus predicts one level for the whole text. On short conversational passages outside its training data it was exact only 22% of the time and rated most B1–C2 texts too low (lexinspect’s CEFR benchmark). Not a placement test.')));
  const btn = h('button', { type: 'button', class: 'btn small' }, t('Run classifier'));
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = t('Running…');
    try {
      const res = await ctx.cefrLevel();
      box.replaceChildren(h('b', {}, t('Estimated level: {level}', { level: res.level ?? res.predicted_level ?? '–' })), h('p', {}, t('Combine it with the vocabulary profile and readability before reporting a level.')));
    } catch (err) {
      btn.disabled = false;
      btn.textContent = t('Run classifier');
      toast(err.message);
    }
  });
  box.appendChild(btn);
  return box;
}

let BNC_WITH_PHRASES = false; // the Frequency tab's view, kept across analyses

function renderBnc(r) {
  const ip = r.phrase?.integrated_profile;
  if (!ip?.counts.phrase_tokens) return bncView(r.bnc_coca, null);
  const out = h('div', {});
  const nav = h('div', { class: 'subnav segmented', role: 'radiogroup', 'aria-label': t('What to count') });
  const body = h('div', {});
  const views = {};
  const select = (withPhrases) => {
    BNC_WITH_PHRASES = withPhrases;
    nav.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.phrases === String(withPhrases))));
    views[withPhrases] ??= bncView(withPhrases ? { ...r.bnc_coca, ...ip } : r.bnc_coca, phraseUnitsNote(r.bnc_coca, ip, withPhrases));
    body.replaceChildren(views[withPhrases]);
  };
  [[false, t('Single words')], [true, t('Words and phrases')]].forEach(([v, label]) =>
    nav.appendChild(h('button', { type: 'button', role: 'radio', dataset: { phrases: String(v) }, onclick: () => select(v) }, label)));
  radioKeys(nav);
  out.append(nav, body);
  select(BNC_WITH_PHRASES);
  return out;
}

/** What counting PHRASE expressions as units changes. */
function phraseUnitsNote(b, ip, withPhrases) {
  const n = ip.counts.phrase_tokens;
  const shift = (threshold) => {
    const w = bandFor(b.per_band, threshold);
    const p = bandFor(ip.per_band, threshold);
    const vars = { threshold: pct(threshold, 0), words: bandCode(w), phrases: bandCode(p), band: bandCode(w) };
    return w === p ? t('{threshold} coverage: {band} either way.', vars) : t('{threshold} coverage: {words} for words alone, {phrases} with phrases.', vars);
  };
  const k1 = (x) => pct(x.per_band['1'].cumulative_coverage_with_supplementary_pct);
  const lead = withPhrases
    ? tn(n, 'The {n} word inside PHRASE List expressions counts at the expression’s band ({raised} higher than its own band, {lowered} lower).', 'The {n} words inside PHRASE List expressions count at each expression’s band ({raised} higher than their own band, {lowered} lower).', { raised: num(ip.counts.raised_tokens), lowered: num(ip.counts.lowered_tokens) })
    : tn(n, 'With phrases, the {n} word inside PHRASE List expressions counts at the expression’s band.', 'With phrases, the {n} words inside PHRASE List expressions count at each expression’s band.');
  return sentences(lead, shift(95), shift(98), t('1K coverage: {words} for words alone, {phrases} with phrases.', { words: k1(b), phrases: k1(ip) }));
}

function bncView(b, note) {
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
    { key: 'supp', label: t('Supplementary'), value: b.counts.supplementary_tokens },
    { key: 'proper', label: t('Names'), value: b.counts.proper_noun_tokens },
    { key: 'off', label: t('Off-list'), value: b.counts.off_list_tokens },
  ], { lens: 'bnc', total: n }));

  const b95 = bandFor(b.per_band, 95);
  const b98 = bandFor(b.per_band, 98);
  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('{pct} coverage', { pct: pct(95, 0) }), bandCode(b95), t('minimal for comprehension')),
    stat(t('{pct} coverage', { pct: pct(98, 0) }), bandCode(b98), t('optimal for comprehension')),
    stat(t('In the 25 bands'), pct(b.coverage_pct), t('{pct} with names and supplementary lists', { pct: pct(b.coverage_with_supplementary_pct) })),
    stat(t('Off-list'), num(b.counts.off_list_tokens), tn(b.counts.off_list_tokens, 'word on no list', 'words on no list'))));
  if (note) out.appendChild(h('p', { class: 'fine' }, note));

  // Coverage curve, one bar per band up to the last band used. The axis starts
  // near the 1K value rather than at 0: the decisions (95%, 98%) are made in the
  // top few points, which a 0–100 axis flattens into one line.
  // The floor drops in steps of 10 when the 1K band alone covers less than 70%.
  const first = b.per_band['1']?.cumulative_coverage_with_supplementary_pct ?? 100;
  const FLOOR = Math.max(0, Math.min(70, Math.floor((first - 4) / 10) * 10));
  const y = (v) => Math.max(0, Math.min(1, (v - FLOOR) / (100 - FLOOR)));
  const last = Math.max(3, ...used.map((x) => x.band));
  const curve = h('div', { class: 'curve', role: 'img', 'aria-label': t('Cumulative coverage by band') });
  let prev = b.counts.content_tokens ? ((b.counts.supplementary_tokens + b.counts.proper_noun_tokens) / n) * 100 : 0;
  bands.filter((x) => x.band <= last).forEach((x) => {
    const cum = x.cumulative_coverage_with_supplementary_pct;
    const vars = { band: bandCode(x.band), pct: pct(x.coverage_pct), cumulative: pct(cum), phrases: num(x.phrase_tokens) };
    const title = x.phrase_tokens
      ? tn(x.tokens, '{band}: {n} word ({pct}), {phrases} of them in expressions; cumulative {cumulative}', '{band}: {n} words ({pct}), {phrases} of them in expressions; cumulative {cumulative}', vars)
      : tn(x.tokens, '{band}: {n} word ({pct}); cumulative {cumulative}', '{band}: {n} words ({pct}); cumulative {cumulative}', vars);
    curve.appendChild(h('div', { class: 'curve-col', title },
      h('span', { class: 'curve-track' },
        h('span', { class: 'curve-bar', style: { height: `${y(cum) * 100}%` } }),
        h('span', { class: 'curve-own', style: { bottom: `${y(prev) * 100}%`, height: `${(y(cum) - y(prev)) * 100}%` } })),
      h('span', { class: 'curve-label' }, String(x.band))));
    prev = cum;
  });
  out.appendChild(h('div', { class: 'curve-wrap' },
    h('div', { class: 'curve-lines' }, h('span', { style: { '--y': y(95) } }, pct(95, 0)), h('span', { style: { '--y': y(98) } }, pct(98, 0))),
    curve,
    h('div', { class: 'curve-axis' }, t('Cumulative coverage by band of 1,000 word families, on an axis from {floor} to {top}. The dark slice is each band’s own share. Names and the supplementary lists count as known.', { floor: pct(FLOOR, 0), top: pct(100, 0) }))));

  if (b.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, t('Off-list words')), chips(b.off_list, { lens: 'bnc' })));
  if (b.proper_nouns.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, t('Names')), chips(b.proper_nouns, { lens: 'bnc', label: asName })));
  const supp = Object.entries(b.supplementary);
  if (supp.length) {
    const names = {
      proper_names: (v) => tn(v, '{n} proper name', '{n} proper names'),
      marginal_words: (v) => tn(v, '{n} marginal word', '{n} marginal words'),
      transparent_compounds: (v) => tn(v, '{n} transparent compound', '{n} transparent compounds'),
      acronyms: (v) => tn(v, '{n} acronym', '{n} acronyms'),
      abbreviations: (v) => tn(v, '{n} abbreviation', '{n} abbreviations'),
    };
    const items = supp.map(([k, v]) => (names[k] ? names[k](v) : `${num(v)} ${k.replace(/_/g, ' ')}`));
    out.appendChild(h('p', { class: 'fine' }, t('Supplementary lists: {list}.', { list: listOf(items) })));
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
    { key: 'proper', label: t('Names'), value: g.counts.proper_noun_tokens },
    { key: 'off', label: t('Off-list'), value: g.counts.off_list_tokens },
  ], { lens: 'ngsl', total: g.counts.content_tokens }));
  out.appendChild(h('div', { class: 'stats-grid' },
    stat('NGSL', pct(g.coverage_pct.ngsl), tn(g.counts.ngsl_lemmas, '{n} lemma', '{n} lemmas')),
    stat('NAWL', pct(g.coverage_pct.nawl), tn(g.counts.nawl_lemmas, '{n} lemma', '{n} lemmas')),
    stat(t('NGSL and NAWL together'), pct(g.coverage_pct.ngsl_plus_nawl)),
    stat(t('Off-list'), pct(g.coverage_pct.off_list))));
  if (g.nawl_words?.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, h('span', { class: 'badge ngsl-nawl' }, 'NAWL'), t('Academic words')), chips(g.nawl_words, { lens: 'ngsl' })));
  if (g.off_list.length) out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, t('Off-list words')), chips(g.off_list, { lens: 'ngsl' })));
  out.appendChild(about('ngsl'));
  return out;
}

function renderAwl(r) {
  const a = r.awl;
  const out = h('div', {});
  out.appendChild(h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, pct(a.coverage_pct)),
    h('div', { class: 'hero-text' },
      h('b', {}, tn(a.counts.awl_families, '{words} from {n} family', '{words} from {n} families', { words: tn(a.counts.awl_tokens, '{n} word', '{n} words') })),
      h('span', {}, t('Academic prose usually runs near 10% AWL words, fiction 1–2%.')))));
  const rows = h('div', { class: 'rows compact' });
  const max = Math.max(1, ...Object.values(a.per_sublist).map((x) => x.tokens));
  for (const [s, v] of Object.entries(a.per_sublist)) {
    rows.appendChild(h('div', { class: `row${v.tokens ? '' : ' dim'}` },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, t('Sublist {number}', { number: num(Number(s)) }))),
      h('div', { class: 'row-viz' }, meter(v.tokens, max, 'awl')),
      h('div', { class: 'row-val' }, h('b', {}, num(v.tokens)), h('span', {}, tn(v.families, '{n} family', '{n} families')))));
  }
  out.appendChild(rows);
  if (a.families_detail.length) {
    out.appendChild(h('div', { class: 'level' }, h('div', { class: 'level-head static' }, t('Families found')),
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

function renderVocabulary(r, ctx, sub, { withPhrases = null } = {}) {
  const out = h('div', {});
  const nav = h('div', { class: 'subnav segmented', role: 'radiogroup', 'aria-label': t('Word list') });
  const body = h('div', {});
  const renderers = { cefr: renderCefr, bnc: renderBnc, ngsl: renderNgsl, awl: renderAwl, diversity: renderDiversity };
  const cache = {};
  const select = (id, { fromLens = false, withPhrases = null } = {}) => {
    if (withPhrases != null) {
      BNC_WITH_PHRASES = withPhrases;
      if (id === 'bnc') delete cache.bnc;
    }
    nav.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.sub === id)));
    // On a narrow screen the row scrolls: keep the chosen list in view.
    const on = nav.querySelector(`[data-sub="${id}"]`);
    if (on && nav.scrollWidth > nav.clientWidth) nav.scrollLeft += on.getBoundingClientRect().left - nav.getBoundingClientRect().left - (nav.clientWidth - on.offsetWidth) / 2;
    cache[id] ??= renderers[id](r, ctx);
    body.replaceChildren(cache[id]);
    out.dataset.sub = id;
    const lens = VOCAB_SUBS.find((x) => x.id === id)?.lens;
    if (!fromLens && lens) Reader.setLens(lens);
  };
  VOCAB_SUBS.forEach((s) => nav.appendChild(h('button', { type: 'button', role: 'radio', dataset: { sub: s.id }, onclick: () => select(s.id) }, t(s.label))));
  radioKeys(nav);
  edgeFade(nav);
  out.append(nav, body);
  out.selectSub = select;
  select(sub || 'cefr', { fromLens: true, withPhrases });
  return out;
}

// ---- phrases -------------------------------------------------------------------------

/** Hit spans per entry rank, for flashing an expression in the reader. */
function phraseSpans(p) {
  const out = new Map();
  for (const x of p.hits) {
    if (!out.has(x.rank)) out.set(x.rank, { spans: [], surfaces: new Set() });
    const g = out.get(x.rank);
    g.spans.push(x.span);
    g.surfaces.add(x.surface.toLowerCase());
  }
  return out;
}

/** The list's rating as three dots, filled for each star (x is none). */
function ratingDots(register, rating) {
  const r = PHRASE_RATINGS.find((x) => x.key === rating);
  const name = t('{register}: {rating}', { register: t(register.label), rating: t(r.label) });
  const dots = h('span', { class: 'dots', 'aria-hidden': 'true' }, [0, 1, 2].map((i) => h('i', { class: i < r.dots ? 'on' : null })));
  return h('span', { class: 'rating', title: name, 'aria-label': name }, t(register.label), dots);
}

/** One bar per register: the share of hits at each of the list's ratings. */
function registerBars(reg) {
  const grid = h('div', { class: 'reg-bars' });
  for (const g of PHRASE_REGISTERS) {
    const counts = reg[g.key];
    const total = PHRASE_RATINGS.reduce((s, x) => s + counts[x.key], 0);
    const shares = listOf(PHRASE_RATINGS.map((x) => share(t(x.label), pct((counts[x.key] / total) * 100, 0))), 'unit');
    const bar = h('div', { class: 'stack', role: 'img', 'aria-label': t('{register} ({shares})', { register: t(g.label), shares }) });
    PHRASE_RATINGS.forEach((x) => {
      if (counts[x.key]) bar.appendChild(h('span', { class: `seg reg-${x.key}`, style: { flexGrow: String(counts[x.key]) }, title: t('{rating} in {register}: {pct}', { rating: t(x.label), register: t(g.long), pct: pct((counts[x.key] / total) * 100, 0) }) }));
    });
    grid.append(h('span', { class: 'reg-label' }, t(g.label)), bar);
  }
  const keys = h('div', { class: 'stack-keys' }, PHRASE_RATINGS.map((x) => h('span', { class: 'stack-key' }, h('i', { class: `sw reg-${x.key}` }), t(x.label))));
  return h('div', { class: 'stack-wrap' }, grid, keys);
}

let PHRASE_SORT = 'text'; // the Expressions list's order, kept across analyses

/** Credit line: the list is the authors' work, used with their permission. */
function phraseCredit() {
  return h('p', { class: 'credit' },
    tr('From the <b>PHRASE List</b> by Ron Martinez and Norbert Schmitt (<a>2012, Applied Linguistics 33(3)</a>), used with the authors’ permission.', null, {
      b: (s) => h('b', {}, s),
      a: (s) => h('a', { href: 'https://doi.org/10.1093/applin/ams010', target: '_blank', rel: 'noopener' }, s),
    }));
}

function phraseRow(e, g) {
  const sense = senseLabel(e);
  const name = phraseName(e);
  // The forms used, when any differs from the entry's own (`there are`, `dealt with`).
  const forms = [...g.surfaces].some((x) => x !== name) ? listOf([...g.surfaces].map(quoted), 'unit') : '';
  const also = e.also_possible?.length ? t('could also be {list}', { list: listOf(e.also_possible.map((a) => senseLabel(a) ?? quoted(phraseName(a))), 'disjunction') }) : '';
  const note = dot(sense, forms, also);
  const perMillion = e.freq_per_100m != null ? e.freq_per_100m / 100 : null;
  return h('button', { type: 'button', class: 'row clickable', onclick: () => Reader.flash(g.spans, 'phrase') },
    h('div', { class: 'row-main' },
      h('span', { class: 'row-name' }, h('span', { class: `badge phrase-${e.k_band}` }, bandCode(e.k_band)), ' ', en(name)),
      note ? h('span', { class: 'row-note' }, note) : null,
      h('span', { class: 'row-note ratings' },
        PHRASE_REGISTERS.map((reg) => ratingDots(reg, e.register[reg.key])),
        e.word_band != null ? h('span', { class: 'word-band', title: t('The highest BNC/COCA band among its words') }, t('words up to {band}', { band: bandCode(e.word_band) })) : null),
      e.example ? h('span', { class: 'row-note example', lang: 'en', dir: 'ltr' }, e.example) : null,
      h('span', { class: 'row-note list-data' },
        dot(t('Rank {rank} on the integrated list', { rank: num(e.rank) }),
          perMillion != null ? t('{count} per million words', { count: num(perMillion, perMillion < 10 ? 1 : 0) }) : null))),
    h('div', { class: 'row-val' }, h('b', {}, `×${num(e.count)}`)));
}

function renderPhrases(r) {
  const p = r.phrase;
  const ip = p.integrated_profile;
  const out = h('div', {});
  out.appendChild(phraseCredit());
  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Expressions'), num(p.counts.total_hits), tn(p.counts.unique_phrases, '{n} distinct expression', '{n} distinct expressions')),
    stat(t('Per 1,000 words'), num(p.counts.hits_per_1000_words, 1)),
    ip && ip.counts.content_tokens ? stat(t('Words inside expressions'), pct((ip.counts.phrase_tokens / ip.counts.content_tokens) * 100), t('of all words')) : null));
  if (!p.counts.total_hits) {
    out.appendChild(h('p', { class: 'muted' }, t('None of the PHRASE List’s expressions occur in this text.')));
    out.appendChild(about('phrase'));
    return out;
  }

  out.appendChild(h('h3', { class: 'sub-h' }, t('By frequency band (1K most common, 5K least)')));
  out.appendChild(stack([1, 2, 3, 4, 5].map((k) => ({ key: String(k), label: bandCode(k), value: p.hits_per_k_band[k] })), { lens: 'phrase' }));

  const groups = phraseSpans(p);
  const exps = p.expressions || [];
  if (p.register) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('How common they are in each register')));
    out.appendChild(registerBars(p.register));
    out.appendChild(h('p', { class: 'fine' }, t('The PHRASE List’s own ratings for every expression found: how common each one is in speech, general writing and academic writing, compared with the other two.')));
    for (const g of PHRASE_REGISTERS) {
      const rare = exps.filter((e) => e.register[g.key] === 'rare');
      if (!rare.length) continue;
      out.appendChild(h('div', { class: 'level' },
        h('div', { class: 'level-head static' }, t('Rare or absent in {register}', { register: t(g.long) })),
        chips(rare, { lens: 'phrase', label: phraseName, count: (e) => e.count, spans: (e) => groups.get(e.rank).spans })));
    }
  }

  // Effect on the frequency profile: the integrated list's point.
  if (ip?.counts.phrase_tokens) {
    const w95 = bandFor(r.bnc_coca.per_band, 95);
    const p95 = bandFor(ip.per_band, 95);
    const n = ip.counts.phrase_tokens;
    const vars = { threshold: pct(95, 0), raised: num(ip.counts.raised_tokens), band: bandCode(w95), from: bandCode(w95), to: bandCode(p95) };
    out.appendChild(h('div', { class: 'callout' },
      h('b', {}, t('Words and phrases as one list')),
      h('p', {}, w95 === p95
        ? tn(n, 'Counting the {n} word inside these expressions at the expressions’ bands, {raised} move to a rarer band; {threshold} coverage stays at {band}.', 'Counting the {n} words inside these expressions at the expressions’ bands, {raised} move to a rarer band; {threshold} coverage stays at {band}.', vars)
        : tn(n, 'Counting the {n} word inside these expressions at the expressions’ bands, {threshold} coverage moves from {from} to {to}: the text is harder than its single words suggest.', 'Counting the {n} words inside these expressions at the expressions’ bands, {threshold} coverage moves from {from} to {to}: the text is harder than its single words suggest.', vars)),
      h('button', { type: 'button', class: 'link-btn', onclick: () => Panels.open('vocabulary', { sub: 'bnc', withPhrases: true, focus: true }) }, t('Open the integrated profile'), icon('arrow-right', { size: 14 }))));
  }

  const head = h('div', { class: 'list-head' }, h('h3', { class: 'sub-h' }, t('Expressions found')));
  const sorter = h('div', { class: 'segmented small', role: 'radiogroup', 'aria-label': t('Order') });
  const list = h('div', { class: 'rows' });
  const ORDERS = {
    text: [t('In text order'), (a, b) => groups.get(a.rank).spans[0][0] - groups.get(b.rank).spans[0][0]],
    band: [t('By band'), (a, b) => b.k_band - a.k_band || a.rank - b.rank],
    count: [t('By count'), (a, b) => b.count - a.count || a.rank - b.rank],
  };
  const sortBy = (key) => {
    PHRASE_SORT = key;
    sorter.querySelectorAll('button').forEach((b) => b.setAttribute('aria-checked', String(b.dataset.k === key)));
    list.replaceChildren(...[...exps].sort(ORDERS[key][1]).map((e) => phraseRow(e, groups.get(e.rank))));
  };
  for (const [key, [label]] of Object.entries(ORDERS)) sorter.appendChild(h('button', { type: 'button', role: 'radio', dataset: { k: key }, onclick: () => sortBy(key) }, label));
  radioKeys(sorter);
  head.appendChild(sorter);
  out.appendChild(head);
  sortBy(PHRASE_SORT);
  out.appendChild(list);
  out.appendChild(about('phrase'));
  return out;
}

// ---- metadiscourse -----------------------------------------------------------------

function renderMetadiscourse(r) {
  const m = r.metadiscourse;
  const out = h('div', {});
  const per1000 = (v) => t('{count} per 1,000 words', { count: num(v, 0) });
  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Markers'), num(m.counts.total_hits), per1000(m.density_per_1000)),
    stat(t('Interactive'), num(m.per_dimension.interactive.hits), per1000(m.per_dimension.interactive.density_per_1000)),
    stat(t('Interactional'), num(m.per_dimension.interactional.hits), per1000(m.per_dimension.interactional.density_per_1000))));

  for (const dim of ['interactive', 'interactional']) {
    const section = h('div', { class: 'md-dim' }, h('button', { type: 'button', class: 'md-dim-head', onclick: () => Reader.focus('md', dim === 'interactive' ? 'ia' : 'il') },
      h('i', { class: `sw md-${dim === 'interactive' ? 'ia' : 'il'}` }), dim === 'interactive' ? t('Interactive: guiding the reader through the text') : t('Interactional: engaging the reader')));
    const rows = h('div', { class: 'rows compact' });
    const max = Math.max(1, ...Object.values(m.per_category).map((c) => c.hits));
    for (const [cat, v] of Object.entries(m.per_category)) {
      if (v.dimension !== dim) continue;
      const hits = m.hits.filter((x) => x.category === cat);
      const markers = new Map();
      hits.forEach((x) => markers.set(x.surface.toLowerCase(), (markers.get(x.surface.toLowerCase()) || 0) + 1));
      const info = MD_CATEGORIES[cat] || { label: cat, note: '', eg: '' };
      const note = v.hits
        ? en([...markers].map(([w, c]) => (c > 1 ? `${w} ×${num(c)}` : w)).join(', '))
        : tr('{description}: <en>{examples}</en>', { description: t(info.note), examples: info.eg }, { en: (s) => en(s) });
      rows.appendChild(h('button', { type: 'button', class: `row clickable${v.hits ? '' : ' dim'}`, disabled: !v.hits, onclick: () => Reader.flash(hits.map((x) => x.span), 'md') },
        h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, t(info.label)), h('span', { class: 'row-note' }, note)),
        h('div', { class: 'row-viz' }, meter(v.hits, max, `md-${dim === 'interactive' ? 'ia' : 'il'}`)),
        h('div', { class: 'row-val' }, h('b', {}, num(v.hits)), h('span', {}, t('{count}/1k', { count: num(v.density_per_1000, 1) })))));
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
  const gb = e.variant === 'gb';
  const out = h('div', {});
  const toggle = h('div', { class: 'segmented', role: 'radiogroup', 'aria-label': t('Spelling variety') },
    ['gb', 'us'].map((v) => h('button', { type: 'button', role: 'radio', 'aria-checked': String(e.variant === v), title: v === 'gb' ? t('British English') : t('American English'), onclick: () => v !== e.variant && ctx.setVariant(v) }, v === 'gb' ? t('UK') : t('US'))));
  radioKeys(toggle);
  out.appendChild(h('div', { class: 'spell-head' }, h('span', {}, gb ? t('Checked as British English') : t('Checked as American English')), toggle));

  const item = (x, kind) =>
    h('div', { class: `fix ${kind}` },
      h('button', { type: 'button', class: 'fix-word', onclick: () => Reader.flash(x.spans, 'spelling'), title: t('Show in the text') }, en(x.surface), x.count > 1 ? h('span', { class: 'chip-n' }, `×${num(x.count)}`) : null),
      h('span', { class: 'fix-arrow', 'aria-hidden': 'true' }, x.suggestions?.length ? icon('arrow-right', { size: 14 }) : null),
      h('span', { class: 'fix-sugs' },
        x.suggestions?.length
          ? x.suggestions.map((s) => h('button', { type: 'button', class: 'sug', title: tn(x.count, 'Replace with {word}', 'Replace all {n} with {word}', { word: quoted(s) }), onclick: () => ctx.applyFix(x.spans, s) }, en(s)))
          : h('span', { class: 'muted' }, kind === 'name' ? t('probably a name') : t('no suggestion'))));

  if (!e.errors.length && !e.variant_mismatches.length) {
    const checked = e.counts.tokens_checked;
    out.appendChild(h('div', { class: 'empty-ok' }, h('b', {}, t('No spelling errors found.')),
      h('span', {}, gb
        ? tn(checked, '{n} word checked against the British English dictionary.', '{n} words checked against the British English dictionary.')
        : tn(checked, '{n} word checked against the American English dictionary.', '{n} words checked against the American English dictionary.'))));
  }
  if (e.errors.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('Possible misspellings · {count}', { count: num(e.counts.errors_total) })));
    out.appendChild(h('div', { class: 'fixes' }, e.errors.map((x) => item(x, 'err'))));
  }
  if (e.variant_mismatches.length) {
    const count = num(e.counts.variant_mismatches);
    out.appendChild(h('h3', { class: 'sub-h' }, gb ? t('American spellings · {count}', { count }) : t('British spellings · {count}', { count })));
    out.appendChild(h('div', { class: 'fixes' }, e.variant_mismatches.map((x) => item(x, 'var'))));
  }
  if (e.unknown_names.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('Not in the dictionary, probably names · {count}', { count: num(e.counts.unknown_names) })));
    out.appendChild(h('div', { class: 'fixes' }, e.unknown_names.map((x) => item(x, 'name'))));
  }
  if (e.errors.length) out.appendChild(h('p', { class: 'fine' }, t('{rate} errors per 100 words.', { rate: num(e.rates.errors_per_100_words, 1) })));
  out.appendChild(about('spelling'));
  return out;
}

// ---- diversity ------------------------------------------------------------------------------

// The published vocd-D ranges (diversity.VOCD_D_REFERENCE_RANGES), by their English name.
const VOCD_BAND_NAMES = {
  'Adult L2 / ESL learner': N_('Adult learners of English as a second language'),
  'Adult native speaker, academic writing': N_('Adult native speakers, academic writing'),
};

function renderDiversity(r) {
  const d = r.diversity;
  const s = d.scores;
  const out = h('div', {});
  const bands = d.references?.vocd_d_bands || [];
  const hero = h('div', { class: 'hero' },
    h('div', { class: 'hero-num' }, s.mtld == null ? '–' : num(s.mtld, 0)),
    h('div', { class: 'hero-text' }, h('b', {}, 'MTLD'),
      h('span', {}, s.mtld == null
        ? t('Needs at least 50 words, not counting numbers.')
        : tn(d.counts.tokens, '{types} different words in {n}.', '{types} different words in {n}.', { types: num(d.counts.types) }))));
  out.appendChild(hero);

  if (s.vocd_d != null && bands.length) {
    const max = Math.max(130, s.vocd_d + 10);
    const bandName = (b) => (VOCD_BAND_NAMES[b.name] ? t(VOCD_BAND_NAMES[b.name]) : b.name);
    const scale = h('div', { class: 'ref-scale' });
    bands.forEach((b, i) => scale.appendChild(h('span', { class: `ref-band b${i}`, style: { '--l': b.min / max, '--w': (b.max - b.min) / max }, title: t('{name}: {min}–{max}', { name: bandName(b), min: num(b.min), max: num(b.max) }) })));
    scale.appendChild(h('span', { class: 'ref-marker', style: { '--l': s.vocd_d / max } }, h('b', {}, num(s.vocd_d, 0))));
    const where = { below: t('below this range'), within: t('within this range'), above: t('above this range') };
    const keys = h('div', { class: 'ref-keys' }, bands.map((b, i) =>
      h('div', { class: 'ref-key' }, h('i', { class: `sw ref-sw b${i}` }),
        h('span', { class: 'ref-key-name' }, bandName(b), h('span', { class: 'muted' }, ` · D ${num(b.min)}–${num(b.max)}`)),
        h('b', { class: `pos-${b.position}` }, where[b.position] ?? b.position))));
    out.appendChild(h('div', { class: 'ref' }, h('div', { class: 'ref-title' }, t('vocd-D {score} against published ranges', { score: num(s.vocd_d, 1) })), scale, keys,
      h('div', { class: 'fine' }, t('Ranges from Durán, Malvern, Richards & Chipere (2004), Applied Linguistics 25/2.'))));
  }

  const row = (m) => {
    const v = s[m.key];
    return h('div', { class: 'row' },
      h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, t(m.name), m.ref ? h('span', { class: 'ref-cite' }, ` ${m.ref}`) : null), h('span', { class: 'row-note' }, t(m.note))),
      h('div', { class: 'row-val' }, h('b', {}, v == null ? '–' : num(v, m.d)), v == null ? h('span', {}, t('text too short')) : null));
  };
  // Grouped by how far the research supports each index (diversity.TIERS).
  const tiers = d.tiers;
  const groups = tiers
    ? [[t('Use with confidence (50+ words, not counting numbers)'), tiers.recommended], [t('Use with caution'), tiers.caution], [t('Depend on text length: compare only same-length texts'), tiers.legacy]]
    : [[null, DIVERSITY.map((m) => m.key)]];
  for (const [title, keys] of groups) {
    if (title) out.appendChild(h('h3', { class: 'sub-h' }, title));
    out.appendChild(h('div', { class: 'rows' }, DIVERSITY.filter((m) => keys.includes(m.key)).map(row)));
  }
  if (tiers) out.appendChild(h('div', { class: 'fine' }, t('Tiers follow TAALED’s guidance (after Zenker & Kyle 2021). TAALED doesn’t rate vocd-D; it is grouped here with HD-D (McCarthy & Jarvis 2007).')));
  out.appendChild(about('diversity'));
  return out;
}

// ---- statistics ------------------------------------------------------------------------------

function renderStatistics(r) {
  const st = r.statistics;
  const tg = r.tagger;
  const out = h('div', {});
  const perSentence = (v) => t('{count} per sentence', { count: num(v, 1) });
  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Words'), num(st.counts.tokens_excluding_numbers), tn(st.counts.excluded_numeric_tokens, '{n} number excluded', '{n} numbers excluded')),
    stat(t('Different words'), num(st.counts.unique_types_excluding_numbers), `TTR ${num(st.averages.type_token_ratio, 2)}`),
    stat(t('Sentences'), num(st.counts.sentences), t('{count} words per sentence', { count: num(st.averages.tokens_per_sentence, 1) })),
    stat(t('Syllables'), num(st.counts.syllables), t('{count} per word', { count: num(st.averages.syllables_per_word, 2) })),
    stat(t('Polysyllabic words'), pct(st.averages.polysyllable_pct), tn(st.counts.polysyllable_words, '{n} word', '{n} words')),
    stat(t('Characters'), num(st.counts.characters_with_spaces), t('{count} without spaces', { count: num(st.counts.characters_without_spaces) })),
    stat(t('Verbal elements'), num(tg.summary.total_verbal_elements), perSentence(tg.summary.verbal_elements_per_sentence)),
    stat(t('Noun elements'), num(tg.summary.total_noun_elements), perSentence(tg.summary.noun_elements_per_sentence))));

  const dist = Object.entries(tg.upos_distribution).filter(([k]) => k !== 'PUNCT' && k !== 'SPACE');
  const total = dist.reduce((s, [, v]) => s + v, 0);
  const max = Math.max(1, ...dist.map(([, v]) => v));
  const rows = h('div', { class: 'rows compact' });
  dist.forEach(([k, v]) => rows.appendChild(h('div', { class: 'row' },
    h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, UPOS[k] ? t(UPOS[k]) : k)),
    h('div', { class: 'row-viz' }, meter(v, max, 'pos')),
    h('div', { class: 'row-val' }, h('b', {}, num(v)), h('span', {}, pct((v / total) * 100))))));
  out.appendChild(h('h3', { class: 'sub-h' }, t('Parts of speech')));
  out.appendChild(rows);
  if (st.excluded_digits?.length) {
    const shown = st.excluded_digits.slice(0, 20).join(', ') + (st.excluded_digits.length > 20 ? '…' : '');
    out.appendChild(h('p', { class: 'fine' }, t('Numbers left out of the word types: {list}', { list: shown })));
  }
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
  let tabs = TABS;

  const LENS_TO_TAB = {
    cefr: ['vocabulary', 'cefr'], bnc: ['vocabulary', 'bnc'], ngsl: ['vocabulary', 'ngsl'], awl: ['vocabulary', 'awl'],
    phrase: ['phrase'], md: ['md'], spelling: ['spelling'], sent: ['sentences'], adapt: ['adapt'],
  };

  // ---- keeping the reader's place across a rebuild ----
  // A rebuild (an edit, a new readers' level, a new language) replaces every
  // node, so focus and scroll are recorded first and put back on the
  // equivalent control: same tag, class and text, nearest in document order.

  let lastFocus = null; // the last control focused in the pane, as a description
  let pending = null; // the record of a render that hasn't painted yet

  function describe(el) {
    if (!(el instanceof Element)) return null;
    const tab = el.closest('.tab');
    if (tab && tabsEl.contains(tab)) return { tab: tab.dataset.tab, isTab: true };
    const panel = el.closest('.panel');
    if (!panel || !panelsEl.contains(panel)) return null;
    const sel = el.tagName.toLowerCase() + (el.classList[0] ? `.${CSS.escape(el.classList[0])}` : '');
    return { tab: panel.dataset.tab, sel, text: el.textContent.trim(), index: [...panel.querySelectorAll(sel)].indexOf(el) };
  }
  panelsEl.addEventListener('focusin', (e) => (lastFocus = describe(e.target)));
  tabsEl.addEventListener('focusin', (e) => (lastFocus = describe(e.target)));

  function snapshot() {
    const pane = $('results');
    const act = document.activeElement;
    const inPane = act && (panelsEl.contains(act) || tabsEl.contains(act));
    const lost = !act || act === document.body;
    return { top: pane?.scrollTop ?? 0, winY: window.scrollY, focus: inPane ? describe(act) : lost ? lastFocus : null };
  }

  /** `byIndex`: the text may have changed (new language), so fall back to position. */
  function restore(state, { byIndex = false } = {}) {
    const f = state.focus;
    let target = null;
    if (f?.isTab) target = tabsEl.querySelector(`.tab[data-tab="${active}"]`);
    else if (f && f.tab === active && built[active]) {
      const panel = built[active];
      const all = [...panel.querySelectorAll(f.sel)];
      const same = all.filter((el) => el.textContent.trim() === f.text);
      target = same.sort((a, b) => Math.abs(all.indexOf(a) - f.index) - Math.abs(all.indexOf(b) - f.index))[0]
        ?? (byIndex ? all[f.index] : null);
      if (target && (target.disabled || !target.offsetParent)) target = null;
      if (!target) {
        panel.tabIndex = -1;
        target = panel;
      }
    }
    target?.focus({ preventScroll: true });
    const pane = $('results');
    if (pane) pane.scrollTop = state.top;
    window.scrollTo(window.scrollX, state.winY);
  }

  function moveIndicator(btn, animate) {
    if (!btn) return;
    indicator.classList.toggle('no-anim', !animate);
    indicator.style.transform = `translateX(${btn.offsetLeft}px) scaleX(${btn.offsetWidth / 100})`;
    indicator.style.opacity = '1';
  }

  function build(id, sub, opts) {
    const r = data.results;
    const go = (tab, s, o) => open(tab, { sub: s, syncLens: true, focus: true, ...o });
    switch (id) {
      case 'overview': return renderOverview(r, go, ctx);
      case 'adapt': return renderAdapt(r, ctx, go);
      case 'readability': return renderReadability(r);
      case 'vocabulary': return renderVocabulary(r, ctx, sub, opts);
      case 'phrase': return renderPhrases(r);
      case 'sentences': return renderSentences(r);
      case 'md': return renderMetadiscourse(r);
      case 'spelling': return renderSpelling(r, ctx);
      case 'statistics': return renderStatistics(r);
    }
  }

  function open(id, { sub = null, syncLens = true, animate = true, focus = false, withPhrases = null } = {}) {
    if (!tabs.some((tab) => tab.id === id)) id = 'overview';
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
      const panel = h('div', { class: 'panel', role: 'tabpanel', id: `panel-${id}`, 'aria-labelledby': `tab-${id}`, dataset: { tab: id } });
      panel.appendChild(build(id, sub, { withPhrases }));
      panelsEl.appendChild(panel);
      built[id] = panel;
      panel.classList.add('fresh');
      setTimeout(() => panel.classList.remove('fresh'), 900);
    } else if (id === 'vocabulary' && (sub || withPhrases != null)) {
      built[id].firstChild.selectSub(sub || built[id].firstChild.dataset.sub, { fromLens: !syncLens, withPhrases });
    }
    Object.values(built).forEach((p) => p.classList.toggle('active', p === built[id]));
    if (syncLens) {
      const tab = tabs.find((x) => x.id === id);
      if (tab?.lens) Reader.setLens(tab.lens);
      if (id === 'vocabulary') {
        const s = sub || built[id].firstChild.dataset.sub;
        const lens = VOCAB_SUBS.find((x) => x.id === s)?.lens;
        if (lens) Reader.setLens(lens);
      }
    }
    if (focus && window.matchMedia('(max-width: 899px)').matches) built[id].scrollIntoView({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }

  tabsEl.addEventListener('keydown', (e) => {
    const i = tabs.findIndex((tab) => tab.id === active);
    const rtl = getComputedStyle(tabsEl).direction === 'rtl';
    let j = null;
    if (e.key === (rtl ? 'ArrowLeft' : 'ArrowRight')) j = (i + 1) % tabs.length;
    if (e.key === (rtl ? 'ArrowRight' : 'ArrowLeft')) j = (i - 1 + tabs.length) % tabs.length;
    if (e.key === 'Home') j = 0;
    if (e.key === 'End') j = tabs.length - 1;
    if (j == null) return;
    e.preventDefault();
    open(tabs[j].id, { animate: false });
    tabsEl.querySelector(`[data-tab="${tabs[j].id}"]`).focus();
  });
  const updateFade = edgeFade(tabsEl);
  window.addEventListener('resize', () => moveIndicator(tabsEl.querySelector('.tab[aria-selected="true"]'), false));

  /** Rebuild the panels the readers' level (or a dropped comparison) changes, keeping the open tab. */
  function retarget() {
    if (!data) return;
    const state = snapshot();
    const vocab = built.vocabulary?.firstChild?.dataset.sub;
    for (const id of ['overview', 'adapt', 'vocabulary']) {
      if (!built[id]) continue;
      built[id].remove();
      delete built[id];
    }
    open(active, { sub: active === 'vocabulary' ? vocab : null, syncLens: false, animate: false });
    restore(state);
  }

  function render(d, context, { keepTab = false, openTab = null, openLens = null, byIndex = false } = {}) {
    data = d;
    CURRENT = d;
    ctx = context;
    // A second render before the first has painted keeps the first one's record.
    const state = keepTab && !openTab ? (pending ??= snapshot()) : null;
    if (state && byIndex) state.byIndex = true;
    tabs = TABS.filter((tab) => !tab.needs || d.results[tab.needs]);
    const prev = openTab || (keepTab ? active : 'overview');
    const prevSub = built.vocabulary?.firstChild?.dataset.sub;
    built = {};
    // Hold the height while the panel is rebuilt, so the pane's scroll position survives.
    if (state) panelsEl.style.minHeight = `${panelsEl.offsetHeight}px`;
    panelsEl.replaceChildren();
    tabsEl.querySelectorAll('.tab').forEach((b) => b.remove());
    tabs.forEach((tab) => tabsEl.appendChild(h('button', { type: 'button', role: 'tab', class: 'tab', id: `tab-${tab.id}`, dataset: { tab: tab.id }, 'aria-controls': `panel-${tab.id}`, onclick: () => open(tab.id) }, t(tab.label))));
    requestAnimationFrame(() => {
      const lensTarget = openLens && LENS_TO_TAB[openLens];
      if (lensTarget && !openTab) {
        Reader.setLens(openLens);
        open(lensTarget[0], { sub: lensTarget[1], syncLens: false, animate: false });
      } else {
        open(prev, { sub: prevSub, syncLens: !!openTab, animate: false });
        if (openLens) Reader.setLens(openLens);
      }
      if (state) {
        pending = null;
        panelsEl.style.minHeight = '';
        restore(state, { byIndex: state.byIndex });
      }
      updateFade();
    });
  }

  // A new interface language: rebuild what is on screen, in place.
  I18n.onChange(() => {
    if (data) render(data, ctx, { keepTab: true, byIndex: true });
  });

  return {
    render(d, context, { keepTab = false, openTab = null, openLens = null } = {}) {
      render(d, context, { keepTab, openTab, openLens });
    },
    /** The reader's lens changed by the user: follow it. */
    followLens(lens) {
      const target = LENS_TO_TAB[lens];
      if (target) open(target[0], { sub: target[1], syncLens: false });
    },
    open,
    retarget,
    radioKeys,
    get active() {
      return active;
    },
  };
})();
