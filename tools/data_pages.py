#!/usr/bin/env python3
"""Build the two single-question data pages from the agencies' open data.

  nyc-jail-population.html   NYC Department of Correction daily file (7479-ugqb)
  ny-prison-population.html  NYS DOCCS people under custody on March 31 (55zc-sp6m)

Each page answers one search question, with the source, the day it was read, a
table beside every chart, and CSV and JSON downloads. The pages are written whole
(not region by region), borrowing the header and footer from data.html so the
navigation stays in sync. data_snapshot.py runs this at the end of every refresh;
it can also be run alone from the Website folder:  python3 tools/data_pages.py

Figures are stated as the agency states them. Computed here, and said on the page:
shares of the total by race and ethnicity.
"""
import json, csv, re, html, pathlib, datetime, collections, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data"
CSVD = DATA / "csv"
SITE = "https://www.caseanalytica.com/"
NOW = datetime.date.today()
TODAY = NOW.isoformat()
LONG = f"{NOW.strftime('%B')} {NOW.day}, {NOW.year}"


def get(url):
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def socrata(host, ds, **q):
    return get(f"https://{host}/resource/{ds}.json?" + urllib.parse.urlencode(q))


def updated(host, ds):
    m = get(f"https://{host}/api/views/{ds}.json")
    return datetime.datetime.fromtimestamp(m["rowsUpdatedAt"], datetime.timezone.utc).strftime("%Y-%m-%d")


def n(x):
    return f"{int(x):,}"


def esc(s):
    return html.escape(str(s), quote=True)


def table(head, rows, cap):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="dt"><caption class="sr-only">{esc(cap)}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def tiles(items):
    return '<div class="dash-tiles">' + "".join(
        f'<div class="tile"><div class="n">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in items) + "</div>"


def source_line(name, url, publisher, upd, caveat):
    return (f'<p class="dir-caveat">Source: <a href="{esc(url)}" target="_blank" rel="noopener">{esc(name)}</a>, published by {esc(publisher)}. '
            f'The agency last updated it on {upd}. Case Analytica read it on {TODAY}. {esc(caveat)}</p>')


def write_csv(name, header, rows):
    CSVD.mkdir(parents=True, exist_ok=True)
    with open(CSVD / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ---- shared shell, taken from the hub page so the nav and footer never drift
hub = (ROOT / "data.html").read_text()
SHELL_TOP = hub[hub.index("<style>"):hub.index("</style>") + 8]
HEADER = hub[hub.index("<header class=\"site-nav\">"):hub.index("<main>")]
FOOTER = hub[hub.index("<footer class=\"site-footer\">"):hub.index("<script src=\"assets/data-charts.js")]
CSS_V = re.search(r'assets/style\.css\?v=(\w+)', hub).group(1)
CHART_V = re.search(r'assets/data-charts\.js\?v=(\w+)', hub).group(1)
HEADER = HEADER.replace('class="current"', "")
HEADER = HEADER.replace('<a href="data.html" >Data</a>', '<a href="data.html" class="current">Data</a>')


def page(slug, title, desc, h1, body, script, ld_extra):
    url = SITE + slug
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
        {"@type": "ListItem", "position": 2, "name": "Data", "item": SITE + "data.html"},
        {"@type": "ListItem", "position": 3, "name": h1, "item": url}]}
    lds = "".join('<script type="application/ld+json">\n' + json.dumps(o, indent=1) + "\n</script>\n" for o in (crumbs, ld_extra))
    return f"""<!doctype html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-035TDMG4Y0"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());

  gtag('config', 'G-035TDMG4Y0');
</script>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="max-image-preview:large">
<link rel="icon" type="image/png" sizes="32x32" href="assets/icons/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="assets/icons/favicon-16.png">
<link rel="apple-touch-icon" href="assets/icons/apple-touch-icon.png">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" type="application/rss+xml" title="Case Analytica" href="https://www.caseanalytica.com/feed.xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Case Analytica">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<link rel="stylesheet" href="assets/style.css?v={CSS_V}">
{lds}{SHELL_TOP}
</head>
<body>

{HEADER}<a href="guide.html" class="guide-fab" aria-label="Get the free guide">
  <span class="guide-fab-icon">📘</span>
  <span class="guide-fab-text">Free Guide</span>
</a>

<main>

<section style="padding-top:48px;">
  <div class="narrow">
{body}
  </div>
</section>

</main>

{FOOTER}<script src="assets/data-charts.js?v={CHART_V}"></script>
<script>
(function(){{
  function $(id){{return document.getElementById(id)}}
  function J(p){{return fetch(p).then(function(r){{return r.json()}})}}
{script}
}})();
</script>
</body>
</html>
"""


def dataset_ld(name, desc, url, source_url, publisher, temporal, files):
    return {"@context": "https://schema.org", "@type": "Dataset", "name": name, "description": desc, "url": url,
            "creator": {"@type": "Organization", "name": publisher}, "isBasedOn": source_url, "temporalCoverage": temporal,
            "spatialCoverage": "New York", "dateModified": TODAY,
            "publisher": {"@type": "Organization", "name": "Case Analytica", "url": SITE},
            "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv" if f.endswith(".csv") else "application/json",
                              "contentUrl": SITE + f} for f in files]}


# =============================================================== NYC jail population
H2, ID = "data.cityofnewyork.us", "7479-ugqb"
jail = json.loads((DATA / "nyc-jail.json").read_text())
hist = json.loads((DATA / "nyc-jail-history.json").read_text())
upd = jail["source_last_updated"]
total = jail["total"]
gender = jail["by_gender"]
bands = jail["by_age_band"]
gtxt = ", ".join(f"{n(v)} {k.lower()}" for k, v in sorted(gender.items(), key=lambda kv: -kv[1]))
first_day = hist["days"][0]["date"]
fd = datetime.date.fromisoformat(first_day)
first_long = f"{fd.strftime('%B')} {fd.day}, {fd.year}"

jail_body = f"""    <p class="eyebrow"><a href="data.html">Data</a> / New York City jails</p>
    <h1 class="serif" style="font-size:clamp(28px,4vw,38px);margin:0 0 18px;">How many people are in NYC jails today?</h1>
    <p class="ind-head">On {LONG}, {n(total)} people were in the custody of the New York City Department of Correction ({gtxt}).</p>
    {source_line("Daily Inmates In Custody", f"https://data.cityofnewyork.us/d/{ID}", "the NYC Department of Correction", upd,
                 "The file shows one day only and leaves out sealed cases.")}
    {tiles([(n(total), f"in custody on {TODAY}")] + [(n(v), k.lower()) for k, v in sorted(gender.items(), key=lambda kv: -kv[1])[:2]])}

    <h2 style="margin-top:34px;">By age</h2>
    <div class="chart"><svg id="c-jail" role="img" aria-label="Bar chart of people in New York City jails by age band on the day the data was read"></svg></div>
    <details class="raw"><summary>The counts behind the chart</summary>
    {table(["Age", "People in custody"], [[b["band"], n(b["count"])] for b in bands], f"People in NYC jails by age band on {TODAY}")}
    </details>

    <h2 style="margin-top:34px;">Is this the Rikers Island population?</h2>
    <p>Not exactly. The file counts everyone in the Department of Correction's custody. It has no field for the facility where a person is held, so Case Analytica does not publish a count for Rikers Island alone. For the Rikers questions the file cannot answer, see the articles at the bottom of this page.</p>

    <h2 style="margin-top:34px;">Why this number can differ from other reports</h2>
    <p>The agency says the file leaves out sealed cases and that totals built from it "may differ slightly from other published statistics." This is also one day's count, read on {LONG}. An average over a month will not match a single day.</p>

    <h2 style="margin-top:34px;">Daily history</h2>
    <p>The agency's file holds only the current day. Case Analytica saves each day it reads the file. The record starts on {first_long} and grows each time this page is refreshed.</p>
    <div id="jail-hist" class="chart" hidden><svg id="c-jhist" role="img" aria-label="Line chart of the daily count of people in New York City jails since this page began recording"></svg></div>
    <details class="raw"><summary>The days recorded so far</summary>
    {table(["Date", "People in custody"], [[d["date"], n(d["total"])] for d in reversed(hist["days"])], "Daily count of people in NYC jails")}
    </details>
    <p class="dl">Download: <a href="assets/data/csv/nyc-jail.csv" download>Today's counts (CSV)</a> · <a href="assets/data/nyc-jail.json" download>Today's counts (JSON)</a> · <a href="assets/data/nyc-jail-history.json" download>Daily history (JSON)</a></p>

    <h2 style="margin-top:34px;">More on New York City jails</h2>
    <ul class="std">
      <li><a href="articles/rikers-island-cost-per-person-ny.html">What Rikers Island costs per person</a></li>
      <li><a href="articles/rikers-detention-plea-leverage-ny.html">How detention at Rikers affects plea decisions</a></li>
      <li><a href="articles/why-rikers-island-should-close-ny.html">Why Rikers Island should close</a></li>
      <li><a href="ny-prison-population.html">New York State prison population by year, race and age</a></li>
      <li><a href="data.html">All the data, with sources and downloads</a></li>
    </ul>
    <p>To cite a figure, cite the agency named under it. Corrections are welcome at <!--email_off--><a href="mailto:caseanalytica@gmail.com">caseanalytica@gmail.com</a><!--/email_off-->. See also <a href="methodology.html">our method</a>.</p>"""

jail_script = """  J('assets/data/nyc-jail.json').then(function(D){
    CAChart.hbars($('c-jail'),D.by_age_band.map(function(b){return {label:b.band,value:b.count}}));
  });
  J('assets/data/nyc-jail-history.json').then(function(H){
    if(H.days.length>1){$('jail-hist').hidden=false;
      CAChart.line($('c-jhist'),[{name:'In custody',cls:'s1',pts:H.days.map(function(d){return {x:d.date.slice(5),y:d.total}})}],{h:220});}
  });"""

jail_title = "NYC Jail Population Today: Daily Count by Age and Gender"
jail_desc = (f"{n(total)} people were in NYC jails on {LONG}, per the Department of Correction's daily file. "
             "Age and gender counts, a daily history and a CSV.")
(ROOT / "nyc-jail-population.html").write_text(page(
    "nyc-jail-population.html", jail_title, jail_desc, "How many people are in NYC jails today?", jail_body, jail_script,
    dataset_ld("People in New York City jails, current day and daily history", jail_desc,
               SITE + "nyc-jail-population.html", f"https://data.cityofnewyork.us/d/{ID}", "NYC Department of Correction",
               f"{first_day}/{hist['days'][-1]['date']}", ["assets/data/csv/nyc-jail.csv", "assets/data/nyc-jail.json", "assets/data/nyc-jail-history.json"])))

# =============================================================== NY prison population
H1, ID = "data.ny.gov", "55zc-sp6m"
upd = updated(H1, ID)
pp = json.loads((DATA / "prison-population.json").read_text())
Y = pp["yearly"]
LY, FY = Y[-1], Y[0]
ly = LY["year"]

race_rows = socrata(H1, ID, **{"$select": "snapshot_year,race_ethnicity,count(*)", "$group": "snapshot_year,race_ethnicity",
                                "$order": "snapshot_year", "$limit": "2000", "$where": "snapshot_year>=2018"})
race = collections.defaultdict(dict)
for r in race_rows:
    race[int(r["snapshot_year"])][r.get("race_ethnicity", "NOT RECORDED")] = int(r["count"])
RN = {"BLACK": "Black", "HISPANIC": "Hispanic", "WHITE": "White", "ASIAN": "Asian", "NATIVE AMERICAN": "Native American", "OTHER": "Other", "UNKNOWN": "Unknown", "NOT RECORDED": "Not recorded"}
cats = [c for c, _ in sorted(race[ly].items(), key=lambda kv: -kv[1])]
gend = {r["gender"].title(): int(r["count"]) for r in socrata(H1, ID, **{"$select": "gender,count(*)", "$group": "gender", "$where": f"snapshot_year={ly}"})}
ages = [(int(r["current_age"]), int(r["count"])) for r in socrata(H1, ID, **{"$select": "current_age,count(*)", "$group": "current_age", "$where": f"snapshot_year={ly}", "$limit": "200"}) if r.get("current_age", "").isdigit()]
BANDS = [("Under 25", 0, 24), ("25 to 34", 25, 34), ("35 to 44", 35, 44), ("45 to 54", 45, 54), ("55 to 64", 55, 64), ("65 and older", 65, 200)]
bands = [{"band": b, "count": sum(c for a, c in ages if lo <= a <= hi)} for b, lo, hi in BANDS]
lt = LY["total"]

demo = {"title": f"People under New York State prison custody on March 31, {ly}, by race and ethnicity, gender and age",
        "source": "NYS Department of Corrections and Community Supervision, via NY Open Data", "source_url": f"https://data.ny.gov/d/{ID}",
        "dataset_id": ID, "source_last_updated": upd, "retrieved": TODAY, "snapshot_year": ly,
        "race_ethnicity_by_year": {str(y): {RN.get(k, k.title()): v for k, v in race[y].items()} for y in sorted(race)},
        "by_gender": gend, "by_age_band": bands,
        "notes": "Age is as of the file date, not March 31. Race and ethnicity is provided from the 2018 snapshot onward, per the agency."}
(DATA / "prison-population-demographics.json").write_text(json.dumps(demo, indent=1) + "\n")
write_csv("prison-population-demographics", ["snapshot_year_as_of_march_31", "group", "value", "count"],
          [[y, "race_ethnicity", RN.get(k, k.title()), v] for y in sorted(race) for k, v in sorted(race[y].items(), key=lambda kv: -kv[1])]
          + [[ly, "gender", k, v] for k, v in sorted(gend.items(), key=lambda kv: -kv[1])]
          + [[ly, "age_band", b["band"], b["count"]] for b in bands])

shares = [[RN.get(c, c.title()), n(race[ly][c]), f"{race[ly][c] / lt * 100:.1f}%"] for c in cats]
yrs = sorted(race)
race_year_table = table(["As of March 31 of"] + [RN.get(c, c.title()) for c in cats],
                        [[y] + [n(race[y].get(c, 0)) for c in cats] for y in reversed(yrs)], "People under custody by race and ethnicity and year")
male, female = gend.get("Male", 0), gend.get("Female", 0)

prison_body = f"""    <p class="eyebrow"><a href="data.html">Data</a> / New York State prisons</p>
    <h1 class="serif" style="font-size:clamp(28px,4vw,38px);margin:0 0 18px;">New York State prison population by year, race and age</h1>
    <p class="ind-head">On March 31, {ly}, {n(lt)} people were in the custody of the state prison system. On March 31, {FY["year"]}, it was {n(FY["total"])}.</p>
    {source_line("Incarcerated Individuals Under Custody: Beginning 2008", f"https://data.ny.gov/d/{ID}", "the NYS Department of Corrections and Community Supervision", upd,
                 "This is a count on one day each year, not a count over the year.")}
    {tiles([(n(lt), f"under custody, March 31, {ly}"), (n(Y[-2]["total"]), f"under custody, March 31, {Y[-2]['year']}"), (n(male), "men"), (n(female), "women")])}

    <h2 style="margin-top:34px;">By year</h2>
    <div class="chart"><svg id="c-pop" role="img" aria-label="Line chart of people under state prison custody on March 31 of each year"></svg></div>
    <details class="raw"><summary>The counts behind the chart</summary>
    {table(["As of March 31 of", "People under custody"], [[r["year"], n(r["total"])] for r in reversed(Y)], "People under custody by year")}
    </details>

    <h2 style="margin-top:34px;">By race and ethnicity, March 31, {ly}</h2>
    <div class="chart"><svg id="c-race" role="img" aria-label="Bar chart of people under state prison custody by race and ethnicity on March 31, {ly}"></svg></div>
    {table(["Race and ethnicity", "People", "Share of all under custody"], shares, f"People under custody by race and ethnicity, March 31, {ly}")}
    <p class="dir-caveat">The shares are Case Analytica's arithmetic from the agency's counts. The agency says this field is what the person reported, adjusted so that anyone of Hispanic ethnicity is counted as Hispanic whatever race they reported. It says the field is provided from the March 31, 2018 snapshot onward, so this table starts in 2018.</p>
    <details class="raw"><summary>Race and ethnicity counts for every year from 2018</summary>
    {race_year_table}
    </details>

    <h2 style="margin-top:34px;">By age, March 31, {ly}</h2>
    <div class="chart"><svg id="c-age" role="img" aria-label="Bar chart of people under state prison custody by age band on March 31, {ly}"></svg></div>
    <details class="raw"><summary>The counts behind the chart</summary>
    {table(["Age", "People"], [[b["band"], n(b["count"])] for b in bands], f"People under custody by age band, March 31, {ly}")}
    </details>
    <p class="dir-caveat">The agency's age field is the person's age as of the file date, not on March 31.</p>

    <h2 style="margin-top:34px;">Population is not admissions</h2>
    <p>The count above is everyone in custody on one day. A different measure, admissions, counts how many people entered state prison during a year, and someone admitted twice is counted twice. The two are never added together. <a href="data.html#prison-admissions">Admissions by year are on the data hub</a>.</p>
    <p class="dl">Download: <a href="assets/data/csv/prison-population.csv" download>Totals by year (CSV)</a> · <a href="assets/data/csv/prison-population-demographics.csv" download>Race, gender and age (CSV)</a> · <a href="assets/data/prison-population-demographics.json" download>Race, gender and age (JSON)</a></p>

    <h2 style="margin-top:34px;">More on New York State prisons and parole</h2>
    <ul class="std">
      <li><a href="articles/parole-board-racial-disparity-release-rates-ny.html">Parole Board release rates and racial disparity</a></li>
      <li><a href="articles/conditional-release-overtakes-parole-board-releases-ny.html">Conditional release now outpaces Parole Board releases</a></li>
      <li><a href="nyc-jail-population.html">How many people are in NYC jails today</a></li>
      <li><a href="data.html">All the data, with sources and downloads</a></li>
    </ul>
    <p>To cite a figure, cite the agency named under it. Corrections are welcome at <!--email_off--><a href="mailto:caseanalytica@gmail.com">caseanalytica@gmail.com</a><!--/email_off-->. See also <a href="methodology.html">our method</a>.</p>"""

prison_script = f"""  J('assets/data/prison-population.json').then(function(D){{
    CAChart.line($('c-pop'),[{{name:'Under custody March 31',cls:'s1',pts:D.yearly.map(function(r){{return {{x:r.year,y:r.total}}}})}}]);
  }});
  J('assets/data/prison-population-demographics.json').then(function(D){{
    var R=D.race_ethnicity_by_year['{ly}'],rows=Object.keys(R).map(function(k){{return {{label:k,value:R[k]}}}}).sort(function(a,b){{return b.value-a.value}});
    CAChart.hbars($('c-race'),rows);
    CAChart.hbars($('c-age'),D.by_age_band.map(function(b){{return {{label:b.band,value:b.count}}}}));
  }});"""

prison_title = "New York Prison Population by Year, Race and Age"
prison_desc = (f"{n(lt)} people were in New York State prisons on March 31, {ly}, {'down' if lt < FY['total'] else 'up'} from {n(FY['total'])} in {FY['year']}. "
               "Counts by year, race and ethnicity, gender and age, with a CSV.")
(ROOT / "ny-prison-population.html").write_text(page(
    "ny-prison-population.html", prison_title, prison_desc, "New York State prison population by year, race and age", prison_body, prison_script,
    dataset_ld("People under New York State prison custody on March 31, by year, race and ethnicity, gender and age", prison_desc,
               SITE + "ny-prison-population.html", f"https://data.ny.gov/d/{ID}", "NYS Department of Corrections and Community Supervision",
               f"{FY['year']}/{ly}", ["assets/data/csv/prison-population.csv", "assets/data/csv/prison-population-demographics.csv", "assets/data/prison-population-demographics.json"])))

print("data pages built:", TODAY, "| jail", n(total), "| prison", n(lt), f"({ly})")
