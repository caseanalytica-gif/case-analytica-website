# Case Analytica website

## Article links are pre-rendered — rebuild after touching data.js

`assets/data.js` is the source of truth for the article list. The links that
Google actually crawls are baked into the HTML at build time, not generated in
the browser, so editing data.js alone is never enough:

```bash
python3 tools/prerender.py
```

Run it after any change to `ARTICLES`, then commit the files it touches. It
rewrites the card grid in `articles.html` and `index.html`, the "Related
reading" block in every `articles/*.html`, and `sitemap.xml`. It is idempotent
and prints what it changed. `--check` reports drift without writing, if you
want it in CI.

Skipping this is the bug it was written to fix: 62 of 71 articles sat
unindexed because their only links existed after JavaScript ran.

Rules that go with it:
- Never hand-edit anything between `<!-- prerender:begin -->` and
  `<!-- prerender:end -->`. The next build overwrites it.
- Articles only publish if the file is git-tracked, which keeps drafts out of
  the grid and the sitemap. Add a draft to `ARTICLES` and it stays invisible
  until its file is committed.
- Bump the `?v=` cache-busters on `data.js` / `site.js` in `articles.html`,
  `index.html`, and `videos.html` when either file changes, or returning
  visitors run stale copies.

## Consolidating duplicate articles

Two pages on the same statute split their own ranking. To merge them, point the
weaker page's `<link rel="canonical">` and `og:url` at the stronger one and
remove its entry from `ARTICLES`. Leave the page live and do NOT add `noindex`
— that contradicts the canonical and throws the signal away instead of moving
it. GitHub Pages cannot serve a 301, so the canonical is the whole mechanism.

## Deploy

`git push origin main` is the entire deploy — GitHub Actions publishes Pages
from `.github/workflows/deploy-pages.yml`, usually live inside a minute.
Cloudflare sits in front for security headers; DNS and TLS are a separate
manual dashboard job, never part of a push.

Stage your own paths and hunks. Never `git add -A` here — the working tree
usually holds unrelated in-progress edits.
