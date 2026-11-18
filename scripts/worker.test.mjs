import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const source = await readFile(new URL("../src/worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
const origin = "https://aoraw.org";
const assets = { ASSETS: { fetch: async () => new Response("asset") } };
const request = (path, options) => worker.fetch(new Request(origin + path, options), assets);

test("the language switcher stores the choice and redirects to the clean URL", async () => {
  const toChinese = await request("/features/?lang=zh-CN");
  assert.equal(toChinese.status, 302);
  assert.equal(toChinese.headers.get("Location"), "/zh-cn/features/");
  assert.match(toChinese.headers.get("Set-Cookie"), /alcedo_lang=zh-CN/);

  const toEnglish = await request("/zh-cn/?lang=en");
  assert.equal(toEnglish.headers.get("Location"), "/");
  assert.match(toEnglish.headers.get("Set-Cookie"), /alcedo_lang=en/);
});

test("a stored choice wins over Accept-Language", async () => {
  const stored = await request("/zh-cn/", { headers: { Cookie: "alcedo_lang=en", "Accept-Language": "zh-CN" } });
  assert.equal(stored.headers.get("Location"), "/");
});

test("Accept-Language picks the best supported language", async () => {
  const preferred = await request("/", { headers: { "Accept-Language": "fr,zh;q=0.8,en;q=0.5" } });
  assert.equal(preferred.headers.get("Location"), "/zh-cn/");
  const english = await request("/zh-cn/features/", { headers: { "Accept-Language": "en-GB" } });
  assert.equal(english.headers.get("Location"), "/features/");
  const other = await request("/", { headers: { "Accept-Language": "fr" } });
  assert.equal(await other.text(), "asset");
});

test("requests without a language preference are served as they are", async () => {
  const crawler = await request("/");
  assert.equal(await crawler.text(), "asset");
  assert.equal(crawler.headers.get("Vary"), "Accept-Language, Cookie");
  const post = await request("/", { method: "POST" });
  assert.equal(await post.text(), "asset");
});
