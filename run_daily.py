"""Daily run: collect from every job board, score, and save a report you can read or share (with Claude, for example).
Usage: python3 run_daily.py            (full run)
       python3 run_daily.py --report   (rebuild the report from today's data without collecting again)

The report is saved to reports/report_YYYY-MM-DD.md (set JOB_REPORT_DIR to save it somewhere else,
for example a folder you share with Claude).
"""
import os, sys, json, subprocess, datetime, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "collectors")); sys.path.insert(0, str(ROOT / "scoring"))
import common
from score import evaluate, GATE

REPORT_DIR = pathlib.Path(os.environ.get("JOB_REPORT_DIR", ROOT / "reports"))

def money(mn, mx):
    return f"${mn:,} to ${mx:,}" if mn and mx and mn != mx else (f"${mn:,}" if mn else "not listed")

def today_stats():
    p = common.STATS_DIR / "all.json"
    if p.exists():
        s = json.loads(p.read_text())
        if s.get("date") == datetime.date.today().isoformat(): return s
    return dict(boards=0, found=0, tracked=0, kept=0, excluded={}, details=[])

def build_report(started):
    st = today_stats()
    shortlist, excl, _ = evaluate(common.connect(), today_only=True)
    tracked = st["tracked"] + sum(1 for e in excl if e[0] == "Already in tracker")
    reasons = collections.Counter(st["excluded"])
    for e in excl:
        if e[0] != "Already in tracker": reasons[e[0]] += 1
    excluded_total = sum(reasons.values())
    now = datetime.datetime.now()
    L = [f"# Job Search Daily Report: {now.strftime('%A, %B %d, %Y').replace(' 0', ' ')}",
         f"Run {started.strftime('%I:%M %p').lstrip('0')} to {now.strftime('%I:%M %p').lstrip('0')}. Boards searched: {st['boards']}.",
         "", "## Summary", "", "| Step | Jobs |", "|---|---|",
         f"| Found (title matches your search) | {st['found']} |",
         f"| Excluded by your criteria | {excluded_total} |",
         f"| Already in your tracker | {tracked} |",
         f"| **Qualify for your tracker** (Fit Score {GATE}+, pending your review) | **{len(shortlist)}** |", ""]
    gap = st["found"] - excluded_total - tracked - len(shortlist)
    if gap:
        L += [f"_Note: {gap:+d} difference. Jobs collected on an earlier day that are still posted are scored but not counted in Found._", ""]
    L += ["## Excluded, by reason", ""]
    if reasons:
        L += ["| Reason | Jobs |", "|---|---|"] + [f"| {r} | {n} |" for r, n in reasons.most_common()]
    else:
        L.append("None.")
    L += ["", "## Qualifying jobs", ""]
    if shortlist:
        L += ["| # | Fit | Company | Title | Location | Pay | Flags |", "|---|---|---|---|---|---|---|"]
        for i, r in enumerate(shortlist, 1):
            L.append(f"| {i} | {r['fit']} | {r['company']} | [{r['title']}]({r['url']}) | {r['location']} | "
                     f"{money(r['smin'], r['smax'])} | {r['flags'] or ''} |")
    else:
        L.append("No new qualifying jobs today.")
    detail = [d for d in st["details"]] + [list(e) for e in excl if e[0] != "Already in tracker"]
    L += ["", "## Excluded jobs (detail)", ""]
    if detail:
        L += ["| Reason | Company | Title | Location |", "|---|---|---|---|"]
        L += [f"| {r} | {c} | {t} | {(l or '')[:60]} |" for r, c, t, l in sorted(detail)]
    else:
        L.append("None.")
    if shortlist:
        L += ["", "## Job descriptions (for Resume Match, see docs/RESUME_MATCH.md)", ""]
        for i, r in enumerate(shortlist, 1):
            L += [f"### {i}. {r['company']}: {r['title']}",
                  f"{r['location']} | {money(r['smin'], r['smax'])} | {r['source']} | {r['url']}", "",
                  " ".join((r["description"] or "").split())[:6000], ""]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"report_{now.date().isoformat()}.md"
    path.write_text("\n".join(L) + "\n")
    return path, st["found"], excluded_total, tracked, shortlist

def main():
    started = datetime.datetime.now()
    if "--report" not in sys.argv:
        subprocess.run([sys.executable, str(ROOT / "collectors" / "collect.py")], cwd=ROOT)
    path, found, excluded, tracked, shortlist = build_report(started)
    print("\n" + "=" * 60)
    print(f"Found: {found} | Excluded: {excluded} | Already in tracker: {tracked} | Qualify: {len(shortlist)}")
    for r in shortlist:
        print(f"  {r['fit']} | {r['company']} | {r['title']} | {money(r['smin'], r['smax'])}")
    print(f"\nReport saved: {path}")
    if shortlist: print("Next: python3 tools/add_to_tracker.py tracker/my_job_tracker.xlsx  (adds these to your tracker)")

if __name__ == "__main__":
    main()
