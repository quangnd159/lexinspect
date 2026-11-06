// "What stands out": the few findings in an analysis a teacher or writer would
// act on, in plain words, each linked to where it is in the text.
//
// Every finding is derived from numbers shown elsewhere; nothing here is a
// new measure. A rule only fires when its finding is worth reading, so a
// clean, easy text gets a short list. Titles, bodies and action labels are
// translated when computed.

const Insights = (() => {
  const LEVEL_RANK = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };

  function bandAt(perBand, threshold) {
    for (const [band, v] of Object.entries(perBand)) if (v.cumulative_coverage_with_supplementary_pct >= threshold) return Number(band);
    return null;
  }

  /** Share of lexical tokens a reader at `target` is likely to know: every
   *  listed word at or below the level, plus names. Words the spell checker
   *  flags are left out of the count: they are off every list only because
   *  of the typo, and would otherwise read as hard vocabulary. */
  function knownAt(r, target) {
    const cefr = r.cefr;
    const bad = misspelt(r);
    const typos = cefr.off_list.reduce((s, w) => s + (bad.has(w.word.toLowerCase()) ? w.count : 0), 0);
    const n = cefr.counts.content_tokens - typos;
    if (n <= 0) return null;
    let known = cefr.counts.proper_noun_tokens;
    for (const l of ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']) {
      known += cefr.per_level[l].tokens;
      if (l === target) break;
    }
    return (known / n) * 100;
  }

  /** Laufer & Ravenhorst-Kalovski (2010): 95% of running words known is the
   *  minimal threshold for reading comprehension, 98% the optimal one. They
   *  measured known word families; on CEFR-list coverage the thresholds apply
   *  by analogy. `label` and `note` are translated at call time. */
  function fit(pctKnown) {
    if (pctKnown == null) return null;
    if (pctKnown >= 98) return { key: 'easy', label: t('Comfortable'), note: t('That reaches 98%, the coverage linked to reading without help.') };
    if (pctKnown >= 95) return { key: 'ok', label: t('Manageable with support'), note: t('That is between 95% and 98%, so expect to gloss or pre-teach some words.') };
    if (pctKnown >= 90) return { key: 'hard', label: t('Challenging'), note: t('That is below 95%, the minimum coverage usually linked to adequate comprehension.') };
    return { key: 'vhard', label: t('Too hard without adapting'), note: t('That is well below 95%, the minimum coverage usually linked to adequate comprehension.') };
  }

  /** The target-fit finding's title, one whole message per verdict. */
  function fitTitle(key, level) {
    if (key === 'easy') return t('For {level} readers: comfortable', { level });
    if (key === 'ok') return t('For {level} readers: manageable with support', { level });
    if (key === 'hard') return t('For {level} readers: challenging', { level });
    return t('For {level} readers: too hard without adapting', { level });
  }

  function misspelt(r) {
    const s = new Set();
    for (const list of [r.errors?.errors ?? [], r.errors?.variant_mismatches ?? []]) for (const e of list) s.add(e.surface.toLowerCase());
    return s;
  }

  /** Content words above the readers' level that recur: the usual candidates
   *  for pre-teaching or a glossary. Without a target, C1 and above. */
  function preTeach(r, target) {
    const bad = misspelt(r);
    const from = target ? LEVEL_RANK[target] + 1 : 5;
    const out = [];
    for (const [level, words] of Object.entries(r.cefr.words_by_level)) {
      if (LEVEL_RANK[level] < from) continue;
      for (const w of words) if (w.count >= 2 && !bad.has(w.word.toLowerCase())) out.push({ ...w, level });
    }
    for (const w of r.cefr.off_list) if (w.count >= 2 && !bad.has(w.word.toLowerCase())) out.push({ ...w, level: null });
    return out.sort((a, b) => b.count - a.count || (LEVEL_RANK[b.level] ?? 7) - (LEVEL_RANK[a.level] ?? 7)).slice(0, 6);
  }

  /**
   * @returns [{tone, title, body, action?: {label, run}}]
   * `tone` is 'note' (neutral), 'flag' (worth a look) or 'good'.
   */
  function compute(r, { target, go, flash, spansOfWord, previous } = {}) {
    const out = [];
    const words = r.readability.counts.words;

    if (words < 100) {
      out.push({
        tone: 'flag',
        title: t('Short text'),
        body: tn(words,
          'At {n} word, readability, diversity and level estimates change a lot with small edits. Treat them as indicative. To compare texts, use at least 100 words, ideally 300 or more.',
          'At {n} words, readability, diversity and level estimates change a lot with small edits. Treat them as indicative. To compare texts, use at least 100 words, ideally 300 or more.'),
      });
    }

    // Target fit.
    if (target) {
      const known = knownAt(r, target);
      const f = fit(known);
      if (f) {
        out.push({
          tone: f.key === 'easy' || f.key === 'ok' ? 'good' : 'flag',
          title: fitTitle(f.key, target),
          body: t('{pct} of the words are {level} or below on the CEFR lists, or are names. {fit} The 95% and 98% thresholds were measured on known word families (Laufer & Ravenhorst-Kalovski 2010), so for CEFR levels they are an approximation.', { pct: pct(known), level: target, fit: f.note }),
          action: { label: t('See the words above {level}', { level: target }), run: () => go('adapt') },
        });
      }
    }

    // Spelling first: it changes every other count.
    const e = r.errors;
    if (e?.counts.errors_total) {
      const examples = listOf(e.errors.slice(0, 3).map((x) => quoted(x.surface)));
      out.push({
        tone: 'flag',
        title: tn(e.counts.errors_total, '{n} possible misspelling', '{n} possible misspellings'),
        body: e.errors.length > 3
          ? t('A misspelt word matches no word list, so misspellings inflate the off-list counts. They include {words}.', { words: examples })
          : t('A misspelt word matches no word list, so misspellings inflate the off-list counts. Check {words}.', { words: examples }),
        action: { label: t('Review spelling'), run: () => go('spelling') },
      });
    }

    // Phrases change the frequency profile (Martinez & Schmitt 2012).
    const ip = r.phrase?.integrated_profile;
    if (ip?.counts.phrase_tokens) {
      const w95 = bandAt(r.bnc_coca.per_band, 95);
      const p95 = bandAt(ip.per_band, 95);
      const n = r.phrase.counts.total_hits;
      // PHRASE List bands and BNC/COCA word bands come from different corpora,
      // so a one-band gap is within noise: only gaps of two bands or more count.
      const rarer = (r.phrase.expressions || []).filter((x) => x.word_band != null && x.k_band - x.word_band >= 2);
      if (w95 != null && p95 != null && p95 > w95) {
        out.push({
          tone: 'flag',
          title: t('The phrases make the text harder than its words suggest'),
          body: tn(n,
            'Counted word by word, 95% coverage needs the first {wordBand}K word families. Counting its {n} PHRASE List expression as a unit, as Martinez & Schmitt’s integrated list does, it needs {phraseBand}K.',
            'Counted word by word, 95% coverage needs the first {wordBand}K word families. Counting its {n} PHRASE List expressions as units, as Martinez & Schmitt’s integrated list does, it needs {phraseBand}K.',
            { wordBand: num(w95), phraseBand: num(p95) }),
          action: { label: t('Compare the profiles'), run: () => go('vocabulary', 'bnc', { withPhrases: true }) },
        });
      } else if (rarer.length) {
        const items = listOf(rarer.slice(0, 3).map((x) =>
          t('{phrase} ({phraseBand}K, words up to {wordBand}K)', { phrase: quoted(phraseName(x)), phraseBand: num(x.k_band), wordBand: num(x.word_band) })));
        let body;
        if (rarer.length === 1) body = t('Learners who know every word may still miss this phrase, ranked at least two bands above its rarest word: {items}.', { items });
        else if (rarer.length <= 3) body = t('Learners who know every word may still miss these phrases, each ranked at least two bands above its rarest word: {items}.', { items });
        else {
          body = tn(rarer.length,
            'Learners who know every word may still miss {n} phrase ranked at least two bands above its rarest word, among them {items}.',
            'Learners who know every word may still miss {n} phrases ranked at least two bands above their rarest word, among them {items}.',
            { items });
        }
        out.push({ tone: 'note', title: t('Phrases rarer than their words'), body, action: { label: t('Show the phrases'), run: () => go('phrase') } });
      }
    }

    // Words worth pre-teaching.
    const pt = preTeach(r, target);
    if (pt.length) {
      const examples = listOf(pt.map((w) =>
        w.level
          ? t('{word} ({level}) ×{count}', { word: quoted(w.word), level: w.level, count: num(w.count) })
          : t('{word} (not on the lists) ×{count}', { word: quoted(w.word), count: num(w.count) })));
      out.push({
        tone: 'note',
        title: target ? t('Recurring words above {level}', { level: target }) : t('Recurring hard words'),
        body: t('Worth pre-teaching or glossing, because readers meet them more than once: {words}.', { words: examples }),
        action: { label: t('Show them in the text'), run: () => flash(pt.flatMap((w) => spansOfWord(w.word)), 'cefr') },
      });
    }

    // Sentences.
    const syn = r.syntax;
    if (syn?.sentences?.length) {
      const long = syn.sentences.filter((s) => s.words > 30);
      const longest = syn.sentences.reduce((a, b) => (b.words > a.words ? b : a));
      if (long.length) {
        out.push({
          tone: 'flag',
          title: tn(long.length, '{n} sentence over 30 words', '{n} sentences over 30 words'),
          body: tn(longest.clauses,
            'The longest has {words} words and {n} clause. Long sentences make every readability formula rate a text harder, and splitting one is often the quickest way to simplify it.',
            'The longest has {words} words and {n} clauses. Long sentences make every readability formula rate a text harder, and splitting one is often the quickest way to simplify it.',
            { words: num(longest.words) }),
          action: { label: t('Show long sentences'), run: () => go('sentences') },
        });
      }
      const passive = syn.counts?.passive_clauses ?? 0;
      const clauses = syn.counts?.clauses ?? 0;
      if (clauses >= 10 && passive / clauses >= 0.25) {
        out.push({
          tone: 'note',
          title: t('{pct} of clauses are passive', { pct: pct((passive / clauses) * 100, 0) }),
          body: tn(passive,
            '{n} passive clause out of {total}. Passives are usual in scientific writing; in other genres, learners often find active clauses easier.',
            '{n} passive clauses out of {total}. Passives are usual in scientific writing; in other genres, learners often find active clauses easier.',
            { total: num(clauses) }),
          action: { label: t('Show sentences'), run: () => go('sentences') },
        });
      }
    }

    // Academic register.
    const awl = r.awl.coverage_pct;
    if (words >= 100 && awl >= 8) {
      out.push({
        tone: 'note',
        title: t('Academic vocabulary: {pct} of words on the AWL', { pct: pct(awl) }),
        body: t('AWL words typically make up about 10% of academic prose and 1–2% of fiction, so expect this text to read as academic.'),
        action: { label: t('Show AWL words'), run: () => go('vocabulary', 'awl') },
      });
    }

    // Changes since the previous version of this text.
    if (previous) out.unshift(...previous);
    return out;
  }

  return { compute, knownAt, fit, bandAt };
})();
