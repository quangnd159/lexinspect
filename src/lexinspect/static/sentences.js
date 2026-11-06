// The Sentences tab: syntactic complexity for the text, and every sentence
// ranked by length, each one a click away from its place in the text.
//
// Loaded by the batch page too (without panels.js or reader.js): nothing here
// may touch their globals at load time.

// Names, groups and notes are N_ strings: translate with t() where shown.
// The abbreviations stay as they are. export.js reads this table as well.
const SYNTAX = [
  { group: N_('Length'), items: [
    { key: 'mls', name: N_('Mean length of sentence'), abbr: 'MLS', d: 1, note: N_('Words per sentence.') },
    { key: 'mlt', name: N_('Mean length of T-unit'), abbr: 'MLT', d: 1, note: N_('Words per main clause with everything attached to it. Grows with proficiency (Lu 2011).') },
    { key: 'mlc', name: N_('Mean length of clause'), abbr: 'MLC', d: 1, note: N_('Words per clause. Longer clauses usually mean denser noun phrases.') },
  ] },
  { group: N_('Subordination'), items: [
    { key: 'c_s', name: N_('Clauses per sentence'), abbr: 'C/S', d: 2 },
    { key: 'c_t', name: N_('Clauses per T-unit'), abbr: 'C/T', d: 2 },
    { key: 'dc_c', name: N_('Dependent clauses per clause'), abbr: 'DC/C', d: 2, note: N_('Dependent clauses are relative, adverbial and complement clauses.') },
    { key: 'dc_t', name: N_('Dependent clauses per T-unit'), abbr: 'DC/T', d: 2 },
    { key: 'ct_t', name: N_('Complex T-units per T-unit'), abbr: 'CT/T', d: 2, note: N_('Share of T-units that contain a dependent clause.') },
  ] },
  { group: N_('Coordination'), items: [
    { key: 't_s', name: N_('T-units per sentence'), abbr: 'T/S', d: 2 },
    { key: 'cp_t', name: N_('Coordinate phrases per T-unit'), abbr: 'CP/T', d: 2 },
    { key: 'cp_c', name: N_('Coordinate phrases per clause'), abbr: 'CP/C', d: 2 },
  ] },
  { group: N_('Phrasal complexity'), items: [
    { key: 'cn_t', name: N_('Complex nominals per T-unit'), abbr: 'CN/T', d: 2 },
    { key: 'cn_c', name: N_('Complex nominals per clause'), abbr: 'CN/C', d: 2, note: N_('Nouns with adjectives, prepositional phrases or clauses attached, and nominal clauses.') },
    { key: 'vp_t', name: N_('Verb phrases per T-unit'), abbr: 'VP/T', d: 2 },
  ] },
];

// The syntax module's reliability thresholds (syntax.py).
const SYNTAX_MIN_WORDS = 100;
const SYNTAX_MIN_SENTENCES = 5;

function sentenceText(r, s) {
  const text = CURRENT.input.normalised_text ?? CURRENT.submitted;
  return text.slice(s.span[0], s.span[1]).replace(/\s+/g, ' ').trim();
}

function sentenceRows(r, list) {
  const rows = h('div', { class: 'rows sentence-rows' });
  for (const s of list) {
    const text = sentenceText(r, s);
    const facts = [tn(s.clauses, '{n} clause', '{n} clauses')];
    if (s.dependent_clauses) facts.push(tn(s.dependent_clauses, '{n} dependent clause', '{n} dependent clauses'));
    if (s.passive) facts.push(tn(s.passive, '{n} passive clause', '{n} passive clauses'));
    rows.appendChild(h('button', { type: 'button', class: 'row clickable sentence-row', onclick: () => Reader.flash([s.span], 'sent') },
      h('div', { class: 'row-main' },
        en(text.length > 180 ? `${text.slice(0, 177).trimEnd()}…` : text, 'sentence-snippet'),
        h('span', { class: 'row-note' }, facts.join(' · '))),
      h('div', { class: 'row-val' }, h('b', {}, num(s.words)), h('span', {}, tn(s.words, 'word', 'words')))));
  }
  return rows;
}

/** Why the ratios are shaky, from the counts (the server's notes are English). */
function syntaxCautions(syn) {
  const words = syn.counts?.words ?? 0;
  const sentences = syn.counts?.sentences ?? syn.sentences.length;
  const out = [];
  if (words < SYNTAX_MIN_WORDS) {
    out.push(tn(words,
      'The text has {n} word. These ratios need {min} or more; in a shorter text, one sentence shifts every measure.',
      'The text has {n} words. These ratios need {min} or more; in a shorter text, one sentence shifts every measure.',
      { min: num(SYNTAX_MIN_WORDS) }));
  }
  if (sentences < SYNTAX_MIN_SENTENCES) {
    out.push(tn(sentences,
      'The text has {n} sentence. Ratios per sentence and per T-unit need {min} or more sentences.',
      'The text has {n} sentences. Ratios per sentence and per T-unit need {min} or more sentences.',
      { min: num(SYNTAX_MIN_SENTENCES) }));
  }
  return out;
}

function renderSentences(r) {
  const syn = r.syntax;
  const out = h('div', {});
  const sc = syn.indices;
  const c = syn.counts;
  const sents = syn.sentences.map((s, i) => ({ ...s, i }));
  const longest = sents.reduce((a, b) => (b.words > a.words ? b : a), sents[0]);

  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Words per sentence'), num(sc.mls, 1), longest ? tn(longest.words, 'Longest: {n} word', 'Longest: {n} words') : null),
    stat(t('Clauses per sentence'), num(sc.c_s, 2), tn(c.dependent_clauses, '{n} dependent clause', '{n} dependent clauses')),
    stat(t('Passive clauses'), c.clauses ? pct((c.passive_clauses / c.clauses) * 100, 0) : '–',
      tn(c.clauses, '{count} of {n} clause', '{count} of {n} clauses', { count: num(c.passive_clauses) })),
    stat(t('Dependency distance'), num(syn.dependency?.mean_dependency_distance, 2), t('Mean distance from a word to its head, in words (Liu 2008)'))));

  const cautions = syn.reliability && !syn.reliability.reliable ? syntaxCautions(syn) : [];
  if (cautions.length) out.appendChild(callout('warn', t('Read these measures with care'), cautions));

  // Sentence length distribution, as the lens colours it.
  const buckets = [
    { key: 's1', label: t('Up to 15 words'), test: (n) => n <= 15 },
    { key: 's2', label: t('16–25 words'), test: (n) => n > 15 && n <= 25 },
    { key: 's3', label: t('26–35 words'), test: (n) => n > 25 && n <= 35 },
    { key: 's4', label: t('Over 35 words'), test: (n) => n > 35 },
  ];
  out.appendChild(h('h3', { class: 'sub-h' }, t('Sentences by length')));
  out.appendChild(stack(buckets.map((b) => ({ key: b.key, label: b.label, value: sents.filter((s) => b.test(s.words)).length })), { lens: 'sent' }));

  out.appendChild(h('h3', { class: 'sub-h' }, t('Longest sentences')));
  out.appendChild(sentenceRows(r, [...sents].sort((a, b) => b.words - a.words).slice(0, 6)));

  out.appendChild(h('h3', { class: 'sub-h' }, t('Syntactic complexity (L2SCA measures, Lu 2010)')));
  for (const g of SYNTAX) {
    const list = h('div', { class: 'rows compact' });
    for (const m of g.items) {
      list.appendChild(h('div', { class: 'row' },
        h('div', { class: 'row-main' }, h('span', { class: 'row-name' }, t(m.name), ' ', h('span', { class: 'ref-cite' }, m.abbr)), m.note ? h('span', { class: 'row-note' }, t(m.note)) : null),
        h('div', { class: 'row-val' }, h('b', {}, num(sc[m.key], m.d)))));
    }
    out.append(h('div', { class: 'group-h' }, t(g.group)), list);
  }

  const ph = syn.phrasal;
  if (ph) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('Noun-phrase complexity per 1,000 words (Biber et al. 2011)')));
    out.appendChild(h('div', { class: 'stats-grid' },
      stat(t('Attributive adjectives'), num(ph.attributive_adjectives_per_1000_words, 0), en('a long journey')),
      stat(t('Nouns before nouns'), num(ph.premodifying_nouns_per_1000_words, 0), en('a bus station')),
      stat(t('Prepositional phrases after nouns'), num(ph.prepositional_postmodifiers_per_1000_words, 0), en('the cost of living'))));
    out.appendChild(h('p', { class: 'fine' }, t('Academic writing packs its complexity into noun phrases more than clauses; conversation does the reverse.')));
  }
  out.appendChild(about('syntax'));
  return out;
}
