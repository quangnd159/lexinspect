// Exports, built in the browser from the response already on screen: nothing is
// sent anywhere and nothing is re-analysed. Every file carries the same
// provenance (version, model, variant, time, a SHA-256 of the text) so a number
// can be traced back to the run that produced it.
//
// Plain functions of (response, meta) -> string or bytes; app.js owns the
// buttons. Column names are part of the output: once published, don't rename
// them, only add new ones at the end, or stacked summary rows stop lining up.

const Export = (() => {
  const SITE = 'https://lexinspect.dqnotes.com';
  const REPO = 'https://github.com/quangnd159/lexinspect';

  const analysedText = (d) => d.input.normalised_text ?? d.submitted;

  const hashes = new WeakMap();

  /** Provenance shared by every export. */
  async function meta(d) {
    if (!hashes.has(d)) {
      try {
        const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(d.submitted));
        hashes.set(d, [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join(''));
      } catch {} // insecure context (plain-http self-hosting): leave it blank
    }
    return metaNow(d);
  }

  /** The same, synchronously, with the hash if `meta` has already computed it. */
  function metaNow(d) {
    const now = new Date();
    return { exportedAt: now.toISOString().replace(/\.\d+Z$/, 'Z'), date: now, sha256: hashes.get(d) ?? '' };
  }

  function bandFor(perBand, threshold) {
    for (const [band, v] of Object.entries(perBand)) if (v.cumulative_coverage_with_supplementary_pct >= threshold) return Number(band);
    return null;
  }

  // ---- the summary row: one stable column per measure ---------------------------

  const COLUMNS = [];
  const col = (name, get, desc) => COLUMNS.push({ name, get, desc });
  const R = (d) => d.results;

  col('lexinspect_version', (d) => d.provenance?.lexinspect, 'lexinspect version that produced every number in the row. Output is deterministic within a version; cite it.');
  col('schema_version', (d) => d.schema_version, 'Version of the JSON output schema.');
  col('spacy_model', (d) => d.provenance?.spacy_model, 'spaCy model used for tokenisation, tagging and parsing.');
  col('spelling_variant', (d) => R(d).errors.variant, 'Spelling variety checked: gb (British) or us (American).');
  col('exported_at', (d, m) => m.exportedAt, 'When this file was exported, UTC, ISO 8601.');
  col('text_sha256', (d, m) => m.sha256, 'SHA-256 of the text as submitted (UTF-8, leading and trailing whitespace removed). Matches the same text analysed again; identifies a text without storing it.');
  col('text_excerpt', (d) => excerpt(d.submitted), 'The first 80 characters of the text, to help you recognise the row.');

  col('words', (d) => R(d).readability.counts.words, 'Orthographic words, including numbers (don’t, well-known and cannot are one word each).');
  col('sentences', (d) => R(d).readability.counts.sentences, 'Sentences.');
  col('characters', (d) => R(d).readability.counts.characters, 'Characters, not counting spaces.');
  col('characters_with_spaces', (d) => R(d).readability.counts.characters_with_spaces, 'Characters, counting spaces.');
  col('syllables', (d) => R(d).readability.counts.syllables, 'Syllables (CMUdict, with a rule-based fallback).');
  col('polysyllable_words', (d) => R(d).readability.counts.polysyllable_words, 'Words of three or more syllables.');
  col('long_words', (d) => R(d).readability.counts.long_words, 'Words of seven or more letters.');
  col('difficult_words', (d) => R(d).readability.counts.difficult_words, 'Words outside the Dale–Chall list of 3,000 familiar words.');
  col('reading_time_seconds', (d) => R(d).readability.counts.reading_time_seconds, 'Estimated silent reading time in seconds.');
  col('words_per_sentence', (d) => R(d).readability.averages.words_per_sentence, 'Mean words per sentence.');
  col('syllables_per_word', (d) => R(d).readability.averages.syllables_per_word, 'Mean syllables per word.');
  col('characters_per_word', (d) => R(d).readability.averages.characters_per_word, 'Mean characters per word.');

  for (const f of FORMULAS) col(`readability_${f.key}`, (d) => R(d).readability.scores[f.key], `${f.name} (${f.ref}). ${f.note}`);
  col('readability_median_grade', (d) => R(d).readability.scores.text_standard, 'Median of the eight grade estimates (US school grade).');
  col('readability_reliable', (d) => R(d).readability.reliability.reliable, 'FALSE when the text is too short for the formulas to be stable (under about 100 words).');

  col('diversity_tokens', (d) => R(d).diversity.counts.tokens, 'Tokens counted for lexical diversity (words, not counting numbers).');
  col('diversity_types', (d) => R(d).diversity.counts.types, 'Distinct word types among those tokens.');
  for (const m of DIVERSITY) col(`diversity_${m.key}`, (d) => R(d).diversity.scores[m.key], `${m.name}${m.ref ? ` (${m.ref})` : ''}. ${m.note} Blank when the text is too short.`);

  col('cefr_coverage_pct', (d) => R(d).cefr.coverage_pct, 'Percentage of words with a CEFR level in CEFR-J 1.5 / Octanove.');
  for (const l of LEVELS) col(`cefr_${l.toLowerCase()}_pct`, (d) => R(d).cefr.per_level[l].coverage_pct, `Percentage of words at CEFR ${l}.`);
  col('cefr_proper_noun_tokens', (d) => R(d).cefr.counts.proper_noun_tokens, 'Proper nouns (given no level).');
  col('cefr_off_list_tokens', (d) => R(d).cefr.counts.off_list_tokens, 'Words in neither CEFR list.');
  col('cefr_dominant_level', (d) => R(d).cefr.dominant_level, 'CEFR level with the most words.');
  col('cefr_highest_level_present', (d) => R(d).cefr.highest_level_present, 'Highest CEFR level of any word.');
  col('cefr_estimated_level_95th', (d) => R(d).cefr.estimated_level_95th, 'Lowest level whose cumulative coverage reaches 95%. A profile of the vocabulary, not of the writer.');

  col('bnc_coverage_pct', (d) => R(d).bnc_coca.coverage_pct, 'Percentage of words in BNC/COCA bands 1–25.');
  col('bnc_coverage_with_supplementary_pct', (d) => R(d).bnc_coca.coverage_with_supplementary_pct, 'As above, also counting proper names, marginal words, transparent compounds and acronyms.');
  col('bnc_band_95', (d) => bandFor(R(d).bnc_coca.per_band, 95), 'Smallest band (in 1,000 word families) giving 95% coverage, counting the supplementary lists. Blank if not reached.');
  col('bnc_band_98', (d) => bandFor(R(d).bnc_coca.per_band, 98), 'Smallest band giving 98% coverage, counting the supplementary lists. Blank if not reached.');
  for (let k = 1; k <= 25; k++) col(`bnc_k${k}_pct`, (d) => R(d).bnc_coca.per_band[k]?.coverage_pct, `Percentage of words in BNC/COCA band ${k} (the ${k === 1 ? 'first' : `${k}th`} 1,000 families).`);
  col('bnc_proper_noun_tokens', (d) => R(d).bnc_coca.counts.proper_noun_tokens, 'Words on Nation’s proper-names list.');
  col('bnc_supplementary_tokens', (d) => R(d).bnc_coca.counts.supplementary_tokens, 'Words on the marginal, compound or acronym lists.');
  col('bnc_off_list_tokens', (d) => R(d).bnc_coca.counts.off_list_tokens, 'Words in no BNC/COCA list.');

  col('ngsl_pct', (d) => R(d).ngsl.coverage_pct.ngsl, 'Percentage of words in the New General Service List.');
  col('nawl_pct', (d) => R(d).ngsl.coverage_pct.nawl, 'Percentage of words in the New Academic Word List.');
  col('ngsl_plus_nawl_pct', (d) => R(d).ngsl.coverage_pct.ngsl_plus_nawl, 'NGSL and NAWL together.');
  col('ngsl_proper_nouns_pct', (d) => R(d).ngsl.coverage_pct.proper_nouns, 'Percentage of words that are proper nouns.');
  col('ngsl_off_list_pct', (d) => R(d).ngsl.coverage_pct.off_list, 'Percentage of words in neither list.');

  col('awl_pct', (d) => R(d).awl.coverage_pct, 'Percentage of words in Coxhead’s Academic Word List.');
  col('awl_tokens', (d) => R(d).awl.counts.awl_tokens, 'AWL words.');
  col('awl_families', (d) => R(d).awl.counts.awl_families, 'Distinct AWL word families.');
  for (let s = 1; s <= 10; s++) col(`awl_sublist${s}_pct`, (d) => R(d).awl.per_sublist[s]?.coverage_pct, `Percentage of words in AWL sublist ${s}.`);

  col('phrase_hits', (d) => R(d).phrase.counts.total_hits, 'PHRASE-list expressions found (Martinez & Schmitt 2012).');
  col('phrase_unique', (d) => R(d).phrase.counts.unique_phrases, 'Distinct PHRASE-list expressions.');
  col('phrase_per_1000_words', (d) => R(d).phrase.counts.hits_per_1000_words, 'Expressions per 1,000 words.');
  for (let k = 1; k <= 5; k++) col(`phrase_k${k}_hits`, (d) => R(d).phrase.hits_per_k_band[k], `Expressions in frequency band K${k}.`);

  col('md_hits', (d) => R(d).metadiscourse.counts.total_hits, 'Metadiscourse markers (Hyland 2005).');
  col('md_per_1000_words', (d) => R(d).metadiscourse.density_per_1000, 'Markers per 1,000 words.');
  col('md_interactive_per_1000_words', (d) => R(d).metadiscourse.per_dimension.interactive.density_per_1000, 'Interactive markers per 1,000 words.');
  col('md_interactional_per_1000_words', (d) => R(d).metadiscourse.per_dimension.interactional.density_per_1000, 'Interactional markers per 1,000 words.');
  for (const [key, c] of Object.entries(MD_CATEGORIES)) {
    col(`md_${key}_hits`, (d) => R(d).metadiscourse.per_category[key].hits, `${c.label}: ${c.note.toLowerCase()} (${c.eg}).`);
    col(`md_${key}_per_1000_words`, (d) => R(d).metadiscourse.per_category[key].density_per_1000, `${c.label} per 1,000 words.`);
  }

  col('spelling_errors', (d) => R(d).errors.counts.errors_total, 'Words the dictionary does not know (Hunspell, LibreOffice dictionaries).');
  col('spelling_unique_errors', (d) => R(d).errors.counts.unique_errors, 'Distinct misspelt forms.');
  col('spelling_errors_per_100_words', (d) => R(d).errors.rates.errors_per_100_words, 'Errors per 100 words.');
  col('spelling_other_variety', (d) => R(d).errors.counts.variant_mismatches, 'Words correct only in the other variety (color in UK mode).');
  col('spelling_unknown_names', (d) => R(d).errors.counts.unknown_names, 'Capitalised words the dictionary does not know, usually names. Not counted as errors.');

  col('pos_tokens', (d) => R(d).tagger.counts.total_tokens, 'Tokens tagged, including punctuation.');
  for (const [tag, label] of Object.entries(UPOS)) col(`pos_${tag.toLowerCase()}`, (d) => R(d).tagger.upos_distribution[tag] ?? 0, `${label} (Universal POS tag ${tag}).`);

  function summaryRow(d, m) {
    return COLUMNS.map((c) => {
      try {
        return c.get(d, m) ?? null;
      } catch {
        return null; // a module missing from a partial response
      }
    });
  }

  function excerpt(text, n = 80) {
    const flat = text.replace(/\s+/g, ' ').trim();
    return flat.length > n ? `${flat.slice(0, n - 1).trimEnd()}…` : flat;
  }

  // ---- the word table: one row per word -----------------------------------------

  const WORD_COLUMNS = [
    ['index', 'Position of the word in the text, from 1.'],
    ['start', 'Character offset where the word starts (0-based, in the analysed text).'],
    ['end', 'Character offset just after the word.'],
    ['word', 'The word as written.'],
    ['cefr', 'CEFR level for its part of speech; proper for names; blank if in neither list.'],
    ['bnc_band', 'BNC/COCA band 1–25; proper or supplementary for Nation’s extra lists; blank if in no list.'],
    ['awl_sublist', 'AWL sublist 1–10; blank if not an AWL word.'],
    ['ngsl', 'ngsl, nawl or proper; blank if in neither list.'],
    ['spelling', 'error, other_variety or unknown_name when flagged by the spell check.'],
    ['phrase', 'The PHRASE-list expression this word is part of, if any.'],
    ['metadiscourse', 'Metadiscourse category of the marker this word is part of, if any.'],
  ];

  function wordRows(d) {
    const text = analysedText(d);
    const r = d.results;
    const idx = (r.profile.columns || []).reduce((o, c, i) => ((o[c] = i), o), {});
    const covering = (list) => {
      const marks = [];
      for (const [spans, label] of list) for (const [a, b] of spans) marks.push([a, b, label]);
      return (a, b) => marks.find(([x, y]) => a >= x && b <= y)?.[2] ?? null;
    };
    const spelling = covering([
      ...r.errors.errors.map((e) => [e.spans, 'error']),
      ...r.errors.variant_mismatches.map((e) => [e.spans, 'other_variety']),
      ...r.errors.unknown_names.map((e) => [e.spans || [], 'unknown_name']),
    ]);
    const phrase = covering(r.phrase.hits.map((p) => [[p.span], p.phrase]));
    const md = covering(r.metadiscourse.hits.map((x) => [[x.span], x.category]));
    return r.profile.rows.map((row, i) => {
      const [a, b] = [row[idx.start], row[idx.end]];
      return [i + 1, a, b, text.slice(a, b), row[idx.cefr], row[idx.bnc], row[idx.awl], row[idx.ngsl], spelling(a, b), phrase(a, b), md(a, b)];
    });
  }

  // ---- CSV ----------------------------------------------------------------------

  // RFC 4180 with a UTF-8 BOM so Excel reads accents and curly quotes correctly;
  // readr, pandas and data.table skip the BOM. Booleans are TRUE/FALSE, missing
  // values are empty.
  function csvCell(v) {
    if (v == null) return '';
    if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
    let s = String(v);
    // A text cell starting with = + - @ would run as a formula in a spreadsheet.
    if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = `'${s}`;
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }
  const csv = (header, rows) => '﻿' + [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n';

  const summaryCsv = (d, m) => csv(COLUMNS.map((c) => c.name), [summaryRow(d, m)]);
  const wordsCsv = (d) => csv(WORD_COLUMNS.map((c) => c[0]), wordRows(d));

  // ---- workbook -----------------------------------------------------------------

  function sheets(d, m) {
    const r = d.results;
    const out = [];
    const sheet = (name, header, rows, widths) => out.push({ name, header, rows, widths });

    const row = summaryRow(d, m);
    sheet('Summary', ['Column', 'Value', 'What it is'], COLUMNS.map((c, i) => [c.name, row[i], c.desc]), [34, 22, 90]);
    sheet('Words', WORD_COLUMNS.map((c) => c[0]), wordRows(d), [7, 7, 7, 18, 8, 13, 11, 8, 13, 26, 20]);

    sheet('Readability', ['Formula', 'Score', 'Scale', 'Reference', 'Note'],
      [...FORMULAS.map((f) => [f.name, r.readability.scores[f.key], f.kind === 'ease' ? '0–100, higher is easier' : f.kind === 'dale' ? 'Dale–Chall score' : 'US grade', f.ref, f.note]),
        ['Median grade', r.readability.scores.text_standard, 'US grade', '', 'Median of the eight grade estimates.']],
      [20, 9, 22, 22, 80]);

    sheet('CEFR', ['Level', 'Words', 'Lemmas', 'Coverage %', 'Cumulative %'],
      LEVELS.map((l) => { const v = r.cefr.per_level[l]; return [l, v.tokens, v.lemmas, v.coverage_pct, v.cumulative_coverage_pct]; }), [8, 9, 9, 12, 13]);

    sheet('BNC-COCA', ['Band (1,000 families)', 'Words', 'Headwords', 'Coverage %', 'Cumulative %', 'Cumulative with supplementary %'],
      Object.entries(r.bnc_coca.per_band).map(([k, v]) => [Number(k), v.tokens, v.headwords, v.coverage_pct, v.cumulative_coverage_pct, v.cumulative_coverage_with_supplementary_pct]), [20, 9, 11, 12, 13, 30]);

    sheet('AWL', ['Sublist', 'Words', 'Families', 'Coverage %'],
      Object.entries(r.awl.per_sublist).map(([k, v]) => [Number(k), v.tokens, v.families, v.coverage_pct]), [9, 9, 10, 12]);

    const lists = [];
    for (const l of LEVELS) for (const w of r.cefr.words_by_level[l] || []) lists.push(['CEFR', l, w.word, w.count]);
    for (const w of r.cefr.off_list || []) lists.push(['CEFR', 'off-list', w.word, w.count]);
    for (const w of r.bnc_coca.proper_nouns || []) lists.push(['BNC/COCA', 'proper names', w.word, w.count]);
    for (const w of r.bnc_coca.off_list || []) lists.push(['BNC/COCA', 'off-list', w.word, w.count]);
    for (const w of r.ngsl.nawl_words || []) lists.push(['NGSL/NAWL', 'NAWL', w.word, w.count]);
    for (const w of r.ngsl.off_list || []) lists.push(['NGSL/NAWL', 'off-list', w.word, w.count]);
    for (const f of r.awl.families_detail || []) lists.push(['AWL', `sublist ${f.sublist}`, f.headword, f.tokens]);
    sheet('Word lists', ['List', 'Group', 'Word', 'Count'], lists, [12, 14, 22, 8]);

    sheet('Phrases', ['Expression', 'As written', 'Sense', 'K band', 'Rank', 'Start', 'End'],
      r.phrase.hits.map((p) => [p.phrase, p.surface, p.sense, p.k_band, p.rank, p.span[0], p.span[1]]), [26, 26, 20, 8, 8, 8, 8]);

    sheet('Metadiscourse', ['Category', 'Dimension', 'Markers', 'Distinct', 'Per 1,000 words', 'Function', 'Examples'],
      Object.entries(r.metadiscourse.per_category).map(([k, v]) => [MD_CATEGORIES[k]?.label ?? k, v.dimension, v.hits, v.unique_markers, v.density_per_1000, MD_CATEGORIES[k]?.note, MD_CATEGORIES[k]?.eg]),
      [20, 14, 9, 9, 15, 34, 34]);
    sheet('Metadiscourse hits', ['Category', 'Dimension', 'Marker', 'As written', 'Start', 'End'],
      r.metadiscourse.hits.map((x) => [MD_CATEGORIES[x.category]?.label ?? x.category, x.dimension, x.marker, x.surface, x.span[0], x.span[1]]), [20, 14, 20, 20, 8, 8]);

    const sp = [];
    for (const [list, kind] of [[r.errors.errors, 'error'], [r.errors.variant_mismatches, 'other variety'], [r.errors.unknown_names, 'unknown name']])
      for (const e of list) sp.push([kind, e.surface, e.count, (e.suggestions || []).join(', ')]);
    sheet('Spelling', ['Type', 'Word', 'Count', 'Suggestions'], sp, [14, 22, 8, 40]);

    const tier = (k) => Object.entries(r.diversity.tiers || {}).find(([, v]) => Array.isArray(v) && v.includes(k))?.[0] ?? '';
    sheet('Diversity', ['Measure', 'Value', 'Tier', 'Reference', 'Note'],
      DIVERSITY.map((x) => [x.name, r.diversity.scores[x.key], tier(x.key), x.ref, x.note]), [16, 10, 12, 30, 80]);

    sheet('Parts of speech', ['Tag set', 'Tag', 'Label', 'Tokens'], [
      ...Object.entries(r.tagger.upos_distribution).map(([t, n]) => ['Universal', t, UPOS[t] ?? t, n]),
      ...Object.entries(r.tagger.ptb_distribution).map(([t, n]) => ['Penn Treebank', t, '', n]),
    ], [16, 10, 16, 9]);

    sheet('Text', ['Paragraph', 'Text'], analysedText(d).split(/\n\s*\n/).map((p, i) => [i + 1, p.trim()]), [10, 120]);

    const notes = [
      ...(r.readability.reliability.notes || []).map((n) => ['Readability', n]),
      ...(r.cefr.estimate_reliability?.notes || []).map((n) => ['CEFR', n]),
      ...(r.diversity.note ? [['Diversity', r.diversity.note]] : []),
    ];
    sheet('About', ['Item', 'Value'], [
      ['Produced by', `lexinspect ${d.provenance?.lexinspect ?? ''} (${SITE})`],
      ['spaCy model', d.provenance?.spacy_model],
      ['Schema version', d.schema_version],
      ['Spelling variety', r.errors.variant === 'us' ? 'American (us)' : 'British (gb)'],
      ['Exported at (UTC)', m.exportedAt],
      ['Text SHA-256', m.sha256],
      ['Words / sentences', `${d.input.word_count} / ${d.input.sentence_count}`],
      ['Offsets', 'Start and End columns are character offsets into the analysed text, on the Text sheet.'],
      ...notes.map(([k, n]) => [`Note: ${k}`, n]),
      ['Cite (APA)', citation(d, m).apa],
      ['Also cite', 'The word lists and formulas you report on. Sources and licences: ' + `${SITE}/licences`],
    ], [22, 110]);
    return out;
  }

  // Minimal SpreadsheetML: inline strings, one bold header style, frozen first
  // row, autofilter.
  async function xlsx(d, m) {
    const list = sheets(d, m);
    const enc = new TextEncoder();
    const esc = (s) => String(s).replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f￾￿]/g, '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const colName = (i) => { let s = ''; for (i++; i; i = Math.floor((i - 1) / 26)) s = String.fromCharCode(65 + ((i - 1) % 26)) + s; return s; };
    const cell = (v, ref, style) => {
      const s = style ? ` s="${style}"` : '';
      if (v == null || v === '') return '';
      if (typeof v === 'number' && Number.isFinite(v)) return `<c r="${ref}"${s}><v>${v}</v></c>`;
      if (typeof v === 'boolean') return `<c r="${ref}"${s} t="b"><v>${v ? 1 : 0}</v></c>`;
      return `<c r="${ref}"${s} t="inlineStr"><is><t xml:space="preserve">${esc(String(v).slice(0, 32767))}</t></is></c>`;
    };
    const sheetXml = ({ header, rows, widths }) => {
      const all = [header, ...rows];
      const last = `${colName(header.length - 1)}${all.length}`;
      const data = all.map((r, i) => `<row r="${i + 1}">${r.map((v, j) => cell(v, `${colName(j)}${i + 1}`, i === 0 ? 1 : 2)).join('')}</row>`).join('');
      const cols = widths ? `<cols>${widths.map((w, i) => `<col min="${i + 1}" max="${i + 1}" width="${w}" customWidth="1"/>`).join('')}</cols>` : '';
      return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:${last}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>${cols}<sheetData>${data}</sheetData>${rows.length ? `<autoFilter ref="A1:${last}"/>` : ''}</worksheet>`;
    };
    const filters = list
      .map((s, i) => (s.rows.length ? `<definedName name="_xlnm._FilterDatabase" localSheetId="${i}" hidden="1">'${esc(s.name)}'!$A$1:$${colName(s.header.length - 1)}$${s.rows.length + 1}</definedName>` : ''))
      .join('');
    const files = [
      ['[Content_Types].xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>${list.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`],
      ['_rels/.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>`],
      ['docProps/core.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>lexinspect analysis</dc:title><dc:creator>lexinspect ${esc(d.provenance?.lexinspect ?? '')}</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">${m.exportedAt}</dcterms:created></cp:coreProperties>`],
      ['xl/workbook.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${list.map((s, i) => `<sheet name="${esc(s.name)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join('')}</sheets>${filters ? `<definedNames>${filters}</definedNames>` : ''}</workbook>`],
      ['xl/_rels/workbook.xml.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${list.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join('')}<Relationship Id="rId${list.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`],
      ['xl/styles.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF3F1EC"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>`],
      ...list.map((s, i) => [`xl/worksheets/sheet${i + 1}.xml`, sheetXml(s)]),
    ];
    return zip(files.map(([name, body]) => [enc.encode(name), enc.encode(body)]), m.date);
  }

  // ---- zip ----------------------------------------------------------------------
  // Deflated with the browser's CompressionStream where there is one, else stored.

  const CRC = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c >>> 0;
    }
    return t;
  })();
  function crc32(bytes) {
    let c = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) c = CRC[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  }

  async function deflate(data) {
    if (typeof CompressionStream === 'undefined') return null;
    try {
      const out = new Uint8Array(await new Response(new Blob([data]).stream().pipeThrough(new CompressionStream('deflate-raw'))).arrayBuffer());
      return out.length < data.length ? out : null;
    } catch {
      return null;
    }
  }

  async function zip(entries, date) {
    const time = (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1);
    const day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
    const chunks = [];
    const central = [];
    let offset = 0;
    for (const [name, data] of entries) {
      const crc = crc32(data);
      const packed = await deflate(data);
      const body = packed ?? data;
      const method = packed ? 8 : 0;
      const head = new DataView(new ArrayBuffer(30));
      head.setUint32(0, 0x04034b50, true);
      head.setUint16(4, 20, true);
      head.setUint16(6, 0x0800, true); // UTF-8 names
      head.setUint16(8, method, true); // 8 deflate, 0 stored
      head.setUint16(10, time, true);
      head.setUint16(12, day, true);
      head.setUint32(14, crc, true);
      head.setUint32(18, body.length, true);
      head.setUint32(22, data.length, true);
      head.setUint16(26, name.length, true);
      chunks.push(new Uint8Array(head.buffer), name, body);
      const dir = new DataView(new ArrayBuffer(46));
      dir.setUint32(0, 0x02014b50, true);
      dir.setUint16(4, 20, true);
      dir.setUint16(6, 20, true);
      dir.setUint16(8, 0x0800, true);
      dir.setUint16(10, method, true);
      dir.setUint16(12, time, true);
      dir.setUint16(14, day, true);
      dir.setUint32(16, crc, true);
      dir.setUint32(20, body.length, true);
      dir.setUint32(24, data.length, true);
      dir.setUint16(28, name.length, true);
      dir.setUint32(42, offset, true);
      central.push(new Uint8Array(dir.buffer), name);
      offset += 30 + name.length + body.length;
    }
    const size = central.reduce((s, c) => s + c.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true);
    end.setUint16(8, entries.length, true);
    end.setUint16(10, entries.length, true);
    end.setUint32(12, size, true);
    end.setUint32(16, offset, true);
    return new Blob([...chunks, ...central, new Uint8Array(end.buffer)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  }

  // ---- text for people ----------------------------------------------------------

  function citation(d, m) {
    const v = d.provenance?.lexinspect ?? '';
    const year = m.date.getUTCFullYear();
    const accessed = m.exportedAt.slice(0, 10);
    return {
      apa: `Nguyen, Q. (${year}). lexinspect (Version ${v}) [Computer software]. ${REPO}`,
      bibtex: `@software{lexinspect,\n  author  = {Nguyen, Quang},\n  title   = {lexinspect},\n  version = {${v}},\n  year    = {${year}},\n  url     = {${REPO}},\n  note    = {spaCy model ${d.provenance?.spacy_model ?? ''}; accessed ${accessed}}\n}`,
    };
  }

  function citationText(d, m) {
    const c = citation(d, m);
    return `${c.apa}\n\n${c.bibtex}\n\nAlso cite the word lists and formulas you report on: ${SITE}/licences\n`;
  }

  /** A few lines to paste into an email, a feedback form or a document. */
  function summaryText(d, m) {
    const r = d.results;
    const rd = r.readability;
    const grade = rd.scores.text_standard;
    const ease = rd.scores.flesch_reading_ease;
    const easeLabel = EASE_BANDS.find(([lo]) => ease >= lo)?.[1] ?? '';
    const b95 = bandFor(r.bnc_coca.per_band, 95);
    const b98 = bandFor(r.bnc_coca.per_band, 98);
    const b2 = ['B2', 'C1', 'C2'].reduce((s, l) => s + r.cefr.per_level[l].coverage_pct, 0);
    const div = r.diversity.scores;
    const e = r.errors;
    const errs = e.errors.slice(0, 8).map((x) => (x.suggestions?.[0] ? `${x.surface} → ${x.suggestions[0]}` : x.surface));
    const lines = [
      `Text analysis by lexinspect, ${m.date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`,
      `“${excerpt(d.submitted, 60)}”`,
      '',
      `Length: ${plural(rd.counts.words, 'word')}, ${plural(rd.counts.sentences, 'sentence')}, ${num(rd.averages.words_per_sentence, 1)} words per sentence, about ${duration(rd.counts.reading_time_seconds)} to read`,
      `Readability: grade ${num(grade, 1)} (${gradeLabel(grade).toLowerCase()}); Flesch Reading Ease ${num(ease)} (${easeLabel.toLowerCase()})${rd.reliability.reliable ? '' : '. Short text: indicative only'}`,
      `Vocabulary level: highest CEFR level ${r.cefr.highest_level_present ?? '–'}; ${pct(b2)} of words at B2 or above`,
      `Vocabulary needed: ${b95 ? `${b95},000` : 'more than 25,000'} word families for 95% coverage${b98 ? `, ${b98},000 for 98%` : ''}`,
      `Academic words: ${pct(r.awl.coverage_pct)} AWL, ${pct(r.ngsl.coverage_pct.nawl)} NAWL`,
      `Lexical diversity: ${div.mtld == null ? 'text too short to measure' : `MTLD ${num(div.mtld)}${div.vocd_d == null ? '' : `, vocd-D ${num(div.vocd_d)}`}`}`,
      `Phrases: ${plural(r.phrase.counts.total_hits, 'expression')} from the PHRASE list`,
      `Metadiscourse: ${plural(r.metadiscourse.counts.total_hits, 'marker')}, ${num(r.metadiscourse.density_per_1000)} per 1,000 words`,
      `Spelling (${e.variant === 'us' ? 'US' : 'UK'}): ${e.counts.errors_total ? `${plural(e.counts.errors_total, 'possible error')}: ${errs.join(', ')}${e.errors.length > errs.length ? ', …' : ''}` : 'no errors found'}`,
      '',
      `lexinspect ${d.provenance?.lexinspect ?? ''} · ${SITE}`,
    ];
    return lines.join('\n') + '\n';
  }

  /** The printable report: every section on paper, in reading order. DOM only. */
  function report(d, m) {
    const r = d.results;
    const rd = r.readability;
    const table = (head, rows, cls) =>
      h('table', { class: cls || null }, h('thead', {}, h('tr', {}, head.map((x) => h('th', {}, x)))), h('tbody', {}, rows.map((row) => h('tr', {}, row.map((x) => h('td', {}, x ?? '–'))))));
    const section = (title, ...body) => h('section', {}, h('h2', {}, title), body);
    const words = (list, n = 60) => (list.length ? `${list.slice(0, n).map((w) => (w.count > 1 ? `${w.word} ×${w.count}` : w.word)).join(', ')}${list.length > n ? `, … (${list.length - n} more)` : ''}` : 'None');
    const grade = rd.scores.text_standard;
    const ease = rd.scores.flesch_reading_ease;
    const b95 = bandFor(r.bnc_coca.per_band, 95);
    const b98 = bandFor(r.bnc_coca.per_band, 98);
    const lastBand = Math.max(b98 ?? 0, ...Object.entries(r.bnc_coca.per_band).filter(([, v]) => v.tokens).map(([k]) => Number(k)), 1);
    const notes = [...(rd.reliability.notes || []), ...(r.cefr.estimate_reliability?.notes || []), ...(r.diversity.note ? [r.diversity.note] : [])];
    const phraseCounts = Object.entries(r.phrase.phrase_frequency || {}).map(([word, count]) => ({ word: word.toLowerCase(), count }));
    const e = r.errors;

    return h('div', { class: 'report-body' },
      h('header', {},
        h('h1', {}, 'Text analysis'),
        h('p', { class: 'report-meta' },
          `lexinspect ${d.provenance?.lexinspect ?? ''} · ${m.date.toLocaleString('en-GB', { dateStyle: 'long', timeStyle: 'short' })} · ${e.variant === 'us' ? 'US' : 'UK'} spelling · ${SITE}`),
        h('p', { class: 'report-excerpt' }, `“${excerpt(d.submitted, 140)}”`)),
      h('div', { class: 'report-stats' },
        [['Words', num(rd.counts.words)], ['Sentences', num(rd.counts.sentences)], ['Words per sentence', num(rd.averages.words_per_sentence, 1)],
          ['Readability grade', num(grade, 1)], ['Highest CEFR level', r.cefr.highest_level_present ?? '–'], ['Families for 95%', b95 ? `${b95}K` : '25K+']]
          .map(([k, v]) => h('div', {}, h('span', {}, k), h('b', {}, v)))),
      notes.length ? h('div', { class: 'report-notes' }, h('b', {}, 'Read with care'), h('ul', {}, notes.map((n) => h('li', {}, n)))) : null,

      section('Readability',
        h('p', {}, `Median grade ${num(grade, 1)} (${gradeLabel(grade).toLowerCase()}). Flesch Reading Ease ${num(ease)}, ${(EASE_BANDS.find(([lo]) => ease >= lo)?.[1] ?? '').toLowerCase()}.`),
        table(['Formula', 'Score', 'Reference'], FORMULAS.map((f) => [f.name, num(rd.scores[f.key], f.kind === 'ease' ? 0 : 1), f.ref]))),

      section('Vocabulary: CEFR',
        table(['Level', 'Words', 'Share', 'Cumulative'], LEVELS.map((l) => { const v = r.cefr.per_level[l]; return [l, num(v.tokens), pct(v.coverage_pct), pct(v.cumulative_coverage_pct)]; })),
        h('p', { class: 'report-words' }, h('b', {}, 'B2 and above: '), words(['B2', 'C1', 'C2'].flatMap((l) => r.cefr.words_by_level[l] || [])))),

      section('Vocabulary: frequency (BNC/COCA)',
        h('p', {}, `${b95 ? `${b95},000` : 'More than 25,000'} word families give 95% coverage${b98 ? `; ${b98},000 give 98%` : '; 98% is not reached'}, counting names and Nation’s supplementary lists as known.`),
        table(['Band', 'Words', 'Share', 'Cumulative'], Object.entries(r.bnc_coca.per_band).filter(([k]) => Number(k) <= lastBand)
          .map(([k, v]) => [`${k}K`, num(v.tokens), pct(v.coverage_pct), pct(v.cumulative_coverage_with_supplementary_pct)])),
        h('p', { class: 'report-words' }, h('b', {}, 'In no list: '), words(r.bnc_coca.off_list || []))),

      section('Vocabulary: NGSL, NAWL and AWL',
        table(['List', 'Share of words'], [['NGSL', pct(r.ngsl.coverage_pct.ngsl)], ['NAWL', pct(r.ngsl.coverage_pct.nawl)], ['AWL', pct(r.awl.coverage_pct)]]),
        h('p', { class: 'report-words' }, h('b', {}, 'AWL families: '), words((r.awl.families_detail || []).map((f) => ({ word: f.headword, count: f.tokens }))))),

      section('Phrases',
        h('p', {}, `${plural(r.phrase.counts.total_hits, 'expression')} from the PHRASE list, ${num(r.phrase.counts.hits_per_1000_words, 1)} per 1,000 words.`),
        phraseCounts.length ? h('p', { class: 'report-words' }, words(phraseCounts)) : null),

      section('Metadiscourse',
        h('p', {}, `${plural(r.metadiscourse.counts.total_hits, 'marker')}, ${num(r.metadiscourse.density_per_1000, 1)} per 1,000 words.`),
        table(['Category', 'Markers', 'Per 1,000 words'], Object.entries(r.metadiscourse.per_category).map(([k, v]) => [MD_CATEGORIES[k]?.label ?? k, num(v.hits), num(v.density_per_1000, 1)]))),

      section(`Spelling (${e.variant === 'us' ? 'US' : 'UK'})`,
        table(['Found', 'Words'], [
          ['Possible errors', e.errors.length ? e.errors.map((x) => (x.suggestions?.[0] ? `${x.surface} → ${x.suggestions[0]}` : x.surface)).join(', ') : 'None'],
          ['Other variety', e.variant_mismatches.length ? e.variant_mismatches.map((x) => x.surface).join(', ') : 'None'],
          ['Unknown names', e.unknown_names.length ? e.unknown_names.map((x) => x.surface).join(', ') : 'None'],
        ])),

      section('Lexical diversity',
        table(['Measure', 'Value', 'Reference'], DIVERSITY.map((x) => [x.name, r.diversity.scores[x.key] == null ? 'Too short' : num(r.diversity.scores[x.key], Math.min(x.d, 2)), x.ref]))),

      section('Text', h('div', { class: 'report-text' }, analysedText(d).split(/\n\s*\n/).map((p) => h('p', {}, p.trim())))),

      h('footer', {},
        h('p', {}, h('b', {}, 'Cite: '), citation(d, m).apa),
        h('p', {}, `Also cite the word lists and formulas you report on (${SITE}/licences). Text SHA-256: ${m.sha256 || 'n/a'}`)));
  }

  function json(d) {
    const { submitted, ...rest } = d;
    return JSON.stringify(rest, null, 2) + '\n';
  }

  /** lexinspect-2026-10-25-some-people-believe */
  function filename(d, m, suffix, ext) {
    const day = m.exportedAt.slice(0, 10);
    const slug = d.submitted.toLowerCase().normalize('NFKD').replace(/[^\w\s-]/g, '').trim().split(/[\s_-]+/).filter(Boolean).slice(0, 4).join('-').slice(0, 40);
    return `lexinspect-${day}${slug ? `-${slug}` : ''}${suffix ? `-${suffix}` : ''}.${ext}`;
  }

  return { meta, metaNow, summaryCsv, wordsCsv, xlsx, json, summaryText, citationText, report, filename, columns: COLUMNS };
})();
