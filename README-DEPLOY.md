# Case Analytica Website — Deploy &amp; Editing Guide

## What this is

A plain static website (no server, no database, no login required to run it).
Pages: Home, **Restorative Justice** (the flagship page — a checklist of exact
questions to ask an attorney, built to be the single most important page on
the site), Videos, Articles, About/Intake. It's already fully built and
previewable by just opening `index.html` in a browser.

## Get it live on your domain (free hosting, ~10 minutes)

You said you already own the domain. Netlify's free tier is the simplest path:

1. Go to **netlify.com** and sign up (free).
2. On the dashboard, drag the entire `Website` folder onto the "Deploy manually"
   drop zone. It'll give you a live `something.netlify.app` URL immediately.
3. In Netlify: **Site settings → Domain management → Add a custom domain** →
   enter your domain.
4. Netlify shows you 1-2 DNS records to add. Go to wherever you bought the
   domain (registrar's dashboard), find the DNS settings, and add those records.
5. DNS changes take anywhere from a few minutes to a few hours to fully
   propagate. Once it does, your domain points straight at this site.

Netlify also auto-provisions free HTTPS (the padlock) once the domain is
connected — no extra step needed.

**Alternative:** Vercel and GitHub Pages both work the same way (drag-and-drop
or connect-a-repo, then point DNS). Netlify's manual drag-and-drop is the
least technical starting point since there's no git involved.

## How to add a new video (once it's uploaded to YouTube)

1. Open `assets/data.js`.
2. Find the matching entry in the `VIDEOS` array (all 12 from the queue are
   already in there, waiting).
3. Paste the YouTube video ID into `youtubeId` (the part after `v=` in the URL).
4. Change `published: false` to `published: true`.
5. Save the file and re-upload/redeploy (drag the folder onto Netlify again,
   or `git push` if you've connected a repo).

The thumbnail, link, and "Coming Soon" badge all update automatically —
nothing else to touch.

## How to publish a new article

1. Duplicate `articles/template.html`, rename it to a short slug
   (e.g. `articles/bail-reform-explained.html` — no spaces, all lowercase).
2. Fill in the bracketed placeholders and write the body.
3. Open `assets/data.js`, add one object to the `ARTICLES` array with a
   matching `slug` (same name, no `.html`).
4. Add one `<url>` entry to `sitemap.xml` (copy an existing one, swap the
   `<loc>` and `<lastmod>`) — this is what tells Google/Bing the new page
   exists. Easy to forget since the site still works fine without it; it
   just won't get found in search as fast.
5. Save all three files and redeploy.

The articles page picks up new entries automatically from `data.js` — you
never have to touch `articles.html` itself.

## Swapping the intake CTA from email to a booking link

Right now "Book a Free Intake Call" opens an email draft. Once you set up a
booking tool (Calendly or similar — you'll need to create that account
yourself), open `about.html`, find the line:

```html
<a class="btn" href="mailto:caseanalytica@gmail.com?subject=Free%20Intake%20Call%20Request">
```

and replace the `href` with your booking link. That single line change updates
the button everywhere it appears (it's the same button referenced from every
page's nav).

## Adding the missing security headers (securityheaders.com grade)

The site is hosted on **GitHub Pages** (see `.github/workflows/deploy-pages.yml`
and the `CNAME` file). GitHub Pages serves static files only — it has no way
to set custom HTTP response headers, so `Content-Security-Policy`,
`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, and
`Permissions-Policy` can't be added directly, which is why a scan like
securityheaders.com grades the site F. This isn't fixable by editing HTML
(a `<meta>` tag doesn't count for most of these) — it needs something in
front of GitHub Pages that can inject headers. The fix here: put the domain
on Cloudflare's free plan and run a small Worker that adds the headers to
every response, while GitHub Pages keeps serving the actual site unchanged.

The Worker code is already written: `cloudflare/security-headers-worker.js`.
One-time setup (all done in the Cloudflare/GoDaddy dashboards, ~15-30 min
including DNS propagation):

1. Sign up free at **cloudflare.com** → **Add a site** → enter `caseanalytica.com`.
   Choose the **Free** plan. Cloudflare scans the existing DNS records
   (the `www` CNAME and the apex `A` record) — just confirm them as shown.
2. Cloudflare gives you two nameservers (something like `xxx.ns.cloudflare.com`).
   Go to **GoDaddy → DNS Management → Nameservers → Change** and replace the
   current `ns23`/`ns24.domaincontrol.com` pair with Cloudflare's two.
   Propagation is usually under an hour, sometimes up to 24h; Cloudflare
   emails you when the site is active.
3. In Cloudflare, **DNS** tab: make sure the `www` (and apex, if used) records
   show the **orange cloud** (Proxied), not grey (DNS only) — the Worker only
   sees traffic that's proxied through Cloudflare.
4. **SSL/TLS** tab → set encryption mode to **Full** (not "Flexible" — Flexible
   causes a redirect loop with GitHub Pages, which already forces HTTPS).
5. **Workers & Pages → Create → Create Worker**. Name it e.g.
   `case-analytica-security-headers`, delete the default code, paste in the
   contents of `cloudflare/security-headers-worker.js`, and **Deploy**.
6. Back on the Worker's page → **Triggers → Add Route**. Route pattern:
   `www.caseanalytica.com/*` (add `caseanalytica.com/*` too if the apex domain
   is also live). Zone: caseanalytica.com.
7. Re-run the scan at securityheaders.com — should jump from F to A/A+.

Nothing about the GitHub repo, the Actions workflow, or how you publish pages
changes — Cloudflare just sits in front and stamps headers on the way out.

## Design system

All colors, type, and spacing live in `assets/style.css` as CSS custom
properties at the top of the file — same visual identity as the video
production queue, so the channel and the site read as one brand.
