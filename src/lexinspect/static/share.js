// Links that carry the text inside them.
//
// The text is deflated and base64url-encoded into the URL fragment, with the
// settings that shape the view. A fragment never reaches the server, so a
// shared analysis is no more stored than an unshared one: the recipient's
// browser decodes it and analyses it afresh.

const Share = (() => {
  const VERSION = '1';

  function toB64url(bytes) {
    let s = '';
    for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  function fromB64url(s) {
    const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(b64 + '='.repeat((4 - (b64.length % 4)) % 4));
    return Uint8Array.from(bin, (c) => c.charCodeAt(0));
  }

  const supported = () => typeof CompressionStream === 'function' && typeof DecompressionStream === 'function';

  async function pack(text) {
    const stream = new Blob([text]).stream().pipeThrough(new CompressionStream('deflate-raw'));
    return toB64url(new Uint8Array(await new Response(stream).arrayBuffer()));
  }

  async function unpack(s) {
    const stream = new Blob([fromB64url(s)]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Response(stream).text();
  }

  /** A link that reopens this text with these settings, on the page at `path`
   *  (this page by default; the batch page passes '/' to open the single view). */
  async function link(text, { variant, target, tab, lens, path = location.pathname } = {}) {
    const p = new URLSearchParams({ v: VERSION, t: await pack(text) });
    if (variant && variant !== 'gb') p.set('var', variant);
    if (target) p.set('for', target);
    if (tab && tab !== 'overview') p.set('tab', tab);
    if (lens) p.set('lens', lens);
    return `${location.origin}${path}#${p}`;
  }

  /** The shared state in the current URL, or null. Throws on a damaged link. */
  async function read() {
    const hash = location.hash.slice(1);
    if (!hash.includes('t=')) return null;
    const p = new URLSearchParams(hash);
    if (!p.get('t')) return null;
    if (!supported()) throw new Error(t('This browser can’t open shared links. Try a current version of Chrome, Edge, Firefox or Safari.'));
    let text;
    try {
      text = await unpack(p.get('t'));
    } catch {
      throw new Error(t('This link is incomplete or damaged, so its text can’t be read. Ask for it to be sent again.'));
    }
    return {
      text,
      variant: p.get('var') === 'us' ? 'us' : 'gb',
      target: p.get('for'),
      tab: p.get('tab'),
      lens: p.get('lens'),
    };
  }

  function clear() {
    history.replaceState(null, '', location.pathname + location.search);
  }

  return { link, read, clear, supported };
})();
