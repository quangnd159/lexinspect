// Interface language. Loaded in <head>, before every other script.
//
// Messages are keyed by their English text (gettext style), so the code reads
// as English and a missing translation falls back to it:
//
//   t('Words above {level}', { level: 'B1' })
//   tn(n, '{n} word', '{n} words')              plural, by Intl.PluralRules
//   tr('From the <a>PHRASE List</a>', {}, { a: (s) => h('a', {href}, s) })
//                                               rich text: returns nodes
//   N_('Hedges')                                marks a constant for
//                                               extraction; translate it with
//                                               t() where it is shown
//
// Catalogues live in /static/locales/<code>.json: {"English": "Translation"},
// and for plurals {"{n} word | {n} words": {"one": "…", "other": "…"}} with
// the categories the locale's plural rules use. `{name}` placeholders and
// <tag>…</tag> pairs must survive translation; tests/test_i18n.py checks that
// every catalogue covers every message in the code and keeps its placeholders.
//
// The text being analysed is English whatever the interface language, so the
// reader, the editor and quoted words keep dir="ltr" and lang="en".

const I18n = (() => {
  const VERSION = '0.5.0';
  /** [code, endonym]. The order is the language menu's. */
  const LOCALES = [
    ['en', 'English'],
    ['ar', 'العربية'],
    ['de', 'Deutsch'],
    ['es', 'Español'],
    ['fr', 'Français'],
    ['id', 'Bahasa Indonesia'],
    ['ja', '日本語'],
    ['ko', '한국어'],
    ['pt-BR', 'Português (Brasil)'],
    ['tr', 'Türkçe'],
    ['vi', 'Tiếng Việt'],
    ['zh-CN', '简体中文'],
  ];
  const CODES = LOCALES.map(([c]) => c);
  const RTL = new Set(['ar']);
  const KEY = 'lexinspect:locale';

  const read = () => {
    try {
      return localStorage.getItem(KEY);
    } catch {
      return null;
    }
  };
  const write = (v) => {
    try {
      localStorage.setItem(KEY, v);
    } catch {}
  };

  /** A supported code for a BCP 47 tag, or null. */
  function match(tag) {
    if (!tag) return null;
    const t = String(tag).toLowerCase();
    const exact = CODES.find((c) => c.toLowerCase() === t);
    if (exact) return exact;
    const base = t.split('-')[0];
    if (base === 'zh') {
      // Simplified only: Traditional-script readers get English rather than
      // a script they don't use.
      return /^zh(-hans|-cn|-sg|-my)?(-|$)/.test(t) && !/-(hant|tw|hk|mo)/.test(t) ? 'zh-CN' : null;
    }
    if (base === 'pt') return 'pt-BR';
    return CODES.find((c) => c === base) ?? null;
  }

  function detect() {
    const fromUrl = new URLSearchParams(location.search).get('lang');
    if (match(fromUrl)) return match(fromUrl);
    const stored = read();
    if (match(stored)) return match(stored);
    for (const l of navigator.languages || [navigator.language]) {
      const m = match(l);
      if (m) return m;
    }
    return 'en';
  }

  let locale = detect();
  let catalog = {};
  let rules = new Intl.PluralRules(locale);
  const listeners = new Set();

  // Until the catalogue is in, keep the page hidden rather than flash English.
  const root = document.documentElement;
  if (locale !== 'en') root.dataset.i18nPending = '';
  setDocument();

  function setDocument() {
    root.lang = locale;
    root.dir = RTL.has(locale) ? 'rtl' : 'ltr';
  }

  async function load(code) {
    if (code === 'en') return {};
    const res = await fetch(`/static/locales/${code}.json?v=${VERSION}`);
    if (!res.ok) throw new Error(`locale ${code}: ${res.status}`);
    return res.json();
  }

  function fill(s, vars) {
    if (!vars) return s;
    return s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] == null ? m : String(vars[k])));
  }

  function lookup(key) {
    const v = catalog[key];
    return v == null || v === '' ? null : v;
  }

  /** Translate `s`, filling `{name}` from `vars`. */
  function t(s, vars) {
    const v = lookup(s);
    return fill(typeof v === 'string' ? v : s, vars);
  }

  /** Plural: `one`/`other` are the English forms; `{n}` is filled with n, formatted. */
  function tn(n, one, other, vars = {}) {
    const key = `${one} | ${other}`;
    const v = lookup(key);
    const all = { n: typeof num === 'function' ? num(n) : String(n), ...vars };
    if (v && typeof v === 'object') {
      const cat = rules.select(n);
      return fill(v[cat] ?? v.other ?? other, all);
    }
    return fill(n === 1 ? one : other, all);
  }

  /** Rich text: <tag>…</tag> pairs become tags[tag](inner). Returns an array for h(). */
  function tr(s, vars, tags = {}) {
    const str = t(s, vars);
    const out = [];
    let last = 0;
    const re = /<(\w+)>([\s\S]*?)<\/\1>/g;
    let m;
    while ((m = re.exec(str))) {
      if (m.index > last) out.push(str.slice(last, m.index));
      out.push(tags[m[1]] ? tags[m[1]](m[2]) : m[2]);
      last = re.lastIndex;
    }
    if (last < str.length) out.push(str.slice(last));
    return out;
  }

  /** Static markup: data-i18n="English" replaces the text; data-i18n-attr="aria-label|title|placeholder"
   *  translates those attributes from their English values (kept in data-i18n-src-*). */
  function apply(scope = document) {
    for (const el of scope.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
    for (const el of scope.querySelectorAll('[data-i18n-attr]')) {
      for (const attr of el.dataset.i18nAttr.split('|')) {
        const srcKey = `i18nSrc${attr.replace(/(^|-)(\w)/g, (_, _d, c) => c.toUpperCase())}`;
        if (!(srcKey in el.dataset)) el.dataset[srcKey] = el.getAttribute(attr) ?? '';
        el.setAttribute(attr, t(el.dataset[srcKey]));
      }
    }
    const title = document.querySelector('meta[name="i18n-title"]')?.content;
    if (title) document.title = t(title);
  }

  async function use(code, { save = false } = {}) {
    const next = match(code) ?? 'en';
    let cat = {};
    try {
      cat = await load(next);
    } catch {
      // Unreachable catalogue: stay readable in English.
      cat = {};
    }
    locale = Object.keys(cat).length || next === 'en' ? next : 'en';
    catalog = cat;
    rules = new Intl.PluralRules(locale);
    if (save) write(locale);
    setDocument();
    if (document.readyState === 'loading') await new Promise((r) => document.addEventListener('DOMContentLoaded', r, { once: true }));
    apply();
    delete root.dataset.i18nPending;
    listeners.forEach((fn) => fn(locale));
    return locale;
  }

  const ready = use(locale);
  // Never leave the page hidden, whatever happens to the request.
  setTimeout(() => delete root.dataset.i18nPending, 2500);

  /** A language menu: a native <select>, labelled by its own endonyms, with
   *  the icons from icons.js (loaded after this file, before the picker is built). */
  function picker() {
    const sel = document.createElement('select');
    sel.className = 'lang-select';
    sel.setAttribute('aria-label', N_('Language'));
    sel.dataset.i18nAttr = 'aria-label';
    for (const [code, name] of LOCALES) {
      const o = document.createElement('option');
      o.value = code;
      o.textContent = name;
      o.lang = code;
      sel.appendChild(o);
    }
    sel.value = locale;
    sel.addEventListener('change', () => use(sel.value, { save: true }));
    listeners.add((l) => (sel.value = l));
    const wrap = document.createElement('span');
    wrap.className = 'lang-pick';
    if (typeof icon === 'function') wrap.append(icon('languages'), sel, icon('chevron-down', { size: 14 }));
    else wrap.append(sel);
    return wrap;
  }

  return {
    LOCALES,
    get locale() {
      return locale;
    },
    /** Locale for Intl formatters. English follows British conventions, like the
     *  copy; Arabic keeps Western digits, so levels and bands read the same. */
    get intl() {
      return locale === 'ar' ? 'ar-u-nu-latn' : locale === 'en' ? 'en-GB' : locale;
    },
    get rtl() {
      return RTL.has(locale);
    },
    ready,
    use,
    apply,
    picker,
    onChange(fn) {
      listeners.add(fn);
    },
    t,
    tn,
    tr,
  };
})();

const t = I18n.t;
const tn = I18n.tn;
const tr = I18n.tr;
/** Marks a string for extraction without translating it here. */
const N_ = (s) => s;
