# Case Analytica website

## Article links are pre-rendered: rebuild after touching data.js

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
remove its entry from `ARTICLES`. Leave the page live and do NOT add `noindex`.
It contradicts the canonical and throws the signal away instead of moving it. GitHub Pages cannot serve a 301, so the canonical is the whole mechanism.

## Writing filter: run it before committing any draft

`WRITING-FILTER.md` in this repo root holds the rules for every public-facing
draft, whether an article, a social caption, an email or a video script. Read it
and run every grep in it against the text before you commit. Do not eyeball it
and do not skip it because the draft reads fine. A site-wide scan on 2026-09-20
found seven instances of a banned construction that a looser instruction had let
through.

Two hard rules, no exceptions: no em dashes and no exclamation points, anywhere.

The pattern that gets past a human read is negative parallelism, the "isn't just
X, it's Y" shape. Rewrite every hit so the sentence asserts the thing directly.

Two things the pass must not do. Do not strip the word "actually", which is the
site's signature and marks the gap between what people are told and what is
true. Do not soften a position to make the prose sound more natural. A hedged
version of the core message is a hard failure, not a style choice.

This section exists because the cloud routine that drafts social copy
(`case-analytica-social-post`) clones this repo and cannot reach the voice files
on the host. It reads this file on every run, so the filter stays in one place
instead of drifting inside a prompt. Say in the PR description that the filter
was run, and name anything it changed.

## Deploy

`git push origin main` is the entire deploy. GitHub Actions publishes Pages
from `.github/workflows/deploy-pages.yml`, usually live inside a minute.
Cloudflare sits in front for security headers; DNS and TLS are a separate
manual dashboard job, never part of a push.

Stage your own paths and hunks. Never `git add -A` here, because the working tree
usually holds unrelated in-progress edits.
