"""One reader per job-board system. Each yields dicts: title, loc, url, plain, wt, smin, smax.
`wanted(title)` lets a reader skip fetching full details for jobs whose title will be filtered out anyway."""
import re, time, urllib.parse
from common import get, post, strip_html

def greenhouse(token, wanted):
    res = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true") or {}
    for j in res.get("jobs") or []:
        if not wanted(j.get("title", "")): continue
        yield dict(title=j["title"], loc=(j.get("location") or {}).get("name", ""), url=j.get("absolute_url"),
                   plain=strip_html(j.get("content")), wt="", smin=None, smax=None)

def _yearly(v, interval):
    return int(v) if v and "year" in str(interval or "").lower() else None

def lever(token, wanted):
    for j in get(f"https://api.lever.co/v0/postings/{token}?mode=json") or []:
        if not wanted(j.get("text", "")): continue
        sr = j.get("salaryRange") or {}
        yield dict(title=j.get("text", ""), loc=(j.get("categories") or {}).get("location") or "", url=j.get("hostedUrl"),
                   plain=j.get("descriptionPlain") or "", wt=(j.get("workplaceType") or "").lower(),
                   smin=_yearly(sr.get("min"), sr.get("interval")), smax=_yearly(sr.get("max"), sr.get("interval")))

def ashby(token, wanted):
    res = get(f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true") or {}
    for j in res.get("jobs") or []:
        if not wanted(j.get("title", "")): continue
        smin = smax = None
        for comp in ((j.get("compensation") or {}).get("summaryComponents") or []):
            if comp.get("compensationType") == "Salary":
                smin, smax = _yearly(comp.get("minValue"), comp.get("interval")), _yearly(comp.get("maxValue"), comp.get("interval"))
        wt = (j.get("workplaceType") or ("Remote" if j.get("isRemote") else "")).lower()
        yield dict(title=j.get("title", ""), loc=j.get("location") or "", url=j.get("jobUrl"),
                   plain=j.get("descriptionPlain") or "", wt=wt, smin=smin, smax=smax)

def smartrecruiters(token, wanted):
    base = f"https://api.smartrecruiters.com/v1/companies/{token}/postings"
    offset = 0
    while True:
        page = get(f"{base}?limit=100&offset={offset}") or {}
        items = page.get("content") or []
        for it in items:
            if not wanted(it.get("name", "")): continue
            det = get(f"{base}/{it['id']}") or {}
            loc = it.get("location") or {}
            where = loc.get("fullLocation") or ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x)
            secs = ((det.get("jobAd") or {}).get("sections") or {}).values()
            yield dict(title=it.get("name", ""), loc=where,
                       url=det.get("postingUrl") or f"https://jobs.smartrecruiters.com/{token}/{it['id']}",
                       plain=strip_html(" ".join((s or {}).get("text", "") for s in secs)),
                       wt="remote" if loc.get("remote") else "hybrid" if loc.get("hybrid") else "", smin=None, smax=None)
            time.sleep(0.2)
        offset += 100
        if not items or offset >= page.get("totalFound", 0): break

def workable(token, wanted):
    res = get(f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true") or {}
    for j in res.get("jobs") or []:
        if not wanted(j.get("title", "")): continue
        wp = str(j.get("workplace") or "").lower()
        yield dict(title=j.get("title", ""), loc=", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x),
                   url=j.get("url") or j.get("shortlink"), plain=strip_html(j.get("description")),
                   wt="remote" if j.get("telecommuting") or "remote" in wp else "hybrid" if "hybrid" in wp else "",
                   smin=None, smax=None)

def workday_parts(url):
    u = urllib.parse.urlparse(url)
    segs = [s for s in u.path.split("/") if s and not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)]
    return u.netloc, u.netloc.split(".")[0], segs[0]

def workday(url, wanted, search_terms):
    from common import NON_US
    host, tenant, site = workday_parts(url)
    api = f"https://{host}/wday/cxs/{tenant}/{site}"
    found = {}
    for term in search_terms:
        for offset in (0, 20, 40):
            res = post(f"{api}/jobs", {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": term}) or {}
            posts = res.get("jobPostings") or []
            for p in posts:
                if p.get("externalPath") and wanted(p.get("title", "")): found[p["externalPath"]] = p
            time.sleep(0.3)
            if len(posts) < 20: break
    for path, p in found.items():
        info = (get(f"{api}{path}") or {}).get("jobPostingInfo") or {}
        locs = [info.get("location") or p.get("locationsText") or ""] + list(info.get("additionalLocations") or [])
        locs = [l for l in locs if l and not NON_US.search(l)] or locs  # keep US locations of multi-country jobs
        rt = str(info.get("remoteType") or "").lower()
        yield dict(title=info.get("title") or p.get("title", ""), loc="; ".join(l for l in locs if l),
                   url=info.get("externalUrl") or f"https://{host}/{site}{path}", plain=strip_html(info.get("jobDescription")),
                   wt="remote" if "remote" in rt else "hybrid" if "hybrid" in rt else "", smin=None, smax=None)
        time.sleep(0.3)
