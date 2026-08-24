// API helpers for the USURPENT SPA.
//
// Tornado's `xsrf_cookies=True` requires every POST to echo the `_xsrf` cookie
// back in the `X-XSRFToken` header, so we read the cookie and send it along.
// The cookie comes from `GET /api/me`, which Auth.svelte calls once on load
// before it can render a form -- and also from the app shell in production.
// /api/me is the one that matters in development, where Vite serves the shell
// and Tornado only sees the proxied /api calls. All calls are same-origin, so
// cookies ride along automatically.

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function apiGet(path) {
  const res = await fetch(path, { credentials: 'same-origin' });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function apiPost(path, body) {
  const xsrf = getCookie('_xsrf');
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-XSRFToken': xsrf || '',
    },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}
