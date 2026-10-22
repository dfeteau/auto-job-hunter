"""Save today's shortlist as a CSV in the template tracker's column order, ready to paste into your tracker.
For an .xlsx tracker, tools/add_to_tracker.py adds the rows for you.
Usage: python3 tools/export_shortlist.py      -> exports/shortlist_YYYY-MM-DD.csv
"""
import csv, datetime, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scoring"))
import common
from score import shortlist

COLUMNS = ["Date Added", "Company", "Job Title", "Location", "Work Type", "Salary Range", "Salary Min", "Source", "Link",
           "Date Applied", "Status", "Resume Match", "Fit Score", "Notes", "Assistant Notes"]
WORK_TYPE = {"remote": "Remote", "hybrid_home": "Hybrid - Home Metro", "onsite_home": "Onsite - Home Metro",
             "hybrid_other": "Hybrid - Other", "onsite_other": "Onsite - Other"}

def main():
    rows, _ = shortlist(common.connect())
    today = datetime.date.today()
    out = common.ROOT / "exports" / f"shortlist_{today.isoformat()}.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(COLUMNS)
        for r in rows:
            sal = f"${r['smin']:,} - ${r['smax']:,}" if r["smin"] else ""
            w.writerow([today.strftime("%m/%d/%Y"), r["company"], r["title"], r["location"], WORK_TYPE.get(r["group"], ""),
                        sal, r["smin"] or "", r["source"], r["url"], "", "New", "", r["fit"], "",
                        f"Flags: {r['flags']}" if r["flags"] else ""])
    print(f"{len(rows)} jobs -> {out}")

if __name__ == "__main__":
    main()
