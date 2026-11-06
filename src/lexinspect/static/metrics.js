// The headline numbers of one analysis, in a fixed order, so two analyses can
// be set side by side: a revision against the version before it, or many texts
// in one table. Each metric says which direction makes a text easier, so a
// change can be read at a glance without implying that easier is better.

const Metrics = (() => {
  function band95(r, withPhrases = false) {
    const src = withPhrases ? r.phrase?.integrated_profile : r.bnc_coca;
    if (!src) return null;
    return Insights.bandAt(src.per_band, 95);
  }

  const LEVEL_RANK = { A1: 1, A2: 2, B1: 3, B2: 4, C1: 5, C2: 6 };

  /** The level estimate's expected rank, A1 = 1 … C2 = 6: moves with the
   *  text even when the most likely level stays the same. */
  function expectedLevel(level) {
    const p = level?.probabilities;
    if (!p) return null;
    let sum = 0;
    let total = 0;
    for (const [l, v] of Object.entries(p)) {
      if (!LEVEL_RANK[l]) continue;
      sum += LEVEL_RANK[l] * v;
      total += v;
    }
    return total ? sum / total : null;
  }

  /** [{key, label, value, d, easier: 'lower'|'higher'|null, unit, text?}].
   *  Labels are translated when this is called. `text`, when set, is shown in
   *  place of the value (the estimated level's letter). */
  function of(r, { target } = {}) {
    const rd = r.readability;
    const list = [
      { key: 'words', label: t('Words'), value: rd.counts.words, d: 0, easier: null },
      { key: 'sentences', label: t('Sentences'), value: rd.counts.sentences, d: 0, easier: null },
      { key: 'wps', label: t('Words per sentence'), value: rd.averages.words_per_sentence, d: 1, easier: 'lower' },
      { key: 'grade', label: t('Readability grade'), value: rd.scores.text_standard, d: 1, easier: 'lower' },
      { key: 'fre', label: t('Flesch Reading Ease'), value: rd.scores.flesch_reading_ease, d: 0, easier: 'higher' },
    ];
    if (r.level?.applicable) list.push({ key: 'level', label: t('Estimated level'), value: expectedLevel(r.level), text: r.level.level, d: 1, easier: 'lower' });
    if (target) list.push({ key: 'above', label: t('Words above {level}', { level: target }), value: Math.max(0, 100 - Insights.knownAt(r, target)), d: 1, unit: '%', easier: 'lower' });
    list.push(
      { key: 'b2plus', label: t('Words at B2 or above'), value: ['B2', 'C1', 'C2'].reduce((s, l) => s + r.cefr.per_level[l].coverage_pct, 0), d: 1, unit: '%', easier: 'lower' },
      { key: 'band95', label: t('Word families for 95% coverage'), value: band95(r), d: 0, unit: 'K', easier: 'lower' },
      { key: 'band95p', label: t('Word families for 95% coverage, counting phrases'), value: band95(r, true), d: 0, unit: 'K', easier: 'lower' },
      { key: 'offlist', label: t('Off-list words'), value: r.bnc_coca.counts.off_list_tokens, d: 0, easier: 'lower' },
      { key: 'awl', label: t('AWL coverage'), value: r.awl.coverage_pct, d: 1, unit: '%', easier: null },
      { key: 'phrases', label: t('PHRASE List expressions'), value: r.phrase.counts.total_hits, d: 0, easier: null },
      { key: 'mtld', label: t('MTLD'), value: r.diversity.scores.mtld, d: 0, easier: null },
    );
    if (r.syntax?.indices) {
      list.push(
        { key: 'mlt', label: t('Mean length of T-unit'), value: r.syntax.indices.mlt, d: 1, easier: 'lower' },
        { key: 'cs', label: t('Clauses per sentence'), value: r.syntax.indices.c_s, d: 2, easier: 'lower' },
      );
    }
    list.push(
      { key: 'md', label: t('Metadiscourse markers per 1,000 words'), value: r.metadiscourse.density_per_1000, d: 0, easier: null },
      { key: 'spelling', label: t('Spelling issues'), value: r.errors.counts.errors_total, d: 0, easier: 'lower' },
    );
    return list;
  }

  /** Word-set overlap of two texts, 0–1: is the new text a revision of the old? */
  function overlap(a, b) {
    const words = (s) => new Set((s.toLowerCase().match(/[\p{L}\p{N}]+(?:['’][\p{L}]+)?/gu) || []));
    const A = words(a);
    const B = words(b);
    if (!A.size || !B.size) return 0;
    let shared = 0;
    for (const w of A) if (B.has(w)) shared++;
    return shared / Math.min(A.size, B.size);
  }

  /** The metrics that changed between two analyses, with direction. */
  function changes(before, after, opts) {
    const a = of(before, opts);
    const b = new Map(of(after, opts).map((m) => [m.key, m]));
    const out = [];
    for (const m of a) {
      const n = b.get(m.key);
      if (!n || m.value == null || n.value == null) continue;
      const delta = n.value - m.value;
      const shown = (v) => Number(v.toFixed(m.d));
      // A metric shown as text (the estimated level) changes when its text does;
      // its value still gives the direction.
      if (m.text != null || n.text != null ? m.text === n.text : shown(m.value) === shown(n.value)) continue;
      const dir = delta === 0 ? null : m.easier == null ? null : (delta < 0) === (m.easier === 'lower') ? 'easier' : 'harder';
      out.push({ ...m, before: m.value, after: n.value, beforeText: m.text, afterText: n.text, delta, dir });
    }
    return out;
  }

  function format(m, v, text) {
    if (text) return text;
    if (v == null) return '–';
    if (m.unit === '%') return pct(v, m.d);
    // Band codes (3K) stay as they are in every language.
    if (m.unit === 'K') return `${num(v, m.d)}K`;
    return num(v, m.d);
  }

  return { of, changes, overlap, format };
})();
