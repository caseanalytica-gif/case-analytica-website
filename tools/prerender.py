#!/usr/bin/env python3
"""Pre-render article links into static HTML so Google can crawl them.

Reads ARTICLES from assets/data.js (the single source of truth) and writes:
  - articles.html        #article-grid       full card grid
  - index.html           front page: lead story, three below, six-headline list
  - articles/<slug>.html related-articles block before </main>
  - sitemap.xml          regenerated from ARTICLES + the static pages

Idempotent: re-running overwrites the generated regions in place.
Run after any change to ARTICLES, then commit the result.

    python3 tools/prerender.py           # write
    python3 tools/prerender.py --check   # report drift, change nothing
"""
import html
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.caseanalytica.com"
FIELDS = ("slug", "title", "category", "stage", "date", "excerpt",
          "image", "imageAlt", "imageCredit")
STATIC_PAGES = [
    ("", "1.0"), ("articles.html", "0.9"), ("about.html", "0.7"),
    ("videos.html", "0.7"), ("restorative-justice.html", "0.7"),
    ("help-after-an-arrest-ny.html", "0.8"), ("checklist.html", "0.7"),
    ("intake-worksheet.html", "0.7"),
    ("parole-file-worksheet.html", "0.7"),
    ("methodology.html", "0.7"),
    ("glossary.html", "0.7"),
    ("directory.html", "0.8"),
    ("parole-data.html", "0.8"),
    ("jobs-records-data.html", "0.8"),
    ("stages/index.html", "0.8"),
    ("stages/arrest.html", "0.8"),
    ("stages/court.html", "0.8"),
    ("stages/bail.html", "0.8"),
    ("stages/counsel.html", "0.8"),
    ("stages/plea.html", "0.8"),
    ("stages/pretrial.html", "0.8"),
    ("stages/sentencing.html", "0.8"),
    ("stages/custody.html", "0.8"),
    ("stages/parole.html", "0.8"),
    ("stages/records.html", "0.8"),
    ("stages/system.html", "0.8"),
]
BEGIN = "<!-- prerender:begin -->"
END = "<!-- prerender:end -->"


def e(s):
    """Match escapeHtml() in site.js."""
    return html.escape(s or "", quote=True)


def parse_articles(js):
    """Extract the ARTICLES array from data.js without a JS engine."""
    start = js.index("const ARTICLES = [")
    depth, i = 0, js.index("[", start)
    for j in range(i, len(js)):
        if js[j] == "[":
            depth += 1
        elif js[j] == "]":
            depth -= 1
            if depth == 0:
                body = js[i + 1:j]
                break
    else:
        raise SystemExit("prerender: could not find end of ARTICLES array")

    out, depth, buf = [], 0, ""
    for ch in body:                      # split top-level { ... } objects
        if ch == "{":
            depth += 1
        if depth:
            buf += ch
        if ch == "}":
            depth -= 1
            if depth == 0:
                out.append(buf)
                buf = ""

    articles = []
    for blob in out:
        a = {}
        for f in FIELDS:
            m = re.search(r'\b%s:\s*"((?:[^"\\]|\\.)*)"' % f, blob)
            if m:
                a[f] = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
        if a.get("slug"):
            articles.append(a)
    return articles


def thumb_html(a, prefix=""):
    """Resolve the thumbnail at build time so there is no 404-and-retry at runtime.

    site.js walks a fallback chain in the browser; here the file is either on
    disk or it is not, so pick the real one and emit nothing when there is none.
    """
    src = None
    img = a.get("image")
    if img and img.startswith(("http://", "https://", "/")):
        src = img                                     # external or root-absolute
    else:
        for rel in ([img] if img else []) + [
            "assets/photos/%s.jpg" % a["slug"],
            "assets/social/thumbs/%s.jpg" % a["slug"],
        ]:
            if os.path.exists(os.path.join(ROOT, rel)):
                src = prefix + rel
                break
    if not src:
        return ""
    credit = ('<span class="thumb-credit">%s</span>' % e(a["imageCredit"])
              if a.get("imageCredit") else "")
    return ('<div class="thumb thumb-figure has-photo">'
            '<img class="thumb-photo-img" src="%s" data-fallbacks="" '
            'alt="%s" loading="lazy" decoding="async">%s</div>'
            % (e(src), e(a.get("imageAlt", "")), credit))


def card_html(a, prefix="", compact=False):
    """Mirror articleCardHtml() in site.js so JS and static output agree."""
    excerpt = "" if compact else "<p>%s</p>" % e(a.get("excerpt", ""))
    return (
        '<a class="card%s" href="%sarticles/%s.html" '
        'style="text-decoration:none;color:inherit;">%s'
        '<div class="body"><span class="cat">%s</span><h3>%s</h3>%s'
        '<span class="meta">%s</span></div></a>'
        % (" card-compact" if compact else "", prefix, e(a["slug"]),
           thumb_html(a, prefix), e(a.get("category", "")), e(a.get("title", "")),
           excerpt, e(a.get("date", "")))
    )


def fill_container(doc, el_id, inner):
    """Replace the generated region inside <div id="el_id">.

    Matches the prerender markers when they are already there; a naive
    non-greedy </div> match would stop at the first nested card div on a
    re-run and leave stale markup behind.
    """
    m = re.search(r'<div\b[^>]*\bid="%s"[^>]*>' % re.escape(el_id), doc)
    if not m:
        raise SystemExit("prerender: #%s not found" % el_id)
    open_tag, after = m.group(0), doc[m.end():]
    if 'data-prerendered' not in open_tag:
        open_tag = open_tag[:-1] + ' data-prerendered="1">'

    if after.startswith(BEGIN):
        end = after.index(END) + len(END)
        rest = after[end:]
    else:
        close = after.index("</div>")           # container was empty
        if after[:close].strip():
            raise SystemExit("prerender: #%s has unmanaged content" % el_id)
        rest = after[close:]
    return doc[:m.start()] + open_tag + BEGIN + inner + END + rest


# Email signup above Related reading on every article. The handler is
# assets/signup.js; it posts to the Apps Script list in email-capture-sheets/.
# Copy went through the writer pass 2026-10-09. The guide email goes out on
# signup, digests only on mornings a new slug publishes, so "After that" holds.
SIGNUP_HTML = '''<section class="wrap article-signup" aria-labelledby="article-signup-h">
  <style>
    .article-signup{margin:2.5rem auto 0;}
    .article-signup .box{border:1px solid var(--line);border-left:4px solid var(--accent);background:var(--paper-raised);padding:1.25rem 1.5rem;border-radius:6px;}
    .article-signup h2{margin:0 0 .4rem;font-family:var(--display);font-size:1.35rem;color:var(--ink);}
    .article-signup p{margin:0 0 .9rem;color:var(--ink-soft);line-height:1.5;}
    .article-signup form{display:flex;gap:.5rem;flex-wrap:wrap;}
    .article-signup input[type=email]{flex:1 1 220px;min-width:0;padding:.65rem .8rem;font:inherit;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink);}
    .article-signup button{padding:.65rem 1.1rem;font:inherit;font-weight:600;border:0;border-radius:4px;background:var(--btn-fill);color:#fff;cursor:pointer;}
    .article-signup button:disabled{opacity:.6;cursor:default;}
    .article-signup .hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;}
    .article-signup .signup-status{margin:.6rem 0 0;font-size:.95rem;}
    .article-signup .signup-status.success{color:var(--pillar);}
    .article-signup .signup-status.error{color:var(--accent-ink);}
  </style>
  <div class="box">
    <h2 id="article-signup-h">New articles by email</h2>
    <p>Sign up and we'll email you the free guide, What New York Doesn't Tell You After an Arrest. After that, one email on mornings a new article goes up, never more than one a day. Every email has an unsubscribe link.</p>
    <form id="article-signup-form" novalidate>
      <label for="article-signup-email" class="hp">Email address</label>
      <input id="article-signup-email" type="email" name="email" autocomplete="email" placeholder="you@example.com" aria-label="Email address" required>
      <span class="hp" aria-hidden="true"><input type="text" name="hp" tabindex="-1" autocomplete="off"></span>
      <button type="submit">Sign me up</button>
    </form>
    <p id="article-signup-status" class="signup-status" role="status" aria-live="polite"></p>
  </div>
  <script src="../assets/signup.js" defer></script>
</section>
'''


def related_block(a, articles, n=3):
    # Walk the list from this article toward older ones, wrapping to the newest,
    # and prefer the same stage, then the same category. Taking "the newest three
    # in the category" instead sent every link to a few recent pieces and left
    # 64 of 80 articles with no Related reading link pointing at them (2026-10-09).
    i = articles.index(a)
    ring = articles[i + 1:] + articles[:i]
    picks = []
    for pool in ([x for x in ring if x.get("stage") == a.get("stage")],
                 [x for x in ring if x.get("category") == a.get("category")],
                 ring):
        for x in pool:
            if x not in picks and len(picks) < n:
                picks.append(x)
    if not picks:
        return ""
    cards = "".join(card_html(x, prefix="../", compact=True) for x in picks)
    return ('\n%s\n%s<section class="wrap related-articles">\n'
            '  <h2>Related reading</h2>\n'
            '  <div class="card-grid">%s</div>\n'
            '</section>\n%s\n' % (BEGIN, SIGNUP_HTML, cards, END))


def replace_region(doc, new):
    """Swap an existing prerender region, or return None if absent."""
    if BEGIN not in doc:
        return None
    return re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _: new.strip("\n"),
                  doc, count=1, flags=re.S)


def sitemap(articles, tracked):
    rows = []
    for path, pri in STATIC_PAGES:
        rows.append((BASE + "/" + path, None, pri))
    for a in articles:
        rel = "articles/%s.html" % a["slug"]
        if rel not in tracked:
            continue
        rows.append((BASE + "/" + rel, a.get("date"), "0.9"))
    body = "".join(
        "  <url>\n    <loc>%s</loc>\n%s    <changefreq>monthly</changefreq>\n"
        "    <priority>%s</priority>\n  </url>\n"
        % (u, ("    <lastmod>%s</lastmod>\n" % d) if d else "", p)
        for u, d, p in rows)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            '%s</urlset>\n' % body)



# --- Closing questions -> checklist.html -------------------------------------
# Every article's "exact question to ask" closer is tagged with a data-stage.
# This collects them so checklist.html's index cannot drift from the articles
# the way a hand-maintained list does.
QSTAGES = ["Right after arrest", "At the courthouse", "Arraignment and bail",
           "Getting a lawyer", "Before any plea", "Discovery and pretrial motions",
           "Trial rights and the clock", "Sentencing", "In custody",
           "Parole and supervision", "Immigration",
           "After the case: records, jobs, housing"]
QBEGIN = "<!-- prerender:questions:begin -->"
QEND = "<!-- prerender:questions:end -->"
LABEL_RE = re.compile(
    r'<(?:h2|p class="k")[^>]*data-stage="([^"]+)"[^>]*>.*?</(?:h2|p)>(.{0,1800})', re.S)
QUOTE_RE = re.compile(r'<em>\s*(?:&quot;|")(.+?)(?:&quot;|")\s*</em>', re.S)


def collect_questions(articles, root):
    """(stage, question, [(slug, title), ...]) for every tagged closer."""
    found = []
    for a in articles:
        path = os.path.join(root, "articles", a["slug"] + ".html")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()
        m = LABEL_RE.search(doc)
        if not m:
            continue
        q = QUOTE_RE.search(m.group(2))
        if not q:
            continue
        text = re.sub(r"<[^>]+>", "", q.group(1)).strip()
        found.append((m.group(1), text, a["slug"], a["title"]))

    # Near-duplicates: several articles land on the same question. Merge them
    # into one entry that lists every article it came from.
    merged = {}
    for stage, text, slug, title in found:
        # Key on the question alone, not the stage: the same question is asked
        # by articles sitting at different points in a case, and listing it
        # twice reads as padding. First stage seen wins.
        key = re.sub(r"[^a-z0-9]", "", text.lower())
        merged.setdefault(key, [stage, text, []])[2].append((slug, title))
    rows = list(merged.values())
    rows.sort(key=lambda r: (QSTAGES.index(r[0]) if r[0] in QSTAGES else 99, r[1]))
    return rows


def questions_html(rows):
    out = []
    for stage in QSTAGES:
        items = [r for r in rows if r[0] == stage]
        if not items:
            continue
        lis = []
        for _, text, srcs in items:
            links = ", ".join('<a href="articles/%s.html">%s</a>' % (s, e(t))
                              for s, t in srcs)
            lis.append('        <li>&ldquo;%s&rdquo;<span class="qi-src">%s</span></li>'
                       % (e(text), links))
        out.append('      <div class="qi-stage">\n        <h3>%s</h3>\n        <ul>\n%s\n'
                   "        </ul>\n      </div>" % (e(stage), "\n".join(lis)))
    return "\n".join(out)


# --- Stage hubs -------------------------------------------------------------
# One page per stage of a case, generated from the `stage` field on each
# article in data.js. The intro copy is authored; the article lists are not,
# so a new article appears in its hub the moment it is registered.
HUBS = [
    ("arrest", "Arrest and the first 24 hours"),
    ("court", "Getting through court"),
    ("bail", "Arraignment, bail and release"),
    ("counsel", "Getting a lawyer"),
    ("plea", "Plea and diversion"),
    ("pretrial", "Discovery, motions and trial rights"),
    ("sentencing", "Sentencing"),
    ("custody", "Jail and prison conditions"),
    ("parole", "Parole and supervision"),
    ("records", "Records, reentry and rights restoration"),
    ("system", "How the system works, and doesn't"),
]
HUB_BEGIN = "<!-- prerender:hub:begin -->"
HUB_END = "<!-- prerender:hub:end -->"


def hub_body(key, articles):
    """Card grid for one stage, newest first."""
    items = [a for a in articles if a.get("stage") == key]
    items.sort(key=lambda a: a.get("date") or "", reverse=True)
    if not items:
        return "", 0
    cards = "".join(card_html(a, prefix="../") for a in items)
    return '<div class="card-grid">%s</div>' % cards, len(items)


def write_hubs(articles, root, writes):
    for key, label in HUBS:
        path = os.path.join(root, "stages", key + ".html")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = fh.read()
        if HUB_BEGIN not in doc:
            continue
        body, n = hub_body(key, articles)
        block = HUB_BEGIN + "\n" + body + "\n    " + HUB_END
        new = re.sub(re.escape(HUB_BEGIN) + r".*?" + re.escape(HUB_END),
                     lambda _: block, doc, count=1, flags=re.S)
        new = re.sub(r'<span class="hub-count">[^<]*</span>',
                     '<span class="hub-count">%d article%s</span>' % (n, "" if n == 1 else "s"),
                     new, count=1)
        if new != doc:
            writes["stages/" + key + ".html"] = new

# --- Front page ---------------------------------------------------------------
# index.html is laid out like a newspaper front: one lead story, three under it,
# six more as a headline list. The dek is the article's own meta description,
# which is shorter than the data.js excerpt and already written to be read cold.
# Everything outside these two marker pairs is authored.
FRONT_BEGIN = "<!-- prerender:front:begin -->"
FRONT_END = "<!-- prerender:front:end -->"
MORE_BEGIN = "<!-- prerender:front-more:begin -->"
MORE_END = "<!-- prerender:front-more:end -->"


def nice_date(iso):
    import datetime
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return e(iso)
    return d.strftime("%b ") + str(d.day) + d.strftime(", %Y")


def article_dek(slug, root):
    path = os.path.join(root, "articles", slug + ".html")
    with open(path, encoding="utf-8") as fh:
        m = re.search(r'<meta name="description" content="([^"]*)"', fh.read())
    return html.unescape(m.group(1)) if m else ""


def front_html(live, root):
    lead, row = live[0], live[1:4]
    href = lambda a: "articles/%s.html" % e(a["slug"])
    og = "assets/social/%s-og.png" % lead["slug"]
    img = ('\n    <a href="%s" tabindex="-1" aria-hidden="true"><img src="%s" alt="" '
           'width="2400" height="1254"></a>' % (href(lead), e(og))
           if os.path.exists(os.path.join(root, og)) else "")
    out = ('\n  <article class="fp-lead">\n    <a href="%s"><span class="fp-kicker">%s</span>'
           '<h2 class="serif">%s</h2><p class="fp-dek">%s</p>'
           '<p class="fp-by">By Dean Mustaphalli &middot; %s</p></a>%s\n  </article>\n'
           % (href(lead), e(lead.get("category")), e(lead["title"]),
              e(article_dek(lead["slug"], root)), nice_date(lead.get("date")), img))
    out += '\n  <div class="fp-row">\n'
    for a in row:
        out += ('    <article><a href="%s"><span class="fp-kicker">%s</span><h3>%s</h3>'
                '<p class="fp-dek">%s</p><p class="fp-by">%s</p></a></article>\n'
                % (href(a), e(a.get("category")), e(a["title"]),
                   e(article_dek(a["slug"], root)), nice_date(a.get("date"))))
    return out + "  </div>\n  "


def more_html(live):
    return "".join(
        '\n        <li><a href="articles/%s.html"><span class="fp-kicker">%s</span>'
        '<h3 class="serif">%s</h3><p class="fp-by">%s</p></a></li>'
        % (e(a["slug"]), e(a.get("category")), e(a["title"]), nice_date(a.get("date")))
        for a in live[4:10]) + "\n        "


def write_front(doc, live, root):
    for begin, end, inner in ((FRONT_BEGIN, FRONT_END, front_html(live, root)),
                              (MORE_BEGIN, MORE_END, more_html(live))):
        if begin not in doc:
            raise SystemExit("prerender: index.html is missing %s" % begin)
        doc = re.sub(re.escape(begin) + r".*?" + re.escape(end),
                     lambda _: begin + inner + end, doc, count=1, flags=re.S)
    return doc


def main():
    check = "--check" in sys.argv
    os.chdir(ROOT)
    articles = parse_articles(open("assets/data.js", encoding="utf-8").read())

    tracked = set(subprocess.run(
        ["git", "ls-files", "articles"], capture_output=True, text=True,
        check=True).stdout.split())
    live = [a for a in articles
            if "articles/%s.html" % a["slug"] in tracked]
    skipped = [a["slug"] for a in articles if a not in live]

    writes = {}

    doc = open("articles.html", encoding="utf-8").read()
    writes["articles.html"] = fill_container(
        doc, "article-grid", "".join(card_html(a) for a in live))

    write_hubs(live, ROOT, writes)

    # checklist.html: the generated index of every closing question
    cpath = os.path.join(ROOT, "checklist.html")
    with open(cpath, encoding="utf-8") as fh:
        cdoc = fh.read()
    if QBEGIN in cdoc:
        rows = collect_questions(live, ROOT)
        body = QBEGIN + "\n" + questions_html(rows) + "\n    " + QEND
        writes["checklist.html"] = re.sub(
            re.escape(QBEGIN) + r".*?" + re.escape(QEND),
            lambda _: body, cdoc, count=1, flags=re.S)

    doc = open("index.html", encoding="utf-8").read()
    writes["index.html"] = write_front(doc, live, ROOT)

    for a in live:
        path = "articles/%s.html" % a["slug"]
        doc = open(path, encoding="utf-8").read()
        if re.search(r'<meta name="robots" content="[^"]*noindex', doc):
            raise SystemExit("prerender: %s still has the template's noindex line" % path)
        block = related_block(a, live)
        new = replace_region(doc, block)
        if new is None:
            if "</main>" not in doc:
                skipped.append(a["slug"] + " (no </main>)")
                continue
            new = doc.replace("</main>", block + "</main>", 1)
        writes[path] = new

    writes["sitemap.xml"] = sitemap(articles, tracked)

    changed = [p for p, c in writes.items()
               if not os.path.exists(p) or open(p, encoding="utf-8").read() != c]

    if check:
        print("prerender --check: %d file(s) would change" % len(changed))
        for p in changed[:20]:
            print("  " + p)
        return 1 if changed else 0

    for p in changed:
        open(p, "w", encoding="utf-8").write(writes[p])

    print("articles in data.js : %d" % len(articles))
    print("published (tracked) : %d" % len(live))
    print("files written       : %d" % len(changed))
    if skipped:
        print("skipped (untracked) : %d" % len(skipped))
        for s in skipped[:12]:
            print("  " + s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
