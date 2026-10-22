"""Collect jobs from every company with a known job board. Needs internet.
Usage: python3 collectors/collect.py [--only greenhouse|lever|ashby|smartrecruiters|workable|workday] [--limit N] [--debug]
--debug prints every matching job and why it was kept or excluded (and, for Workday, what each site returned).
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
    done = set()
    for c in companies:
        ats = c.get("ats")
        if not ats or (only and ats != only) or flt.skip_company(c): continue
        if ats == "workday" and not c.get("workday_url"): continue
        board = c.get("workday_url") if ats == "workday" else f"{ats}:{c.get('token')}"
        if board in done: continue   # same board listed under two company names
        done.add(board)
        if limit and n >= limit: break
        n += 1; flt.stats["boards"] += 1
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
    flt.save_stats(only or "all")
    print(f"boards searched: {n} | found: {flt.stats['found']} | excluded: {sum(flt.stats['excluded'].values())} | "
          f"already in tracker: {flt.counts['already_tracked']} | kept for scoring: {flt.counts['kept']}")

if __name__ == "__main__":
    main()
