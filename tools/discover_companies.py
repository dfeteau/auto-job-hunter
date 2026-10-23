"""Find companies you've never heard of: every Greenhouse, Lever and Ashby job board that has a job matching your
titles right now. Needs internet. Good for a first run when your company list is short, then about once a month.
Usage: python3 tools/discover_companies.py                  (find boards, check them, add the matches)
       python3 tools/discover_companies.py --dry-run        (check and report, but don't change companies.json)
Options: --crawls N         how many recent Common Crawl snapshots to read (default 2)
         --max-pages N      read at most N index pages per site and snapshot (a quicker, partial first run)
         --skip-crawl       only check boards already found by an earlier run
         --sites LIST       comma-separated, from greenhouse,lever,ashby (default all three)
         --limit N          check at most N boards this run
         --workers N        boards checked at the same time (default 8)
         --recheck-days N   check again boards that had no match more than N days ago (default 30)

How it works:
1. Board discovery. Common Crawl (commoncrawl.org) is a free public archive of the web. Its index lists every
   page it saved from boards.greenhouse.io, job-boards.greenhouse.io, jobs.lever.co and jobs.ashbyhq.com, and
   each address contains the company's board name. This is the slow part (the index is large), and it picks
   up where it left off if you stop it with Ctrl+C.
2. Live check. Each new board's current job list is read once. A board counts as a match when at least one job
   passes your title, excluded-title, location and industry rules in config/profile.json.
3. Matching companies are added to config/companies.json with their board, so collect.py searches them daily.
   Lever and Ashby don't report a company name, so those are named from the board name and marked
   "unverified": open one job link to confirm.

Progress is saved in data/discovery/boards.json (not uploaded to git). Boards without a match are checked again
after --recheck-days, so a monthly run picks up companies that start hiring for your titles.
"""
import concurrent.futures, datetime, json, re, sys, time, pathlib, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
try:
    import common
except FileNotFoundError:
    sys.exit("No config/profile.json yet. Run python3 setup_wizard.py first, so discovery knows which titles to look for.")
from common import norm_co, classify, UA
from find_boards import SKIP_RE

STATE = common.ROOT / "data" / "discovery" / "boards.json"
COLLINFO = "https://index.commoncrawl.org/collinfo.json"
HOSTS = {"greenhouse": ["boards.greenhouse.io", "job-boards.greenhouse.io"],
         "lever": ["jobs.lever.co"], "ashby": ["jobs.ashbyhq.com"]}
NOT_BOARDS = {"", "embed", "v1", "jobs", "api", "favicon.ico", "robots.txt", "sitemap.xml", "static", "assets",
              "_next", "careers", "search", "login", "privacy", "terms", "cdn-cgi", "js", "css", "images"}
TOKEN = re.compile(r"^[a-z0-9][a-z0-9._ -]{1,79}$", re.I)   # Ashby board names can contain spaces
LISTING = {"greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs",
           "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
           "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}"}
GH_NAME = "https://boards-api.greenhouse.io/v1/boards/{t}"

def opt(name, default=None, cast=int):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default

# ---------- network (kept small so tests can replace them) ----------

def fetch_text(url, tries=5, timeout=60):
    """Text of a URL, waiting and retrying when the server is busy. None if it can't be read."""
    req = urllib.request.Request(url, headers=UA)
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            if e.code in (429, 500, 502, 503, 504): time.sleep(10 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def fetch_json(url):
    return common.get(url, tries=2, timeout=20)

# ---------- step 1: find boards in the Common Crawl index ----------

def recent_crawls(n):
    txt = fetch_text(COLLINFO)
    if not txt: sys.exit("Couldn't reach the Common Crawl index (index.commoncrawl.org). Check your internet and try again.")
    crawls = sorted(json.loads(txt), key=lambda c: c["id"], reverse=True)
    return [(c["id"], c["cdx-api"]) for c in crawls[:n]]

def board_token(ats, url):
    """The board name in a job-board address, or None. Lowercase, except Ashby, which keeps its spelling."""
    p = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    seg = [s for s in p.path.split("/") if s]
    first = urllib.parse.unquote(seg[0]).strip() if seg else ""
    if ats != "ashby": first = first.lower()
    if ats == "greenhouse" and first == "embed":
        q = urllib.parse.parse_qs(p.query)
        first = (q.get("for") or [""])[0].strip().lower()
    if first.lower() in NOT_BOARDS or not TOKEN.match(first): return None
    return first

def crawl_boards(state, crawls, sites, max_pages):
    boards = state["boards"]
    for crawl_id, api in crawls:
        for ats in sites:
            for host in HOSTS[ats]:
                key = f"{crawl_id}|{host}"
                done = state["pages_done"].setdefault(key, [])
                base = f"{api}?url={host}/*&output=json&fl=url"
                info = fetch_text(base + "&showNumPages=true")
                try:
                    pages = int(json.loads(info)["pages"])
                except Exception:
                    print(f"  {crawl_id} {host}: index not available right now, skipped", flush=True); continue
                todo = [p for p in range(pages) if p not in done][: (max_pages or pages)]
                if not todo:
                    print(f"  {crawl_id} {host}: " + (f"already read ({pages} pages)" if pages else "nothing indexed"),
                          flush=True); continue
                print(f"  {crawl_id} {host}: reading {len(todo)} of {pages} index pages", flush=True)
                for n, page in enumerate(todo, 1):
                    txt = fetch_text(f"{base}&page={page}")
                    if txt is None:
                        print(f"    page {page}: couldn't be read, will retry next run", flush=True); continue
                    new, seen_lower = 0, {k.lower() for k in boards}
                    for line in txt.splitlines():
                        try: url = json.loads(line)["url"]
                        except Exception: continue
                        tok = board_token(ats, url)
                        if tok and f"{ats}:{tok}" not in boards and f"{ats}:{tok}".lower() not in seen_lower:
                            boards[f"{ats}:{tok}"] = {"found": datetime.date.today().isoformat()}; new += 1
                            seen_lower.add(f"{ats}:{tok}".lower())
                    done.append(page)
                    print(f"    page {n}/{len(todo)}: new boards {new}, total {len(boards)}", flush=True)
                    save_state(state)
                    time.sleep(1)   # be gentle with Common Crawl's free index

# ---------- step 2: check each board's current jobs ----------

def listing(ats, token):
    """(title, location, workplace) for every open job, or None if the board doesn't exist."""
    res = fetch_json(LISTING[ats].format(t=urllib.parse.quote(token)))
    if ats == "greenhouse":
        if not isinstance(res, dict) or "jobs" not in res: return None
        return [(j.get("title", ""), (j.get("location") or {}).get("name", ""), "") for j in res["jobs"]]
    if ats == "lever":
        if not isinstance(res, list): return None
        return [(j.get("text", ""), (j.get("categories") or {}).get("location") or "", j.get("workplaceType") or "")
                for j in res]
    if not isinstance(res, dict) or not isinstance(res.get("jobs"), list): return None
    return [(j.get("title", ""), j.get("location") or "",
             j.get("workplaceType") or ("Remote" if j.get("isRemote") else "")) for j in res["jobs"]]

def matching(flt, jobs):
    out = []
    for title, loc, wt in jobs:
        title = " ".join((title or "").split())
        if not flt.title_match(title) or flt.title_excluded(title): continue
        if flt.industry and flt.industry.search(title): continue
        if not flt.location_ok(classify(loc, "", wt)): continue
        out.append(title)
    return out

def check(flt, key):
    ats, token = key.split(":", 1)
    try:
        jobs = listing(ats, token)
    except Exception:
        jobs = None
    if jobs is None: return key, {"status": "gone"}
    m = matching(flt, jobs)
    return key, {"status": "match" if m else "no match", "open_jobs": len(jobs), "matches": len(m), "titles": m[:3]}

def board_name(ats, token):
    if ats == "greenhouse":
        r = fetch_json(GH_NAME.format(t=urllib.parse.quote(token)))
        if isinstance(r, dict) and r.get("name"): return r["name"].strip(), "name ok"
    pretty = " ".join(w.capitalize() for w in re.split(r"[-_.\s]+", token) if w)
    return pretty, "unverified"

# ---------- saving ----------

def load_state():
    if STATE.exists(): return json.loads(STATE.read_text())
    return {"boards": {}, "pages_done": {}}

def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp"); tmp.write_text(json.dumps(state)); tmp.replace(STATE)

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]): sys.exit(__doc__)
    dry = "--dry-run" in sys.argv
    sites = [s.strip() for s in opt("--sites", "greenhouse,lever,ashby", str).split(",") if s.strip() in HOSTS]
    recheck = opt("--recheck-days", 30); today = datetime.date.today()
    state = load_state()
    data = common.load("companies.json")
    known = {f"{c['ats']}:{str(c['token']).lower()}" for c in data["companies"] if c.get("ats") and c.get("token")}
    flt = common.Filter()

    try:
        if "--skip-crawl" not in sys.argv:
            print("Step 1 of 3: finding job boards in the Common Crawl index (slow the first time; Ctrl+C is safe)",
                  flush=True)
            crawl_boards(state, recent_crawls(opt("--crawls", 2)), sites, opt("--max-pages"))
        boards = state["boards"]

        def due(key, b):
            if key.lower() in known or key.split(":")[0] not in sites: return False
            if not b.get("checked"): return True
            if b.get("status") == "match": return False      # already offered; added unless excluded
            age = (today - datetime.date.fromisoformat(b["checked"])).days
            return age >= recheck
        todo = [k for k, b in boards.items() if due(k, b)]
        if opt("--limit"): todo = todo[:opt("--limit")]
        print(f"\nStep 2 of 3: checking {len(todo)} boards for jobs that match your titles "
              f"({len(boards)} found so far, {len(known)} already on your list)", flush=True)
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=opt("--workers", 8)) as pool:
            for key, res in pool.map(lambda k: check(flt, k), todo):
                boards[key].update(res, checked=today.isoformat()); done += 1
                if res["status"] == "match":
                    print(f"  + {key}: {res['matches']} matching ({'; '.join(res['titles'])})", flush=True)
                if done % 100 == 0:
                    save_state(state); print(f"  ...{done}/{len(todo)} checked", flush=True)
        save_state(state)
    except KeyboardInterrupt:
        save_state(state)
        sys.exit("\nStopped. Progress is saved; run the same command again to continue.")

    print("\nStep 3 of 3: adding companies with matching jobs", flush=True)
    have = {norm_co(c["company"]): c for c in data["companies"]}
    added, filled, skipped = [], [], []
    for key, b in sorted(state["boards"].items(), key=lambda kv: -kv[1].get("matches", 0)):
        if b.get("status") != "match" or key.lower() in known or key.split(":")[0] not in sites or b.get("added"): continue
        ats, token = key.split(":", 1)
        name, check_note = board_name(ats, token)
        why = ("recruiter or job site" if SKIP_RE.search(name) else
               "excluded company" if norm_co(name) in flt.skip_cos else
               "excluded industry word" if flt.industry_co and flt.industry_co.search(name) else None)
        if why:
            skipped.append((name, why)); b["added"] = f"skipped: {why}"; continue
        entry = {"ats": ats, "token": token, "match_check": check_note, "discovered": today.isoformat(),
                 "discovered_titles": b.get("titles", [])}
        existing = have.get(norm_co(name))
        if existing and not existing.get("ats"):
            existing.update(entry); filled.append((existing["company"], key, b))
        elif existing:
            b["added"] = "skipped: already listed with another board"; continue
        else:
            c = {"company": name, **entry}; data["companies"].append(c); have[norm_co(name)] = c
            added.append((name, key, b))
        b["added"] = today.isoformat()
    for name, key, b in added + filled:
        print(f"  + {name} ({key}): {b.get('matches', 0)} matching, e.g. {b.get('titles', [''])[0]}")
    for name, why in skipped: print(f"  - {name}: {why}")
    total = sum(1 for c in data["companies"] if c.get("ats"))
    if dry:
        print(f"\nDry run: {len(added)} would be added and {len(filled)} updated. companies.json not changed.")
        return
    save_state(state)
    common.save("companies.json", data)
    print(f"\nAdded {len(added)} companies, found boards for {len(filled)} already on your list, skipped {len(skipped)}. "
          f"Companies with a board: {total}.")
    if any(k.split(":")[0] in ("lever", "ashby") for _, k, _ in added):
        print("Lever and Ashby companies are named from their board name and marked unverified. If a name looks wrong,")
        print("fix it in config/companies.json.")
    print("Next: python3 run_daily.py")

if __name__ == "__main__":
    main()
