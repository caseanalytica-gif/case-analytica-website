#!/usr/bin/env python3
"""Refresh the data hub (data.html) from the agencies' open data.

Reads four public datasets, writes one JSON and one CSV per indicator under
assets/data/, and rewrites the generated regions of data.html (the pairs of
<!-- ind:ID-top:begin --> ... <!-- ind:ID-top:end --> and the -bot pairs), so the
figures are in the HTML for crawlers and for readers without JavaScript. The
charts read the JSON in the browser.

  prison-admissions   NYS DOCCS, data.ny.gov m2rg-xjan
  prison-population   NYS DOCCS, data.ny.gov 55zc-sp6m
  adult-arrests       NYS DCJS,  data.ny.gov rikd-mt35
  nyc-jail            NYC DOC,   data.cityofnewyork.us 7479-ugqb  (daily feed)
  parole              reads assets/data/parole-board-decisions.json (tools/parole_snapshot.py)

Run from the Website folder:  python3 tools/data_snapshot.py
Then look at the page and commit the changed files. A source is only re-read
when this is run, so each indicator's "Read" date is the date of the last run.
The NYC jail feed holds one day only, so each run appends that day to
assets/data/nyc-jail-history.json; the series starts the first day it was run.

Figures are stated as the source states them. The one thing computed here is the
adult-arrests state total, which adds up the county rows; the page says so.
"""
import json, csv, re, html, pathlib, datetime, collections, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "assets" / "data"
CSVD = DATA / "csv"
PAGE = ROOT / "data.html"
TODAY = datetime.date.today().isoformat()
SITE = "https://www.caseanalytica.com/"


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
    return html.escape(s, quote=True)


def write_json(name, obj):
    (DATA / f"{name}.json").write_text(json.dumps(obj, indent=1) + "\n")


def write_csv(name, header, rows):
    CSVD.mkdir(parents=True, exist_ok=True)
    with open(CSVD / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def table(head, rows, cap):
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="dt"><caption class="sr-only">{esc(cap)}</caption><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def tiles(items):
    return '<div class="dash-tiles">' + "".join(
        f'<div class="tile"><div class="n">{esc(v)}</div><div class="l">{esc(l)}</div></div>' for v, l in items) + "</div>"


def downloads(name):
    return (f'<p class="dl">Download: <a href="assets/data/csv/{name}.csv" download>CSV</a> · '
            f'<a href="assets/data/{name}.json" download>JSON</a></p>')


def source_line(src_name, src_url, publisher, upd, caveat):
    return (f'<p class="dir-caveat">Source: <a href="{esc(src_url)}" target="_blank" rel="noopener">{esc(src_name)}</a>, '
            f'published by {esc(publisher)}. The agency last updated it on {upd}. Case Analytica read it on {TODAY}. {esc(caveat)}</p>')


regions = {}   # region id -> html
catalog = []   # for data.html JSON-LD and assets/data/catalog.json


# ---------------------------------------------------------------- prison admissions
HOST = "data.ny.gov"
ID = "m2rg-xjan"
rows = socrata(HOST, ID, **{"$select": "admission_year,latest_admission_type,count(*)",
                            "$group": "admission_year,latest_admission_type", "$limit": "10000"})
upd = updated(HOST, ID)
TYPES = {"NEW COURT COMMITMENT": "new_court_commitment", "RET PAROLE VIOLATOR": "returned_parole_violator"}
adm = collections.defaultdict(collections.Counter)
raw_types = collections.Counter()
for r in rows:
    k = TYPES.get(r["latest_admission_type"], "other")
    adm[int(r["admission_year"])][k] += int(r["count"])
    raw_types[r["latest_admission_type"]] += int(r["count"])
ys = sorted(adm)
yearly = [{"year": y, "new_court_commitment": adm[y]["new_court_commitment"],
           "returned_parole_violator": adm[y]["returned_parole_violator"], "other": adm[y]["other"],
           "total": sum(adm[y].values())} for y in ys]
pop = "Admissions to state prison for a new offense or a parole violation, counted by year of admission."
write_json("prison-admissions", {
    "title": "New York State prison admissions by year", "source": "NYS Department of Corrections and Community Supervision, via NY Open Data",
    "source_url": f"https://data.ny.gov/d/{ID}", "dataset_id": ID, "source_last_updated": upd, "retrieved": TODAY,
    "population": pop, "admission_types_in_source": dict(sorted(raw_types.items())), "yearly": yearly})
write_csv("prison-admissions", ["year", "new_court_commitment", "returned_parole_violator", "other", "total"],
          [[r["year"], r["new_court_commitment"], r["returned_parole_violator"], r["other"], r["total"]] for r in yearly])
L, F = yearly[-1], yearly[0]
regions["prison-admissions-top"] = (
    f'<p class="ind-head">The state prison system admitted {n(L["total"])} people in {L["year"]}, down from {n(F["total"])} in {F["year"]}. '
    f'In {L["year"]}, {n(L["new_court_commitment"])} were new court commitments and {n(L["returned_parole_violator"])} were people returned for a parole violation.</p>'
    + source_line("Prison Admissions: Beginning 2008", f"https://data.ny.gov/d/{ID}", "the NYS Department of Corrections and Community Supervision", upd,
                  "This counts admissions, not people: someone admitted twice in a year is counted twice. The agency says its county field should not be used to count convictions by county.")
    + tiles([(n(L["total"]), f"admissions in {L['year']}"), (n(L["new_court_commitment"]), "new court commitments"),
             (n(L["returned_parole_violator"]), "returned for a parole violation")]))
regions["prison-admissions-bot"] = (
    '<details class="raw"><summary>The counts behind the chart</summary>'
    + table(["Year", "New court commitments", "Returned parole violators", "Total"],
            [[r["year"], n(r["new_court_commitment"]), n(r["returned_parole_violator"]), n(r["total"])] for r in reversed(yearly)],
            "Prison admissions by year") + "</details>" + downloads("prison-admissions"))
catalog.append({"id": "prison-admissions", "name": "New York State prison admissions by year, 2008 to present",
                "description": "Annual counts of admissions to New York State prisons, split into new court commitments and returned parole violators. Counts come from the NYS Department of Corrections and Community Supervision.",
                "temporal": f"{ys[0]}/{ys[-1]}", "source_url": f"https://data.ny.gov/d/{ID}", "publisher": "NYS Department of Corrections and Community Supervision"})

# ---------------------------------------------------------------- prison population
ID = "55zc-sp6m"
rows = socrata(HOST, ID, **{"$select": "snapshot_year,count(*)", "$group": "snapshot_year", "$order": "snapshot_year"})
upd = updated(HOST, ID)
py = [{"year": int(r["snapshot_year"]), "total": int(r["count"])} for r in rows]
pop = "People under DOCCS custody on March 31 of the snapshot year. Incarcerated individuals only."
write_json("prison-population", {
    "title": "People under New York State prison custody on March 31 of each year", "source": "NYS Department of Corrections and Community Supervision, via NY Open Data",
    "source_url": f"https://data.ny.gov/d/{ID}", "dataset_id": ID, "source_last_updated": upd, "retrieved": TODAY,
    "population": pop, "yearly": py})
write_csv("prison-population", ["snapshot_year_as_of_march_31", "people_under_custody"], [[r["year"], r["total"]] for r in py])
L, F = py[-1], py[0]
regions["prison-population-top"] = (
    f'<p class="ind-head">On March 31, {L["year"]}, {n(L["total"])} people were in the custody of the state prison system. On March 31, {F["year"]}, it was {n(F["total"])}.</p>'
    + source_line("Incarcerated Individuals Under Custody: Beginning 2008", f"https://data.ny.gov/d/{ID}", "the NYS Department of Corrections and Community Supervision", upd,
                  "This is a count on one day each year, not a count over the year. It is a different measure from admissions above.")
    + tiles([(n(L["total"]), f"under custody, March 31, {L['year']}"), (n(py[-2]["total"]), f"under custody, March 31, {py[-2]['year']}")]))
regions["prison-population-bot"] = (
    '<details class="raw"><summary>The counts behind the chart</summary>'
    + table(["As of March 31 of", "People under custody"], [[r["year"], n(r["total"])] for r in reversed(py)], "People under custody by year")
    + "</details>" + downloads("prison-population"))
catalog.append({"id": "prison-population", "name": "People under New York State prison custody on March 31, 2008 to present",
                "description": "Counts of incarcerated people under the custody of the NYS Department of Corrections and Community Supervision on March 31 of each year.",
                "temporal": f"{py[0]['year']}/{py[-1]['year']}", "source_url": f"https://data.ny.gov/d/{ID}", "publisher": "NYS Department of Corrections and Community Supervision"})

# ---------------------------------------------------------------- adult arrests
ID = "rikd-mt35"
rows = socrata(HOST, ID, **{"$select": "year,sum(total),sum(felony_total),sum(misdemeanor_total)", "$group": "year", "$order": "year", "$limit": "200"})
upd = updated(HOST, ID)
ay = [{"year": int(r["year"]), "total": int(float(r["sum_total"])), "felony": int(float(r["sum_felony_total"])),
       "misdemeanor": int(float(r["sum_misdemeanor_total"]))} for r in rows]
ly = ay[-1]["year"]
BOROS = ["New York", "Kings", "Bronx", "Queens", "Richmond"]
boro_rows = socrata(HOST, ID, **{"$where": f"year='{ly}' AND county in('New York','Kings','Bronx','Queens','Richmond')",
                                  "$select": "county,total,felony_total,misdemeanor_total"})
NAMES = {"New York": "Manhattan (New York County)", "Kings": "Brooklyn (Kings County)", "Bronx": "Bronx", "Queens": "Queens", "Richmond": "Staten Island (Richmond County)"}
boros = [{"county": NAMES[c], "total": int(next(r for r in boro_rows if r["county"] == c)["total"]),
          "felony": int(next(r for r in boro_rows if r["county"] == c)["felony_total"]),
          "misdemeanor": int(next(r for r in boro_rows if r["county"] == c)["misdemeanor_total"])} for c in BOROS]
pop = ("Arrest events for people 18 or older when the crime was committed, for fingerprintable offenses (any felony, and misdemeanors "
       "defined in the penal law). Each event is counted once, under its most serious charge. State totals add up the county rows.")
write_json("adult-arrests", {
    "title": "Adult arrests in New York State by year", "source": "NYS Division of Criminal Justice Services, via NY Open Data",
    "source_url": f"https://data.ny.gov/d/{ID}", "dataset_id": ID, "source_last_updated": upd, "retrieved": TODAY,
    "population": pop, "yearly": ay, "nyc_counties_latest_year": {"year": ly, "rows": boros}})
write_csv("adult-arrests", ["year", "total_arrest_events", "felony", "misdemeanor"], [[r["year"], r["total"], r["felony"], r["misdemeanor"]] for r in ay])
L, P = ay[-1], ay[-2]
nyc_total = sum(b["total"] for b in boros)
regions["adult-arrests-top"] = (
    f'<p class="ind-head">The county rows add up to {n(L["total"])} adult arrest events in {L["year"]}, and {n(P["total"])} in {P["year"]}. '
    f'In {L["year"]}, {n(L["felony"])} were counted as felonies and {n(L["misdemeanor"])} as misdemeanors. The five New York City counties account for {n(nyc_total)}.</p>'
    + source_line("Adult Arrests 18 and Older by County: Beginning 1970", f"https://data.ny.gov/d/{ID}", "the NYS Division of Criminal Justice Services", upd,
                  "Case Analytica added up the county rows to get a state figure. Arrests of people under 18 and non-fingerprintable offenses are not included.")
    + tiles([(n(L["total"]), f"adult arrest events, {L['year']}"), (n(L["felony"]), "counted as felonies"), (n(L["misdemeanor"]), "counted as misdemeanors")]))
regions["adult-arrests-bot"] = (
    f'<h3>New York City counties, {ly}</h3>'
    + table(["County", "All arrest events", "Felony", "Misdemeanor"], [[b["county"], n(b["total"]), n(b["felony"]), n(b["misdemeanor"])] for b in boros],
            f"Adult arrest events by New York City county, {ly}")
    + '<details class="raw"><summary>The state counts behind the chart</summary>'
    + table(["Year", "All arrest events", "Felony", "Misdemeanor"], [[r["year"], n(r["total"]), n(r["felony"]), n(r["misdemeanor"])] for r in reversed(ay)],
            "Adult arrest events in New York State by year") + "</details>" + downloads("adult-arrests"))
catalog.append({"id": "adult-arrests", "name": "Adult arrests in New York State by year, 1970 to present",
                "description": "Annual counts of arrest events for adults in New York State, from the county rows published by the NYS Division of Criminal Justice Services, with felony and misdemeanor totals.",
                "temporal": f"{ay[0]['year']}/{ay[-1]['year']}", "source_url": f"https://data.ny.gov/d/{ID}", "publisher": "NYS Division of Criminal Justice Services"})

# ---------------------------------------------------------------- NYC jail (daily feed, one day at a time)
H2, ID = "data.cityofnewyork.us", "7479-ugqb"
total = int(socrata(H2, ID, **{"$select": "count(inmateid)"})[0]["count_inmateid"])
upd = updated(H2, ID)
GL = {"M": "Male", "F": "Female"}
gender = {GL.get(r.get("gender", ""), "Not recorded"): int(r["count_inmateid"]) for r in socrata(H2, ID, **{"$select": "gender,count(inmateid)", "$group": "gender"})}
ages = [int(r["age"]) for r in socrata(H2, ID, **{"$select": "age", "$limit": "20000"}) if r.get("age", "").isdigit()]
BANDS = [("Under 18", 0, 17), ("18 to 24", 18, 24), ("25 to 34", 25, 34), ("35 to 44", 35, 44), ("45 to 54", 45, 54), ("55 and older", 55, 200)]
bands = [{"band": b, "count": sum(1 for a in ages if lo <= a <= hi)} for b, lo, hi in BANDS]
if total - sum(b["count"] for b in bands):
    bands.append({"band": "Age not recorded", "count": total - sum(b["count"] for b in bands)})
pop = "People in New York City Department of Correction custody on the day the feed was read. The agency excludes sealed cases, so totals can differ slightly from its other published statistics."
hist_path = DATA / "nyc-jail-history.json"
hist = json.loads(hist_path.read_text()) if hist_path.exists() else {"note": "One row per day this page was refreshed. The agency's feed holds only the current day, so this series starts the first day it was recorded.", "days": []}
hist["days"] = [d for d in hist["days"] if d["date"] != TODAY] + [{"date": TODAY, "total": total}]
hist["days"].sort(key=lambda d: d["date"])
hist_path.write_text(json.dumps(hist, indent=1) + "\n")
write_json("nyc-jail", {
    "title": "People in New York City jails, current day", "source": "NYC Department of Correction, via NYC Open Data",
    "source_url": f"https://data.cityofnewyork.us/d/{ID}", "dataset_id": ID, "source_last_updated": upd, "retrieved": TODAY,
    "population": pop, "total": total, "by_gender": gender, "by_age_band": bands, "history_file": "assets/data/nyc-jail-history.json"})
write_csv("nyc-jail", ["read_date", "group", "value", "count"],
          [[TODAY, "total", "all", total]] + [[TODAY, "gender", k, v] for k, v in sorted(gender.items())] + [[TODAY, "age_band", b["band"], b["count"]] for b in bands])
gtxt = ", ".join(f"{n(v)} {k.lower()}" for k, v in sorted(gender.items(), key=lambda kv: -kv[1]))
regions["nyc-jail-top"] = (
    f'<p class="ind-head">On {datetime.date.today().strftime("%B")} {datetime.date.today().day}, {datetime.date.today().year}, {n(total)} people were in the custody of the New York City Department of Correction ({gtxt}).</p>'
    + source_line("Daily Inmates In Custody", f"https://data.cityofnewyork.us/d/{ID}", "the NYC Department of Correction", upd,
                  "The feed shows one day only and excludes sealed cases. Case Analytica records each day it reads the feed, so a daily series builds up from the first day it was recorded.")
    + tiles([(n(total), f"in custody on {TODAY}")] + [(n(v), k.lower()) for k, v in sorted(gender.items(), key=lambda kv: -kv[1])[:2]]))
regions["nyc-jail-bot"] = (
    '<details class="raw"><summary>The counts behind the chart</summary>'
    + table(["Age", "People in custody"], [[b["band"], n(b["count"])] for b in bands], f"People in NYC jails by age band on {TODAY}")
    + "</details>" + downloads("nyc-jail"))
catalog.append({"id": "nyc-jail", "name": "People in New York City jails, daily from the first recorded day",
                "description": "Count of people in NYC Department of Correction custody on the day it was read, by gender and age band. Sealed cases are excluded by the agency.",
                "temporal": f"{hist['days'][0]['date']}/{hist['days'][-1]['date']}", "source_url": f"https://data.cityofnewyork.us/d/{ID}", "publisher": "NYC Department of Correction"})

# ---------------------------------------------------------------- parole (from parole_snapshot.py output)
pj = json.loads((DATA / "parole-board-decisions.json").read_text())
Y = pj["yearly"]; last, first = Y[-1], Y[0]
tot = lambda r: r["approved"] + r["denied"] + r["postponed"]
regions["parole-top"] = (
    f'<p class="ind-head">In {last["year"]} the Board of Parole approved {n(last["approved"])} of its {n(tot(last))} first-interview decisions, or {last["approved"] / tot(last) * 100:.1f}%. '
    f'In {first["year"]} it was {first["approved"] / tot(first) * 100:.1f}%.</p>'
    + source_line("Parole Board Decisions for Initial Interviews by Crime Type: Beginning 2008", pj["source_url"], "the NYS Department of Corrections and Community Supervision", pj["source_last_updated"],
                  "First interviews only. These are not the Earned Eligibility Certificate denials the parole reporting project reads.")
    + tiles([(n(last["approved"]), f"approved in {last['year']}"), (n(last["denied"]), f"denied in {last['year']}"), (n(last["postponed"]), f"postponed in {last['year']}")]))
catalog.append({"id": "parole-board-decisions", "name": "New York Board of Parole first-interview decisions, 2008 to present",
                "description": "Approvals, denials and postponements at New York parole first interviews, by year and crime class, from NYS Department of Corrections and Community Supervision data.",
                "temporal": f"{first['year']}/{last['year']}", "source_url": pj["source_url"], "publisher": "NYS Department of Corrections and Community Supervision"})


# ---------------------------------------------------------------- homepage band (index.html, between ind:home-top markers)
RD = datetime.date.today().strftime("%b ") + str(datetime.date.today().day)
lastA, lastP, lastY = yearly[-1], py[-1], Y[-1]
home_items = [
    (n(lastA["total"]), f"people admitted to state prison in {lastA['year']}", "NYS Corrections", "data.html#prison-admissions"),
    (n(lastP["total"]), f"in state prison on March 31, {lastP['year']}", "NYS Corrections", "ny-prison-population.html"),
    (n(total), "in New York City jails today", "NYC Correction", "nyc-jail-population.html"),
    (f'{lastY["approved"] / tot(lastY) * 100:.1f}%', f"of first parole interviews approved in {lastY['year']}", "NYS Corrections", "data.html#parole"),
]
home = ('<section class="fp-nums" aria-labelledby="fp-nums-h">\n  <h2 class="fp-label" id="fp-nums-h">The numbers</h2>\n  <ul class="fp-nums-grid">\n'
        + "".join(f'    <li><a href="{u}"><span class="n">{esc(v)}</span><span class="l">{esc(l)}</span><span class="s">{esc(src)}, read {RD}</span></a></li>\n' for v, l, src, u in home_items)
        + '  </ul>\n  <p class="fp-more"><a href="data.html">All the data, with sources and downloads</a></p>\n</section>')

# ---------------------------------------------------------------- write the catalog and the page
write_json("catalog", {"title": "Case Analytica data catalog", "url": SITE + "data.html", "generated": TODAY, "indicators": catalog})

page = PAGE.read_text()
for rid, body in regions.items():
    pat = re.compile(rf"(<!-- ind:{re.escape(rid)}:begin -->).*?(<!-- ind:{re.escape(rid)}:end -->)", re.S)
    if not pat.search(page):
        raise SystemExit(f"marker pair missing in data.html: ind:{rid}")
    page = pat.sub(lambda m: m.group(1) + "\n" + body + "\n" + m.group(2), page)

ld = {"@context": "https://schema.org", "@type": "DataCatalog", "name": "Case Analytica data hub", "url": SITE + "data.html",
      "publisher": {"@type": "Organization", "name": "Case Analytica", "url": SITE},
      "dataset": [{
          "@type": "Dataset", "name": c["name"], "description": c["description"], "url": SITE + "data.html#" + c["id"],
          "creator": {"@type": "Organization", "name": c["publisher"]}, "isBasedOn": c["source_url"], "temporalCoverage": c["temporal"],
          "spatialCoverage": "New York", "dateModified": TODAY, "license": "https://creativecommons.org/licenses/by/4.0/" if False else None,
          "distribution": ([{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE}assets/data/csv/{c['id']}.csv"},
                            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}assets/data/{c['id']}.json"}]
                           if c["id"] != "parole-board-decisions" else
                           [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}assets/data/parole-board-decisions.json"}])}
          for c in catalog]}
for d in ld["dataset"]:
    d.pop("license", None)
blob = '<script type="application/ld+json">\n' + json.dumps(ld, indent=1) + "\n</script>"
page = re.sub(r"<!-- ld:begin -->.*?<!-- ld:end -->", lambda m: "<!-- ld:begin -->\n" + blob + "\n<!-- ld:end -->", page, flags=re.S)
PAGE.write_text(page)
INDEX = ROOT / "index.html"
if INDEX.exists():
    ix = INDEX.read_text()
    pat = re.compile(r"(<!-- ind:home-top:begin -->).*?(<!-- ind:home-top:end -->)", re.S)
    if pat.search(ix):
        INDEX.write_text(pat.sub(lambda m: m.group(1) + "\n" + home + "\n" + m.group(2), ix))
print("data.html and assets/data/* refreshed", TODAY)
import subprocess, sys
subprocess.run([sys.executable, str(ROOT / "tools" / "data_pages.py")], check=True)
for c in catalog:
    print(" -", c["id"], c["temporal"])
