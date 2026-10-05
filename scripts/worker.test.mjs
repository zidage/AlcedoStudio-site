import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const source = await readFile(new URL("../src/worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const originalFetch = globalThis.fetch;
const origin = "https://aoraw.org";
const root = "https://static.aoraw.org/updates/v1/stable/";
const windows = "windows-x86_64";
const mac = "macos-arm64";
const assets = { ASSETS: { fetch: async () => new Response("asset") } };
const packageUrl = (platform, build, extension) => `${root}builds/${build}/${platform}/AlcedoStudio.${extension}`;
const manifest = (platform, build) => ({
  artifacts: {
    [platform]: {
      url: packageUrl(platform, build, platform === mac ? "zip" : "exe"),
      ...(platform === mac ? { manualUrl: packageUrl(platform, build, "dmg") } : {}),
    },
  },
});
const request = (path, options) => worker.fetch(new Request(origin + path, options), assets);

async function withFetch(mock, run) {
  globalThis.fetch = mock;
  try { await run(); } finally { globalThis.fetch = originalFetch; }
}

test("downloads follow a newly published build without changing the website", async () => {
  let build = 3000;
  await withFetch(async (url, options) => {
    assert.equal(url, `${root}${windows}/manifest.json`);
    assert.equal(options.cache, "no-store");
    assert.equal(options.redirect, "manual");
    assert.ok(options.signal instanceof AbortSignal);
    return Response.json(manifest(windows, build));
  }, async () => {
    for (const next of [3000, 3002, 3003]) {
      build = next;
      const response = await request(`/download/${windows}?lang=zh-CN`, {
        headers: { "Accept-Language": "zh-CN", Cookie: "alcedo_lang=zh-CN" },
      });
      assert.equal(response.status, 302);
      assert.equal(response.headers.get("Location"), packageUrl(windows, build, "exe"));
      assert.equal(response.headers.get("Cache-Control"), "no-store");
    }
  });
});

test("macOS downloads select the manual DMG, and both checksum routes follow their build", async () => {
  await withFetch(async url => {
    const platform = url.includes(mac) ? mac : windows;
    return Response.json(manifest(platform, platform === mac ? 3002 : 3003));
  }, async () => {
    const dmg = await request(`/download/${mac}`);
    assert.equal(dmg.headers.get("Location"), packageUrl(mac, 3002, "dmg"));
    for (const [platform, build] of [[windows, 3003], [mac, 3002]]) {
      const response = await request(`/download/${platform}/checksums`);
      assert.equal(response.status, 302);
      assert.equal(response.headers.get("Location"), `${root}builds/${build}/${platform}/SHA256SUMS-${platform}.txt`);
    }
  });
});

test("HEAD resolves the installer and checksums with no response body", async () => {
  await withFetch(async () => Response.json(manifest(windows, 3002)), async () => {
    for (const suffix of ["", "/checksums"]) {
      const response = await request(`/download/${windows}${suffix}`, { method: "HEAD" });
      assert.equal(response.status, 302);
      assert.equal(await response.text(), "");
    }
  });
});

test("invalid, missing, and failed manifests return 503 instead of a stale installer", async () => {
  const cases = [
    async () => { throw new Error("network failure"); },
    async () => new Response("unavailable", { status: 500 }),
    async () => new Response(null, { status: 302, headers: { Location: "https://example.com/manifest.json" } }),
    async () => new Response("not JSON"),
    async () => Response.json(null),
    async () => Response.json({ artifacts: {} }),
    ...[
      "https://example.com/AlcedoStudio.exe",
      "http://static.aoraw.org/updates/v1/stable/builds/3002/windows-x86_64/App.exe",
      `${root}builds/3002/macos-arm64/App.exe`,
      `${root}builds/3002/windows-x86_64/App.zip`,
      `${root}builds/3002/windows-x86_64/App.exe?redirect=other`,
    ].map(url => async () => Response.json({ artifacts: { [windows]: { url } } })),
  ];
  for (const mock of cases) {
    await withFetch(mock, async () => {
      const response = await request(`/download/${windows}`);
      assert.equal(response.status, 503);
      assert.equal(response.headers.get("Location"), null);
      assert.equal(response.headers.get("Cache-Control"), "no-store");
      assert.match(await response.text(), /github.com\/zidage\/AlcedoStudio\/releases/);
    });
  }
  await withFetch(async () => Response.json(manifest(mac, 3002).artifacts[mac].url), async () => {
    const response = await request(`/download/${mac}`, { method: "HEAD" });
    assert.equal(response.status, 503);
    assert.equal(await response.text(), "");
  });
});

test("macOS never falls back to the updater ZIP when manualUrl is missing", async () => {
  const data = manifest(mac, 3002);
  delete data.artifacts[mac].manualUrl;
  await withFetch(async () => Response.json(data), async () => {
    assert.equal((await request(`/download/${mac}`)).status, 503);
  });
});

test("unsupported methods and unknown platforms never fetch a manifest", async () => {
  await withFetch(async () => { assert.fail("unexpected manifest fetch"); }, async () => {
    const response = await request(`/download/${windows}`, { method: "POST" });
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("Allow"), "GET, HEAD");
    assert.equal(await (await request("/download/linux")).text(), "asset");
  });
});

test("language preferences and static asset responses retain their behavior", async () => {
  const explicit = await request("/features/?lang=zh-CN");
  assert.equal(explicit.headers.get("Location"), "/zh-cn/features/");
  assert.match(explicit.headers.get("Set-Cookie"), /alcedo_lang=zh-CN/);
  const stored = await request("/zh-cn/", { headers: { Cookie: "alcedo_lang=en", "Accept-Language": "zh-CN" } });
  assert.equal(stored.headers.get("Location"), "/");
  const preferred = await request("/", { headers: { "Accept-Language": "fr,zh;q=0.8,en;q=0.5" } });
  assert.equal(preferred.headers.get("Location"), "/zh-cn/");
  const crawler = await request("/");
  assert.equal(await crawler.text(), "asset");
  assert.equal(crawler.headers.get("Vary"), "Accept-Language, Cookie");
});
