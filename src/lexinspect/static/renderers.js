// Per-module renderers. Each `render*` function receives that module's
// `result` object from the `/v1/analyze` envelope and returns a DOM element to
// be inserted into the panel. Rendering is one-shot — panels are rebuilt on
// every Analyze click rather than diffed.
//
// The `cefr-level` panel is the exception: it doesn't appear in `analyze` (the
// model is heavy and opt-in), so its renderer wires up a Run button that
// calls `/v1/cefr-level` on demand.

function renderOverview(r) {
  const wrap = el('div');
  wrap.appendChild(
    el('p', {
      html:
        `<span class="pill">10 modules ran</span> &nbsp; ${r.tagger.counts.total_tokens} tokens · ${r.tagger.counts.sentences} sentences. ` +
        `Reading ease ${r.readability.scores.flesch_reading_ease.toFixed(0)} (Flesch). ` +
        `MTLD ${r.diversity.scores.mtld != null ? r.diversity.scores.mtld.toFixed(0) : 'n/a'}. ` +
        `${r.awl.counts.awl_families} AWL families. ${r.bnc_coca.coverage_pct.toFixed(0)}% within BNC/COCA K1–K10. ` +
        `Dominant CEFR level ${r.cefr.dominant_level || 'n/a'}. ` +
        `Metadiscourse density ${r.metadiscourse.density_per_1000.toFixed(0)} per 1k tokens.`,
    })
  );
  wrap.appendChild(
    el('p', {
      html: `<small>Pick a module from the left rail for the full output. The same JSON is at <code>POST /v1/analyze</code> for agents.</small>`,
    })
  );
  return wrap;
}

/** Generic 3-column key-value layout (scores, counts, averages) used by readability & diversity. */
function renderKV(...sections) {
  const wrap = el('div', { class: 'grid-2' });
  const labels = ['scores', 'counts', 'averages'];
  sections.forEach((s, i) => {
    if (!s) return;
    const col = el('div');
    col.appendChild(el('h3', {}, labels[i] || 'fields'));
    col.appendChild(kvTable(s, fmtNum));
    wrap.appendChild(col);
  });
  return wrap;
}

/**
 * Diversity tab — score table plus the published vocd-D reference ranges
 * from Durán et al. 2004. Reference-only: lexinspect doesn't compute vocd-D,
 * so no automatic comparison is performed against the user's HD-D / MTLD.
 */
function renderDiversity(d) {
  const wrap = el('div');
  wrap.appendChild(renderKV(d.scores, d.counts));

  const refs = d.references;
  if (!refs || !refs.vocd_d_bands) return wrap;

  wrap.appendChild(el('h3', {}, 'vocd-D reference ranges (Durán et al. 2004)'));
  const table = el('table', { class: 'kv' });
  refs.vocd_d_bands.forEach((b) => {
    const row = el('tr');
    row.appendChild(el('td', {}, b.name));
    row.appendChild(el('td', {}, `D ${b.min}–${b.max}`));
    table.appendChild(row);
  });
  wrap.appendChild(table);
  if (refs.note) wrap.appendChild(el('p', { html: `<small>${refs.note}</small>` }));
  return wrap;
}

function renderStatistics(s) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });

  const counts = el('div');
  counts.appendChild(el('h3', {}, 'Counts'));
  counts.appendChild(kvTable(s.counts, fmtNum));
  top.appendChild(counts);

  const avgs = el('div');
  avgs.appendChild(el('h3', {}, 'Averages and ratios'));
  avgs.appendChild(kvTable(s.averages, fmtNum));
  top.appendChild(avgs);

  wrap.appendChild(top);

  if (s.excluded_digits && s.excluded_digits.length) {
    wrap.appendChild(el('h3', {}, `Excluded digits (${s.excluded_digits.length})`));
    wrap.appendChild(
      el('div', {
        html: s.excluded_digits.map((d) => `<span class="pill">${d}</span>`).join(''),
      })
    );
  }
  return wrap;
}

function renderTagger(t) {
  const wrap = el('div');

  if (t.summary) {
    wrap.appendChild(el('h3', {}, 'Summary'));
    wrap.appendChild(kvTable(t.summary, fmtNum));
  }

  const grid = el('div', { class: 'grid-2' });
  const left = el('div');
  left.appendChild(el('h3', {}, 'Universal POS'));
  left.appendChild(barChart(t.upos_distribution, t.counts.total_tokens));
  const right = el('div');
  right.appendChild(el('h3', {}, 'Penn Treebank tags'));
  right.appendChild(barChart(t.ptb_distribution, t.counts.total_tokens));
  grid.appendChild(left);
  grid.appendChild(right);
  wrap.appendChild(grid);

  return wrap;
}

function renderAwl(a) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'AWL summary'));
  stats.appendChild(
    kvTable({
      'AWL coverage': a.coverage_pct + '%',
      'AWL tokens': a.counts.awl_tokens,
      'unique families': a.counts.awl_families,
      'content tokens': a.counts.content_tokens,
    })
  );
  top.appendChild(stats);

  const sublistDist = el('div');
  sublistDist.appendChild(el('h3', {}, 'Per-sublist coverage'));
  const dist = {};
  Object.entries(a.per_sublist).forEach(([k, v]) => {
    dist[`sub ${k}`] = v.tokens;
  });
  sublistDist.appendChild(barChart(dist, a.counts.content_tokens));
  top.appendChild(sublistDist);
  wrap.appendChild(top);

  if (a.families_found && a.families_found.length) {
    wrap.appendChild(el('h3', {}, `Families found (${a.families_found.length})`));
    wrap.appendChild(
      el('div', {
        html: a.families_found.map((f) => `<span class="pill" style="margin:2px">${f}</span>`).join(''),
      })
    );
  }
  return wrap;
}

function renderBncCoca(b) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'BNC/COCA summary'));
  stats.appendChild(
    kvTable({
      'on-list coverage': b.coverage_pct + '%',
      'on-list tokens': b.counts.on_list_tokens,
      'off-list tokens': b.counts.off_list_tokens,
      'content tokens': b.counts.content_tokens,
    })
  );
  top.appendChild(stats);

  const cumChart = el('div');
  cumChart.appendChild(el('h3', {}, 'Cumulative coverage curve'));
  const cum = el('div', { class: 'bar-chart' });
  Object.entries(b.per_band).forEach(([band, v]) => {
    const row = el('div', { class: 'bar-row' });
    row.appendChild(el('div', { class: 'lbl' }, `K${band}`));
    const track = el('div', { class: 'bar-track' });
    const fill = el('div', { class: 'bar-fill cumulative' });
    fill.style.width = `${v.cumulative_coverage_pct}%`;
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el('div', { class: 'num' }, `${v.cumulative_coverage_pct.toFixed(1)}%`));
    cum.appendChild(row);
  });
  cumChart.appendChild(cum);
  top.appendChild(cumChart);
  wrap.appendChild(top);

  if (b.off_list_sample && b.off_list_sample.length) {
    wrap.appendChild(el('h3', {}, `Off-list sample (${b.off_list_sample.length})`));
    wrap.appendChild(
      el('div', {
        html: b.off_list_sample.map((w) => `<span class="pill" style="margin:2px">${w}</span>`).join(''),
      })
    );
  }
  return wrap;
}

function renderNgsl(n) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'NGSL + NAWL'));
  stats.appendChild(
    kvTable({
      'NGSL coverage': n.coverage_pct.ngsl + '%',
      'NAWL coverage': n.coverage_pct.nawl + '%',
      'NGSL + NAWL': n.coverage_pct.ngsl_plus_nawl + '%',
      'off-list': n.coverage_pct.off_list + '%',
      'NGSL lemmas': n.counts.ngsl_lemmas,
      'NAWL lemmas': n.counts.nawl_lemmas,
    })
  );
  top.appendChild(stats);

  const split = el('div');
  split.appendChild(el('h3', {}, 'Distribution'));
  split.appendChild(
    barChart(
      {
        NGSL: n.counts.ngsl_tokens,
        NAWL: n.counts.nawl_tokens,
        'off-list': n.counts.off_list_tokens,
      },
      n.counts.content_tokens
    )
  );
  top.appendChild(split);
  wrap.appendChild(top);
  return wrap;
}

function renderPhrase(p) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'PHRASE list summary'));
  stats.appendChild(
    kvTable({
      'total hits': p.counts.total_hits,
      'unique phrases': p.counts.unique_phrases,
      'content tokens': p.counts.content_tokens,
    })
  );
  top.appendChild(stats);

  const bandChart = el('div');
  bandChart.appendChild(el('h3', {}, 'Hits per K-band'));
  bandChart.appendChild(
    barChart(
      Object.fromEntries(Object.entries(p.hits_per_k_band).map(([k, v]) => [`K${k}`, v])),
      p.counts.total_hits || 1
    )
  );
  top.appendChild(bandChart);
  wrap.appendChild(top);

  if (p.hits && p.hits.length) {
    wrap.appendChild(el('h3', {}, `Hits (${p.hits.length})`));
    const list = el('div', { class: 'hits-list' });
    p.hits.forEach((h) => {
      const item = el('div', { class: 'hit-item' });
      item.appendChild(el('div', { class: 'cat' }, `K${h.k_band}`));
      item.appendChild(
        el(
          'div',
          { class: 'surface' },
          h.phrase + (h.surface !== h.phrase.toLowerCase() ? ` ("${h.surface}")` : '')
        )
      );
      item.appendChild(el('div', { class: 'meta' }, `rank ${h.rank}`));
      list.appendChild(item);
    });
    wrap.appendChild(list);
  } else {
    wrap.appendChild(el('p', { html: '<small>No PHRASE list expressions detected.</small>' }));
  }
  return wrap;
}

function renderCefr(c) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'CEFR summary'));
  stats.appendChild(
    kvTable({
      'on-list coverage': c.coverage_pct + '%',
      'on-list tokens': c.counts.on_list_tokens,
      'off-list tokens': c.counts.off_list_tokens,
      'dominant level': c.dominant_level || '—',
      '95th-percentile level': c.estimated_level_95th || '—',
    })
  );
  top.appendChild(stats);

  const dist = el('div');
  dist.appendChild(el('h3', {}, 'Per-level distribution'));
  const chart = el('div', { class: 'bar-chart' });
  Object.entries(c.per_level).forEach(([lvl, v]) => {
    const row = el('div', { class: 'bar-row' });
    row.appendChild(el('div', { class: 'lbl' }, lvl));
    const track = el('div', { class: 'bar-track' });
    const fill = el('div', { class: 'bar-fill' });
    fill.style.width = `${v.coverage_pct}%`;
    track.appendChild(fill);
    const cum = el('div', { class: 'bar-fill cumulative' });
    cum.style.width = `${v.cumulative_coverage_pct - v.coverage_pct}%`;
    cum.style.position = 'absolute';
    cum.style.left = `${v.coverage_pct}%`;
    cum.style.top = '0';
    track.appendChild(cum);
    row.appendChild(track);
    row.appendChild(
      el('div', { class: 'num' }, `${v.coverage_pct.toFixed(1)}% / ${v.cumulative_coverage_pct.toFixed(1)}%`)
    );
    chart.appendChild(row);
  });
  dist.appendChild(chart);
  top.appendChild(dist);
  wrap.appendChild(top);

  wrap.appendChild(el('div', { class: 'caveat', html: c.caveat }));
  return wrap;
}

/** Renders a Run button; on click POSTs to /v1/cefr-level and renders the result. */
function renderCefrLevel() {
  const wrap = el('div');
  const runBtn = el('button', {}, 'Run CEFR classifier');
  const resultWrap = el('div');
  resultWrap.style.marginTop = '14px';

  runBtn.addEventListener('click', async () => {
    const t = $('text').value;
    if (!t || !t.trim()) {
      resultWrap.innerHTML = '<p><small>Paste some text in the box above first.</small></p>';
      return;
    }
    runBtn.disabled = true;
    runBtn.textContent = 'Running classifier (~3–5s)…';
    resultWrap.innerHTML = '<p><small>Sending to /v1/cefr-level …</small></p>';
    try {
      const r = await fetch('/v1/cefr-level', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: t, source: '<web>' }),
      });
      if (r.status === 503) {
        const j = await r.json().catch(() => ({}));
        const detail = (j.detail || 'Optional extra not installed.').replace(/\n/g, '<br>');
        resultWrap.innerHTML = '<div class="caveat"><b>Optional extra not installed.</b><br>' + detail + '</div>';
        return;
      }
      if (!r.ok) {
        const txt = await r.text();
        resultWrap.innerHTML = '<div class="caveat"><b>Error ' + r.status + '</b>: ' + txt + '</div>';
        return;
      }
      const data = await r.json();
      resultWrap.innerHTML = '';
      resultWrap.appendChild(renderCefrLevelResult(data.result));
    } catch (e) {
      resultWrap.innerHTML = '<div class="caveat"><b>Network error</b>: ' + (e && e.message ? e.message : String(e)) + '</div>';
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = 'Run CEFR classifier';
    }
  });

  wrap.appendChild(runBtn);
  wrap.appendChild(resultWrap);
  return wrap;
}

function renderCefrLevelResult(c) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });

  const stats = el('div');
  stats.appendChild(el('h3', {}, 'Prediction'));
  stats.appendChild(
    kvTable({
      'predicted level': c.level || '—',
      confidence: c.confidence != null ? (c.confidence * 100).toFixed(2) + '%' : '—',
      'top-2': Array.isArray(c.top_2) && c.top_2.length ? c.top_2.join(' → ') : '—',
      model: c.model,
      method: c.method,
    })
  );
  top.appendChild(stats);

  const distWrap = el('div');
  distWrap.appendChild(el('h3', {}, 'Per-level probability'));
  const chart = el('div', { class: 'bar-chart' });
  Object.entries(c.all_levels || {}).forEach(([lvl, p]) => {
    const pct = (typeof p === 'number' ? p : 0) * 100;
    const row = el('div', { class: 'bar-row' });
    row.appendChild(el('div', { class: 'lbl' }, lvl));
    const track = el('div', { class: 'bar-track' });
    const fill = el('div', { class: 'bar-fill' });
    fill.style.width = pct + '%';
    track.appendChild(fill);
    row.appendChild(track);
    row.appendChild(el('div', { class: 'num' }, pct.toFixed(2) + '%'));
    chart.appendChild(row);
  });
  distWrap.appendChild(chart);
  top.appendChild(distWrap);
  wrap.appendChild(top);

  if (c.caveat) wrap.appendChild(el('div', { class: 'caveat', html: c.caveat }));
  return wrap;
}

/**
 * Errors tab — like cefr-level, opt-in. Renders a variant toggle (gb/us) and
 * a Run button; on click POSTs to /v1/errors and renders the result. The
 * extra has to be installed and the dictionary fetched on first call (~1.5MB).
 */
function renderErrors() {
  const wrap = el('div');

  const controls = el('div');
  controls.style.display = 'flex';
  controls.style.gap = '12px';
  controls.style.alignItems = 'center';
  controls.style.flexWrap = 'wrap';

  const variantLabel = el('span', {}, 'Variant:');
  variantLabel.style.color = 'var(--muted)';
  variantLabel.style.fontSize = '12px';

  const variantSelect = el('select');
  variantSelect.style.fontFamily = 'var(--mono)';
  variantSelect.style.padding = '6px 10px';
  variantSelect.style.border = '1px solid var(--border)';
  variantSelect.style.background = 'var(--surface)';
  variantSelect.style.color = 'var(--ink)';
  ['gb', 'us'].forEach((v) => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v === 'gb' ? 'British (gb)' : 'American (us)';
    variantSelect.appendChild(opt);
  });

  const runBtn = el('button', {}, 'Check spelling');
  controls.appendChild(variantLabel);
  controls.appendChild(variantSelect);
  controls.appendChild(runBtn);

  const resultWrap = el('div');
  resultWrap.style.marginTop = '14px';

  runBtn.addEventListener('click', async () => {
    const t = $('text').value;
    if (!t || !t.trim()) {
      resultWrap.innerHTML = '<p><small>Paste some text in the box above first.</small></p>';
      return;
    }
    const variant = variantSelect.value;
    runBtn.disabled = true;
    runBtn.textContent = 'Checking…';
    resultWrap.innerHTML = '<p><small>Sending to /v1/errors …</small></p>';
    try {
      const r = await fetch('/v1/errors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: t, source: '<web>', variant }),
      });
      if (r.status === 503) {
        const j = await r.json().catch(() => ({}));
        const detail = (j.detail || 'Optional extra not installed.').replace(/\n/g, '<br>');
        resultWrap.innerHTML = '<div class="caveat"><b>Optional extra not installed.</b><br>' + detail + '</div>';
        return;
      }
      if (!r.ok) {
        const txt = await r.text();
        resultWrap.innerHTML = '<div class="caveat"><b>Error ' + r.status + '</b>: ' + txt + '</div>';
        return;
      }
      const data = await r.json();
      resultWrap.innerHTML = '';
      resultWrap.appendChild(renderErrorsResult(data.result));
    } catch (e) {
      resultWrap.innerHTML = '<div class="caveat"><b>Network error</b>: ' + (e && e.message ? e.message : String(e)) + '</div>';
    } finally {
      runBtn.disabled = false;
      runBtn.textContent = 'Check spelling';
    }
  });

  wrap.appendChild(controls);
  wrap.appendChild(resultWrap);
  return wrap;
}

function renderErrorsResult(r) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });

  const stats = el('div');
  stats.appendChild(el('h3', {}, 'Summary'));
  stats.appendChild(
    kvTable({
      variant: r.variant,
      'tokens checked': r.counts.tokens_checked,
      sentences: r.counts.sentences,
      'errors total': r.counts.errors_total,
      'unique errors': r.counts.unique_errors,
      'errors per sentence': r.rates.errors_per_sentence,
      'errors per 100 words': r.rates.errors_per_100_words,
    })
  );
  top.appendChild(stats);

  const provenance = el('div');
  provenance.appendChild(el('h3', {}, 'Dictionary'));
  provenance.appendChild(
    kvTable({
      source: r.dictionary.source,
      licence: r.dictionary.licence,
    })
  );
  top.appendChild(provenance);
  wrap.appendChild(top);

  if (r.errors && r.errors.length) {
    wrap.appendChild(el('h3', {}, `Flagged tokens (${r.errors.length})`));
    const list = el('div', { class: 'hits-list' });
    r.errors.forEach((err) => {
      const item = el('div', { class: 'hit-item' });
      item.appendChild(el('div', { class: 'cat' }, '×'));
      item.appendChild(el('div', { class: 'surface' }, err.surface));
      item.appendChild(el('div', { class: 'meta' }, `×${err.count}`));
      list.appendChild(item);
    });
    wrap.appendChild(list);
  } else {
    wrap.appendChild(el('p', { html: '<small>No spelling errors detected.</small>' }));
  }

  if (r.caveat) wrap.appendChild(el('div', { class: 'caveat', html: r.caveat }));
  return wrap;
}

function renderMetadiscourse(m) {
  const wrap = el('div');
  const top = el('div', { class: 'grid-2' });
  const stats = el('div');
  stats.appendChild(el('h3', {}, 'Metadiscourse summary'));
  stats.appendChild(
    kvTable({
      'total hits': m.counts.total_hits,
      'interactive hits': m.counts.interactive_hits,
      'interactional hits': m.counts.interactional_hits,
      'density per 1k': m.density_per_1000,
      'content tokens': m.counts.content_tokens,
    })
  );
  top.appendChild(stats);

  const catChart = el('div');
  catChart.appendChild(el('h3', {}, 'Per category (hits)'));
  const cats = {};
  Object.entries(m.per_category).forEach(([k, v]) => {
    cats[k] = v.hits;
  });
  catChart.appendChild(barChart(cats, m.counts.total_hits || 1));
  top.appendChild(catChart);
  wrap.appendChild(top);

  if (m.hits && m.hits.length) {
    wrap.appendChild(el('h3', {}, `Hits (${m.hits.length})`));
    const list = el('div', { class: 'hits-list' });
    m.hits.forEach((h) => {
      const item = el('div', { class: 'hit-item' });
      item.appendChild(el('div', { class: 'cat' }, h.category.replace(/_/g, ' ')));
      item.appendChild(el('div', { class: 'surface' }, h.surface));
      item.appendChild(el('div', { class: 'meta' }, h.dimension));
      list.appendChild(item);
    });
    wrap.appendChild(list);
  }
  return wrap;
}
