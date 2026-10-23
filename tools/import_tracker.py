"""Read your job tracker and update the pipeline's lists.
Usage: python3 tools/import_tracker.py                     (the tracker set up in config/tracker_map.json)
       python3 tools/import_tracker.py path/to/tracker.xlsx (or a .csv file, or a Google Sheets link)

- Rebuilds config/seen.json with every job in the tracker, so those jobs are never shown again.
- Adds any company in the tracker that is not yet in config/companies.json.
  Run collectors/find_boards.py afterward to find job boards for the new companies.

Column names come from config/tracker_map.json (defaults match the template tracker).
Excel needs openpyxl (pip3 install openpyxl), Google Sheets needs gspread (pip3 install gspread). CSV needs nothing.
"""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from common import norm_co, norm_title
from find_boards import words
import tracker_io
from tracker_io import HYPERLINK

def read_rows(tracker, cols):
    """Yields dicts keyed by our field names. Finds the header row in the first 10 rows."""
    grid = tracker.grid()
    wanted = {k: v.strip().lower() for k, v in cols.items()}
    for hi, row in enumerate(grid[:10]):
        names = [str(v or "").strip().lower() for v, _ in row]
        if wanted["company"] in names and wanted["title"] in names:
            idx = {k: names.index(v) for k, v in wanted.items() if v in names}
            break
    else:
        sys.exit(f"Could not find the '{cols['company']}' and '{cols['title']}' headers. Check config/tracker_map.json.")
    for row in grid[hi + 1:]:
        cell = lambda k: row[idx[k]] if k in idx and idx[k] < len(row) else (None, None)
        rec = {}
        for k in idx:
            v, link = cell(k)
            v = "" if v is None else str(v)
            m = HYPERLINK.match(v)
            if m:  # a cell like =HYPERLINK("url", "text")
                link = link or (m.group(1) if m.group(1).startswith("http") else None)
                v = m.group(2)
            rec[k] = v.strip()
            if k == "link": rec[k] = link or (v if v.startswith("http") else "")
        if rec.get("company") and rec.get("title"): yield rec

def guess_slug(name):
    return "".join(x for x in words(re.sub(r"\(.*?\)", " ", name)) if x != "and")

def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]): sys.exit(__doc__)
    tmap = common.load("tracker_map.json")
    tracker = tracker_io.open_tracker(sys.argv[1] if len(sys.argv) > 1 else None, tmap)
    print(f"Reading your tracker ({tracker.kind}): {tracker.label}")
    skip = {s.lower() for s in tmap.get("skip_statuses", [])}
    jobs = [r for r in read_rows(tracker, tmap["columns"]) if r.get("status", "").lower() not in skip]
    common.save("seen.json", {"_readme": "Jobs already in your tracker, so they are not shown again. Rebuilt by tools/import_tracker.py.",
                              "jobs": [{"company": j["company"], "title": j["title"], "status": j.get("status"),
                                        "url": j.get("link") or None} for j in jobs]})
    data = common.load("companies.json")
    have = {norm_co(c["company"]) for c in data["companies"]}
    added = []
    for j in jobs:
        key = norm_co(j["company"])
        if key and key not in have:
            have.add(key)
            data["companies"].append({"company": j["company"], "guess_slug": guess_slug(j["company"]), "ats": None, "token": None})
            added.append(j["company"])
    common.save("companies.json", data)
    print(f"tracker jobs saved to seen.json: {len(jobs)} | new companies added: {len(added)} | "
          f"companies total: {len(data['companies'])}")
    if added: print("next: python3 collectors/find_boards.py")

if __name__ == "__main__":
    main()
