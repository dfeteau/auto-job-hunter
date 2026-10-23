"""Add every qualifying job from the shortlist to your tracker, with Status New.
Usage: python3 tools/add_to_tracker.py [--dry-run]               (the tracker set up in config/tracker_map.json)
       python3 tools/add_to_tracker.py path/to/tracker.xlsx      (or a Google Sheets link)

- Adds each job that passed your Fit Score gate and isn't in the tracker yet: Date Added, Company, Job Title,
  Location, Work Type, Salary Range, Salary Min, Source, Link, Status New and Fit Score. Resume Match is left
  blank for your assistant (or you) to fill in.
- Flags such as "salary unknown" go in the Assistant Notes column. Your Notes column is never written to.
  If your tracker has no Assistant Notes column, one is added after your last column.
- Saves a backup in tracker/backups/ before changing anything (for a Google Sheet, a CSV snapshot; Google's
  File > Version history also works).
- Then runs tools/import_tracker.py, so these jobs aren't suggested again.

You review the new rows in the tracker: set Status (Applied, Did Not Apply, ...) and write your reasons in Notes.
Works with Excel (.xlsx, needs openpyxl) and Google Sheets (needs gspread). For a CSV tracker, use
tools/export_shortlist.py.
"""
import datetime, subprocess, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scoring"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from common import norm_co, norm_title
from score import shortlist
from export_shortlist import WORK_TYPE
import tracker_io

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    tracker = tracker_io.open_tracker(args[0] if args else None)
    if not tracker.can_write:
        sys.exit("This tool writes Excel and Google Sheets trackers. For a CSV tracker, run tools/export_shortlist.py.")
    print(f"Your tracker ({tracker.kind}): {tracker.label}")
    existing = tracker.existing_keys()

    jobs, _ = shortlist(common.connect())
    new = [j for j in jobs if norm_co(j["company"]) + "|" + norm_title(j["title"]) not in existing]
    print(f"{len(jobs)} qualifying jobs, {len(jobs) - len(new)} already in the tracker, {len(new)} to add.")
    for j in new: print(f"  + {j['fit']:>3} | {j['company']} | {j['title']}")
    if dry or not new:
        if dry: print("Dry run: tracker not changed.")
        return

    backup = tracker.backup()
    today = datetime.date.today()
    records = []
    for j in new:
        sal = f"${j['smin']:,} - ${j['smax']:,}" if j["smin"] and j["smax"] else (f"${j['smin']:,}" if j["smin"] else None)
        note = [f"Added by pipeline {today:%m/%d}"] + ([f"Flags: {j['flags']}"] if j.get("flags") else [])
        records.append({"Date Added": today, "company": j["company"], "title": j["title"], "Location": j["location"],
                        "Work Type": WORK_TYPE.get(j.get("group")), "Salary Range": sal, "Salary Min": j["smin"],
                        "Source": j["source"], "link": j["url"], "status": "New", "Fit Score": j["fit"],
                        tracker_io.ASSISTANT_NOTES: ". ".join(note) + "."})
    tracker.append(records)
    print(f"Added {len(new)} rows to your tracker (backup: {backup.name}).")
    subprocess.run([sys.executable, str(common.ROOT / "tools" / "import_tracker.py")] + args[:1], check=False)

if __name__ == "__main__":
    main()
