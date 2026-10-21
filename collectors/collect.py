"""Collect jobs from every company with a known job board. Needs internet.
Usage: python3 collectors/collect.py [--only greenhouse|lever|ashby|smartrecruiters|workable|workday] [--limit N]
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common, sources

def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    companies = common.load("companies.json")["companies"]
    flt = common.Filter()
    con = common.connect()
    n = 0
    for c in companies:
        ats = c.get("ats")
        if not ats or (only and ats != only) or flt.skip_company(c): continue
        if ats == "workday" and not c.get("workday_url"): continue
        if limit and n >= limit: break
        n += 1
        print(f"  [{n}] {c['company']} ({ats})", flush=True)
        try:
            if ats == "workday":
                jobs = sources.workday(c["workday_url"], flt.wants_title, common.PROFILE["search"]["titles"])
            else:
                jobs = getattr(sources, ats)(c["token"], flt.wants_title)
            for j in jobs:
                common.save_job(con, flt, c["company"], ats, j)
        except Exception as e:
            print(f"      skipped after error: {e}", flush=True)
        con.commit(); time.sleep(0.3)
    print(f"boards searched: {n} | kept: {flt.counts['kept']} | already in tracker: {flt.counts['already_tracked']}")

if __name__ == "__main__":
    main()
