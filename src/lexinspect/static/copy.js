// Every piece of explanatory text on the page, plus the samples. Pure data.
//
// Displayed strings are marked with N_() for extraction and translated with t()
// where they are shown. SECTION_INFO's `about` and `caveats` may hold bare
// <b>…</b> and <i>…</i> pairs, rendered with tr() (never innerHTML); <i> marks
// English example words, which translations keep in English. Citations
// (`ref`), example markers (`eg`), the phrase list's own data and the sample
// texts are English data and stay untranslated.

const SECTION_INFO = {
  readability: {
    about:
      N_('Eight published readability formulas, each computed as originally defined from the same counts of words, sentences and syllables. The overall grade is the <b>median</b> of the eight grade estimates, so half the formulas rate the text harder and half easier.'),
    caveats: [
      N_('All eight measure only sentence length and word length. They cannot see vocabulary level, grammar, cohesion or topic, so read them alongside the CEFR and frequency profiles of the words.'),
      N_('Grades are US school grades. Add about 5 to get a reader’s age.'),
    ],
  },
  cefr: {
    about:
      N_('Each word gets the CEFR level of its part of speech, from the CEFR-J Vocabulary Profile 1.5 (A1–B2) and the Octanove Vocabulary Profile (C1–C2). <i>Present</i> is A1 as a noun and B2 as a verb, and the parser tags each occurrence as one or the other.'),
    caveats: [
      N_('A profile of the words, not a level for the writer or the text. Function words make every text mostly A1, so the upper levels tell you more.'),
      N_('These levels are not from the Cambridge English Vocabulary Profile. If you report them, cite CEFR-J and Octanove.'),
    ],
  },
  bnc: {
    about:
      N_('Paul Nation’s BNC/COCA lists group English words into 25 bands of 1,000 word families, ordered by frequency, with further lists of proper names, marginal words, transparent compounds and acronyms. A family includes inflections and derivations, so <i>analyse</i>, <i>analysis</i> and <i>analytical</i> count as one.'),
    caveats: [
      N_('Laufer & Ravenhorst-Kalovski (2010) put the minimal threshold for reading comprehension at knowing 95% of the running words, and the optimal threshold at 98%. These coverage figures count names and the words on the supplementary lists as known.'),
      N_('Counted with phrases, each word inside a PHRASE List expression takes the expression’s band, as in Martinez & Schmitt’s integrated list, so <i>in terms of</i> counts as three 2K words, not three 1K ones. Only PHRASE List expressions count as units; other multiword expressions still count word by word.'),
    ],
  },
  ngsl: {
    about:
      N_('The New General Service List (NGSL) has 2,809 lemmas that cover about 92% of general English. The New Academic Word List (NAWL) adds 959 lemmas for academic reading beyond the NGSL. Both are by Browne, Culligan & Phillips.'),
    caveats: [],
  },
  awl: {
    about:
      N_('Coxhead’s Academic Word List (AWL) has 570 word families that are common across academic disciplines and fall outside the 2,000 most frequent words. Sublist 1 holds the most frequent families, sublist 10 the least frequent.'),
    caveats: [
      N_('AWL words typically make up about 10% of academic prose and 1–2% of fiction. The AWL dates from 2000; the NAWL is a newer alternative.'),
    ],
  },
  phrase: {
    about:
      N_('The PHRASal Expressions List (Martinez & Schmitt 2012) holds the most frequent multiword expressions in English whose meaning is hard to work out from their words. It was compiled for teaching reading. Each expression is ranked in the same 1,000-item bands as the BNC word families, as if words and phrases formed one list, so <i>in terms of</i>, made of 1K words, is a 2K item. The list also rates how common each expression is in speech, general writing and academic writing. Matching follows inflections (<i>dealt with</i>), checks the grammar where senses differ (<i>going to</i> as future, not direction), and counts only the longest of overlapping expressions.'),
    caveats: [
      N_('The register ratings compare the three registers for one expression; they are not frequencies. An expression rated rare in academic writing is worth a second look in an academic text, but the rating is not a rule against it.'),
      N_('An expression’s band comes from the BNC lists the PHRASE List was built on; word bands come from Nation’s later BNC/COCA lists. The two draw on different corpora, so a one-band gap between an expression and its words is approximate.'),
      N_('When two senses of one form both fit, the match takes the more frequent sense and notes the others. Expressions split by inserted words (<i>on the very other hand</i>) are not found.'),
    ],
  },
  metadiscourse: {
    about:
      N_('Hyland’s (2005) model describes how writers organise a text (interactive metadiscourse) and engage the reader (interactional metadiscourse). Each candidate marker is checked against the parse of its sentence before it counts. <i>So</i> is a transition only when it joins clauses, <i>table</i> is endophoric only in <i>Table 2</i>, and <i>clear</i> is a booster only in <i>it is clear that</i>.'),
    caveats: [
      N_('Hyland coded his corpus by hand. Automatic tagging finds the clear cases but misses irony and some hedges that depend on context alone.'),
      N_('Densities are per 1,000 words, the unit Hyland reports, so they compare directly with published corpus studies.'),
    ],
  },
  spelling: {
    about:
      N_('Spelling is checked with Hunspell and the LibreOffice English dictionaries. Words fall into three groups: errors, words that are correct only in the other variety (<i>color</i> when checking British spelling), and capitalised words the dictionary doesn’t know, which are usually names.'),
    caveats: [
      N_('A dictionary check cannot catch real words used wrongly (<i>their</i>/<i>there</i>, <i>form</i>/<i>from</i>). Rare technical terms may be flagged as errors.'),
    ],
  },
  syntax: {
    about:
      N_('These measures follow Lu’s (2010) L2 Syntactic Complexity Analyzer (L2SCA): the length of sentences, T-units and clauses, how much subordination and coordination they carry, and how much is packed into noun phrases. A <b>T-unit</b> is a main clause with everything attached to it, so <i>I left because it rained</i> is one T-unit with two clauses.'),
    caveats: [
      N_('L2SCA finds these units with Tregex patterns over a constituency parse; these figures read them off spaCy’s dependency parse instead. Counts of sentences, clauses and words agree closely with L2SCA. Dependent clauses, coordinate phrases and complex nominals are approximations.'),
      N_('The parser was trained on edited English. On learner writing with many errors it misreads more clauses, so compare learner texts with each other rather than with published native-speaker norms.'),
      N_('Length and subordination grow with proficiency up to about B2. Beyond that, growth shows mainly in longer clauses and denser noun phrases (Norris & Ortega 2009; Biber, Gray & Poonpon 2011).'),
    ],
  },
  diversity: {
    about:
      N_('These indices measure how varied the vocabulary is. The simple type/token ratio falls as a text grows, so it cannot compare texts of different lengths. <b>MTLD</b>, <b>HD-D</b> and <b>vocd-D</b> were designed to avoid this.'),
    caveats: [
      N_('Below about 50 words (not counting numbers) every measure is unstable, and Maas needs about 100. Compare texts of the same genre, because genre alone changes these scores.'),
    ],
  },
  statistics: {
    about:
      N_('These are the counts every other measure is built on. A word is an orthographic word, so <i>don’t</i>, <i>well-known</i> and <i>cannot</i> are one word each. Numbers count as words for readability but are left out of type counts.'),
    caveats: [
      N_('Parts of speech come from spaCy’s small English model (about 97% tag accuracy on spaCy’s OntoNotes benchmark of edited English, lower on learner writing).'),
    ],
  },
};

const LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

// `name` and `note` are shown (t() them); `ref` is a citation and stays as it is.
const FORMULAS = [
  { key: 'flesch_kincaid_grade', name: N_('Flesch–Kincaid'), kind: 'grade', ref: 'Kincaid et al. 1975', note: N_('Words per sentence and syllables per word. The standard formula in US education and the US military.') },
  { key: 'flesch_reading_ease', name: N_('Flesch Reading Ease'), kind: 'ease', ref: 'Flesch 1948', note: N_('Scored 0–100; higher is easier. 60–70 is plain English.') },
  { key: 'gunning_fog', name: N_('Gunning Fog'), kind: 'grade', ref: 'Gunning 1952', note: N_('Sentence length and words of three or more syllables, not counting names, compounds and -ed/-es/-ing forms.') },
  { key: 'smog_index', name: N_('SMOG'), kind: 'grade', ref: 'McLaughlin 1969', note: N_('Polysyllables per 30 sentences. Predicts the grade needed for full comprehension, so it runs higher than the others.') },
  { key: 'coleman_liau_index', name: N_('Coleman–Liau'), kind: 'grade', ref: 'Coleman & Liau 1975', note: N_('Letters and sentences per 100 words, with no syllable counting.') },
  { key: 'automated_readability_index', name: N_('ARI'), kind: 'grade', ref: 'Smith & Senter 1967', note: N_('Characters per word and words per sentence.') },
  { key: 'dale_chall_readability_score', name: N_('Dale–Chall'), kind: 'dale', ref: 'Chall & Dale 1995', note: N_('Share of words outside a list of 3,000 familiar words, plus sentence length.') },
  { key: 'linsear_write_formula', name: N_('Linsear Write'), kind: 'grade', ref: 'O’Hayre 1966', note: N_('Easy and hard words in a 100-word sample. Reportedly devised for US Air Force technical manuals.') },
];

/** Flesch Reading Ease bands: [lowest score, label]. t() the label. */
const EASE_BANDS = [
  [90, N_('Very easy')], [80, N_('Easy')], [70, N_('Fairly easy')], [60, N_('Plain English')],
  [50, N_('Fairly difficult')], [30, N_('Difficult')], [-Infinity, N_('Very difficult')],
];

/** The school stage for a US grade, translated. */
function gradeLabel(g) {
  if (g == null) return '';
  if (g < 1) return t('Kindergarten');
  if (g < 6) return t('Primary school');
  if (g < 9) return t('Middle school');
  if (g < 13) return t('High school');
  if (g < 17) return t('University');
  return t('Postgraduate');
}

// `name` and `note` are shown (t() them); `ref` is a citation.
const DIVERSITY = [
  { key: 'mtld', name: N_('MTLD'), ref: 'McCarthy & Jarvis 2010', note: N_('Mean length of word runs that keep the type/token ratio above 0.72. Higher is more varied; about 70–100 is typical of adult writing.'), d: 1 },
  { key: 'vocd_d', name: N_('vocd-D'), ref: 'McKee, Malvern & Richards 2000', note: N_('Fits a curve to the TTR of random samples of 35–50 words. Comparable with published reference ranges (Durán et al. 2004).'), d: 1 },
  { key: 'hdd', name: N_('HD-D'), ref: 'McCarthy & Jarvis 2007', note: N_('Expected share of each word type in a random 42-word sample, 0–1.'), d: 3 },
  { key: 'mattr', name: N_('MATTR'), ref: 'Covington & McFall 2010', note: N_('Average TTR over a moving 50-word window, 0–1.'), d: 3 },
  { key: 'msttr', name: N_('MSTTR'), ref: 'Johnson 1944', note: N_('Average TTR over consecutive 50-word segments, 0–1.'), d: 3 },
  { key: 'ttr', name: N_('TTR'), ref: '', note: N_('Types divided by tokens. Falls as texts get longer, so compare only texts of the same length.'), d: 3 },
  { key: 'rttr', name: N_('Root TTR'), ref: 'Guiraud 1954', note: N_('Types / √tokens.'), d: 2 },
  { key: 'cttr', name: N_('Corrected TTR'), ref: 'Carroll 1964', note: N_('Types / √(2 × tokens).'), d: 2 },
  { key: 'herdan', name: N_('Herdan’s C'), ref: 'Herdan 1960', note: N_('log types / log tokens.'), d: 3 },
  { key: 'summer', name: N_('Summer’s S'), ref: 'Summer 1966', note: N_('log log types / log log tokens.'), d: 3 },
  { key: 'maas', name: N_('Maas a²'), ref: 'Maas 1972', note: N_('(log tokens − log types) / (log tokens)². Lower is more varied.'), d: 4 },
];

// Hyland's categories. `label` and `note` are shown (t() them); `eg` lists
// English markers and stays English.
const MD_CATEGORIES = {
  transitions: { label: N_('Transitions'), note: N_('Link steps in the argument'), eg: 'however, therefore, in addition' },
  frame_markers: { label: N_('Frame markers'), note: N_('Sequence and stage the text'), eg: 'first, finally, to conclude' },
  endophoric_markers: { label: N_('Endophoric markers'), note: N_('Point to other parts of the text'), eg: 'see Table 2, as noted above' },
  evidentials: { label: N_('Evidentials'), note: N_('Attribute ideas to sources'), eg: 'according to, Smith argues' },
  code_glosses: { label: N_('Code glosses'), note: N_('Rephrase and give examples'), eg: 'for example, in other words' },
  hedges: { label: N_('Hedges'), note: N_('Withhold full commitment'), eg: 'may, perhaps, suggest' },
  boosters: { label: N_('Boosters'), note: N_('Express certainty'), eg: 'clearly, in fact, demonstrate' },
  attitude_markers: { label: N_('Attitude markers'), note: N_('Express the writer’s attitude'), eg: 'unfortunately, important' },
  engagement_markers: { label: N_('Engagement markers'), note: N_('Address the reader directly'), eg: 'consider, note that, you' },
  self_mentions: { label: N_('Self-mentions'), note: N_('Refer to the writer'), eg: 'I, we argue, my' },
};

// The PHRASE List's register columns, and its legend for the ratings in them
// (* * * most common in this genre, or as common; * * less common;
// * infrequent; x rare or non-existent). `label` and `long` are shown.
const PHRASE_REGISTERS = [
  { key: 'spoken_general', label: N_('Spoken'), long: N_('speech') },
  { key: 'written_general', label: N_('Written'), long: N_('general writing') },
  { key: 'written_academic', label: N_('Academic'), long: N_('academic writing') },
];
const PHRASE_RATINGS = [
  { key: 'most_common', label: N_('Most common'), dots: 3 },
  { key: 'less_common', label: N_('Less common'), dots: 2 },
  { key: 'infrequent', label: N_('Infrequent'), dots: 1 },
  { key: 'rare', label: N_('Rare or absent'), dots: 0 },
];

/** An entry's form for display: its sense gloss dropped, optional parts kept,
 *  so IN (THE SENSE) THAT reads "in (the sense) that", not "in that".
 *  English list data: not translated. */
function phraseName(x) {
  const form = x.sense ? x.phrase.replace(/\s*\([^()]*\)\s*$/, '') : x.phrase;
  return form.toLowerCase();
}

// Glosses in the source that are abbreviations or carry stray quotes. The
// grammatical descriptions are interface text (N_); the rest are English
// glosses, like every other sense in the list, and stay English.
const SENSE_LABELS = {
  '+NP': N_('with a noun phrase'), 'adv.': N_('adverb'), anaphor: N_('referring back'),
  TRANs: 'transport', 'IN’/’FROM': 'in, from', DECISIONS: 'someone’s decision',
};
const SENSE_TRANSLATED = new Set(['+NP', 'adv.', 'anaphor']);

/** A sense for display: grammatical descriptions translated, glosses in English. */
function senseLabel(x) {
  if (!x.sense) return null;
  const label = SENSE_LABELS[x.sense];
  if (label == null) return x.sense.toLowerCase();
  return SENSE_TRANSLATED.has(x.sense) ? t(label) : label;
}

/** Universal POS tags, as shown. t() the value. */
const UPOS = {
  NOUN: N_('Nouns'), VERB: N_('Verbs'), ADJ: N_('Adjectives'), ADV: N_('Adverbs'), PRON: N_('Pronouns'), PROPN: N_('Proper nouns'),
  DET: N_('Determiners'), ADP: N_('Prepositions'), AUX: N_('Auxiliaries'), CCONJ: N_('Coordinators'), SCONJ: N_('Subordinators'),
  PART: N_('Particles'), NUM: N_('Numerals'), INTJ: N_('Interjections'), PUNCT: N_('Punctuation'), SYM: N_('Symbols'), X: N_('Other'),
};

// The texts are English input and stay English; `label` and `note` are shown.
const SAMPLES = [
  {
    id: 'essay',
    label: N_('Learner essay'),
    note: N_('IELTS-style, with errors'),
    text:
      'Some people believe that goverments should spend more money on public transport, while others think that building new roads is more important. In my opinion, investing in public transport is the better choice, becuase it benefits more people and protects the enviroment.\n\nFirstly, public transport can carry alot of passengers at once. For example, a single bus can replace forty cars, which reduces traffic and pollution in big cities. Moreover, people who cannot afford a car, such as students and elderly people, depend on buses and trains to go to work or school.\n\nOn the other hand, new roads may be necessary in rural areas where there is no other option. However, I think that roads only encourage people to drive more, and in the long run the traffic will become worse again.\n\nIn conclusion, although roads have some advantages, I strongly believe that spending on public transport is more effective and fair. Goverments should therefore make it cheaper and more reliable so that more people choose to use it.',
  },
  {
    id: 'academic',
    label: N_('Research abstract'),
    note: N_('Academic register'),
    text:
      'Previous research has established that vocabulary knowledge is a strong predictor of reading comprehension in a second language. However, the extent to which this relationship depends on text type remains unclear. The present study examined the comprehension of expository and narrative texts by 214 university students of English as a foreign language. Participants completed a vocabulary size test and two reading tasks of comparable length. The results indicate that vocabulary size accounted for a substantially larger proportion of variance in expository comprehension (R² = .41) than in narrative comprehension (R² = .22). We argue that expository texts, which contain a higher density of low-frequency and academic vocabulary, impose greater lexical demands on readers. These findings suggest that instruction should arguably prioritise academic vocabulary for learners preparing for university study, although further research is needed to confirm whether the effect holds across proficiency levels.',
  },
  {
    id: 'story',
    label: N_('Short story'),
    note: N_('Narrative, plain style'),
    text:
      'Maria had always loved the smell of rain on dry earth. As a child she would run outside the moment thunder rolled across the valley, splashing barefoot through the puddles that formed along the gravel road. Her grandmother would scold her gently, wrap a thick towel around her shoulders and press a mug of hot cocoa into her cold hands.\n\nYears later, walking home through a sudden downpour in a city far from those hills, she felt the same wild joy rising in her chest. She stopped under a streetlight, closed her eyes and laughed out loud at nothing at all.',
  },
  {
    id: 'news',
    label: N_('News report'),
    note: N_('Journalistic'),
    text:
      'The city council has approved a plan to turn three central streets into pedestrian zones by next summer, despite objections from local businesses. Under the proposal, cars will be banned from the area between 10 a.m. and 6 p.m., although deliveries will still be allowed in the early morning.\n\nCouncillors who supported the scheme said it would cut air pollution and make the centre more attractive to visitors. "We have seen this work in other cities," said one. Shop owners, however, warned that fewer drivers could mean fewer customers, and called for a six-month trial before any permanent change.',
  },
];
