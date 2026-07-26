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

## Design system

All colors, type, and spacing live in `assets/style.css` as CSS custom
properties at the top of the file — same visual identity as the video
production queue, so the channel and the site read as one brand.
