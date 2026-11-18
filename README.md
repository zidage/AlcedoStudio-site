# Alcedo Studio website

The standalone static website for Alcedo Studio, deployed through Cloudflare Workers.
Only `site/` is published. This repository intentionally contains only the deployment
artifact and the validation tool, keeping Cloudflare's Git checkout small and website
work separate from the desktop application.

## Layout

```text
copy/en.md, copy/zh-CN.md   all page text, one file per language (reviewed by the maintainer)
copy/screenshots.md          the screenshot list: what each section's screenshot shows
site/                        production files served by Workers (pages are generated)
src/worker.js                language routing
scripts/build_pages.py       copy/ -> site/*.html, sitemap.xml, llms.txt, llms-full.txt
scripts/build_images.py      screenshots/ -> site/assets/shots, icons, social cards
scripts/verify_site.py       deployment validation
wrangler.jsonc               Cloudflare Workers Static Assets configuration
```

The site is HTML and CSS only; it has no scripts besides JSON-LD.

- `/` and `/zh-cn/`: name, version and release date, the download, documentation, and
  source code links, and one screenshot of the editor.
- `/features/` and `/zh-cn/features/`: every feature by area. Each area has a screenshot,
  a one-sentence summary, and a list of facts.

## Changing the text

1. Edit `copy/en.md` and `copy/zh-CN.md`. Keep the keys and the section ids; the format
   is described at the top of each file. A `[待确认]` marker stops the build.
2. For a new release, also update `VERSION`, `RELEASE_DATE`, and `UPDATED` in
   `scripts/build_pages.py` and the release date in `home.release`.
3. Run `python scripts/build_pages.py` and commit the copy and the generated files.

`npm run verify` fails when `site/` is out of date with `copy/`.

## Changing the screenshots

Screenshots are full editor windows, about 3868 x 2090, one with the English interface and
one with the Chinese interface. Put them in `screenshots/site/` (git-ignored) as
`<section id>.en.png` and `<section id>.zh-CN.png` (`home` and `top` are the home page and
the top of the features page); `copy/screenshots.md` lists what each one shows. Put the
1024 px application icon at `screenshots/logo.png`. Then run:

```bash
python scripts/build_images.py [id ...]   # AVIF at 1280/1920/2560 px and a WebP fallback
python scripts/build_pages.py              # picks up new image sizes
```

When a Chinese screenshot is missing, the Chinese pages use the English one. Credit every
photo that is not the developer's in the photo credits section of the copy, and use only
photos whose license allows it (pixls.us Play Raw photos are CC BY-SA 4.0). Library
screenshots show thumbnails too: they must follow the same rule.

## Search engines and AI assistants

Each page has a canonical URL, `hreflang` alternates, Open Graph and Twitter cards, and
JSON-LD (`SoftwareApplication` and `SoftwareSourceCode` on the home pages, `WebPage` and
`BreadcrumbList` on the feature pages). `sitemap.xml` lists both languages with alternates.
`llms.txt` summarizes the project and links the downloads, documentation, and source;
`llms-full.txt` and `zh-cn/llms-full.txt` contain the feature list as Markdown.

## Language routing

`src/worker.js` runs for `/`, `/features/`, `/zh-cn/`, and `/zh-cn/features/`
(`run_worker_first`); every other file is served from static assets.

- The language switcher links carry `?lang=en` or `?lang=zh-CN`. The Worker stores
  the choice in the `alcedo_lang` cookie and redirects to the clean URL.
- Without a stored choice, `Accept-Language` decides: any `zh*` preference goes to
  `/zh-cn/`, `en*` goes to the English pages, other languages are left alone.
- Requests without `Accept-Language` (most crawlers) are never redirected, so each
  language stays indexed at its canonical URL.

## Deploy to Cloudflare Workers

The configuration is already ready for Workers Static Assets:

- `site/` is the published directory;
- unknown URLs return `site/404.html`;
- a tiny Worker (`src/worker.js`) picks the page language; there is no database or
  build step.

For a local or manual deployment:

```bash
npm install
npm run verify
npm run deploy
```

For Cloudflare's Git integration, select the `main` branch and set:

```text
Root directory: (leave empty)
Build command: (leave empty)
Deploy command: npm run deploy
```

After the first deployment, attach the custom domain in **Worker > Settings >
Domains & Routes**. Keep `www` redirected permanently to the apex domain so search
engines see one hostname.

Canonical, `hreflang`, Open Graph, JSON-LD, robots, and sitemap use
`https://aoraw.org`.

## Download links

The download and SHA-256 links are maintained by hand. For each release, set `VERSION`,
`RELEASE_DATE`, `UPDATED`, `BUILDS`, `DOWNLOAD`, and `CHECKSUMS` at the top of
`scripts/build_pages.py`, update the date in `home.release` in `copy/*.md`, and run
`python scripts/build_pages.py`. The Windows link is the .exe installer and the macOS
link is the .dmg (not the updater ZIP). `npm run verify` requires a .exe and a .dmg link
on both home pages and checks that every download link responds.

## Local preview and checks

```bash
npm run serve
npm run verify
npm test
```

Open `http://127.0.0.1:8080/` for the preview. The validator checks required files, SEO
metadata, robots/sitemap entries, internal relative links, scripts, JSON-LD, image alt
text, and that the generated files match `copy/`. Use `npm run dev` to test the
language routing of the Worker locally.
