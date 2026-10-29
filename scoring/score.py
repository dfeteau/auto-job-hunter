"""Score collected jobs with the rules in config/profile.json and print the shortlist.
Usage: python3 scoring/score.py [--all]     (--all also lists jobs below the gate)

Fit Score = (salary points + location points) / (max salary points + max location points) * 100
Jobs below the salary floor, outside accepted locations, or below the gate are left off the shortlist.
evaluate() is also used by run_daily.py to build the daily report.
"""
import sys, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
import common
from common import PROFILE, LOC_GROUP, is_non_us, recheck_remote

S, L, SC = PROFILE["salary"], PROFILE["location"], PROFILE["scoring"]
TIERS = sorted(S["tiers_by_min"], key=lambda t: -t["min"])
MAX_SAL = max([t["points"] for t in TIERS] + [S.get("unknown_points", 0)])
MAX_LOC = max(SC["location_points"].values())
RANK = {k.lower(): v for k, v in SC["title_rank"].items()}
GATE = SC["gate_min"]

def salary_points(mn):
    if mn is None: return S.get("unknown_points", 0)
    return next((t["points"] for t in TIERS if mn >= t["min"]), 0)

def evaluate(con, include_all=False, today_only=False):
    """Scores jobs, writes scores to the database. Returns (shortlist, excluded, total).
    excluded: (reason, company, title, location). Current rules are re-applied, so edits to
    profile.json or the tracker take effect without collecting again."""
    flt = common.Filter()
    q = ("select id,company,title,location,remote_type,salary_min,salary_max,flags,description,url,source from jobs")
    if today_only: q += f" where last_seen_date = '{datetime.date.today().isoformat()}'"
    rows = con.execute(q).fetchall()
    out, excluded = [], []
    for id_, co, ti, loc, rt, mn, mx, flags, desc, url, src in rows:
        def drop(reason): excluded.append((reason, co, ti, loc or ""))
        if flt.tracked(co, ti): drop("Already in tracker"); continue
        if flt.skip_company({"company": co}): drop("Excluded company"); continue
        if is_non_us(loc or ""): drop("Outside the US"); continue
        rt = recheck_remote(rt, loc, desc)   # stored jobs get the current location checks too
        reason = flt.why_not(co, ti, loc, rt, desc)
        if reason: drop(reason); continue
        if mx is not None and mx < S["floor_high_end"]: drop(f"Pay tops out under ${S['floor_high_end']:,}"); continue
        group = LOC_GROUP[rt]
        if group in ("hybrid_home", "onsite_home") and L.get("home_min_salary") and (mn or 0) < L["home_min_salary"]:
            drop(f"Home-area job under ${L['home_min_salary']:,} or pay not listed"); continue
        fit = round((salary_points(mn) + SC["location_points"].get(group, 0)) / (MAX_SAL + MAX_LOC) * 100)
        tl = (ti or "").lower(); d = (desc or "").lower()
        tr = max([v for k, v in RANK.items() if k in tl] or [0])
        tb = sum(p for k, p in SC["skill_points"].items() if k.lower() in d)
        con.execute("update jobs set fit_score=?, title_rank=?, skills_tiebreak=? where id=?", (fit, tr, tb, id_))
        if fit < GATE and not include_all: drop(f"Fit Score under {GATE}"); continue
        out.append(dict(fit=fit, rank=tr, skills=tb, company=co, title=ti, location=loc, group=group,
                        smin=mn, smax=mx, flags=flags, url=url, source=src, description=desc))
    con.commit()
    out.sort(key=lambda r: (-r["fit"], -r["rank"], -r["skills"]))
    return out, excluded, len(rows)

def shortlist(con, include_all=False):
    out, _, total = evaluate(con, include_all)
    return out, total

def main():
    con = common.connect()
    out, total = shortlist(con, "--all" in sys.argv)
    passed = sum(1 for r in out if r["fit"] >= GATE)
    print(f"{total} collected, {passed} passed the gate ({GATE}+)\n")
    for r in out:
        sal = f"${r['smin']:,}-${r['smax']:,}" if r["smin"] else "n/a"
        print(f"{r['fit']:>3} | {r['company']} | {r['title']} | {r['location']} | {sal}" + (f" | {r['flags']}" if r["flags"] else ""))

if __name__ == "__main__":
    main()
