"""Setup wizard: answers a few questions and writes config/profile.json and config/tracker_map.json for you.
Usage: python3 setup_wizard.py            (everything)
       python3 setup_wizard.py --tracker  (only the tracker: Excel, Google Sheets or CSV)

Press Enter to accept the suggestion in [brackets]. Run it again any time to start over;
your previous settings are saved to config/profile.backup.json first.
"""
import json, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
CFG = ROOT / "config"
PROFILE = CFG / "profile.json"
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "collectors"))
import tracker_io
TEMPLATE = ROOT / "templates" / "job_tracker_template.xlsx"
TEMPLATE_MAP = {"company": "Company", "title": "Job Title", "status": "Status", "link": "Link"}

STATES = {"AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
          "CT": "connecticut", "DE": "delaware", "DC": "district of columbia", "FL": "florida", "GA": "georgia",
          "HI": "hawaii", "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
          "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan",
          "MN": "minnesota", "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
          "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york", "NC": "north carolina",
          "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon", "PA": "pennsylvania",
          "RI": "rhode island", "SC": "south carolina", "SD": "south dakota", "TN": "tennessee", "TX": "texas",
          "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west virginia",
          "WI": "wisconsin", "WY": "wyoming"}

# Typing one of these names expands to title keywords for that industry.
INDUSTRIES = {
    "healthcare": ["health", "medical", "medicine", "clinical", "patient", "hospital", "nursing", "physician", "dental"],
    "pharma": ["pharma", "biotech", "drug", "life sciences"],
    "defense": ["defense", "security clearance", "clearance", "dod", "military"],
    "government": ["government", "federal", "public sector"],
    "gambling": ["casino", "gaming", "betting", "sportsbook"],
    "crypto": ["crypto", "blockchain", "web3"],
    "insurance": ["insurance", "underwriting", "actuarial"],
}

def ask(question, default=None, help_text=None):
    if help_text: print(f"   {help_text}")
    suffix = f" [{default}]" if default not in (None, "") else ""
    ans = input(f"{question}{suffix}: ").strip()
    return ans if ans else (default if default is not None else "")

def ask_list(question, default="", help_text=None, required=False):
    while True:
        raw = ask(question, default, help_text)
        items = [x.strip() for x in raw.split(",") if x.strip()] if raw.lower() not in ("none", "-") else []
        if items or not required: return items
        print("   Please enter at least one.")

def ask_yes(question, default=True):
    d = "Y/n" if default else "y/N"
    while True:
        ans = input(f"{question} [{d}]: ").strip().lower()
        if not ans: return default
        if ans in ("y", "yes"): return True
        if ans in ("n", "no"): return False
        print("   Please answer y or n.")

def ask_money(question, default=None, help_text=None, required=True):
    while True:
        raw = ask(question, f"{default:,}" if default else ("" if required else "none"), help_text)
        if not required and raw.lower() in ("", "none", "0", "-"): return None
        txt = raw.lower().replace("$", "").replace(",", "").strip()
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(k)?", txt)
        if m:
            val = float(m.group(1)) * (1000 if m.group(2) else 1)
            if val < 1000: val *= 1000  # "120" means 120K
            return int(round(val))
        print("   Please enter an amount like 120000, 120K or $120,000.")

def ask_int(question, default, lo, hi):
    while True:
        raw = ask(question, str(default))
        if raw.isdigit() and lo <= int(raw) <= hi: return int(raw)
        print(f"   Please enter a number from {lo} to {hi}.")

def ask_choice(question, options, default=1):
    for i, o in enumerate(options, 1): print(f"   {i}. {o}")
    while True:
        raw = ask(question, str(default))
        if raw.isdigit() and 1 <= int(raw) <= len(options): return int(raw)
        print(f"   Please enter a number from 1 to {len(options)}.")

def round5k(x):
    return int(round(x / 5000.0) * 5000)

def section(title):
    print(f"\n=== {title} ===")

# ---------- tracker ----------

def check_headers(tracker, tmap, can_add_headers=False):
    """Reads the tracker and confirms the company and title columns can be found. Returns True when they can."""
    try:
        grid = [[v for v, _ in row] for row in tracker.grid()]
    except SystemExit as e:
        print(f"   {e}"); return False
    if not any(str(v or "").strip() for row in grid for v in row):
        if can_add_headers and ask_yes("   This tab is empty. Add the template's column headers to row 1?", True):
            try:
                tracker.write_headers()
            except SystemExit as e:
                print(f"   {e}"); return False
            tmap["columns"] = dict(TEMPLATE_MAP); tracker.cols = tmap["columns"]
            print("   Added: " + ", ".join(tracker_io.TEMPLATE_COLUMNS) + ".")
            return True
        print("   The tracker is empty. Add a header row with at least a company column and a job title column.")
        return False
    for attempt in (1, 2):
        try:
            hr, _ = tracker_io.find_header(grid, tmap["columns"])
            jobs = sum(1 for row in grid[hr + 1:] if any(str(v or "").strip() for v in row))
            print(f"   Tracker read. Headers are in row {hr + 1}, "
                  + (f"with {jobs} row{'s' if jobs != 1 else ''} below them." if jobs else "with no jobs yet."))
            return True
        except SystemExit:
            if attempt == 2: break
            print(f"   Couldn't find the columns '{tmap['columns']['company']}' and '{tmap['columns']['title']}'.")
            if not ask_yes("   Tell me your column names now?", True): break
            cols = tmap["columns"]
            cols["company"] = ask("   Header of the company column", cols.get("company"))
            cols["title"] = ask("   Header of the job title column", cols.get("title"))
            cols["status"] = ask("   Header of the status column", cols.get("status"))
            cols["link"] = ask("   Header of the job link column", cols.get("link"))
            tracker.cols = cols
    print("   You can fix the column names later in config/tracker_map.json.")
    return False

def tracker_excel(tmap, src):
    path = ask("Path to your tracker file", src.get("path") if src.get("type") == "excel" else tracker_io.DEFAULT_EXCEL,
               "A path inside this project folder (like tracker/my_job_tracker.xlsx) or a full path.")
    p = tracker_io.resolve(path)
    tab = None
    if not p.exists():
        print("   That file doesn't exist yet.")
        if ask_yes("   Start a new tracker there from the template?", True):
            p.parent.mkdir(parents=True, exist_ok=True); shutil.copy(TEMPLATE, p)
            tmap["columns"] = dict(TEMPLATE_MAP)
            print(f"   Created {p}. Its second tab explains each column.")
        else:
            print("   Have a tracker in another layout? tools/migrate_tracker.py copies it into the template "
                  "(README.md, step 3). Then run python3 setup_wizard.py --tracker again.")
    else:
        tab = ask("Tab name (press Enter for the first tab)", tmap.get("sheet") or "") or None
    tmap["sheet"] = tab
    if p.exists():
        try:
            import openpyxl  # noqa: F401
            check_headers(tracker_io.ExcelTracker(p, tab, tmap["columns"]), tmap)
        except ImportError:
            print("   Reading Excel files needs one package: pip3 install openpyxl")
    return {"type": "excel", "path": path}

def tracker_google(tmap, src):
    print("   One-time Google setup (about 10 minutes; README.md, \"Using Google Sheets\", has every click):")
    print("     1. In Google Cloud Console, create a project and turn on the Google Sheets API.")
    print("     2. Create a service account, add a JSON key, and save the downloaded key file in this")
    print("        project's config folder as google_service_account.json (it stays out of git).")
    print("     3. Open your Google Sheet, click Share, and add the service account's email as an Editor.")
    print("   Starting fresh? Create a blank Google Sheet; the wizard can add the column headers for you.")
    print("   Moving from Excel? In Google Sheets use File > Import, then point the wizard at the new sheet.")
    try:
        import gspread  # noqa: F401
        have_pkg = True
    except ImportError:
        have_pkg = False
        print("   You'll also need one package: pip3 install gspread")
    creds = ask("Path to your service account key file",
                src.get("credentials") if src.get("type") == "google_sheets" else tracker_io.DEFAULT_CREDENTIALS)
    cp = tracker_io.resolve(creds)
    if cp.exists():
        try:
            email = json.loads(cp.read_text()).get("client_email")
        except Exception:
            email = None
        if email: print(f"   Share your Google Sheet with {email} as an Editor.")
        else: print("   That file doesn't look like a service account key (no client_email). Check step 2.")
    else:
        print("   That file isn't there yet. You can finish now and test later with: python3 setup_wizard.py --tracker")
    while True:
        url = ask("Your Google Sheet's link (copy it from the browser address bar)",
                  src.get("url") if src.get("type") == "google_sheets" else "")
        if tracker_io.is_sheets_link(url) or re.fullmatch(r"[A-Za-z0-9_-]{25,}", url): break
        print("   Please paste the full link. It contains /spreadsheets/d/.")
    tab = ask("Tab name (press Enter for the first tab)", tmap.get("sheet") or "") or None
    tmap["sheet"] = tab
    if have_pkg and cp.exists() and ask_yes("Test the connection now?", True):
        check_headers(tracker_io.GoogleSheetsTracker(url, tab, tmap["columns"], creds), tmap, can_add_headers=True)
    return {"type": "google_sheets", "url": url, "credentials": creds}

def tracker_csv(tmap, src):
    path = ask("Path to your CSV tracker", src.get("path") if src.get("type") == "csv" else "tracker/my_job_tracker.csv")
    p = tracker_io.resolve(path)
    tmap["sheet"] = None
    if p.exists(): check_headers(tracker_io.CsvTracker(p, None, tmap["columns"]), tmap)
    else: print(f"   {p} doesn't exist yet. Export your tracker as CSV and save it there.")
    print("   The pipeline reads CSV trackers but doesn't write them. Each day, tools/export_shortlist.py")
    print("   saves the new jobs as rows you can paste in.")
    return {"type": "csv", "path": path}

def setup_tracker():
    section("7. Your tracker")
    print("   Your tracker is the spreadsheet where you log applications. The pipeline reads it so jobs you")
    print("   already track never come back, and adds each day's qualifying jobs to it.")
    tmap = tracker_io.load_map()
    tmap.setdefault("columns", dict(TEMPLATE_MAP))
    src = tmap.get("source") or {}
    kinds = ["excel", "google_sheets", "csv"]
    choice = ask_choice("Which do you use?", ["Excel (an .xlsx file on this computer)", "Google Sheets",
                        "A CSV file (exported from Notion, Airtable or similar)"],
                        kinds.index(src["type"]) + 1 if src.get("type") in kinds else 1)
    src = [tracker_excel, tracker_google, tracker_csv][choice - 1](tmap, src)
    tmap["source"] = src
    tracker_io.save_map(tmap)
    print(f"\nSaved to {CFG / 'tracker_map.json'}: {tracker_io.describe_source(src)}"
          + (f", tab '{tmap['sheet']}'" if tmap.get("sheet") else "") + ".")
    print("Next: python3 tools/import_tracker.py  (reads your tracker; README.md, step 4)")

def offer_discovery():
    """When the company list is short, offer to find companies with matching jobs (tools/discover_companies.py)."""
    try:
        boards = sum(1 for c in json.loads((CFG / "companies.json").read_text())["companies"] if c.get("ats"))
    except Exception:
        boards = 0
    if boards >= 25: return
    section("8. Find companies")
    print(f"   Your company list has {boards} companies with a known job board. The pipeline only searches")
    print("   companies on that list, so it can look for you: it finds Greenhouse, Lever and Ashby job boards in a")
    print("   free public web archive and adds every company that has a job matching your titles right now.")
    print("   The first run can take an hour or more. Ctrl+C stops it safely, and running it again continues.")
    print("   (Bringing in a tracker first? You can still do this now; companies already listed are skipped.)")
    if ask_yes("Find companies now?", True):
        subprocess.run([sys.executable, str(ROOT / "tools" / "discover_companies.py")], cwd=ROOT)
    else:
        print("   Any time later: python3 tools/discover_companies.py")

def main():
    if "--tracker" in sys.argv:
        setup_tracker(); return
    print(__doc__.split("\n")[0])
    print("This takes about 5 minutes. Answers can be changed later in config/profile.json and config/tracker_map.json.")

    section("1. Job titles")
    titles = ask_list("Job titles to search for (comma-separated, most wanted first)", "",
                      "A job matches if its title CONTAINS one of these, so 'Data Analyst' also finds "
                      "'Senior Data Analyst, Marketing'. Example: Senior Data Analyst, Data Analyst, BI Analyst",
                      required=True)
    excluded_titles = ask_list("Words that rule a title out (comma-separated)", "Junior, Intern, Entry Level, Director, Head of",
                               "Example: Junior, Intern, Manager, Director. Type 'none' for no exclusions.")

    section("2. Industries and companies to avoid")
    print("   Shortcuts: " + ", ".join(INDUSTRIES) + ". You can also type your own keywords.")
    raw_ind = ask_list("Industries or keywords to avoid (comma-separated, or none)", "none",
                       "Checked against the job title, the company name, and how the posting describes the company.")
    industry_words = []
    for w in raw_ind:
        industry_words += INDUSTRIES.get(w.lower(), [w])
    companies = ask_list("Companies you never want to see (comma-separated, or none)", "none")
    has_clearance = ask_yes("Do you hold an active US security clearance?", False)
    if not has_clearance:
        print("   Jobs that require a clearance will be skipped.")

    section("3. Location")
    print("   This tool searches US jobs only.")
    city = ask("Your home city (for hybrid/onsite jobs)", "", "Example: Denver")
    while True:
        st = ask("Your state (2 letters)", "", "Example: CO").upper()
        if st in STATES: break
        print("   Please enter a 2-letter US state code, like CO or IL.")
    nearby = ask_list("Nearby cities you'd commute to (comma-separated, or none)", "none",
                      "Example: Boulder, Lakewood, Aurora")
    patterns = [re.escape(c.lower()) for c in [city] + nearby if c]
    whole_state = not patterns or ask_yes(f"Count a job anywhere in {STATES[st].title()} as nearby?", False)
    if whole_state: patterns += [STATES[st], f", {st.lower()}\\b"]
    print("\n   Which kinds of jobs should be kept?")
    accept = {
        "remote": ask_yes("   Remote (anywhere in the US)?", True),
        "hybrid_home": ask_yes(f"   Hybrid in the {city or 'home'} area?", True),
        "onsite_home": ask_yes(f"   Fully onsite in the {city or 'home'} area?", False),
        "hybrid_other": ask_yes("   Hybrid in another city (would relocate)?", False),
        "onsite_other": ask_yes("   Onsite in another city (would relocate)?", False),
    }
    if not any(accept.values()):
        print("   Nothing selected, so keeping remote jobs."); accept["remote"] = True
    home_min = None
    if accept["hybrid_home"] or accept["onsite_home"]:
        home_min = ask_money("Minimum salary to make a commute worth it (or none)", None,
                             "Hybrid/onsite jobs below this are dropped. Remote jobs are not affected.", required=False)

    section("4. Salary")
    floor = ask_money("Lowest salary you would consider", None,
                      "Jobs whose posted range tops out below this are dropped. Jobs with no salary listed are kept.")
    while True:
        ideal = ask_money("Your target salary", round5k(floor * 1.2), "Jobs starting at or above this score best.")
        if ideal > floor: break
        print("   Target should be higher than the lowest salary you'd consider.")
    mid = round5k((floor + ideal) / 2)
    tiers = [{"min": ideal, "points": 4}, {"min": mid, "points": 3}, {"min": floor, "points": 2}]
    tiers = [t for i, t in enumerate(tiers) if t["min"] not in [x["min"] for x in tiers[:i]]]

    section("5. Skills (tiebreaker only)")
    skills = ask_list("Your strongest skills or tools, most important first (comma-separated)", "",
                      "Jobs mentioning these rank higher among equal scores. Example: SQL, Python, Tableau, Excel")

    section("6. Shortlist size")
    gate = ask_int("Minimum Fit Score to make the shortlist (0-100)", 50, 0, 100)

    loc_points = {"remote": 4, "hybrid_home": 3, "onsite_home": 2, "hybrid_other": 1, "onsite_other": 1}
    profile = {
        "_readme": "Created by setup_wizard.py. Edit any value by hand, or run python3 setup_wizard.py again. See README.md, step 2.",
        "search": {"titles": titles, "excluded_title_words": excluded_titles,
                   "excluded_title_exceptions": ["senior associate", "sr. associate", "sr associate",
                                                 "associate principal", "associate director", "associate vice president"],
                   "excluded_industry_words": industry_words, "excluded_companies": companies,
                   "exclude_clearance_required": not has_clearance},
        "location": {"country": "US", "home_metro_name": city or st, "home_metro_patterns": patterns,
                     "home_state": STATES[st].title() if st in STATES else None,
                     "accept": accept, "home_min_salary": home_min},
        "salary": {"floor_high_end": floor, "tiers_by_min": tiers, "unknown_points": 0},
        "scoring": {"location_points": loc_points, "gate_min": gate,
                    "title_rank": {t: max(30 - 5 * i, 5) for i, t in enumerate(titles)},
                    "skill_points": {s.lower(): (10 if i < 2 else 5) for i, s in enumerate(skills)}},
    }

    section("Summary")
    yes = lambda b: "yes" if b else "no"
    print(f"   Titles:            {', '.join(titles)}")
    print(f"   Excluding titles:  {', '.join(excluded_titles) or 'nothing'}")
    print(f"   Avoiding:          {', '.join(raw_ind) or 'nothing'}" + (f"; companies: {', '.join(companies)}" if companies else ""))
    print(f"   Home area:         " + (f"anywhere in {STATES[st].title()}" if whole_state else ", ".join([city] + nearby) + f" ({st})"))
    print(f"   Keep remote: {yes(accept['remote'])} | hybrid nearby: {yes(accept['hybrid_home'])} | "
          f"onsite nearby: {yes(accept['onsite_home'])} | hybrid elsewhere: {yes(accept['hybrid_other'])} | "
          f"onsite elsewhere: {yes(accept['onsite_other'])}")
    if home_min: print(f"   Commute minimum:   ${home_min:,}")
    print(f"   Salary:            drop if range tops out under ${floor:,}; best score at ${ideal:,}+")
    print(f"   Clearance jobs:    {'kept' if has_clearance else 'skipped'}")
    print(f"   Skills:            {', '.join(skills) or 'none'}")
    print(f"   Shortlist:         Fit Score {gate}+")
    print("\n   Example scores: remote at your target salary = 100; remote with no salary listed = 50"
          + (f"; hybrid nearby at ${mid:,} = 75" if accept["hybrid_home"] else "") + ".")

    if not ask_yes("\nSave these settings?", True):
        print("Nothing saved. Run python3 setup_wizard.py to start again."); return
    if PROFILE.exists():
        (CFG / "profile.backup.json").write_text(PROFILE.read_text())
    PROFILE.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"\nSaved to {PROFILE}.")
    if ask_yes("\nSet up your tracker now (Excel, Google Sheets or CSV)?", True):
        setup_tracker()
    else:
        print("Next: python3 setup_wizard.py --tracker, then build your company list (README.md, steps 3 and 4).")
    offer_discovery()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Nothing was saved."); sys.exit(1)
