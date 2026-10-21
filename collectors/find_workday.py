"""Verify and find Workday career-site addresses. Needs internet.
Usage: python3 collectors/find_workday.py [--recheck]

Reads config/workday_seeds.json: company name -> Workday URL, or null to guess from the name.
It tests each URL, then tries common variations (servers wd1/wd3/wd5/wd12 and typical site
names). A URL counts only if Workday's job API answers it. Working URLs are saved to
config/companies.json (ats "workday" + workday_url), adding the company if it is new.

How to find a company's Workday URL: open any of its job postings. If the address looks like
https://acme.wd5.myworkdayjobs.com/en-US/Acme_Careers/job/..., the seed is
https://acme.wd5.myworkdayjobs.com/Acme_Careers
"""
import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import common
from sources import workday_parts
from find_boards import variants

SERVERS = ["wd1", "wd5", "wd3", "wd12"]

def works(url):
    host, tenant, site = workday_parts(url)
    r = common.post(f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                    {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, tries=1)
    time.sleep(0.15)
    return isinstance(r, dict) and "total" in r

def site_names(tenant):
    t = tenant.capitalize()
    return ["External", "Careers", "careers", "External_Careers", f"{t}_Careers", f"{t}Careers", f"{tenant}_careers", t, "Search"]

def find(company, seed, check=works):
    tried = set()
    def attempt(u):
        if u in tried: return None
        tried.add(u)
        return u if check(u) else None
    if seed:
        if attempt(seed): return seed
        _, tenant, site = workday_parts(seed)
        for srv in SERVERS:
            if attempt(f"https://{tenant}.{srv}.myworkdayjobs.com/{site}"): return f"https://{tenant}.{srv}.myworkdayjobs.com/{site}"
        tenants = [tenant]
    else:
        tenants = [v for v, _ in variants(company) if "-" not in v][:2]
    for tenant in tenants:
        for srv in SERVERS:
            for site in site_names(tenant):
                u = f"https://{tenant}.{srv}.myworkdayjobs.com/{site}"
                if attempt(u): return u
    return None

def main():
    recheck = "--recheck" in sys.argv
    seeds = common.load("workday_seeds.json")["seeds"]
    data = common.load("companies.json")
    by_name = {c["company"]: c for c in data["companies"]}
    found = 0
    for name, seed in seeds.items():
        c = by_name.get(name)
        if c is None:
            c = {"company": name, "ats": None, "token": None}; data["companies"].append(c); by_name[name] = c
        if c.get("ats") and c["ats"] != "workday": continue
        if c.get("workday_checked") and not recheck: continue
        url = find(name, seed)
        c["workday_checked"] = True
        if url:
            c.update(ats="workday", workday_url=url); found += 1
            print(f"  + {name} -> {url}", flush=True)
        else:
            print(f"  - {name}: not found (may not use Workday, or uses an unusual address)", flush=True)
        common.save("companies.json", data)
    print(f"Workday sites verified: {found}")

if __name__ == "__main__":
    main()
