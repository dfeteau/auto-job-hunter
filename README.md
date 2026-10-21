# auto-job-hunter

A personal job-search pipeline. It checks company job boards directly, keeps only the jobs that match your criteria, scores them on salary and location, and gives you a ranked shortlist. You then score the shortlist against your resume (with Claude) and log the keepers in your tracker.

**What it does:** Find boards → Collect jobs → Filter → Skip jobs you already track → Score → Shortlist

**Where it looks:** the career sites of the companies on your list, on Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Workday. It does not search LinkedIn, Indeed or other job sites, so keep using those to discover new companies and add them to your list.

Everything runs on your own computer. Nothing is sent anywhere except requests to the job boards' public job lists.

---

## Getting started

### Step 0. What you need

- A Mac, Windows or Linux computer
- **Python 3.10 or newer.** Check by opening Terminal (Mac) or Command Prompt (Windows) and typing `python3 --version` (on Windows, `python --version`). If it's missing, install it from [python.org](https://www.python.org/downloads/).
- A GitHub account if you want your own copy online (optional)

### Step 1. Get your own copy

Pick one:

- **On GitHub:** click **Use this template → Create a new repository**, choose **Private**, then download it with **Code → Download ZIP** (or `git clone`).
- **Without GitHub:** download the ZIP from this page and unzip it.

Keep your copy **private**. Once you add your tracker, the config folder holds your application history.

Open Terminal in the project folder for every command below. On Windows, type `python` wherever you see `python3`.

### Step 2. Set your criteria in `config/profile.json`

This one file holds all of your settings. Every value in it is an example, so go through each section.

| Section | Setting | What it means |
|---|---|---|
| `search` | `titles` | Job titles to look for. A job matches if its title *contains* one of these, so "Data Analyst" also matches "Senior Data Analyst, Marketing". |
| | `excluded_title_words` | Skip titles containing any of these (for example Junior, Intern, Manager). |
| | `excluded_industry_words` | Skip titles containing these (for example "clinical", "pharma"). Leave empty to allow all industries. |
| | `excluded_companies` | Companies never to show. |
| `location` | `home_metro_name`, `home_metro_patterns` | Your metro area and the words that identify it in a job location (city names, state, `, co\\b` for ", CO"). |
| | `accept` | Which job types to keep: `remote`, `hybrid_home`, `onsite_home` (in your metro), `hybrid_other`, `onsite_other` (elsewhere). `true` keeps, `false` drops. |
| | `home_min_salary` | Optional. Minimum salary for hybrid or onsite jobs in your metro (worth the commute). `null` for none. |
| `salary` | `floor_high_end` | Drop jobs whose posted range tops out below this. Jobs with no salary listed are kept. |
| | `tiers_by_min` | Salary points by the low end of the range. More points = better fit. |
| | `unknown_points` | Points when no salary is posted (0 is safest). |
| `scoring` | `location_points` | Points for each location type. |
| | `gate_min` | Minimum Fit Score (0 to 100) to make the shortlist. |
| | `title_rank` | Tie-breaker: which titles you prefer. |
| | `skill_points` | Tie-breaker: keywords in the description you like to see. Never changes the Fit Score. |

**Fit Score** = (salary points + location points) ÷ (top salary points + top location points) × 100.
With the example settings, a remote job paying $130K+ scores 100, a remote job with no salary listed scores 50, and a hybrid job in your metro paying $120K scores 75.

### Step 3. Set up your tracker

- **New tracker:** copy `templates/job_tracker_template.xlsx` (or the `.csv`) somewhere you'll keep it. Its second tab explains each column.
- **Your own tracker:** open `config/tracker_map.json` and put your column headers next to `company`, `title`, `status` and `link`. Set `sheet` to the tab name if it isn't the first tab.

Reading `.xlsx` files needs one package: `pip3 install openpyxl`. CSV trackers need nothing extra.

### Step 4. Build your company list

The pipeline searches only companies on your list. Add them any of these ways:

```bash
python3 tools/import_tracker.py ~/path/to/your_tracker.xlsx     # every company in your tracker
python3 tools/add_companies.py "Acme Corp" "Globex"              # specific companies
python3 tools/add_companies.py --file my_companies.txt           # one name per line
```

`import_tracker.py` also records every job already in your tracker so they never show up as new.

**Large employers on Workday (optional):** open any of their job postings. If the address contains `myworkdayjobs.com`, add the company to `config/workday_seeds.json`:

```json
"seeds": {
  "Acme Corp": "https://acme.wd5.myworkdayjobs.com/Acme_Careers",
  "Globex": null
}
```

Use the part of the address up to the site name, without `/en-US` and without `/job/...`. Use `null` to let the finder guess.

### Step 5. One-time setup run

```bash
python3 init_db.py                    # creates the local database
python3 collectors/find_workday.py    # only if you added Workday seeds
python3 collectors/find_boards.py     # finds each company's job board
```

`find_boards.py` tries several name variations per company, so expect a few minutes per 50 companies. It prints each board it finds. Results are saved, so it only needs to run again when you add companies.

Matches marked `unverified` (Lever and Ashby) can't be name-checked automatically. Open one job link from each to confirm it's the right company. If it isn't, delete that company's `ats` and `token` values in `config/companies.json`.

Companies reported as not found usually use a career site this tool doesn't cover (iCIMS, Taleo, Oracle, SuccessFactors, or their own). Keep checking those by hand or through job sites.

### Step 6. Daily run

```bash
python3 collectors/collect.py         # pull new jobs from every known board
python3 scoring/score.py              # print the ranked shortlist
python3 tools/export_shortlist.py     # optional: CSV in your tracker's format, in exports/
```

Each shortlist line shows: Fit Score | company | title | location | salary | flags.

- `salary unknown`: no pay listed. Check the posting.
- `single figure, check`: only one dollar amount was found, so it may not be the salary.
- `check location`: listed as remote, but the country isn't clear.

Add `--all` to `score.py` to also see jobs below your gate.

### Step 7. Resume Match and tracking

1. Give Claude your resume and the shortlist. [docs/RESUME_MATCH.md](docs/RESUME_MATCH.md) has a prompt to copy.
2. Add the jobs you want to track to your tracker (Status: New).
3. Run `python3 tools/import_tracker.py your_tracker.xlsx` again so they don't come back.

---

## Changing your criteria later

Edit `config/profile.json` and run `python3 scoring/score.py`. Scoring re-applies your title, location, company and tracker rules to everything already collected, so you don't need to collect again. (Adding new titles does need a fresh `collect.py` run to pick up jobs that were skipped before.)

## Files

```
config/
  profile.json          Your criteria: titles, location, salary, scoring
  tracker_map.json      Which tracker columns hold company, title, status, link
  companies.json        Companies to search and their job boards (built by the tools)
  workday_seeds.json    Workday career-site addresses to verify
  seen.json             Jobs already in your tracker (built by import_tracker.py)
collectors/
  collect.py            Daily collection from all boards
  find_boards.py        Finds Greenhouse, Lever, Ashby, SmartRecruiters, Workable boards
  find_workday.py       Verifies and corrects Workday addresses
  sources.py            How each job-board system is read
  common.py             Shared rules: filtering, location, salary, saving
scoring/
  score.py              Fit Score, gate, ranking, shortlist
tools/
  import_tracker.py     Reads your tracker: skip tracked jobs, add new companies
  add_companies.py      Adds companies by name
  export_shortlist.py   Shortlist as a tracker-ready CSV
templates/              Blank tracker (.xlsx and .csv)
docs/RESUME_MATCH.md    How to score the shortlist against your resume with Claude
init_db.py              Creates data/jobs.db
data/jobs.db            Your collected jobs (local only, never uploaded)
```

## Known limits

- US job searches only. Jobs located outside the US are dropped.
- Only companies on your list are searched.
- Board names are guessed from company names. Unusual names may need a manual entry in `companies.json` (`"ats": "greenhouse", "token": "boardname"`).
- Salary is read from the posting text when the board has no pay field. Ranges that combine several locations or levels should be checked.
- LinkedIn, Indeed, Built In and similar sites are not searched.

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: python3` | Install Python from python.org, or use `python` on Windows. |
| `No module named openpyxl` | `pip3 install openpyxl`, or save your tracker as CSV. |
| `Could not find the 'Company' and 'Job Title' headers` | Update `config/tracker_map.json` with your exact header names. |
| `no such table: jobs` | Run `python3 init_db.py` first. |
| A wrong company's jobs appear | Remove that company's `ats` and `token` in `config/companies.json`, or add it to `excluded_companies`. |
| Too few jobs | Add companies, loosen `excluded_title_words`, or set more `accept` options to `true`. |
| Too many jobs | Raise `gate_min` or `floor_high_end`, or narrow `titles`. |
