#!/usr/bin/env python3
"""Pre-render article links into static HTML so Google can crawl them.

Reads ARTICLES from assets/data.js (the single source of truth) and writes:
  - articles.html        #article-grid       full card grid
  - index.html           #home-article-grid  3 compact cards
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
FIELDS = ("slug", "title", "category", "date", "excerpt",
          "image", "imageAlt", "imageCredit")
STATIC_PAGES = [
    ("", "1.0"), ("articles.html", "0.9"), ("about.html", "0.7"),
    ("videos.html", "0.7"), ("restorative-justice.html", "0.7"),
    ("help-after-an-arrest-ny.html", "0.8"), ("checklist.html", "0.7"),
    ("intake-worksheet.html", "0.7"),
    ("methodology.html", "0.7"),
    ("glossary.html", "0.7"),
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


def related_block(a, articles, n=3):
    same = [x for x in articles
            if x["slug"] != a["slug"] and x.get("category") == a.get("category")]
    rest = [x for x in articles
            if x["slug"] != a["slug"] and x not in same]
    picks = (same + rest)[:n]
    if not picks:
        return ""
    cards = "".join(card_html(x, prefix="../", compact=True) for x in picks)
    return ('\n%s\n<section class="wrap related-articles">\n'
            '  <h2>Related reading</h2>\n'
            '  <div class="card-grid">%s</div>\n'
            '</section>\n%s\n' % (BEGIN, cards, END))


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
    writes["index.html"] = fill_container(
        doc, "home-article-grid",
        "".join(card_html(a, compact=True) for a in live[:3]))

    for a in live:
        path = "articles/%s.html" % a["slug"]
        doc = open(path, encoding="utf-8").read()
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
