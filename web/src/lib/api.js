// API helpers for the USURPENT SPA.
//
// The server sets a `_xsrf` cookie on any non-asset GET (see
// SpaStaticFileHandler). Tornado's `xsrf_cookies=True` requires every POST to
// echo that token back in the `X-XSRFToken` header, so we read the cookie and
// send it along. All calls are same-origin in production (Tornado serves the
// built SPA), so cookies ride along automatically.

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
