// App entry — wires the textarea, fixture buttons, and Analyze action up to
// the renderers. Also owns the click-to-explain summary chips and the small
// explainer panel that pops out below them.

// ---- Explainer panel (summary chip click-to-explain) ----

function showExplainer(metricKey, value) {
  const info = METRIC_INFO[metricKey];
  if (!info) return;
  const exBox = $('explainer');
  const exContent = $('exContent');

  let html = `<h3 class="ex-title">${info.title}</h3>`;
  if (value != null) html += `<div class="ex-value">Your score: <b>${value}</b></div>`;
  html += `<p class="ex-desc">${info.desc}</p>`;

  if (info.scale && typeof value === 'number') {
    const v = Math.max(info.scale.min, Math.min(info.scale.max, value));
    const pct = ((v - info.scale.min) / (info.scale.max - info.scale.min)) * 100;
    html += `<div class="scale">
      <div class="scale-bar"><div class="scale-marker" style="left:${pct}%"></div></div>
      <div class="scale-labels"><span>${info.scale.leftLabel} (${info.scale.min})</span><span>${info.scale.rightLabel} (${info.scale.max})</span></div>`;
    if (info.bands) {
      // No fallback band. A score outside every band means the formula has run
      // off its validated range — which happens constantly on short input, where
      // Flesch Reading Ease exceeds 100 and grade levels go negative. Falling
      // back to the last band used to label a 5-word sentence (ease 117) as
      // "Very difficult — postgraduate reader", the exact inverse of the truth.
      const band = info.bands.find(([lo, hi]) => value >= lo && value < hi);
      if (band) {
        html += `<div class="scale-band">Reading: <b>${band[2]}</b></div>`;
      } else {
        html +=
          `<div class="scale-band scale-band-offscale">Off scale — <b>${value}</b> falls outside ` +
          `this formula's validated range (${info.scale.min}–${info.scale.max}), which usually ` +
          `means the text is too short to score. Add more text.</div>`;
      }
    }
    html += `</div>`;
  } else if (info.bands && info.isCategorical) {
    const band = info.bands.find(([key]) => key === value);
    if (band) html += `<div class="scale-band" style="margin-top:0">Reading: <b>${band[2]}</b></div>`;
  }

  if (info.caveats && info.caveats.length) {
    html +=
      `<div class="ex-caveats"><b>Worth knowing</b><ul>` +
      info.caveats.map((c) => `<li>${c}</li>`).join('') +
      `</ul></div>`;
  }

  exContent.innerHTML = html;
  exBox.classList.add('visible');
  document.querySelectorAll('.chip').forEach((c) => c.classList.toggle('active', c.dataset.metricKey === metricKey));
  exBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideExplainer() {
  $('explainer').classList.remove('visible');
  document.querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
}

// ---- Bootstrapping ----

const text = $('text');
const status = $('status');
const results = $('results');
const summary = $('summary');
const tabs = $('tabs');
const panels = $('panels');

function liveCount() {
  const t = text.value;
  $('liveChars').textContent = t.length;
  $('liveWords').textContent = (t.trim().match(/\S+/g) || []).length;
}

text.addEventListener('input', liveCount);

document.querySelectorAll('[data-fixture]').forEach((btn) => {
  btn.addEventListener('click', () => {
    text.value = FIXTURES[btn.dataset.fixture];
    liveCount();
  });
});

$('clearBtn').addEventListener('click', () => {
  text.value = '';
  results.classList.remove('visible');
  status.textContent = '';
  liveCount();
});

$('exClose').addEventListener('click', hideExplainer);

fetch('/v1/version')
  .then((r) => r.json())
  .then((v) => {
    $('version-meta').textContent = `v${v.version} · schema ${v.schema_version}`;
  })
  .catch(() => {
    $('version-meta').textContent = 'offline';
  });

// Optional modules need install extras the hosted build doesn't ship. Ask the
// server which ones are live so we don't render a tab that can only 501. Start
// optimistic: a self-hosted `uv sync --all-extras` has everything, and if the
// probe fails we'd rather show a tab that errors than silently hide a feature.
const OPTIONAL_TAB_MODULE = { 'cefr-level': 'cefr_level' };
let OPTIONAL_AVAILABLE = { cefr_level: true };

const capabilitiesReady = fetch('/v1/schema')
  .then((r) => r.json())
  .then((s) => {
    if (s.optional_available) OPTIONAL_AVAILABLE = s.optional_available;
  })
  .catch(() => {});

$('analyzeBtn').addEventListener('click', async () => {
  const body = text.value.trim();
  if (!body) {
    status.textContent = 'Paste some text first.';
    status.className = 'error';
    return;
  }
  status.textContent = 'Analysing';
  status.className = 'loading';
  $('analyzeBtn').disabled = true;
  results.classList.remove('visible');

  try {
    const r = await fetch('/v1/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: body, source: 'web-ui' }),
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${await r.text()}`);
    const data = await r.json();
    await capabilitiesReady;
    render(data);
    status.textContent = '';
    status.className = '';
    results.classList.add('visible');
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
    status.className = 'error';
  } finally {
    $('analyzeBtn').disabled = false;
  }
});

/** Share of on-list content tokens whose CEFR-J level is B2 or above. */
function cefrB2Plus(cefr) {
  return ['B2', 'C1', 'C2'].reduce((sum, lvl) => sum + (cefr.per_level[lvl]?.coverage_pct || 0), 0);
}

// ---- Top-level render orchestrator ----

function render(data) {
  const r = data.results;
  summary.innerHTML = '';
  tabs.innerHTML = '';
  panels.innerHTML = '';

  // Headline summary chips. `metricKey` points at METRIC_INFO; `rawValue` is
  // the un-formatted number so the explainer's scale/band lookup gets the
  // right input.
  const fre = r.readability.scores.flesch_reading_ease;
  const fk = r.readability.scores.flesch_kincaid_grade;
  const mtld = r.diversity.scores.mtld;
  const chips = [
    {
      metricKey: 'words',
      label: 'words',
      value: r.readability.counts.words,
      rawValue: r.readability.counts.words,
      sub: `${r.readability.counts.sentences} sentences`,
    },
    {
      metricKey: 'flesch_reading_ease',
      label: 'reading ease',
      value: fre.toFixed(0),
      rawValue: fre,
      sub: 'Flesch',
    },
    {
      metricKey: 'flesch_kincaid_grade',
      label: 'FK grade',
      value: fk.toFixed(1),
      rawValue: fk,
      sub: 'US school grade',
    },
    {
      metricKey: 'mtld',
      label: 'MTLD',
      value: mtld != null ? mtld.toFixed(1) : '—',
      rawValue: mtld,
      sub: 'lex. diversity',
    },
    {
      metricKey: 'awl_coverage',
      label: 'AWL coverage',
      value: `${r.awl.coverage_pct.toFixed(1)}%`,
      rawValue: r.awl.coverage_pct,
      sub: `${r.awl.counts.awl_families} families`,
    },
    {
      metricKey: 'bnc_coca_coverage',
      label: 'BNC/COCA on-list',
      value: `${r.bnc_coca.coverage_pct.toFixed(1)}%`,
      rawValue: r.bnc_coca.coverage_pct,
      sub: 'K1–K10',
    },
    // Deliberately not `dominant_level`. That is the argmax of per-level token
    // counts, and function words swamp it, so it reads "A1" on a C1 text — the
    // module's own caveat says not to surface it alone. B2+ coverage separates
    // registers the way a reader expects: 0% on simple prose, ~29% on academic.
    {
      metricKey: 'cefr_b2plus',
      label: 'CEFR B2+ vocab',
      value: `${cefrB2Plus(r.cefr).toFixed(1)}%`,
      rawValue: cefrB2Plus(r.cefr),
      sub: `${r.cefr.coverage_pct.toFixed(0)}% on-list`,
    },
    {
      metricKey: 'metadiscourse_density',
      label: 'metadiscourse',
      value: r.metadiscourse.density_per_1000.toFixed(0),
      rawValue: r.metadiscourse.density_per_1000,
      sub: 'per 1k tokens',
    },
  ];

  hideExplainer();
  chips.forEach((c) => {
    const elx = document.createElement('div');
    elx.className = 'chip';
    elx.dataset.metricKey = c.metricKey;
    elx.innerHTML =
      `<div class="label"><span>${c.label}</span>` +
      `<span class="info-mark" role="button" tabindex="0" aria-label="What does ${c.label} mean?" title="What does this mean?">?</span></div>` +
      `<div class="value">${c.value}</div>` +
      `<div class="sublabel">${c.sub}</div>`;
    const mark = elx.querySelector('.info-mark');
    const toggle = (e) => {
      e.stopPropagation();
      if (elx.classList.contains('active')) hideExplainer();
      else showExplainer(c.metricKey, c.rawValue);
    };
    mark.addEventListener('click', toggle);
    mark.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle(e);
      }
    });
    summary.appendChild(elx);
  });

  // Each module is a (renderer, optional intro) pair. Adding a module = one
  // entry plus a METRIC_INFO/MODULE_INTROS update.
  const renderers = {
    overview: () => renderOverview(r),
    readability: () => renderKV(r.readability.scores, r.readability.counts, r.readability.averages),
    statistics: () => renderStatistics(r.statistics),
    diversity: () => renderDiversity(r.diversity),
    tagger: () => renderTagger(r.tagger),
    awl: () => renderAwl(r.awl),
    'bnc/coca': () => renderBncCoca(r.bnc_coca),
    ngsl: () => renderNgsl(r.ngsl),
    phrase: () => renderPhrase(r.phrase),
    cefr: () => renderCefr(r.cefr),
    'cefr-level': () => renderCefrLevel(),
    metadiscourse: () => renderMetadiscourse(r.metadiscourse),
    errors: () => renderErrors(),
  };

  // Sidebar groups. Order here defines panel order; flat list flows top to
  // bottom in the nav. To add a module: append to a group + add a renderers
  // entry. The 'overview' group has no label — it's the landing.
  const NAV_GROUPS = [
    { label: null, items: ['overview'] },
    { label: 'text', items: ['readability', 'statistics', 'diversity', 'tagger'] },
    { label: 'vocabulary', items: ['awl', 'bnc/coca', 'ngsl', 'phrase', 'cefr', 'cefr-level'] },
    { label: 'craft', items: ['metadiscourse', 'errors'] },
  ]
    // Drop tabs whose module isn't installed here, then drop groups left empty.
    .map((g) => ({
      ...g,
      items: g.items.filter((name) => {
        const module = OPTIONAL_TAB_MODULE[name];
        return !module || OPTIONAL_AVAILABLE[module];
      }),
    }))
    .filter((g) => g.items.length > 0);

  const flatOrder = NAV_GROUPS.flatMap((g) => g.items);

  // Build panels in flat order (matches nav top-to-bottom).
  flatOrder.forEach((name, idx) => {
    const panel = document.createElement('div');
    panel.className = 'panel' + (idx === 0 ? ' active' : '');
    const moduleInfo = MODULE_INTROS[name];
    if (moduleInfo) {
      const intro = document.createElement('div');
      intro.className = 'module-intro';
      let introHtml = moduleInfo.intro;
      if (moduleInfo.caveat) introHtml += `<span class="caveat-line">${moduleInfo.caveat}</span>`;
      intro.innerHTML = introHtml;
      panel.appendChild(intro);
    }
    panel.appendChild(renderers[name]());
    panels.appendChild(panel);
  });

  // Build grouped sidebar nav.
  let panelIdx = 0;
  NAV_GROUPS.forEach((group) => {
    const groupEl = document.createElement('div');
    groupEl.className = 'nav-group';
    if (group.label) {
      const label = document.createElement('div');
      label.className = 'nav-group-label';
      label.textContent = group.label;
      groupEl.appendChild(label);
    }
    group.items.forEach((name) => {
      const idx = panelIdx++;
      const item = document.createElement('button');
      item.className = 'nav-item' + (idx === 0 ? ' active' : '');
      item.textContent = name;
      item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
        document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
        item.classList.add('active');
        panels.children[idx].classList.add('active');
      });
      groupEl.appendChild(item);
    });
    tabs.appendChild(groupEl);
  });
}

// Initialise live counters at first paint.
liveCount();
