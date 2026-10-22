"""Shared helpers: settings, HTTP, text cleanup, location and salary parsing, filtering, saving."""
import json, re, sys, time, html, pathlib, sqlite3, datetime, collections, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = ROOT / "config"
DB = ROOT / "data" / "jobs.db"
UA = {"User-Agent": "auto-job-hunter/1.0"}

def load(name):
    return json.loads((CFG / name).read_text())

def save(name, data):
    (CFG / name).write_text(json.dumps(data, indent=1, ensure_ascii=False))

PROFILE = load("profile.json")

# ---------- HTTP ----------

def get(url, tries=3, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(5 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None

def post(url, body, tries=3):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**UA, "Content-Type": "application/json", "Accept": "application/json"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(5 * (i + 1)); continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None

# ---------- text ----------

def strip_html(s):
    s = re.sub(r"<style.*?</style>", " ", html.unescape(s or ""), flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", s).split())

def norm_co(name):
    n = re.sub(r"\(.*?\)", "", str(name or "").lower())
    n = re.sub(r"\b(inc|llc|llp|corp|corporation|co|company|ltd|group|holdings|the)\b\.?", "", n)
    return re.sub(r"[^a-z0-9]", "", n)

def norm_title(t):
    t = re.sub(r"\(.*?\)", " ", str(t or "").lower())
    t = re.sub(r"[‐-―]", "-", t)
    return " ".join(t.split())

def salary(text):
    """Best-effort annual salary range from dollar figures in a description."""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\$\s?(\d{2,3},\d{3})", text or "")]
    nums = [n for n in nums if 30000 <= n <= 600000]
    if not nums: return None, None, None
    lo, hi = min(nums), max(nums)
    return lo, hi, ("single figure, check" if lo == hi else None)

# ---------- location ----------

NON_US = re.compile(
    r"\b(canada|toronto|vancouver|montreal|ontario|british columbia|quebec|emea|europe|uk|united kingdom|london|"
    r"scotland|edinburgh|ireland|dublin|india|bengaluru|bangalore|hyderabad|pune|mumbai|apac|latam|mexico|brazil|"
    r"sao paulo|argentina|buenos aires|colombia|bogota|chile|peru|uruguay|costa rica|germany|berlin|munich|france|paris|"
    r"spain|madrid|barcelona|poland|warsaw|krakow|portugal|lisbon|netherlands|amsterdam|belgium|brussels|luxembourg|"
    r"switzerland|zurich|geneva|austria|vienna|czech|prague|hungary|budapest|greece|athens|croatia|estonia|latvia|"
    r"lithuania|israel|tel aviv|singapore|japan|tokyo|australia|sydney|new zealand|philippines|romania|serbia|bulgaria|"
    r"ukraine|china|korea|taiwan|hong kong|vietnam|thailand|malaysia|indonesia|pakistan|bangladesh|dubai|uae|"
    r"united arab emirates|abu dhabi|saudi arabia|riyadh|qatar|doha|egypt|nigeria|kenya|south africa|cape town|"
    r"johannesburg|turkey|italy|sweden|denmark|norway|finland)\b", re.I)
US_TOK = re.compile(r"\b(us|usa|u\.s\.|united states|america)\b", re.I)
US_STATE = re.compile(r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|"
                      r"NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b")
HOME = re.compile("|".join(PROFILE["location"]["home_metro_patterns"]) or r"$^", re.I)
ONSITE = re.compile(r"\b(on-?site|in[- ]office|in the office|5 days a week|five days a week)\b", re.I)
CLEARANCE = re.compile(r"clearance\s*required\s*:?\s*(?!none|n/a|no\b)(yes|secret|top|ts|public|active|dod|\w)"
    r"|\b(active|current|existing|must (?:have|hold|possess)|ability to obtain|able to obtain|eligible (?:for|to obtain))\b[^.]{0,50}"
    r"\b(secret|ts/sci|top secret|security clearance|public trust)\b", re.I)

def needs_clearance(text):
    """True if the posting requires a security clearance ("Clearance Required: None" does not count)."""
    return bool(CLEARANCE.search(text or ""))

def classify(loc, plain="", workplace=""):
    """Returns remote_us, remote_unknown, us_unspecified, hybrid_home, home_unclear, onsite_home, hybrid_other, onsite_other or non_us.
    workplace is the source's own remote/hybrid label when it has one."""
    l = (loc or "").strip(); ll = l.lower(); wt = (workplace or "").lower()
    if NON_US.search(l): return "non_us"
    if "remote" in ll or wt == "remote":
        if US_TOK.search(l) or US_STATE.search(l) or ll in ("", "remote", "us remote", "remote - us") or HOME.search(l):
            return "remote_us"
        return "remote_unknown"
    if re.search(r"any location|anywhere", l, re.I): return "us_unspecified"
    hybrid = "hybrid" in ll or wt == "hybrid" or "hybrid" in (plain or "")[:3000].lower()
    if HOME.search(l):
        if hybrid: return "hybrid_home"
        if wt in ("onsite", "on-site") or ONSITE.search(l) or ONSITE.search((plain or "")[:3000]): return "onsite_home"
        return "home_unclear"   # posting doesn't say: treated as hybrid, flagged "check if hybrid"
    return "hybrid_other" if hybrid else "onsite_other"

LOC_GROUP = {"remote_us": "remote", "remote_unknown": "remote", "us_unspecified": "remote",
             "hybrid_home": "hybrid_home", "home_unclear": "hybrid_home", "onsite_home": "onsite_home",
             "hybrid_other": "hybrid_other", "onsite_other": "onsite_other", "non_us": None}

# ---------- filtering and saving ----------

DEFAULT_TITLE_EXCEPTIONS = ["senior associate", "sr. associate", "sr associate", "associate principal",
                            "associate director", "associate vice president"]
LOCATION_REASON = {"non_us": "Outside the US", "onsite_home": "Onsite in home area", "hybrid_home": "Hybrid in home area not accepted",
                   "home_unclear": "Home area (arrangement not stated) not accepted", "hybrid_other": "Hybrid outside home area",
                   "onsite_other": "Onsite outside home area", "remote_us": "Remote not accepted",
                   "remote_unknown": "Remote not accepted", "us_unspecified": "Remote not accepted"}
DEBUG = "--debug" in sys.argv

class Filter:
    """Applies the profile's title, industry, company, clearance, location and already-tracked rules,
    and counts what happened to every job for the daily report."""
    def __init__(self):
        s = PROFILE["search"]
        self.titles = [t.lower() for t in s["titles"]]
        self.bad_title = [w.lower() for w in s["excluded_title_words"]]
        self.exceptions = [e.lower() for e in s.get("excluded_title_exceptions", DEFAULT_TITLE_EXCEPTIONS)]
        words = [re.escape(w) for w in s.get("excluded_industry_words", [])]
        self.industry = re.compile("|".join(words), re.I) if words else None
        self.no_clearance = s.get("exclude_clearance_required", True)
        self.skip_cos = {norm_co(x) for x in s.get("excluded_companies", [])}
        self.accept = PROFILE["location"]["accept"]
        self.seen = {norm_co(j["company"]) + "|" + norm_title(j["title"]) for j in load("seen.json")["jobs"]}
        self.counts = {"kept": 0, "already_tracked": 0}
        self.stats = dict(boards=0, found=0, excluded=collections.Counter(), details=[])

    def title_match(self, title):
        tl = title.lower()
        return any(t in tl for t in self.titles)

    def title_excluded(self, title):
        """Whole words only (so "Intern" doesn't catch "Internal"); exception phrases are ignored first."""
        tl = " ".join(title.lower().split())
        for e in self.exceptions: tl = tl.replace(e, " ")
        return any(re.search(r"\b" + re.escape(w) + r"\b", tl) for w in self.bad_title)

    def wants_title(self, title):
        """Quick check used by the readers before fetching full details."""
        return self.title_match(title)

    def skip_company(self, c):
        return c.get("skip") or norm_co(c["company"]) in self.skip_cos

    def location_ok(self, rt):
        g = LOC_GROUP.get(rt)
        return bool(g) and self.accept.get(g, False)

    def tracked(self, company, title):
        return norm_co(company) + "|" + norm_title(title) in self.seen

    def why_not(self, company, title, loc, rt, plain):
        """Reason a job is excluded by the collection rules, or None."""
        if self.title_excluded(title): return "Excluded title word"
        if self.industry and self.industry.search(title): return "Excluded industry word"
        if not self.location_ok(rt): return LOCATION_REASON.get(rt, "Location not accepted")
        if self.no_clearance and needs_clearance(plain): return "Security clearance required"
        return None

    def save_stats(self, source="all"):
        d = STATS_DIR; d.mkdir(parents=True, exist_ok=True)
        (d / f"{source}.json").write_text(json.dumps(dict(
            source=source, date=datetime.date.today().isoformat(), boards=self.stats["boards"],
            found=self.stats["found"], tracked=self.counts["already_tracked"], kept=self.counts["kept"],
            excluded=dict(self.stats["excluded"]), details=self.stats["details"]), indent=1))

STATS_DIR = ROOT / "data" / "run_stats"

def connect():
    return sqlite3.connect(DB)

def save_job(con, flt, company, source, job):
    """job: dict(title, loc, url, plain, wt, smin, smax). Returns True if stored."""
    title = " ".join((job.get("title") or "").split())
    if not job.get("url") or not flt.title_match(title): return False
    flt.stats["found"] += 1
    rt = classify(job.get("loc"), job.get("plain"), job.get("wt"))
    reason = flt.why_not(company, title, job.get("loc"), rt, job.get("plain"))
    if reason:
        flt.stats["excluded"][reason] += 1
        flt.stats["details"].append([reason, company, title, job.get("loc") or ""])
        if DEBUG: print(f"      - {title} | {(job.get('loc') or '')[:60]} | {reason}", flush=True)
        return False
    if flt.tracked(company, title):
        flt.counts["already_tracked"] += 1
        if DEBUG: print(f"      = {title} | already in tracker", flush=True)
        return False
    if DEBUG: print(f"      + {title} | {(job.get('loc') or '')[:60]} | {rt}", flush=True)
    smin, smax, sflag = job.get("smin"), job.get("smax"), None
    if smin is None: smin, smax, sflag = salary(job.get("plain"))
    elif smin == smax: sflag = "single figure, check"
    flags = [f for f in ["salary unknown" if smin is None else None, sflag,
             "check location" if rt in ("remote_unknown", "us_unspecified") else None,
             "check if hybrid" if rt == "home_unclear" else None] if f]
    today = datetime.date.today().isoformat()
    con.execute("""INSERT INTO jobs (company,title,source,location,remote_type,salary_min,salary_max,url,description,
        discovered_date,last_seen_date,flags,dedupe_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(url) DO UPDATE SET last_seen_date=excluded.last_seen_date""",
        (company, title, source, job.get("loc") or "", rt, smin, smax, job["url"], (job.get("plain") or "")[:20000],
         today, today, "; ".join(flags) or None, f"{norm_co(company)}|{norm_title(title)}"))
    flt.counts["kept"] += 1
    return True
