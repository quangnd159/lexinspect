// Cloudflare Turnstile, loaded only when the server advertises a site key
// (/v1/schema → turnstile_site_key). Local and self-hosted runs never fetch it.
//
// One check per hour: the first analysis carries a token, the server answers
// with a signed HttpOnly cookie, and later requests ride on that. The widget
// runs in "interaction-only" mode, so almost everyone sees nothing; when
// Cloudflare does want a click, a small card rises from the bottom of the page.

const Human = (() => {
  const SCRIPT = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=__lexinspectTurnstile';
  const PASS_KEY = 'lexinspect:pass-until';
  const PASS_MS = 55 * 60 * 1000; // a little under the server's hour

  let siteKey = null;
  // Settles once /v1/schema has said whether the gate is on, so an analysis
  // started before then doesn't go out without a token.
  let configured;
  const ready = new Promise((resolve) => (configured = resolve));
  let loading = null;
  let widget = null;
  let waiting = null; // { resolve, reject } for the token being fetched
  let pending = null; // that fetch, shared by everyone who asks meanwhile
  let early = null; // { promise, at }: a token fetched at page load, used once
  const TOKEN_MS = 4 * 60 * 1000; // tokens live 300 s; leave a margin

  function load() {
    if (loading) return loading;
    loading = new Promise((resolve, reject) => {
      window.__lexinspectTurnstile = resolve;
      const s = document.createElement('script');
      s.src = SCRIPT;
      s.async = true;
      s.onerror = () => {
        loading = null;
        reject(new Error('The human check couldn’t load. Check your connection or content blocker, then try again.'));
      };
      document.head.appendChild(s);
    });
    return loading;
  }

  function settle(fn, value) {
    const w = waiting;
    waiting = null;
    $('challenge').classList.remove('asking');
    w?.[fn](value);
  }

  function freshToken() {
    if (pending) return pending;
    pending = load()
      .then(
        () =>
          new Promise((resolve, reject) => {
            waiting = { resolve, reject };
            if (widget == null) {
              widget = window.turnstile.render($('challengeWidget'), {
                sitekey: siteKey,
                action: 'analyse',
                appearance: 'interaction-only',
                execution: 'execute',
                callback: (t) => settle('resolve', t),
                'error-callback': (code) => {
                  // Codes: developers.cloudflare.com/turnstile/troubleshooting/client-side-errors/
                  console.warn(`Turnstile error ${code}`);
                  settle('reject', new Error('The human check failed. Try again.'));
                  return true; // handled; don't let Turnstile throw
                },
                'timeout-callback': () => settle('reject', new Error('The human check timed out. Try again.')),
                'before-interactive-callback': () => $('challenge').classList.add('asking'),
                'after-interactive-callback': () => $('challenge').classList.remove('asking'),
              });
            } else {
              window.turnstile.reset(widget);
            }
            window.turnstile.execute(widget);
          }),
      )
      .finally(() => (pending = null));
    return pending;
  }

  const hasPass = () => Number(store.get(PASS_KEY, 0)) > Date.now();

  async function token() {
    const e = early;
    early = null;
    if (e && Date.now() - e.at < TOKEN_MS) {
      try {
        return await e.promise;
      } catch {}
    }
    return freshToken();
  }

  return {
    /** Call with /v1/schema's turnstile_site_key. Prefetches a token so the first analysis doesn't wait. */
    configure(key) {
      siteKey = key || null;
      configured();
      if (!siteKey || hasPass()) return;
      const promise = freshToken();
      promise.catch(() => {});
      early = { promise, at: Date.now() };
    },

    /**
     * fetch() for a gated endpoint. Sends a token when there's no live pass, and
     * on `challenge_required` (cookie expired or cleared) retries once with a new one.
     */
    async fetch(url, init) {
      const send = async (withToken) => {
        const headers = new Headers(init.headers);
        if (withToken) headers.set('CF-Turnstile-Response', await token());
        return fetch(url, { ...init, headers, credentials: 'same-origin' });
      };
      await ready;
      if (!siteKey) return fetch(url, init);
      let res = await send(!hasPass());
      if (res.status === 403) {
        const body = await res.clone().json().catch(() => ({}));
        if (body.detail?.error === 'challenge_required') {
          store.set(PASS_KEY, 0);
          res = await send(true);
        }
      }
      if (res.ok) store.set(PASS_KEY, String(Date.now() + PASS_MS));
      return res;
    },
  };
})();
