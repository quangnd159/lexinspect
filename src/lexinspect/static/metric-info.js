// Plain-English metric explanations for the headline summary chips, plus
// per-tab introductions and the small fixture corpus available behind the
// "simple / academic / narrative" buttons.
//
// Pure data — no DOM access, no side effects. Loaded before any renderer or
// app code so its globals (`METRIC_INFO`, `MODULE_INTROS`, `FIXTURES`) are
// available everywhere downstream.

// Each entry: { title, desc, scale: {min,max,leftLabel,rightLabel}, bands: [[lo,hi,label]...], caveats? }
const METRIC_INFO = {
  words: {
    title: 'Word count',
    desc: 'How many running words are in the text. Useful for context — short samples (under ~50 words) make many other measures unreliable.',
    caveats: ['Under ~50 words, most diversity and CEFR signals get noisy. Treat very short samples as indicative, not diagnostic.'],
  },
  flesch_reading_ease: {
    title: 'Flesch Reading Ease',
    desc: 'A 0–100 score where higher means easier to read. Based on how long the sentences and words are. Widely used in publishing and education to gauge accessibility.',
    scale: { min: 0, max: 100, leftLabel: 'Hard', rightLabel: 'Easy' },
    bands: [
      [90, 100, 'Very easy — 5th grade reader'],
      [80, 90, 'Easy — 6th grade reader'],
      [70, 80, 'Fairly easy — 7th grade reader'],
      [60, 70, 'Standard — 8th–9th grade reader'],
      [50, 60, 'Fairly difficult — 10th–12th grade reader'],
      [30, 50, 'Difficult — college reader'],
      [-200, 30, 'Very difficult — postgraduate reader'],
    ],
    caveats: [
      'Counts only sentence and syllable length. It can\'t see grammar, vocabulary level, or topic — a short, syntactically simple text on quantum mechanics will look "easy" but read like a wall.',
      'The syllable counter mis-counts rare technical words. Margins of error grow on jargon-dense text.',
    ],
  },
  flesch_kincaid_grade: {
    title: 'Flesch–Kincaid Grade',
    desc: 'Estimates the US school grade level needed to comfortably read the text. A score of 8 means an 8th-grade student should follow it without much effort.',
    scale: { min: 0, max: 18, leftLabel: 'Grade 0', rightLabel: 'Grade 18+' },
    bands: [
      [0, 5, 'Elementary'],
      [5, 8, 'Middle school'],
      [8, 12, 'High school'],
      [12, 16, 'College'],
      [16, 100, 'Postgraduate'],
    ],
    caveats: [
      'Same blind spots as Flesch Reading Ease — sentence and syllable length only. Treat as a triage signal, not a placement test.',
      'US grade levels don\'t map cleanly to UK / Vietnamese / IELTS levels. For CEFR or IELTS placement, prefer the CEFR tab and BNC/COCA coverage.',
    ],
  },
  mtld: {
    title: 'Lexical diversity (MTLD)',
    desc: 'How wide the range of words is. A higher number means the writer keeps reaching for new words instead of repeating the same ones. Stable across different text lengths, unlike a simple type/token ratio.',
    scale: { min: 0, max: 200, leftLabel: 'Repetitive', rightLabel: 'Diverse' },
    bands: [
      [0, 50, 'Very repetitive — common in basic spoken language'],
      [50, 80, 'Limited variety — typical of A2/B1 student writing'],
      [80, 120, 'Moderate variety — typical general writing'],
      [120, 160, 'Strong variety — typical good academic writing'],
      [160, 1000, 'Very wide variety — dense, sophisticated text'],
    ],
    caveats: [
      'Wobbles on texts under ~50 tokens. The module returns nothing rather than a bad number, but very short samples won\'t produce a meaningful score.',
      'Genre matters. Fiction and conversation reach higher MTLD than academic writing of the same level. Compare like with like.',
    ],
  },
  awl_coverage: {
    title: 'Academic vocabulary (AWL coverage)',
    desc: 'How much of the text comes from Coxhead\'s 570 Academic Word List head words — vocabulary that appears across academic disciplines. A higher percentage signals an academic register.',
    scale: { min: 0, max: 20, leftLabel: '0%', rightLabel: '20%+' },
    bands: [
      [0, 2, 'Very little — conversational or narrative'],
      [2, 5, 'Some — general non-fiction'],
      [5, 10, 'Notable — typical academic prose'],
      [10, 100, 'Heavy — dense academic or technical writing'],
    ],
    caveats: [
      'Coxhead 2000 is the original AWL. Newer alternatives — Gardner & Davies\'s AVL (2014), the NAWL — are built from larger corpora and arguably cover academic vocabulary more cleanly. Treat AWL as the canonical-but-dated baseline.',
    ],
  },
  bnc_coca_coverage: {
    title: 'Within the 10,000 most common words (BNC/COCA)',
    desc: 'How much of the text falls inside the first 10,000 most-frequent English head words (Nation\'s BNC/COCA bands). The remainder is rarer vocabulary — proper nouns, jargon, or words above this level.',
    scale: { min: 0, max: 100, leftLabel: '0%', rightLabel: '100%' },
    bands: [
      [0, 70, 'High share of rare vocabulary — challenging for learners'],
      [70, 85, 'Some rare vocabulary — typical academic or specialised text'],
      [85, 95, 'Mostly common vocabulary — general writing'],
      [95, 100, 'Almost all common vocabulary — accessible to most readers'],
    ],
    caveats: [
      'The bundled list is head words only — derivationally related forms like "analytically" may not match the "analyse" head word. lexinspect tries the surface form and the lemma to compensate, but recall is lower than commercial tools that ship the full Nation family lists.',
      'The off-list residual lumps together proper nouns, technical terms, and rarer vocabulary above the first 10,000. A high off-list percentage isn\'t automatically "hard" — it might just be a name-heavy text.',
    ],
  },
  cefr_dominant: {
    title: 'CEFR vocabulary level',
    desc: 'Based on the CEFR-J wordlist (A1–B2) and the Octanove C1/C2 list, the level where most of the text\'s recognisable vocabulary sits. Read alongside the per-level distribution in the CEFR tab — function words ("the", "of") almost always make A1 the dominant slot, so this number alone is not a placement.',
    bands: [
      ['A1', 'A1', 'Beginner — basic everyday phrases'],
      ['A2', 'A2', 'Elementary — familiar everyday topics'],
      ['B1', 'B1', 'Intermediate — most everyday situations'],
      ['B2', 'B2', 'Upper-intermediate — abstract and concrete topics'],
      ['C1', 'C1', 'Advanced — complex texts on most subjects'],
      ['C2', 'C2', 'Proficient — nuanced and idiomatic use'],
    ],
    isCategorical: true,
    caveats: [
      'Function words ("the", "of", "and") are A1, so they dominate the count in any text. If this says A1 on an academic passage, it is not telling you the text is A1-level — it\'s telling you the most frequent tokens are function words. Always read the full per-level distribution in the CEFR tab.',
      'Not Cambridge English Vocabulary Profile (EVP). The underlying CEFR-J + Octanove lists use different corpora and methodology, so numbers will diverge from EVP-based tools like Text Inspector\'s premium output.',
    ],
  },
  metadiscourse_density: {
    title: 'Metadiscourse density',
    desc: 'How often the text uses words and phrases that organise the argument ("however", "first", "in conclusion") or address the reader ("clearly", "we suggest", "you can see"). Reported per 1,000 content tokens — the standard comparability measure in academic writing research.',
    scale: { min: 0, max: 200, leftLabel: 'Sparse', rightLabel: 'Heavy' },
    bands: [
      [0, 30, 'Sparse — typical of narrative or descriptive text'],
      [30, 80, 'Moderate — general non-fiction'],
      [80, 130, 'Dense — typical academic or argumentative writing'],
      [130, 1000, 'Very dense — heavily signposted argument'],
    ],
    caveats: [
      '9 of 10 categories use a curated reference subset of canonical Hyland 2005 markers, not his full Appendix A. Hedges are the only verbatim mirror. Coverage is enough for diagnostic ELT work but will under-report on long academic texts versus tools with the complete inventory.',
      'Detection is literal-string matching with verb-inflection tolerance — context-blind. A booster like "clearly" used ironically still counts as a booster.',
    ],
  },
};

// Each entry: { intro: html-string, caveat: optional plain-text limitation }
const MODULE_INTROS = {
  overview: {
    intro: '<b>Overview</b> — a quick read of the eight headline numbers. Click any chip above for what it means and how to read it. Pick a module from the left rail for the full breakdown.',
  },
  readability: {
    intro: '<b>Readability</b> measures how hard or easy a text is to read using sentence length and word length. The eight scores agree most of the time but use different scales (US grade level, Flesch index, etc.). Treat them as triangulation, not gospel.',
    caveat: 'All eight formulas use the same surface signals (sentence and word length). They can\'t see grammar, vocabulary level, or topic — a syntactically simple sentence on quantum mechanics still scores "easy" here.',
  },
  statistics: {
    intro: '<b>Statistics</b> — the basic countable properties of the text. Sentence count, token count (excluding pure-digit numerals), unique types, syllable counts, ratios. The same numbers Text Inspector breaks out under its Statistics tab. Useful as the raw input to the readability formulas above and as a quick sanity check on length and density.',
    caveat: '"Excluded digits" lists pure-numeric tokens like 2025 or 1.5 — word numerals (one, twentieth) stay in the token count. Syllable counts come from textstat, which uses a dictionary-based syllabifier; rare technical words can be off by a syllable or two.',
  },
  diversity: {
    intro: '<b>Lexical diversity</b> tells you whether the writer is reaching for new words or repeating the same ones. <b>MTLD</b> and <b>HD-D</b> are the most reliable across different text lengths; <b>TTR</b> is simple but skewed against longer texts.',
    caveat: 'Most diversity measures wobble on texts under ~50 tokens. lexinspect returns nothing for the affected scores rather than a misleading number — check the value before drawing conclusions.',
  },
  tagger: {
    intro: '<b>POS tagging</b> labels each word with its part of speech. Penn Treebank tags are detailed (e.g. NNS = plural noun, VBZ = 3rd-person singular verb); Universal POS is the broader category (NOUN, VERB, ADJ). Useful for spotting style — heavy noun phrases, verb-light prose, etc.',
    caveat: 'Uses the small spaCy English model for speed — about 2 percentage points less accurate than the large model on tag accuracy. Fine for ELT triage, swap to the large model if you start using these counts for serious syntactic analysis.',
  },
  awl: {
    intro: '<b>Academic Word List</b> coverage. Coxhead\'s 570 head words appear across academic disciplines and are not in the most common 2,000 English words. Higher coverage signals an academic register. Sublists 1–10 go from most common to least.',
    caveat: 'Coxhead 2000 is the canonical-but-dated list. Gardner & Davies\'s Academic Vocabulary List (AVL, 2014) was built from a larger academic corpus and is arguably stronger; lexinspect doesn\'t bundle it yet.',
  },
  'bnc/coca': {
    intro: '<b>BNC/COCA frequency bands</b>. Each band is 1,000 head words, ordered by frequency in real-world English. The cumulative curve answers "what proportion of this text is within the first N thousand most common words?" — the standard ELT readout for vocabulary load.',
    caveat: 'Bundled list is head words only (CC0-clean mirror) — derivationally related forms like "analytically" may not match the "analyse" head word. Surface + lemma fallback partially mitigates, but recall is lower than commercial tools that ship the full Nation family lists.',
  },
  ngsl: {
    intro: '<b>NGSL + NAWL</b> coverage. The New General Service List covers ~92% of general English with 2,809 lemmas; the New Academic Word List adds 959 academic lemmas for use after NGSL. Off-list residual is everything else — proper nouns, low-frequency or technical terms.',
  },
  phrase: {
    intro: '<b>PHRASE list</b> detection (Martinez & Schmitt 2012). 506 multi-word expressions from "have to" and "of course" to "on the other hand", banded by frequency (K1 most common, K5 least). Strong indicator of natural phrasing in writing.',
    caveat: 'Verb-slot phrases are partially handled. Modal-slot expressions like "(may/might) have to" detect only the first variant. Detection is also literal-string matching, so creative or modified phrasings (e.g. "on the very other hand") are missed.',
  },
  cefr: {
    intro: '<b>CEFR vocabulary profile</b>. Each lemma is mapped to the lowest CEFR level at which it\'s listed (A1 to C2). Read the full distribution, not just the dominant level — function words inflate A1 in any text. The 95th-percentile heuristic gives the lowest level at which the text becomes mostly familiar.',
    caveat: 'Built from the CEFR-J wordlist (Tono, TUFS) plus Octanove C1/C2 — not the Cambridge English Vocabulary Profile (EVP). Different corpora and methodology mean numbers will diverge from EVP-based commercial tools.',
  },
  metadiscourse: {
    intro: '<b>Metadiscourse markers</b> (Hyland 2005). Words and phrases that organise the text (<i>interactive</i>: transitions, frame markers, evidentials…) or engage the reader (<i>interactional</i>: hedges, boosters, attitude markers…). Density per 1,000 tokens is the standard comparability metric.',
    caveat: '9 of 10 categories use a curated reference subset of canonical Hyland 2005 markers, not the full Appendix A. Hedges are the only verbatim mirror. Coverage is enough for diagnostic ELT work but under-reports on long academic texts versus tools with the complete inventory.',
  },
  'cefr-level': {
    intro: '<b>CEFR text-level classifier</b> (UniversalCEFR ModernBERT, Apache 2.0). Predicts a single CEFR band (A1–C2) for the whole text from a transformer fine-tuned on 505k labelled texts. Distinct from the <b>cefr</b> tab: that one profiles vocabulary; this one returns a judgement. Optional module — click <i>Run classifier</i> to fire it.',
    caveat: 'Estimate, not a verdict. Adjacent-band confusion is irreducible (even human raters disagree at this granularity). Vocabulary features dominate the prediction; syntactic complexity and discourse organisation are under-weighted. Combine with the other tabs before reporting a level. Requires the optional <code>cefr-level</code> install extra; takes ~3–5s per call.',
  },
  errors: {
    intro: "<b>Spelling errors</b> (Hunspell). Flags tokens that aren't in the chosen English dictionary. Toggle between British (default) and American variants. Runs on demand — click <i>Check spelling</i> to fire it.",
    caveat: "Hunspell only knows what's in the dictionary — proper nouns, brand names, neologisms, and rare technical vocabulary will routinely show up as false positives. spaCy splits possessive 's from its host noun, so possessive forms aren't spell-checked as wholes. The first call per variant downloads a ~1.5 MB dictionary before it can answer.",
  },
};

const FIXTURES = {
  simple: "The cat sat on the mat. The dog ran in the park. Birds fly high in the sky. Children play with toys every day. The sun is bright and warm.",
  academic: "The empirical analysis demonstrates that significant variations in methodology produce substantially different outcomes across comparable contexts. Subsequent investigations have confirmed this hypothesis through rigorous statistical evaluation of comprehensive datasets. Research participants exhibited consistent patterns of behavioural adaptation when exposed to environmental modifications. The theoretical framework underlying this approach derives from established principles of cognitive psychology and contemporary neuroscience. Researchers consequently recommend further longitudinal studies to validate preliminary findings and explore potential implications for educational policy.",
  narrative: "Maria had always loved the smell of rain on dry earth. As a child she would race outside the moment thunder rolled across the valley, splashing barefoot through the puddles that formed along the gravel road. Her grandmother would scold her gently, wrapping a thick towel around her shoulders and pressing a steaming mug of cocoa into her cold hands. Years later, walking home through a sudden downpour in a city far from those hills, she felt the same wild joy rising in her chest, and she laughed out loud at nothing at all.",
};
