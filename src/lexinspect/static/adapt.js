// The Adapt tab: what to change so a text suits readers at one CEFR level.
//
// Everything here follows the readers' level picked in Prefs and needs no new
// request when it changes: the server sends simpler alternatives for every
// word from A2 up, already inflected for each place the word occurs, and this
// tab shows the ones that matter for the chosen level. Swapping a word edits
// the text and re-analyses it, so every number stays the analyser's.

const LEVEL_RANK = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };

/** Every word above the target, from the per-token profile, so the counts are
 *  the CEFR module's and the reader's. Occurrences the alternatives module
 *  covers are grouped by its lemma and carry its suggestions and inflected
 *  replacements; the rest are grouped by form and level, with nothing to swap. */
function aboveTarget(r, target) {
  const rank = LEVEL_RANK[target];
  const text = CURRENT.input.normalised_text ?? CURRENT.submitted;
  const alt = new Map(); // token start -> [item, occurrence]
  for (const item of r.alternatives?.items ?? []) for (const o of item.occurrences) alt.set(o.span[0], [item, o]);
  const groups = new Map();
  for (const [a, b, level] of r.profile.rows) {
    if (!(LEVEL_RANK[level] > rank)) continue;
    const surface = text.slice(a, b);
    const hit = alt.get(a);
    const item = hit && hit[0].level === level ? hit[0] : null;
    const key = item ? `alt|${item.lemma}|${item.pos}|${level}` : `form|${surface.toLowerCase()}|${level}`;
    if (!groups.has(key)) groups.set(key, { lemma: item?.lemma ?? surface.toLowerCase(), level, count: 0, occurrences: [], suggestions: item?.suggestions ?? [] });
    const g = groups.get(key);
    g.count++;
    g.occurrences.push(item ? { ...hit[1], span: [a, b], surface } : { span: [a, b], surface });
  }
  // Highest level first, then the most frequent; ties keep text order.
  return [...groups.values()].sort((x, y) => LEVEL_RANK[y.level] - LEVEL_RANK[x.level] || y.count - x.count);
}

/** Off-list words a reader may not know: not on the CEFR lists, not names, not misspelt. */
function unlistedWords(r) {
  const bad = new Set([...(r.errors?.errors ?? []), ...(r.errors?.variant_mismatches ?? [])].map((e) => e.surface.toLowerCase()));
  return r.cefr.off_list.filter((w) => !bad.has(w.word.toLowerCase()));
}

/** A re-analysis is running: a second swap would edit a text that is about to change. */
function swapsBusy(ctx) {
  return Boolean(ctx?.busy) || 'busy' in document.body.dataset;
}

const times = (n) => t('×{count}', { count: num(n) });

function adaptIntro() {
  return h('div', { class: 'adapt-empty' },
    h('p', {}, t('Choose your readers’ CEFR level to see the words above it, simpler words to swap in, phrases learners may miss and sentences worth splitting.')),
    targetPicker(t('Readers’ level')));
}

/** The banner's heading, one whole message per verdict (Insights.fit keys). */
function fitTitle(fit, level) {
  switch (fit.key) {
    case 'easy': return t('Comfortable for {level} readers', { level });
    case 'ok': return t('Manageable for {level} readers with support', { level });
    case 'hard': return t('Challenging for {level} readers', { level });
    case 'vhard': return t('Too hard for {level} readers without adapting', { level });
    default: return fit.label;
  }
}

function fitBanner(known, target) {
  const fit = Insights.fit(known);
  if (!fit) return null;
  return h('div', { class: `fit-banner fit-${fit.key}` },
    h('div', { class: 'fit-num', 'aria-hidden': 'true' }, pct(known)),
    h('div', { class: 'fit-text' },
      h('b', {}, fitTitle(fit, target)),
      h('span', {}, t('{pct} of the words are at {level} or below on the CEFR lists, or are names.', { pct: pct(known), level: target })),
      h('span', { class: 'fit-note' }, t('Laufer & Ravenhorst-Kalovski (2010) link knowing {min} of the words to reading with support and {max} to reading independently. They counted known word families; CEFR-list coverage approximates that.', { min: pct(95, 0), max: pct(98, 0) }))));
}

function wordRow(item, target, ctx) {
  const rank = LEVEL_RANK[target];
  const options = item.suggestions.filter((s) => LEVEL_RANK[s.level] <= rank);
  const surfaces = [...new Set(item.occurrences.map((o) => o.surface.toLowerCase()))];
  const spans = item.occurrences.map((o) => o.span);
  const swap = (word) => {
    if (swapsBusy(ctx)) return;
    const edits = item.occurrences.map((o) => ({ span: o.span, text: o.replacements?.[word] ?? word }));
    ctx.applyEdits(edits, tn(edits.length,
      'Replaced {word} with {replacement}',
      'Replaced {word} with {replacement} in {n} places',
      { word: quoted(surfaces[0]), replacement: quoted(word) }));
  };
  const busy = swapsBusy(ctx);
  return h('div', { class: 'adapt-row' },
    h('button', { type: 'button', class: 'adapt-word', onclick: () => Reader.flash(spans, 'adapt'), title: t('Show in the text') },
      h('span', { class: `badge cefr-${item.level}` }, item.level),
      en(surfaces.join(', '), 'adapt-surface'),
      item.count > 1 ? h('span', { class: 'chip-n' }, times(item.count)) : null),
    options.length
      ? h('div', { class: 'adapt-options', role: 'group', 'aria-label': t('Simpler words for {word}', { word: quoted(surfaces[0]) }) },
        options.map((s) => h('button', {
          type: 'button',
          class: 'chip swap',
          disabled: busy,
          onclick: () => swap(s.word),
          title: tn(item.count,
            'Replace with {replacement} ({level})',
            'Replace with {replacement} ({level}) in all {n} places',
            { replacement: quoted(s.word), level: s.level }),
        }, en(s.word), h('span', { class: 'chip-level' }, s.level))))
      : null);
}

function renderAdapt(r, ctx, go) {
  const out = h('div', {});
  const target = Prefs.target;
  if (!target) {
    out.appendChild(adaptIntro());
    return out;
  }
  const rank = LEVEL_RANK[target];
  const known = Insights.knownAt(r, target);
  const above = aboveTarget(r, target);
  const aboveTokens = above.reduce((s, x) => s + x.count, 0);
  const unlisted = unlistedWords(r);
  const swappable = above.filter((x) => x.suggestions.some((s) => LEVEL_RANK[s.level] <= rank));

  out.appendChild(h('div', { class: 'adapt-head' }, targetPicker(t('Readers’ level'))));
  // After a swap, show what it changed here too, where the editing happens.
  const strip = changesStrip(CURRENT.changes, ctx);
  if (strip) out.appendChild(strip);
  const banner = fitBanner(known, target);
  if (banner) out.appendChild(banner);

  out.appendChild(h('div', { class: 'stats-grid' },
    stat(t('Words above {level}', { level: target }), num(aboveTokens), tn(above.length, '{n} different word', '{n} different words')),
    stat(t('Not on the CEFR lists'), num(unlisted.reduce((s, w) => s + w.count, 0)), tn(unlisted.length, '{n} different word', '{n} different words')),
    !r.alternatives ? null : stat(t('With a simpler word'), num(swappable.length), tn(above.length, 'out of {n} different word', 'out of {n} different words'))));

  // Words above the level: the ones with a simpler word first, as rows to
  // swap from; the rest as one group of chips to gloss or pre-teach.
  out.appendChild(h('h3', { class: 'sub-h' }, t('Words above {level}', { level: target })));
  if (!above.length) {
    out.appendChild(h('p', { class: 'muted' }, t('Every word on the CEFR lists is at {level} or below.', { level: target })));
  } else {
    const rest = above.filter((x) => !swappable.includes(x));
    if (swappable.length) {
      const list = h('div', { class: 'adapt-list' });
      swappable.forEach((x) => list.appendChild(wordRow(x, target, ctx)));
      out.appendChild(list);
      out.appendChild(h('p', { class: 'fine' }, t('A swap replaces the word everywhere it occurs and keeps its form (plural, past tense, capital letter); then every figure updates. Check that the new word fits each sentence: a synonym rarely fits every sense. Suggestions come from Open English WordNet: synonyms of the word’s main sense that are on the CEFR lists at or below the readers’ level.')));
    }
    if (rest.length) {
      if (swappable.length) out.appendChild(h('div', { class: 'group-h' }, t('No simpler word on the CEFR lists')));
      const wrap = h('div', { class: 'chips' });
      const make = (x) => {
        const surfaces = [...new Set(x.occurrences.map((o) => o.surface.toLowerCase()))];
        return h('button', { type: 'button', class: 'chip', title: t('Show in the text'), onclick: () => Reader.flash(x.occurrences.map((o) => o.span), 'adapt') },
          en(surfaces[0] ?? x.lemma), h('span', { class: 'chip-level' }, x.level), x.count > 1 ? h('span', { class: 'chip-n' }, times(x.count)) : null);
      };
      const LIMIT = 40;
      rest.slice(0, LIMIT).forEach((x) => wrap.appendChild(make(x)));
      if (rest.length > LIMIT) {
        const more = h('button', { type: 'button', class: 'chip more' }, tn(rest.length - LIMIT, '+{n} more', '+{n} more'));
        more.addEventListener('click', () => {
          rest.slice(LIMIT).forEach((x) => wrap.insertBefore(make(x), more));
          more.remove();
        });
        wrap.appendChild(more);
      }
      out.appendChild(wrap);
      out.appendChild(h('p', { class: 'fine' }, r.alternatives
        ? t('Gloss these, pre-teach them or rephrase around them. Keep the ones the topic needs.')
        : t('Simpler-word suggestions are not available.')));
    }
  }

  if (unlisted.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('Not on the CEFR lists')));
    out.appendChild(chips(unlisted, { lens: 'adapt' }));
    out.appendChild(h('p', { class: 'fine' }, t('Rare words, technical terms and new coinages have no CEFR level. Topic words are often worth keeping and glossing.')));
  }

  // Phrases readers may miss. The PHRASE List's bands and the BNC/COCA word
  // bands come from different corpora, so a one-band gap is noise: keep
  // expressions two or more bands above their rarest word, or in 3K and beyond.
  const exps = (r.phrase?.expressions ?? []).filter((e) => (e.word_band != null && e.k_band - e.word_band >= 2) || e.k_band >= 3);
  if (exps.length) {
    const groups = phraseSpans(r.phrase);
    out.appendChild(h('h3', { class: 'sub-h' }, t('Phrases learners may miss')));
    out.appendChild(h('p', { class: 'fine' }, t('These PHRASE List expressions (Martinez & Schmitt 2012) are in its 3K band or beyond, or well above the bands of their words. Readers who know every word may still miss the meaning.')));
    const list = h('div', { class: 'rows' });
    for (const e of exps) {
      const band = `${e.k_band}K`;
      list.appendChild(h('button', { type: 'button', class: 'row clickable', onclick: () => Reader.flash(groups.get(e.rank).spans, 'phrase') },
        h('div', { class: 'row-main' },
          h('span', { class: 'row-name' }, h('span', { class: `badge phrase-${e.k_band}` }, band), ' ', en(phraseName(e))),
          h('span', { class: 'row-note' }, e.word_band != null
            ? t('{band} expression; its rarest word is {wordBand}', { band, wordBand: `${e.word_band}K` })
            : t('{band} expression', { band }))),
        h('div', { class: 'row-val' }, h('b', {}, times(e.count)))));
    }
    out.appendChild(list);
  }

  // Sentences worth splitting.
  const long = (r.syntax?.sentences ?? []).map((s, i) => ({ ...s, i })).filter((s) => s.words > 25 || s.clauses >= 4);
  if (long.length) {
    out.appendChild(h('h3', { class: 'sub-h' }, t('Sentences worth splitting')));
    out.appendChild(sentenceRows(r, long.sort((a, b) => b.words - a.words).slice(0, 8)));
  }

  // Take-away: a word list for the class.
  const words = [...above, ...unlisted.map((w) => ({ lemma: w.word, level: '', count: w.count, occurrences: [{ surface: w.word }] }))];
  if (words.length) {
    out.appendChild(h('div', { class: 'adapt-actions' },
      h('button', { type: 'button', class: 'btn small', onclick: () => ctx.copyWordList(words, target) }, t('Copy word list')),
      h('span', { class: 'fine inline' }, t('Every word above {level} and every word not on the CEFR lists, with its level and count, to paste into a glossary or a spreadsheet.', { level: target }))));
  }
  return out;
}
