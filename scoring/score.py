"""Score collected jobs with the rules in config/profile.json and print the shortlist.
Usage: python3 scoring/score.py [--all]     (--all also lists jobs below the gate)

Fit Score = (salary points + location points) / (max salary points + max location points) * 100
Jobs below the salary floor, outside accepted locations, or below the gate are left off the shortlist.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
import common
from common import PROFILE, LOC_GROUP, NON_US

S, L, SC = PROFILE["salary"], PROFILE["location"], PROFILE["scoring"]
TIERS = sorted(S["tiers_by_min"], key=lambda t: -t["min"])
MAX_SAL = max([t["points"] for t in TIERS] + [S.get("unknown_points", 0)])
MAX_LOC = max(SC["location_points"].values())
RANK = {k.lower(): v for k, v in SC["title_rank"].items()}

def salary_points(mn):
    if mn is None: return S.get("unknown_points", 0)
    return next((t["points"] for t in TIERS if mn >= t["min"]), 0)

def shortlist(con, include_all=False):
    """Scores every job, writes scores to the database, returns rows sorted best first."""
    flt = common.Filter()
    rows = con.execute("select id,company,title,location,remote_type,salary_min,salary_max,flags,description,url,source "
                       "from jobs").fetchall()
    out = []
    for id_, co, ti, loc, rt, mn, mx, flags, desc, url, src in rows:
        # re-apply current rules so edits to profile.json or the tracker take effect without recollecting
        if flt.skip_company({"company": co}) or flt.tracked(co, ti) or not flt.wants_title(ti): continue
        if NON_US.search(loc or "") or not flt.location_ok(rt): continue
        if mx is not None and mx < S["floor_high_end"]: continue
        group = LOC_GROUP[rt]
        if group in ("hybrid_home", "onsite_home") and L.get("home_min_salary") and (mn or 0) < L["home_min_salary"]: continue
        fit = round((salary_points(mn) + SC["location_points"].get(group, 0)) / (MAX_SAL + MAX_LOC) * 100)
        tl = (ti or "").lower(); d = (desc or "").lower()
        tr = max([v for k, v in RANK.items() if k in tl] or [0])
        tb = sum(p for k, p in SC["skill_points"].items() if k.lower() in d)
        con.execute("update jobs set fit_score=?, title_rank=?, skills_tiebreak=? where id=?", (fit, tr, tb, id_))
        if fit >= SC["gate_min"] or include_all:
            out.append(dict(fit=fit, rank=tr, skills=tb, company=co, title=ti, location=loc, group=group,
                            smin=mn, smax=mx, flags=flags, url=url, source=src))
    con.commit()
    out.sort(key=lambda r: (-r["fit"], -r["rank"], -r["skills"]))
    return out, len(rows)

def main():
    con = common.connect()
    out, total = shortlist(con, "--all" in sys.argv)
    passed = sum(1 for r in out if r["fit"] >= SC["gate_min"])
    print(f"{total} collected, {passed} passed the gate ({SC['gate_min']}+)\n")
    for r in out:
        sal = f"${r['smin']:,}-${r['smax']:,}" if r["smin"] else "n/a"
        print(f"{r['fit']:>3} | {r['company']} | {r['title']} | {r['location']} | {sal}" + (f" | {r['flags']}" if r["flags"] else ""))

if __name__ == "__main__":
    main()
