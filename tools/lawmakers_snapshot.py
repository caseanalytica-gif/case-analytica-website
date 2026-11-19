#!/usr/bin/env python3
"""Refresh the NYS lawmakers tracker (lawmakers.html) from the NY Senate's Open Legislation API.

What it reads, per tracked bill, in both houses: the sponsor, the cosponsors of the active version,
the same-as bill in the other house, the status and its date, and the Senate committee and floor
roll calls member by member. The API carries NO Assembly floor votes, so none are shown.
Nothing here rates or ranks a lawmaker. The tracker states facts and links to the official bill page.

  python3 tools/lawmakers_snapshot.py --candidates   print the bills the topic rules find (no files written)
  python3 tools/lawmakers_snapshot.py --links       refresh the official member page links and Assembly emails only
  python3 tools/lawmakers_snapshot.py --page-only   rewrite the static list in lawmakers.html from the saved JSON
  python3 tools/lawmakers_snapshot.py               read every tracked bill and write assets/data/lawmakers/*.json

The API key is read from the NYSENATE_API_KEY environment variable, or from the file named in
NYSENATE_API_KEY_FILE, or from ../Project Notes/Private/nysenate-api-key.txt. It must never be committed.
The API allows 10 requests a second and 4 at once; this script makes one request at a time with a pause.
Standard library only (no node, no pip).
"""
import json, os, re, sys, time, unicodedata, pathlib, datetime, urllib.request, urllib.parse, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "data" / "lawmakers"
API = "https://legislation.nysenate.gov/api/3/"
YEAR = 2025          # the 2025-2026 legislative session

# ---- Which bills are tracked (the criteria are printed on the page, "How it works") -------------
# A bill is a candidate when its title matches a topic Case Analytica covers AND it is in a
# criminal-justice committee in either house. A candidate is tracked when it has at least
# MIN_SUPPORT sponsors and cosponsors in total, or has moved past committee, or has a recorded
# Senate floor vote. Bills are paired with their same-as bill in the other house and shown once.
TOPICS = {
    "parole": 'title:(parole* OR clemency OR "board of parole")',
    "sentencing": 'title:(sentenc* OR resentenc* OR "second look" OR "earned time" OR "merit time" OR "good time" OR "time allowance*")',
    "sealing": 'title:(seal* OR "clean slate" OR expung* OR "criminal record*")',
    "prisons": 'title:("correctional facilit*" OR incarcerat* OR "state prison*" OR "solitary" OR "segregat*" OR "correction law")',
    "jails": 'title:("local correctional" OR jail* OR "rikers")',
    "bail": 'title:(bail OR pretrial OR "securing order*" OR "release on recognizance")',
    "reentry": 'title:(reentry OR re-entry OR "reentering")',
}
TOPIC_LABELS = {
    "parole": "Parole and clemency", "sentencing": "Sentencing and time served",
    "sealing": "Record sealing", "prisons": "Prisons and conditions",
    "jails": "Jails", "bail": "Bail and pretrial", "reentry": "Reentry",
}
CJ_COMMITTEES = ("Crime Victims, Crime And Correction", "Codes", "Correction", "Judiciary",
                 "Crime Victims, Crime and Correction")
MIN_SUPPORT = 15
BEYOND_COMMITTEE = {"PASSED_SENATE", "PASSED_ASSEMBLY", "DELIVERED_TO_GOV", "SIGNED_BY_GOV", "VETOED",
                    "SENATE_FLOOR", "ASSEMBLY_FLOOR"}
DEAD = {"STRICKEN", "SUBSTITUTED"}   # replaced by or merged into another bill: not tracked
# Candidates the rules find that are off topic (the title matched a word, the bill is not about our topics).
# Each entry needs a reason. Add by bill number, either house.
EXCLUDE = {
    "A659": "landlord rent information, matched a word in the title",
    "S450": "landlord rent information, matched a word in the title",
    "S9650": "landlord rent information, matched a word in the title",
    "S866": "defines 'physically helpless' in the sex offense law, matched a word in the title",
    "A2629": "professional discipline reporting for physicians, not the criminal process",
}
# Bills Dean or the editor adds by hand (bill number, either house), each with the reason it is tracked.
INCLUDE = {}

_last = [0.0]


def key():
    k = os.environ.get("NYSENATE_API_KEY")
    if k:
        return k.strip()
    p = os.environ.get("NYSENATE_API_KEY_FILE") or str(ROOT.parent / "Project Notes" / "Private" / "nysenate-api-key.txt")
    return pathlib.Path(p).read_text().strip()


def get(path, **params):
    params["key"] = key()
    wait = 0.4 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CaseAnalyticaLawmakers/1.0)", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                _last[0] = time.time()
                return json.load(r)
        except urllib.error.HTTPError as e:
            print("HTTP %s on %s %s" % (e.code, path, {k: v for k, v in params.items() if k != "key"}), file=sys.stderr)
            if e.code in (401, 429, 503) and attempt < 5:
                time.sleep(min(30, 5 * 2 ** attempt) if e.code == 401 else 2 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")


SEEN = {}   # memberId -> member record, filled from every bill so the roll is complete


def member(m):
    """Return the member's id; remember the record. Bills refer to members by id to keep the JSON small."""
    SEEN[m["memberId"]] = {"id": m["memberId"], "name": m["fullName"], "short": m.get("shortName") or "",
                           "chamber": m["chamber"], "district": m["districtCode"], "alternate": m.get("alternate", False),
                           "incumbent": m.get("incumbent", True)}
    return m["memberId"]


def base_of(print_no):
    """A8840A -> A8840: one key per bill, whatever version letter the source shows."""
    m = re.match(r"^[SA]\d+", print_no)
    return m.group(0) if m else print_no      # resolutions (J, K, E...) keep their own number


def search_topic(topic, term):
    found = {}
    offset = 1
    while True:
        d = get("bills/%d/search" % YEAR, term=term, limit=100, offset=offset)
        items = d["result"]["items"]
        for it in items:
            r = it["result"]
            found[base_of(r["basePrintNo"]["printNo"] if isinstance(r.get("basePrintNo"), dict) else r["printNo"])] = r
        if offset + len(items) > d["total"] or not items:
            break
        offset += len(items)
    return found


def committee_ok(r):
    c = (r.get("status") or {}).get("committeeName") or ""
    return any(c.lower() == x.lower() for x in CJ_COMMITTEES)


FAILED = []


def detail(print_no):
    """One bill's record, or None when the API keeps refusing it (logged and listed at the end).
    The service sometimes answers HTTP 401 to a valid key for a single bill, then accepts the same call later,
    so a refused bill is retried in three rounds with a pause before it is given up."""
    last = None
    for rnd in range(3):
        try:
            return get("bills/%d/%s" % (YEAR, print_no))["result"]
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 401:
                break
            time.sleep(20 * (rnd + 1))
    FAILED.append("%s (HTTP %s)" % (print_no, last.code if last else "?"))
    return None


def candidates():
    """Return {basePrintNo: set(topics)} for bills whose title matches a topic and that sit in or came through a CJ committee."""
    out = {}
    for topic, term in TOPICS.items():
        for pn, r in search_topic(topic, term).items():
            pcs = [c.get("committeeName", "") for c in (r.get("pastCommittees", {}) or {}).get("items", [])] if isinstance(r.get("pastCommittees"), dict) else []
            in_cj = committee_ok(r) or any(any(c.lower() == x.lower() for x in CJ_COMMITTEES) for c in pcs)
            if in_cj or r["status"]["statusType"] in BEYOND_COMMITTEE:
                out.setdefault(pn, {"topics": set(), "r": r})["topics"].add(topic)
    return out


def assembly_url(base):
    """The Assembly's own bill page: chamber letter plus the number padded to five digits."""
    letter, num = base[0], base[1:]
    return ("https://nyassembly.gov/leg/?default_fld=&leg_video=&bn=%s%s&term=%d&Summary=Y&Actions=Y&Votes=Y"
            % (letter, num.zfill(5), YEAR))


def build_bill(d):
    av = d["activeVersion"]
    am = d["amendments"]["items"][av]
    co = [member(m) for m in am["coSponsors"]["items"]]
    multi = [member(m) for m in am["multiSponsors"]["items"]]
    sp = d["sponsor"].get("member")
    votes = []
    for v in d["votes"]["items"]:
        mv = {}
        for code, grp in v.get("memberVotes", {}).get("items", {}).items():
            mv[code] = [m["memberId"] for m in grp["items"]]
        votes.append({"date": v["voteDate"], "type": v["voteType"], "version": v.get("version") or "",
                      "committee": (v.get("committee") or {}).get("name"), "counts": {k: len(x) for k, x in mv.items()},
                      "members": mv})
    return {
        "printNo": d["printNo"], "base": d["basePrintNo"], "chamber": d["billType"]["chamber"],
        "version": av, "title": d["title"], "summary": d.get("summary") or "",
        "sponsor": member(sp) if sp else None, "coSponsors": co, "multiSponsors": multi,
        "sameAs": [x["printNo"] for x in am["sameAs"]["items"]],
        "status": d["status"]["statusDesc"], "statusType": d["status"]["statusType"],
        "statusDate": d["status"]["actionDate"], "committee": d["status"].get("committeeName"),
        "votes": votes,
        "url": ("https://www.nysenate.gov/legislation/bills/%d/%s" % (YEAR, d["basePrintNo"])),
        "assemblyUrl": assembly_url(d["basePrintNo"]),
    }


def esc(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def update_page(groups, roll, stamp):
    """Write the plain-HTML list of tracked bills between <!-- lm:begin --> and <!-- lm:end --> in lawmakers.html,
    so search engines and readers without JavaScript see the bills. The page's script replaces it with the interactive view."""
    page = ROOT / "lawmakers.html"
    if not page.exists():
        return
    rows = []
    for g in sorted(groups, key=lambda g: max(b["statusDate"] for b in g["bills"]), reverse=True):
        b0 = g["bills"][0]
        nums = " and ".join('<a href="%s" rel="noopener">%s</a>' % (esc(b["url"]), esc(b["printNo"])) for b in g["bills"])
        sp = "; ".join("%s (%s)" % (esc(roll[b["sponsor"]]["name"]), b["chamber"].title()) for b in g["bills"] if b["sponsor"])
        st = "; ".join("%s: %s, %s" % (b["printNo"], esc(b["status"]), b["statusDate"]) for b in g["bills"])
        rows.append("<li><strong>%s</strong> (%s). Sponsor: %s. Status: %s.</li>" % (esc(b0["title"]), nums, sp or "none listed", st))
    html = "<!-- lm:begin -->\n<p>Bills tracked in the 2025-2026 session, newest official action first. Read %s.</p>\n<ol class=\"lm-static\">\n%s\n</ol>\n<!-- lm:end -->" % (stamp, "\n".join(rows))
    t = page.read_text(encoding="utf-8")
    a, z = t.find("<!-- lm:begin -->"), t.find("<!-- lm:end -->")
    if a < 0 or z < 0:
        return
    page.write_text(t[:a] + html + t[z + len("<!-- lm:end -->"):], encoding="utf-8")


def build_links(roll):
    """Official page for every member: Senate pages from tools/senate_links.json (nysenate.gov blocks scripts, so that
    list is read in a browser), Assembly pages and published email addresses from nyassembly.gov/mem/?sh=email.
    Written to assets/data/lawmakers/official-links.json. Names are checked against the session roll."""
    sen = json.loads((ROOT / "tools" / "senate_links.json").read_text(encoding="utf-8"))
    req = urllib.request.Request("https://nyassembly.gov/mem/?sh=email", headers={"User-Agent": "Mozilla/5.0 (compatible; CaseAnalyticaLawmakers/1.0)"})
    html_text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "ignore")
    asm = {}
    for m in re.finditer(r'<li><a href="/mem/([^"?#/]+)">\s*([^<]+?)\s*</a>\s*<div class="email2">(\d+)(?:st|nd|rd|th) District</div>\s*<a href="mailto:([^"]+)">', html_text):
        slug, name, d, mail = m.groups()
        asm[d] = {"slug": slug, "name": name.replace("&amp;", "&"), "email": mail}
    by_dist = {"SENATE": {}, "ASSEMBLY": {}}
    for r in roll.values():
        if r.get("incumbent", True) and not r.get("alternate"):
            by_dist[r["chamber"]][str(r["district"])] = r
    warn = []
    def last(n):
        n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z]", "", n.split(",")[0].replace(" jr.", "").replace(" jr", "").split()[-1])
    for d, r in by_dist["SENATE"].items():
        if d not in sen["senate"]:
            warn.append("no Senate page for district %s (%s)" % (d, r["name"]))
        elif last(r["name"]) not in sen["senate"][d].replace("-", ""):
            warn.append("Senate district %s: roll says %s, page slug %s" % (d, r["name"], sen["senate"][d]))
    for d, r in by_dist["ASSEMBLY"].items():
        if d not in asm:
            warn.append("no Assembly page for district %s (%s)" % (d, r["name"]))
        elif last(r["name"]) != last(asm[d]["name"]):
            warn.append("Assembly district %s: roll says %s, directory says %s" % (d, r["name"], asm[d]["name"]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "official-links.json").write_text(json.dumps({
        "read": datetime.date.today().isoformat(), "senateRead": sen["read"],
        "senate": sen["senate"], "assembly": asm}, separators=(",", ":")))
    for w in warn:
        print("LINK CHECK: " + w, file=sys.stderr)
    print("official links: %d Senate, %d Assembly, %d warnings" % (len(sen["senate"]), len(asm), len(warn)), file=sys.stderr)


def page_only():
    """Rewrite the static list in lawmakers.html from the JSON already on disk (no API calls)."""
    b = json.loads((OUT / "bills.json").read_text(encoding="utf-8"))
    m = json.loads((OUT / "members.json").read_text(encoding="utf-8"))
    update_page(b["groups"], {x["id"]: x for x in m["members"]}, b["read"])


def main():
    if "--page-only" in sys.argv:
        return page_only()
    if "--links" in sys.argv:
        m = json.loads((OUT / "members.json").read_text(encoding="utf-8"))
        return build_links({x["id"]: x for x in m["members"]})
    only_candidates = "--candidates" in sys.argv
    cands = candidates()
    for pn in INCLUDE:
        cands.setdefault(pn, {"topics": set(), "r": None})
    print("candidates", len(cands), file=sys.stderr)
    bills = {}
    for pn in sorted(cands):
        if pn in EXCLUDE:
            continue
        d = detail(pn)
        if d is None or d["status"]["statusType"] in DEAD:
            continue
        b = build_bill(d)
        if b["base"] in bills:                       # already read under another key: merge topics, do not duplicate
            bills[b["base"]]["topics"] = sorted(set(bills[b["base"]]["topics"]) | cands[pn]["topics"])
            continue
        b["topics"] = sorted(cands[pn]["topics"])
        support = (1 if b["sponsor"] else 0) + len(b["coSponsors"]) + len(b["multiSponsors"])
        b["support"] = support
        has_floor = any(v["type"] == "FLOOR" for v in b["votes"])
        keep = support >= MIN_SUPPORT or b["statusType"] in BEYOND_COMMITTEE or has_floor or pn in INCLUDE
        if only_candidates:
            print("%s %-8s %-3d %-22s %-5s %s | %s" % ("KEEP" if keep else "skip", pn, support, b["statusType"][:22],
                  ",".join(b["topics"])[:5], b["title"][:70], b["committee"] or ""))
            continue
        if keep:
            bills[b["base"]] = b
    if only_candidates:
        return
    # fetch the same-as bill in the other house for every tracked bill, so each entry shows both houses
    for pn in list(bills):
        for x in bills[pn]["sameAs"]:
            base = base_of(x)
            if base in bills or x in bills or base in EXCLUDE:
                continue
            d = detail(base)
            if d is None or d["status"]["statusType"] in DEAD:
                continue
            m = build_bill(d)
            m["topics"] = list(bills[pn]["topics"])
            m["support"] = (1 if m["sponsor"] else 0) + len(m["coSponsors"]) + len(m["multiSponsors"])
            bills[base] = m
    # group a bill with every same-as bill in the other house (connected through same-as links), shown once
    parent = {k: k for k in bills}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for pn, b in bills.items():
        for x in b["sameAs"]:
            bx = base_of(x)
            if bx in bills:
                parent[find(bx)] = find(pn)
    comps = {}
    for pn in bills:
        comps.setdefault(find(pn), []).append(bills[pn])
    groups = []
    for members_of in comps.values():
        members_of.sort(key=lambda x: (x["chamber"] != "SENATE", x["base"]))
        groups.append({"id": "-".join(sorted((x["base"] for x in members_of), key=lambda z: (z[0] != "A", int(re.sub(r"\D", "", z) or 0)))),
                       "topics": sorted(set(t for x in members_of for t in x["topics"])), "bills": members_of})
    groups.sort(key=lambda g: g["id"])
    # tracked-bill members, plus the whole roll of the session so "no record" can be read
    roll = {}
    off = 1
    while True:
        d = get("members/%d" % YEAR, full="true", limit=100, offset=off)
        for m in d["result"]["items"]:
            roll[m["memberId"]] = {"id": m["memberId"], "name": m["fullName"], "short": m.get("shortName") or "",
                                   "chamber": m["chamber"], "district": m["districtCode"], "alternate": m["alternate"],
                                   "incumbent": m.get("incumbent", True)}
        if off + len(d["result"]["items"]) > d["total"] or not d["result"]["items"]:
            break
        off += len(d["result"]["items"])
    for mid, rec in SEEN.items():          # anyone named on a tracked bill but missing from the roll
        roll.setdefault(mid, rec)
    for x in groups:
        for b in x["bills"]:
            ids = [b["sponsor"]] + b["coSponsors"] + b["multiSponsors"]
            for v in b["votes"]:
                for grp in v["members"].values():
                    ids += grp
            for i in ids:
                if i is not None and i not in roll:
                    raise SystemExit("member %s on %s is missing from the roll" % (i, b["printNo"]))
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    (OUT / "bills.json").write_text(json.dumps({"read": stamp, "session": "2025-2026", "topics": TOPIC_LABELS,
                                                "minSupport": MIN_SUPPORT, "excluded": EXCLUDE,
                                                "committees": ["Crime Victims, Crime and Correction", "Codes", "Correction", "Judiciary"],
                                                "groups": groups}, ensure_ascii=False, separators=(",", ":")))
    (OUT / "members.json").write_text(json.dumps({"read": stamp, "members": list(roll.values())}, ensure_ascii=False, separators=(",", ":")))
    build_links(roll)
    update_page(groups, roll, stamp)
    if FAILED:
        print("WARNING: could not read these bills, so they are missing or unpaired: " + ", ".join(FAILED), file=sys.stderr)
    print("wrote %d bill groups (%d bills), %d members" % (len(groups), sum(len(g["bills"]) for g in groups), len(roll)), file=sys.stderr)


if __name__ == "__main__":
    main()
