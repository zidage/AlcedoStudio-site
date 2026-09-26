// Language routing for the static site.
//
// Only the four HTML entry pages reach this Worker (see run_worker_first in
// wrangler.jsonc); every other request is served straight from static assets.
//
// 1. `?lang=en|zh-CN` comes from the on-page language switcher. It stores the
//    choice in a cookie and redirects to the clean URL, so an explicit choice
//    always wins over the browser's language.
// 2. With no stored choice, the Accept-Language header decides: Chinese
//    readers are sent to /zh-cn/, everyone else to the English pages.
//    Requests without the header (most crawlers) are never redirected, so
//    search engines index each language at its canonical URL.

const COOKIE = "alcedo_lang";
const ONE_YEAR = 60 * 60 * 24 * 365;

// English path -> Chinese path. Both directions are derived from this table.
const PAGES = {
  "/": "/zh-cn/",
  "/features/": "/zh-cn/features/",
};

function localeOfPath(pathname) {
  return pathname.startsWith("/zh-cn/") ? "zh-CN" : "en";
}

function pathFor(pathname, locale) {
  if (locale === "zh-CN") return PAGES[pathname] ?? pathname;
  for (const [en, zh] of Object.entries(PAGES)) {
    if (zh === pathname) return en;
  }
  return pathname;
}

function normalizeLocale(value) {
  if (!value) return null;
  const v = value.trim().toLowerCase();
  if (v === "en" || v.startsWith("en-")) return "en";
  if (v === "zh" || v.startsWith("zh-")) return "zh-CN";
  return null;
}

function readCookie(request) {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === COOKIE) return normalizeLocale(rest.join("="));
  }
  return null;
}

// Pick the highest-weighted language we support. Unsupported languages are
// skipped, so "fr, zh;q=0.8" still resolves to Chinese.
function preferredLocale(acceptLanguage) {
  let best = null;
  let bestQ = 0;
  for (const entry of acceptLanguage.split(",")) {
    const [tag, ...params] = entry.trim().split(";");
    const locale = normalizeLocale(tag);
    if (!locale) continue;
    let q = 1;
    for (const p of params) {
      const [k, v] = p.trim().split("=");
      if (k === "q") q = Number.parseFloat(v);
    }
    if (Number.isFinite(q) && q > bestQ) {
      best = locale;
      bestQ = q;
    }
  }
  return best;
}

function redirect(location, extraHeaders = {}) {
  return new Response(null, {
    status: 302,
    headers: {
      Location: location,
      "Cache-Control": "private, no-store",
      Vary: "Accept-Language, Cookie",
      ...extraHeaders,
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const method = request.method;
    if (method !== "GET" && method !== "HEAD") {
      return env.ASSETS.fetch(request);
    }

    const current = localeOfPath(url.pathname);

    const explicit = normalizeLocale(url.searchParams.get("lang"));
    if (explicit) {
      url.searchParams.delete("lang");
      url.pathname = pathFor(url.pathname, explicit);
      return redirect(url.pathname + url.search + url.hash, {
        "Set-Cookie": `${COOKIE}=${explicit}; Path=/; Max-Age=${ONE_YEAR}; SameSite=Lax; Secure`,
      });
    }

    const stored = readCookie(request);
    const acceptLanguage = request.headers.get("Accept-Language");
    const wanted = stored ?? (acceptLanguage ? preferredLocale(acceptLanguage) : null);

    if (wanted && wanted !== current) {
      return redirect(pathFor(url.pathname, wanted) + url.search);
    }

    const response = await env.ASSETS.fetch(request);
    const headers = new Headers(response.headers);
    headers.append("Vary", "Accept-Language, Cookie");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
