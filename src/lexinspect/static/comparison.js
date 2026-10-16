// Progressive enhancements: all findings and downloads work without JavaScript.
'use strict';
const filter = document.getElementById('differences-only');
filter.closest('label').hidden = false;
filter.addEventListener('change', () => {
  document.querySelectorAll('.metric-group').forEach(group => {
    let visible = 0;
    group.querySelectorAll('.metric-row').forEach(row => {
      row.hidden = filter.checked && row.dataset.different !== 'true';
      if (!row.hidden) visible += 1;
    });
    group.hidden = visible === 0;
  });
  document.getElementById('filter-status').textContent = filter.checked
    ? 'Showing four measures with different results.'
    : 'Showing all eighteen measures.';
});
const copy = document.getElementById('copy-passage');
if (navigator.clipboard && window.isSecureContext) {
  copy.hidden = false;
  copy.addEventListener('click', async () => {
    const text = Array.from(document.querySelectorAll('#comparison-passage p'))
      .map(p => p.textContent).join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      document.getElementById('copy-status').textContent = 'Passage copied';
    } catch {
      document.getElementById('copy-status').textContent = 'Copy unavailable. Download the text instead.';
    }
  });
}
