# Alcedo Studio website

The standalone static website for Alcedo Studio, deployed through Cloudflare Workers.
Only `site/` is published. This repository intentionally contains only the deployment
artifact and the validation tool, keeping Cloudflare's Git checkout small and website
work separate from the desktop application.

## Layout

```text
site/                 production files served by Workers
src/worker.js         language routing for the four HTML entry pages
scripts/              deployment validation and image compression
wrangler.jsonc        Cloudflare Workers Static Assets configuration
```

## Language routing

`src/worker.js` runs only for `/`, `/features/`, `/zh-cn/`, and `/zh-cn/features/`
(`run_worker_first`); every other file is served straight from static assets.

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
`https://aoraw.org`. Installer links use the package URLs from the public live
stable manifests:

- Windows: `https://static.aoraw.org/updates/v1/stable/windows-x86_64/manifest.json`
  → `artifacts.windows-x86_64.url`
- macOS: `https://static.aoraw.org/updates/v1/stable/macos-arm64/manifest.json`
  → `artifacts.macos-arm64.manualUrl` (DMG)

`npm run verify` fetches those manifests and requires the HTML to match.
GitHub Releases remains the archive and fallback. After a stable upload, update
the four HTML download URLs to the new package and checksum objects.

## Local preview and checks

```bash
npm run serve
python scripts/verify_site.py
```

Open `http://127.0.0.1:8080/` for the preview. The validator checks required files,
SEO metadata, robots/sitemap entries, and internal relative links.

To update markup, edit the finished static files in `site/` and commit them.

To update images, put the raw PNG/JPEG screenshots and photos in `screenshots/`
(git-ignored) under the names listed in `scripts/build_images.py`, then run
`python scripts/build_images.py`. It writes the AVIF and WebP sizes into `site/assets/`.
Only the compressed output is committed. The three stacked tool screenshots on the home
page must keep the editor's right-hand panel at about 17.6 % of the width; the stack
geometry in `site.css` and `site.js` depends on it.
