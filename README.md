# Alcedo Studio website

The standalone static website for Alcedo Studio, deployed through Cloudflare Workers.
Only `site/` is published. This repository intentionally contains only the deployment
artifact and the validation tool, keeping Cloudflare's Git checkout small and website
work separate from the desktop application.

## Layout

```text
site/                 production files served by Workers
scripts/              deployment validation
wrangler.jsonc        Cloudflare Workers Static Assets configuration
```

## Deploy to Cloudflare Workers

The configuration is already ready for Workers Static Assets:

- `site/` is the published directory;
- unknown URLs return `site/404.html`;
- no application server, database, or build step is required.

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

The current canonical, `hreflang`, Open Graph, JSON-LD, robots, and sitemap URLs still
refer to the existing GitHub Pages hostname. Change all of them together only after the
custom domain serves this site successfully.

## Local preview and checks

```bash
npm run serve
python scripts/verify_site.py
```

Open `http://127.0.0.1:8080/` for the preview. The validator checks required files,
SEO metadata, robots/sitemap entries, and internal relative links.

To update images or markup, make and review the finished static files in `site/`, then
commit them. The original design-source screenshots stay in the desktop application's
repository and are deliberately not copied here.
