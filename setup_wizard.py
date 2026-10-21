"""Setup wizard: answers a few questions and writes config/profile.json for you.
Usage: python3 setup_wizard.py

Press Enter to accept the suggestion in [brackets]. Run it again any time to start over;
your previous settings are saved to config/profile.backup.json first.
"""
import json, pathlib, re, sys

CFG = pathlib.Path(__file__).resolve().parent / "config"
PROFILE = CFG / "profile.json"

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

def round5k(x):
    return int(round(x / 5000.0) * 5000)

def section(title):
    print(f"\n=== {title} ===")

def main():
    print(__doc__.split("\n")[0])
    print("This takes about 3 minutes. Answers can be changed later in config/profile.json.")

    section("1. Job titles")
    titles = ask_list("Job titles to search for (comma-separated, most wanted first)", "",
                      "A job matches if its title CONTAINS one of these, so 'Data Analyst' also finds "
                      "'Senior Data Analyst, Marketing'. Example: Senior Data Analyst, Data Analyst, BI Analyst",
                      required=True)
    excluded_titles = ask_list("Words that rule a title out (comma-separated)", "Junior, Intern, Entry Level",
                               "Example: Junior, Intern, Manager, Director. Type 'none' for no exclusions.")

    section("2. Industries and companies to avoid")
    print("   Shortcuts: " + ", ".join(INDUSTRIES) + ". You can also type your own keywords.")
    raw_ind = ask_list("Industries or title keywords to avoid (comma-separated, or none)", "none")
    industry_words = []
    for w in raw_ind:
        industry_words += INDUSTRIES.get(w.lower(), [w])
    companies = ask_list("Companies you never want to see (comma-separated, or none)", "none")

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
                   "excluded_industry_words": industry_words, "excluded_companies": companies},
        "location": {"country": "US", "home_metro_name": city or st, "home_metro_patterns": patterns,
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
    print("Next: set up your tracker and company list (README.md, steps 3 and 4).")

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. Nothing was saved."); sys.exit(1)
