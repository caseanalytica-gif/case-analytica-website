#!/usr/bin/env python3
"""Refresh parole-board-decisions.html from NY Open Data.

Pulls the Board of Parole initial-interview decisions (data.ny.gov cgk2-twzc),
writes assets/data/parole-board-decisions.json, and rewrites the two generated
regions of parole-board-decisions.html (between <!-- data-top:begin --> and
<!-- data-bottom:end -->), so the figures are in the HTML for crawlers and for
readers without JavaScript. The charts read the JSON in the browser.

Run from the repo root:  python3 tools/parole_snapshot.py
Then look at the page and commit both files. The source is only re-read when
this is run, so the page's "Read" date is the date of the last run.
"""
import json, datetime, urllib.parse, urllib.request, collections, pathlib, re, html

ID = "cgk2-twzc"
BASE = f"https://data.ny.gov/resource/{ID}.json"
META = f"https://data.ny.gov/api/views/{ID}.json"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "parole-board-decisions.json"
PAGE = ROOT / "parole-board-decisions.html"

def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)

rows = get(f"{BASE}?" + urllib.parse.urlencode({
    "$select": "year,month_code,decision,crime,count(*)",
    "$group": "year,month_code,decision,crime", "$limit": "100000"}))
meta = get(META)

FOLD = {"APPROVED": "approved", "DENIED": "denied", "POSTPONED": "postponed", "POSPONED": "postponed"}
raw = collections.Counter(); total = 0
yearly = collections.defaultdict(collections.Counter)
bycrime = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for r in rows:
    n = int(r["count"]); total += n; raw[r["decision"]] += n
    d = FOLD[r["decision"].upper()]; y = int(r["year"])
    yearly[y][d] += n; bycrime[y][r["crime"]][d] += n
years = sorted(yearly); ly = years[-1]
K = ("approved", "denied", "postponed")
today = datetime.date.today().isoformat()
updated = datetime.datetime.fromtimestamp(meta["rowsUpdatedAt"], datetime.timezone.utc).strftime("%Y-%m-%d")
population = ("Initial parole-board interviews only, by calendar year of the decision. "
              "Not reappearances, and not limited to Earned Eligibility Certificate holders.")

data = {
  "title": "New York Board of Parole: initial-interview decisions",
  "source": "NYS Department of Corrections and Community Supervision, via NY Open Data",
  "source_url": f"https://data.ny.gov/d/{ID}", "dataset_id": ID,
  "source_last_updated": updated, "retrieved": today, "population": population,
  "rows_counted": total, "folded_values": dict(sorted(raw.items())),
  "yearly": [{"year": y, **{k: yearly[y][k] for k in K}} for y in years],
  "by_crime_latest_year": {"year": ly, "rows": sorted(
      [{"crime": c, **{d: v[d] for d in K}} for c, v in bycrime[ly].items()],
      key=lambda r: -sum(r[d] for d in K))},
}
OUT.write_text(json.dumps(data, indent=1) + "\n")

f = lambda n: f"{n:,}"
e = html.escape
L = yearly[ly]; lt = sum(L[k] for k in K)
tiles = [(f(lt), f"initial-interview decisions in {ly}"), (f(L["approved"]), f"approved in {ly}"),
         (f(L["denied"]), f"denied in {ly}"), (f"{L['approved']/lt*100:.1f}%", f"of {ly} decisions were approvals")]
F = yearly[years[0]]; ft = sum(F[k] for k in K)
top = (f'<p style="font-size:17px;color:var(--ink-soft);margin:0 0 10px;">In {ly} the Board of Parole approved {f(L["approved"])} of its {f(lt)} first-interview decisions, or {L["approved"]/lt*100:.1f}%. '
       f'In {years[0]} it was {F["approved"]/ft*100:.1f}%. These charts show every year in between, taken from the state\u2019s own published data.</p>\n'
       f'    <p class="dir-caveat">The agency last updated this data on {updated}. Case Analytica read it on {today}. The figures stop at the end of {ly}.</p>\n'
       '    <div class="dash-tiles">\n' + "\n".join(
         f'      <div class="tile"><div class="n">{e(n)}</div><div class="l">{e(l)}</div></div>' for n, l in tiles) + "\n    </div>")
tb = "".join(f'<tr><td>{y}</td><td>{f(yearly[y]["approved"])}</td><td>{f(yearly[y]["denied"])}</td><td>{f(yearly[y]["postponed"])}</td><td>{f(sum(yearly[y][k] for k in K))}</td></tr>' for y in reversed(years))
bottom = ('<details class="raw"><summary>The counts behind the charts</summary>\n'
  '    <table class="dt"><thead><tr><th>Year</th><th>Approved</th><th>Denied</th><th>Postponed</th><th>Total</th></tr></thead><tbody>' + tb + '</tbody></table>\n    </details>\n'
  '    <h2>What this does not show</h2>\n'
  '    <p>These are first-interview decisions only. They are not the Earned Eligibility Certificate denials this project reads (402 between October 2025 and March 2026, by the state prison system’s own count), and they say nothing about the reasons the Board gave. That count comes from a different source and is a different measure, so the two are not combined here.</p>\n'
  '    <h2>Source and method</h2>\n'
  f'    <p>Data: <a href="https://data.ny.gov/d/{ID}" target="_blank" rel="noopener">Parole Board Decisions for Initial Interviews by Crime Type: Beginning 2008</a>, published by the NYS Department of Corrections and Community Supervision on NY Open Data. {f(total)} decisions counted. {e(population)} '
  f'The source records the decision in mixed upper and lower case, and spells “postponed” as “POSPONED” in {f(raw["POSPONED"])} rows. Case Analytica counted those with the matching decisions and changed nothing else. The approval share is Case Analytica’s division of approved decisions by all decisions that year, and the source does not publish it. Cite the source, not this page.</p>\n'
  '    <p>Case Analytica refreshes this page by re-reading the source, not continuously. The date above is the only claim about how current it is. See <a href="parole-data.html">how the parole data record is kept</a>.</p>')

s = PAGE.read_text()
for name, body in (("top", top), ("bottom", bottom)):
    s, n = re.subn(rf"(<!-- data-{name}:begin -->).*?(<!-- data-{name}:end -->)", lambda m: f"{m.group(1)}\n    {body}\n    {m.group(2)}", s, flags=re.S)
    assert n == 1, name
PAGE.write_text(s)
print("ok", total, years[0], ly, today)
