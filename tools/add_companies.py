"""Add companies you want searched, by name or from a list collected on any job site.
Usage: python3 tools/add_companies.py "Acme Corp" "Globex" ...
       python3 tools/add_companies.py --file companies.txt              (one name per line)
       python3 tools/add_companies.py --file companies.csv --source "Built In NYC" --dry-run
Then run: python3 collectors/find_boards.py (it looks up boards for companies added without one)

Options:
  --file PATH     A .txt file (one company per line) or a .csv file with a "company" column. A CSV may also
                  have a "link" column (an apply or job-board address). When the link is a Greenhouse, Lever,
                  Ashby, SmartRecruiters, Workable or Workday address, the company's job board is filled in
                  directly, so find_boards.py doesn't have to guess it.
  --source NAME   Where the list came from (for example "Built In Chicago"). Saved on each new company as
                  "discovered_via", so you can see later which site found it.
  --dry-run       Show what would be added, skipped and filled in, without changing anything.

Skipped automatically: companies already on your list, recruiters, staffing firms and aggregators, your
excluded_companies, and names containing one of your excluded_industry_words. Names that look similar to a
company you already have are added but listed, so you can check they aren't duplicates.
"""
import csv, re, sys, pathlib, datetime, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from common import norm_co
from import_tracker import guess_slug
from find_boards import SKIP_RE

TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,79}$")
NOT_BOARDS = {"embed", "jobs", "job", "api", "v1", "v0", "posting-api", "widget", "accounts", "careers", "search",
              "j", "o", "en", "en-us"}

def board_from_link(link):
    """(ats, token, workday_url) from a job or job-board address, or (None, None, None)."""
    link = (link or "").strip()
    if not link: return None, None, None
    p = urllib.parse.urlsplit(link if "://" in link else "https://" + link)
    host = p.netloc.lower().split(":")[0]
    seg = [urllib.parse.unquote(s) for s in p.path.split("/") if s]
    first = seg[0] if seg else ""
    if host.endswith("myworkdayjobs.com"):
        site = [s for s in seg if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)]
        if not site: return None, None, None
        return "workday", None, f"https://{host}/{site[0]}"
    if host.endswith("greenhouse.io"):
        if first == "embed":
            first = (urllib.parse.parse_qs(p.query).get("for") or [""])[0]
        if host.startswith("boards-api.") and len(seg) >= 3: first = seg[2]   # /v1/boards/<token>
        ats, first = "greenhouse", first.lower()
    elif host == "jobs.lever.co" or host == "api.lever.co":
        if host == "api.lever.co" and len(seg) >= 3: first = seg[2]           # /v0/postings/<token>
        ats, first = "lever", first.lower()
    elif host in ("jobs.ashbyhq.com", "api.ashbyhq.com"):
        if host == "api.ashbyhq.com" and len(seg) >= 3: first = seg[2]        # /posting-api/job-board/<token>
        ats = "ashby"                                                         # Ashby keeps its spelling
    elif host.endswith("smartrecruiters.com"):
        ats, first = "smartrecruiters", first
    elif host == "apply.workable.com":
        ats, first = "workable", first.lower()
    else:
        return None, None, None
    if not first or first.lower() in NOT_BOARDS or not TOKEN.match(first): return None, None, None
    return ats, first, None

def read_file(path):
    """[(company, link)] from a .txt or .csv file."""
    path = pathlib.Path(path).expanduser()
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() != ".csv":
        return [(l.strip(), "") for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
    rows = list(csv.DictReader(text.splitlines()))
    if not rows: return []
    cols = {k.lower().strip(): k for k in rows[0].keys() if k}
    name_col = next((cols[k] for k in ("company", "employer", "company name", "name") if k in cols), None)
    if not name_col: sys.exit(f'{path.name} needs a "company" column. Columns found: {", ".join(rows[0].keys())}')
    link_col = next((cols[k] for k in ("link", "board", "apply link", "apply url", "url", "job link") if k in cols), None)
    return [((r.get(name_col) or "").strip(), (r.get(link_col) or "").strip() if link_col else "")
            for r in rows if (r.get(name_col) or "").strip()]

def similar(key, have):
    """An existing name key that starts with this one or the other way round (5+ characters), or None."""
    if len(key) < 5: return None
    return next((h for h in have if len(h) >= 5 and h != key and (h.startswith(key) or key.startswith(h))), None)

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"): sys.exit(__doc__)
    dry = "--dry-run" in args
    source = args[args.index("--source") + 1] if "--source" in args else None
    if "--file" in args:
        entries = read_file(args[args.index("--file") + 1])
    else:
        skip_next, entries = False, []
        for a in args:
            if skip_next: skip_next = False; continue
            if a == "--source": skip_next = True; continue
            if a.startswith("--"): continue
            entries.append((a, ""))

    s = common.PROFILE["search"]
    excluded_cos = {norm_co(x) for x in s.get("excluded_companies", [])}
    words = [re.escape(w) for w in s.get("excluded_industry_words", [])]
    industry = re.compile(r"\b(?:" + "|".join(words) + ")", re.I) if words else None

    data = common.load("companies.json")
    by_key = {norm_co(c["company"]): c for c in data["companies"]}
    today = datetime.date.today().isoformat()
    added, already, filled, skipped, check = [], [], [], [], []
    for name, link in entries:
        key = norm_co(name)
        if not key: continue
        ats, token, wd = board_from_link(link)
        if key in by_key:
            c = by_key[key]
            if ats and not c.get("ats"):   # a known company with no board yet: use the board from the link
                c.update(ats=ats, token=token, match_check="from job link")
                if wd: c["workday_url"] = wd
                filled.append(f"{c['company']} -> {ats}:{token or wd}")
            else:
                already.append(name)
            continue
        if SKIP_RE.search(name): skipped.append(f"{name} (recruiter or aggregator)"); continue
        if key in excluded_cos: skipped.append(f"{name} (in your excluded_companies)"); continue
        if industry and industry.search(name): skipped.append(f"{name} (excluded industry word)"); continue
        sim = similar(key, by_key)
        if sim: check.append(f"{name}  ~  {by_key[sim]['company']}")
        c = {"company": name, "guess_slug": guess_slug(name), "ats": ats, "token": token}
        if ats: c["match_check"] = "from job link"
        if wd: c["workday_url"] = wd
        if source: c.update(discovered_via=source, added_date=today)
        data["companies"].append(c); by_key[key] = c
        added.append(name + (f"  [{ats}:{token or wd}]" if ats else ""))

    with_board = sum(1 for n in added if "[" in n)
    print(f"{'Would add' if dry else 'Added'} {len(added)} companies ({with_board} with their job board from a link)"
          + (f" from {source}" if source else ""))
    for n in added: print(f"  + {n}")
    if filled:
        print(f"\nJob board {'would be ' if dry else ''}filled in for {len(filled)} companies already on your list:")
        for n in filled: print(f"  ~ {n}")
    if skipped:
        print(f"\nSkipped {len(skipped)}:")
        for n in skipped: print(f"  - {n}")
    if check:
        print(f"\nSimilar to a company you already have (check these aren't duplicates):")
        for n in check: print(f"  ? {n}")
    print(f"\nAlready on your list: {len(already)}")
    if dry:
        print("\nDry run: nothing was changed. Run again without --dry-run to save.")
        return
    common.save("companies.json", data)
    print(f"Companies total: {len(data['companies'])}")
    if added or filled:
        print("Next: python3 collectors/find_boards.py  (looks up boards for the companies added without one)")

if __name__ == "__main__":
    main()
