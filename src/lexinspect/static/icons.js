// Interface icons: a subset of Lucide 1.69.0 (ISC licence, https://lucide.dev),
// drawn on a 24-unit grid with round caps and joins. Every icon renders with
// the same visual stroke (2 units at 16px, scaled at other sizes), so a 14px
// caret and a 16px button icon read as one family.
//
//   icon('folder-open')            16px, decorative (aria-hidden)
//   icon('x', { size: 14 })
//
// Static markup asks for one with <span class="i" data-icon="name"></span>;
// the span keeps the icon's space (styles.css) and is swapped for the SVG as
// soon as the page is parsed. Icons that point along the line of text
// (arrows, chevrons) carry data-flip and are mirrored on right-to-left pages.

/*
 * ISC License
 *
 * Copyright (c) 2026 Lucide Icons and Contributors
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 *
 * Of the icons here, arrow-down, arrow-right, arrow-up, arrow-up-right, check, chevron-down, chevron-right, clipboard, download, link, table-2, upload, x derive
 * from the Feather project:
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2013-present Cole Bemis
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

const Icons = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const FLIP = new Set(['arrow-right', 'arrow-up-right', 'chevron-right']);
  const NODES = {
    'arrow-down': [['path', { d: 'M12 5v14' }], ['path', { d: 'm19 12-7 7-7-7' }]],
    'arrow-right': [['path', { d: 'M5 12h14' }], ['path', { d: 'm12 5 7 7-7 7' }]],
    'arrow-up': [['path', { d: 'm5 12 7-7 7 7' }], ['path', { d: 'M12 19V5' }]],
    'arrow-up-right': [['path', { d: 'M7 7h10v10' }], ['path', { d: 'M7 17 17 7' }]],
    'braces': [['path', { d: 'M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1' }], ['path', { d: 'M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1' }]],
    'check': [['path', { d: 'M20 6 9 17l-5-5' }]],
    'chevron-down': [['path', { d: 'm6 9 6 6 6-6' }]],
    'chevron-right': [['path', { d: 'm9 18 6-6-6-6' }]],
    'clipboard': [['rect', { width: '8', height: '4', x: '8', y: '2', rx: '1', ry: '1' }], ['path', { d: 'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2' }]],
    'clipboard-paste': [['path', { d: 'M11 14h10' }], ['path', { d: 'M16 4h2a2 2 0 0 1 2 2v1.344' }], ['path', { d: 'm17 18 4-4-4-4' }], ['path', { d: 'M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 1.793-1.113' }], ['rect', { x: '8', y: '2', width: '8', height: '4', rx: '1' }]],
    'copy': [['rect', { width: '14', height: '14', x: '8', y: '8', rx: '2', ry: '2' }], ['path', { d: 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2' }]],
    'download': [['path', { d: 'M12 15V3' }], ['path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }], ['path', { d: 'm7 10 5 5 5-5' }]],
    'folder-open': [['path', { d: 'm6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2' }]],
    'languages': [['path', { d: 'm5 8 6 6' }], ['path', { d: 'm4 14 6-6 2-3' }], ['path', { d: 'M2 5h12' }], ['path', { d: 'M7 2h1' }], ['path', { d: 'm22 22-5-10-5 10' }], ['path', { d: 'M14 18h6' }]],
    'link': [['path', { d: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71' }], ['path', { d: 'M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71' }]],
    'list': [['path', { d: 'M3 5h.01' }], ['path', { d: 'M3 12h.01' }], ['path', { d: 'M3 19h.01' }], ['path', { d: 'M8 5h13' }], ['path', { d: 'M8 12h13' }], ['path', { d: 'M8 19h13' }]],
    'pencil': [['path', { d: 'M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z' }], ['path', { d: 'm15 5 4 4' }]],
    'printer': [['path', { d: 'M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2' }], ['path', { d: 'M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6' }], ['rect', { x: '6', y: '14', width: '12', height: '8', rx: '1' }]],
    'quote': [['path', { d: 'M16 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2z' }], ['path', { d: 'M5 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2z' }]],
    'sheet': [['rect', { width: '18', height: '18', x: '3', y: '3', rx: '2', ry: '2' }], ['line', { x1: '3', x2: '21', y1: '9', y2: '9' }], ['line', { x1: '3', x2: '21', y1: '15', y2: '15' }], ['line', { x1: '9', x2: '9', y1: '9', y2: '21' }], ['line', { x1: '15', x2: '15', y1: '9', y2: '21' }]],
    'table-2': [['path', { d: 'M3 9h18' }], ['path', { d: 'M9 3v18' }], ['rect', { x: '3', y: '3', width: '18', height: '18', rx: '2' }]],
    'upload': [['path', { d: 'M12 3v12' }], ['path', { d: 'm17 8-5-5-5 5' }], ['path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }]],
    'x': [['path', { d: 'M18 6 6 18' }], ['path', { d: 'm6 6 12 12' }]],
  };

  function icon(name, { size = 16 } = {}) {
    const nodes = NODES[name];
    if (!nodes) throw new Error(`unknown icon: ${name}`);
    const svg = document.createElementNS(NS, 'svg');
    const attrs = {
      class: `icon icon-${name}`,
      width: size,
      height: size,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      'stroke-width': +((2 * 16) / size).toFixed(2),
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round',
      'aria-hidden': 'true',
      focusable: 'false',
    };
    for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, v);
    if (FLIP.has(name)) svg.dataset.flip = '';
    for (const [tag, a] of nodes) {
      const el = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(a)) el.setAttribute(k, v);
      svg.appendChild(el);
    }
    return svg;
  }

  /** Swap every <span class="i" data-icon="…" data-size="…"> in scope for its SVG. */
  function hydrate(scope = document) {
    for (const el of scope.querySelectorAll('.i[data-icon]')) {
      el.replaceWith(icon(el.dataset.icon, { size: Number(el.dataset.size) || 16 }));
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => hydrate(), { once: true });
  else hydrate();

  return { icon, hydrate };
})();

const icon = Icons.icon;
