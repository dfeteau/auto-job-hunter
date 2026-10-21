"""Find job boards for companies in config/companies.json that have none yet. Needs internet.
Usage: python3 collectors/find_boards.py [--limit N] [--dry-run] [--recheck]

For each company it builds several board-name guesses (joined, hyphenated, "and" for "&",
names in parentheses, shortened names) and tries Greenhouse, SmartRecruiters, Workable,
Lever and Ashby. Greenhouse and SmartRecruiters report the company's name, so those matches
are checked against yours. Workable matches also need at least one open job. Lever and Ashby do not, so their matches are
marked "unverified": open one of their job links once to confirm it is the right company.
Recruiters, staffing firms and aggregators are marked skip and never searched.
Workday is handled separately by find_workday.py.
"""
import re, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from common import get, norm_co

GH = "https://boards-api.greenhouse.io/v1/boards/{t}"
SR = "https://api.smartrecruiters.com/v1/companies/{t}/postings?limit=1"
WK = "https://apply.workable.com/api/v1/widget/accounts/{t}"
LEVER = "https://api.lever.co/v0/postings/{t}?mode=json&limit=1"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{t}"

SKIP_RE = re.compile(r"recruit|staffing|talent solutions|undisclosed|confidential|\(client|posted via|\bvia\b|"
                     r"jobgether|jobright|ladders|robert half|kforce|teksystems|insight global|randstad|adecco|"
                     r"manpower|aerotek|kelly services|hays\b", re.I)
SUFFIX = re.compile(r"\b(inc|llc|llp|lp|ltd|corp|corporation|co|company|companies|holdings?|group|the|pa|plc|"
                    r"incorporated|limited)\b\.?", re.I)
GENERIC = {"american", "national", "general", "united", "central", "first", "global", "allied", "international",
           "advanced", "digital", "software", "health", "data", "capital", "federal", "valley", "great", "north",
           "south", "east", "west", "new", "open", "smart", "progressive", "the"}

def words(name):
    n = SUFFIX.sub(" ", name.replace("&", " and ").replace("+", " and "))
    return [w.lower() for w in re.sub(r"[^A-Za-z0-9 ]", " ", n.replace(".", "")).split()]

def variants(company):
    """Board-name guesses as (name, loose). Loose guesses are accepted only where the company name can be checked."""
    base = re.sub(r"\(.*?\)", " ", company)
    parens = [p for p in re.findall(r"\((.*?)\)", company) if not SKIP_RE.search(p) and "formerly" not in p.lower()]
    out = []
    for src in [base] + parens:
        w = words(src)
        if not w: continue
        core = [x for x in w if x != "and"]
        out += [(x, False) for x in ("".join(core), "-".join(core), "".join(w), "-".join(w))]
        if len(core) > 2: out += [("".join(core[:2]), True), ("-".join(core[:2]), True)]
        if len(core) > 1 and core[0] not in GENERIC and len(core[0]) >= 4: out.append((core[0], True))
        out += [("".join(core) + "inc", False), ("".join(core) + "hq", False)]
    seen, res = set(), []
    for v, loose in out:
        if len(v.replace("-", "")) >= 4 and v not in seen: seen.add(v); res.append((v, loose))
    return res

def name_ok(ours, theirs):
    a, b = norm_co(ours), norm_co(theirs or "")
    return bool(a and b) and (a in b or b in a or a[:6] == b[:6])

def probe(company):
    for v, loose in variants(company):
        r = get(GH.format(t=v), tries=1, timeout=8); time.sleep(0.1)
        if isinstance(r, dict) and r.get("name") is not None and name_ok(company, r["name"]): return "greenhouse", v, "name ok"
        r = get(SR.format(t=v), tries=1, timeout=8); time.sleep(0.1)
        if isinstance(r, dict) and r.get("totalFound"):
            nm = ((r.get("content") or [{}])[0].get("company") or {}).get("name")
            if name_ok(company, nm): return "smartrecruiters", v, "name ok"
        r = get(WK.format(t=v), tries=1, timeout=8); time.sleep(0.1)
        # Workable answers with a name even for boards that don't exist, so require real job postings
        if isinstance(r, dict) and r.get("jobs") and name_ok(company, r.get("name")): return "workable", v, "has jobs"
        if loose: continue
        r = get(LEVER.format(t=v), tries=1, timeout=8); time.sleep(0.1)
        if isinstance(r, list) and r: return "lever", v, "unverified"
        r = get(ASHBY.format(t=v), tries=1, timeout=8); time.sleep(0.1)
        if isinstance(r, dict) and isinstance(r.get("jobs"), list) and r["jobs"]: return "ashby", v, "unverified"
    return None, None, None

def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    dry, recheck = "--dry-run" in sys.argv, "--recheck" in sys.argv
    data = common.load("companies.json")
    todo, skipped = [], 0
    for c in data["companies"]:
        if c.get("ats") or (c.get("probed") and not recheck): continue
        if SKIP_RE.search(c["company"]):
            c["skip"] = "recruiter/aggregator"; skipped += 1; continue
        todo.append(c)
    if limit: todo = todo[:limit]
    print(f"marked skip: {skipped} | to search: {len(todo)}", flush=True)
    if dry:
        for c in todo[:15]: print(f"  {c['company']}: {[v for v, _ in variants(c['company'])]}")
        return
    found = 0
    for i, c in enumerate(todo, 1):
        ats, tok, check = probe(c["company"])
        c["probed"] = True
        if ats:
            c.update(ats=ats, token=tok, match_check=check); found += 1
            print(f"  + {c['company']} -> {ats}:{tok} ({check})", flush=True)
        if i % 20 == 0:
            common.save("companies.json", data); print(f"  ...{i}/{len(todo)} searched, {found} found", flush=True)
    common.save("companies.json", data)
    total = sum(1 for c in data["companies"] if c.get("ats"))
    print(f"new boards found: {found} | companies with a board: {total} of {len(data['companies'])}")

if __name__ == "__main__":
    main()
