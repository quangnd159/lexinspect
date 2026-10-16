// Progressive enhancements: all findings and downloads work without JavaScript.
'use strict';
// Input modality gates motion: keyboard interactions remain immediate.
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const passage = document.querySelector('.comparison-passage');
const passageBody = document.getElementById('comparison-passage');
let passageAnimation;
let feedbackAnimation;
const cancelMotion = () => {
  passageAnimation?.cancel();
  feedbackAnimation?.cancel();
};
document.addEventListener('pointerdown', () => {
  document.body.dataset.input = 'pointer';
}, { passive: true });
document.addEventListener('keydown', () => {
  document.body.dataset.input = 'keyboard';
  cancelMotion();
}, true);
reducedMotion.addEventListener('change', cancelMotion);
passage.addEventListener('toggle', () => {
  passageAnimation?.cancel();
  if (passage.open && document.body.dataset.input === 'pointer' && !reducedMotion.matches) {
    passageAnimation = passageBody.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 150,
      easing: getComputedStyle(document.documentElement).getPropertyValue('--ease-out').trim(),
    });
  }
});
const feedback = document.getElementById('copy-status');
function showCopyFeedback(message, pointerInitiated) {
  feedbackAnimation?.cancel();
  feedback.textContent = message;
  if (pointerInitiated && document.body.dataset.input === 'pointer') {
    feedbackAnimation = feedback.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: 150,
      easing: getComputedStyle(document.documentElement).getPropertyValue('--ease-out').trim(),
    });
  }
}
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
  copy.addEventListener('click', async event => {
    const pointerInitiated = event.detail > 0;
    const text = Array.from(document.querySelectorAll('#comparison-passage p'))
      .map(p => p.textContent).join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      showCopyFeedback('Passage copied', pointerInitiated);
    } catch {
      showCopyFeedback('Use Download text instead.', pointerInitiated);
    }
  });
}
