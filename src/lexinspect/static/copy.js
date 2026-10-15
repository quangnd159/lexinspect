// Every piece of explanatory text on the page, plus the samples. Pure data.
// Strings in `html` fields are trusted constants; nothing here is user input.

const SECTION_INFO = {
  readability: {
    about:
      'Eight published readability formulas, each computed to its original definition on the same word, sentence and syllable counts. The headline grade is the <b>median</b> of the eight grade estimates: half the formulas rate the text harder, half easier.',
    caveats: [
      'All eight measure sentence length and word length only. They cannot see vocabulary level, grammar, cohesion or topic, so read them alongside the Vocabulary tab.',
      'Grades are US school grades. Roughly, add 5 for a reader’s age.',
    ],
  },
  cefr: {
    about:
      'Each word’s CEFR level for its part of speech, from the CEFR-J Vocabulary Profile 1.5 (A1–B2) and the Octanove Vocabulary Profile (C1–C2). <i>Present</i> is A1 as a noun and B2 as a verb; the parser decides which one the text uses.',
    caveats: [
      'A profile of the words, not a placement of the writer or a level for the text. Function words make every text mostly A1; look at the upper levels.',
      'Not the Cambridge English Vocabulary Profile. Cite CEFR-J and Octanove if you report these numbers.',
    ],
  },
  bnc: {
    about:
      'Paul Nation’s BNC/COCA word families: 25 bands of 1,000 families ordered by frequency, plus his lists of proper names, marginal words, transparent compounds and acronyms. A family includes inflections and derivations, so <i>analyse</i>, <i>analysis</i> and <i>analytical</i> count as one.',
    caveats: [
      'Readers need to know about 95% of the running words for adequate comprehension and 98% for comfortable reading (Laufer & Ravenhorst-Kalovski 2010). The 95% and 98% markers show which band gets there, counting names and the supplementary lists as known.',
    ],
  },
  ngsl: {
    about:
      'The New General Service List (2,809 lemmas covering about 92% of general English) and the New Academic Word List (959 lemmas for academic reading beyond the NGSL), Browne, Culligan & Phillips.',
    caveats: [],
  },
  awl: {
    about:
      'Coxhead’s Academic Word List: 570 word families common across academic disciplines and outside the 2,000 most frequent words. Sublist 1 holds the most frequent families, sublist 10 the least.',
    caveats: [
      'Academic prose typically scores about 10%; fiction about 1–2%. The AWL dates from 2000; the NAWL on the NGSL tab is a newer alternative.',
    ],
  },
  phrase: {
    about:
      'The PHRASE list (Martinez & Schmitt 2012): 506 common multi-word expressions whose meaning is not the sum of their parts, banded K1–K5 by frequency. Matching follows inflections (<i>dealt with</i>), checks the grammar where senses differ (<i>going to</i> as future, not direction), and counts the longest expression once.',
    caveats: [
      'When two senses of one form fit, the more frequent is shown and the others are listed. Expressions split by inserted words (<i>on the very other hand</i>) are not found.',
    ],
  },
  metadiscourse: {
    about:
      'Hyland’s (2005) model of how writers organise a text (interactive) and engage the reader (interactional). Each candidate is checked against the parse before it counts: <i>so</i> is a transition only when it joins clauses, <i>table</i> is endophoric only in <i>Table 2</i>, <i>clear</i> is a booster only in <i>it is clear that</i>.',
    caveats: [
      'Hyland coded his corpus by hand. Automatic tagging gets the clear cases; irony, and some hedges carried by context alone, are beyond it.',
      'Densities are per 1,000 words, the unit Hyland reports, so they compare directly with published corpus studies.',
    ],
  },
  spelling: {
    about:
      'Hunspell with the LibreOffice English dictionaries. Results are split into errors, words that are correct only in the other variety (<i>color</i> in UK mode), and capitalised words the dictionary does not know, which are usually names.',
    caveats: [
      'A dictionary check cannot catch real words used wrongly (<i>their</i>/<i>there</i>, <i>form</i>/<i>from</i>). Rare technical terms may be flagged.',
    ],
  },
  diversity: {
    about:
      'How varied the vocabulary is. Simple type/token ratios fall as a text grows, so they cannot compare texts of different lengths. <b>MTLD</b>, <b>HD-D</b> and <b>vocd-D</b> were designed not to.',
    caveats: [
      'Below about 100 words every measure is unstable. Compare texts of similar genre: narrative always varies more than argument.',
    ],
  },
  statistics: {
    about:
      'The counts every other measure is built on. A word is an orthographic word: <i>don’t</i>, <i>well-known</i> and <i>cannot</i> are one word each. Numbers count as words for readability and are excluded from type counts.',
    caveats: [
      'Parts of speech come from spaCy’s small English model (about 97% tag accuracy on news text, lower on learner writing).',
    ],
  },
};

const FORMULAS = [
  { key: 'flesch_kincaid_grade', name: 'Flesch–Kincaid', kind: 'grade', ref: 'Kincaid et al. 1975', note: 'Words per sentence and syllables per word. The US military and education standard.' },
  { key: 'flesch_reading_ease', name: 'Flesch Reading Ease', kind: 'ease', ref: 'Flesch 1948', note: '0–100, higher is easier. 60–70 is plain English.' },
  { key: 'gunning_fog', name: 'Gunning Fog', kind: 'grade', ref: 'Gunning 1952', note: 'Sentence length and words of three or more syllables, excluding names, compounds and -ed/-es/-ing forms.' },
  { key: 'smog_index', name: 'SMOG', kind: 'grade', ref: 'McLaughlin 1969', note: 'Polysyllables per 30 sentences. Predicts the grade for full comprehension, so it reads higher than the others.' },
  { key: 'coleman_liau_index', name: 'Coleman–Liau', kind: 'grade', ref: 'Coleman & Liau 1975', note: 'Letters and sentences per 100 words; no syllable counting.' },
  { key: 'automated_readability_index', name: 'ARI', kind: 'grade', ref: 'Smith & Senter 1967', note: 'Characters per word and words per sentence.' },
  { key: 'dale_chall_readability_score', name: 'Dale–Chall', kind: 'dale', ref: 'Chall & Dale 1995', note: 'Share of words outside a list of 3,000 familiar words, plus sentence length.' },
  { key: 'linsear_write_formula', name: 'Linsear Write', kind: 'grade', ref: 'O’Hayre 1966', note: 'Easy and hard words in a 100-word sample. Reportedly devised for US Air Force technical manuals.' },
];

const EASE_BANDS = [
  [90, 'Very easy'], [80, 'Easy'], [70, 'Fairly easy'], [60, 'Plain English'],
  [50, 'Fairly difficult'], [30, 'Difficult'], [-Infinity, 'Very difficult'],
];

function gradeLabel(g) {
  if (g == null) return '';
  if (g < 1) return 'Kindergarten';
  if (g < 6) return 'Primary school';
  if (g < 9) return 'Middle school';
  if (g < 13) return 'High school';
  if (g < 17) return 'University';
  return 'Postgraduate';
}

const DIVERSITY = [
  { key: 'mtld', name: 'MTLD', ref: 'McCarthy & Jarvis 2010', note: 'Mean length of word runs that keep the type/token ratio above 0.72. Higher is more varied; about 70–100 is typical of adult writing.', d: 1 },
  { key: 'vocd_d', name: 'vocd-D', ref: 'McKee, Malvern & Richards 2000', note: 'Fits a curve to the TTR of random samples of 35–50 words. Comparable with the published reference ranges below.', d: 1 },
  { key: 'hdd', name: 'HD-D', ref: 'McCarthy & Jarvis 2007', note: 'Expected share of each word type in a random 42-word sample, 0–1.', d: 3 },
  { key: 'mattr', name: 'MATTR', ref: 'Covington & McFall 2010', note: 'Average TTR over a moving 50-word window, 0–1.', d: 3 },
  { key: 'msttr', name: 'MSTTR', ref: 'Johnson 1944', note: 'Average TTR over consecutive 50-word segments, 0–1.', d: 3 },
  { key: 'ttr', name: 'TTR', ref: '', note: 'Types divided by tokens. Falls as texts get longer; do not compare across lengths.', d: 3 },
  { key: 'rttr', name: 'Root TTR', ref: 'Guiraud 1954', note: 'Types / √tokens.', d: 2 },
  { key: 'cttr', name: 'Corrected TTR', ref: 'Carroll 1964', note: 'Types / √(2 × tokens).', d: 2 },
  { key: 'herdan', name: 'Herdan’s C', ref: 'Herdan 1960', note: 'log types / log tokens.', d: 3 },
  { key: 'summer', name: 'Summer’s S', ref: 'Summer 1966', note: 'log log types / log log tokens.', d: 3 },
  { key: 'maas', name: 'Maas a²', ref: 'Maas 1972', note: '(log tokens − log types) / (log tokens)². Lower is more varied.', d: 4 },
];

const MD_CATEGORIES = {
  transitions: { label: 'Transitions', note: 'Link steps in the argument', eg: 'however, therefore, in addition' },
  frame_markers: { label: 'Frame markers', note: 'Sequence and stage the text', eg: 'first, finally, to conclude' },
  endophoric_markers: { label: 'Endophoric markers', note: 'Point to other parts of the text', eg: 'see Table 2, as noted above' },
  evidentials: { label: 'Evidentials', note: 'Attribute ideas to sources', eg: 'according to, Smith argues' },
  code_glosses: { label: 'Code glosses', note: 'Rephrase and exemplify', eg: 'for example, in other words' },
  hedges: { label: 'Hedges', note: 'Withhold full commitment', eg: 'may, perhaps, suggest' },
  boosters: { label: 'Boosters', note: 'Express certainty', eg: 'clearly, in fact, demonstrate' },
  attitude_markers: { label: 'Attitude markers', note: 'Express the writer’s attitude', eg: 'unfortunately, important' },
  engagement_markers: { label: 'Engagement markers', note: 'Address the reader directly', eg: 'consider, note that, you' },
  self_mentions: { label: 'Self-mentions', note: 'Refer to the author', eg: 'I, we argue, my' },
};

const UPOS = {
  NOUN: 'Nouns', VERB: 'Verbs', ADJ: 'Adjectives', ADV: 'Adverbs', PRON: 'Pronouns', PROPN: 'Proper nouns',
  DET: 'Determiners', ADP: 'Prepositions', AUX: 'Auxiliaries', CCONJ: 'Coordinators', SCONJ: 'Subordinators',
  PART: 'Particles', NUM: 'Numerals', INTJ: 'Interjections', PUNCT: 'Punctuation', SYM: 'Symbols', X: 'Other',
};

const SAMPLES = [
  {
    id: 'essay',
    label: 'Learner essay',
    note: 'IELTS-style, with errors',
    text:
      'Some people believe that goverments should spend more money on public transport, while others think that building new roads is more important. In my opinion, investing in public transport is the better choice, becuase it benefits more people and protects the enviroment.\n\nFirstly, public transport can carry alot of passengers at once. For example, a single bus can replace forty cars, which reduces traffic and pollution in big cities. Moreover, people who cannot afford a car, such as students and elderly people, depend on buses and trains to go to work or school.\n\nOn the other hand, new roads may be necessary in rural areas where there is no other option. However, I think that roads only encourage people to drive more, and in the long run the traffic will become worse again.\n\nIn conclusion, although roads have some advantages, I strongly believe that spending on public transport is more effective and fair. Goverments should therefore make it cheaper and more reliable so that more people choose to use it.',
  },
  {
    id: 'academic',
    label: 'Research abstract',
    note: 'Academic register',
    text:
      'Previous research has established that vocabulary knowledge is a strong predictor of reading comprehension in a second language. However, the extent to which this relationship depends on text type remains unclear. The present study examined the comprehension of expository and narrative texts by 214 university students of English as a foreign language. Participants completed a vocabulary size test and two reading tasks of comparable length. The results indicate that vocabulary size accounted for a substantially larger proportion of variance in expository comprehension (R² = .41) than in narrative comprehension (R² = .22). We argue that expository texts, which contain a higher density of low-frequency and academic vocabulary, impose greater lexical demands on readers. These findings suggest that instruction should arguably prioritise academic vocabulary for learners preparing for university study, although further research is needed to confirm whether the effect holds across proficiency levels.',
  },
  {
    id: 'story',
    label: 'Short story',
    note: 'Narrative, plain style',
    text:
      'Maria had always loved the smell of rain on dry earth. As a child she would run outside the moment thunder rolled across the valley, splashing barefoot through the puddles that formed along the gravel road. Her grandmother would scold her gently, wrap a thick towel around her shoulders and press a mug of hot cocoa into her cold hands.\n\nYears later, walking home through a sudden downpour in a city far from those hills, she felt the same wild joy rising in her chest. She stopped under a streetlight, closed her eyes and laughed out loud at nothing at all.',
  },
  {
    id: 'news',
    label: 'News report',
    note: 'Journalistic',
    text:
      'The city council has approved a plan to turn three central streets into pedestrian zones by next summer, despite objections from local businesses. Under the proposal, cars will be banned from the area between 10 a.m. and 6 p.m., although deliveries will still be allowed in the early morning.\n\nCouncillors who supported the scheme said it would cut air pollution and make the centre more attractive to visitors. "We have seen this work in other cities," said one. Shop owners, however, warned that fewer drivers could mean fewer customers, and called for a six-month trial before any permanent change.',
  },
];
