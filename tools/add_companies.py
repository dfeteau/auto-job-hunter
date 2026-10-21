"""Add companies you want searched, without a tracker.
Usage: python3 tools/add_companies.py "Acme Corp" "Globex" ...
       python3 tools/add_companies.py --file companies.txt     (one name per line)
Then run: python3 collectors/find_boards.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collectors"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from common import norm_co
from import_tracker import guess_slug

def main():
    args = sys.argv[1:]
    if not args: sys.exit(__doc__)
    if args[0] == "--file":
        names = [l.strip() for l in pathlib.Path(args[1]).expanduser().read_text().splitlines() if l.strip()]
    else:
        names = args
    data = common.load("companies.json")
    have = {norm_co(c["company"]) for c in data["companies"]}
    added = 0
    for n in names:
        if norm_co(n) and norm_co(n) not in have:
            data["companies"].append({"company": n, "guess_slug": guess_slug(n), "ats": None, "token": None})
            have.add(norm_co(n)); added += 1
    common.save("companies.json", data)
    print(f"added {added} | companies total: {len(data['companies'])}")

if __name__ == "__main__":
    main()
