# auto-job-hunter

A personal job-search pipeline. It checks company job boards directly, keeps only the jobs that match your criteria, scores them on salary and location, and gives you a ranked shortlist. Every qualifying job goes into your tracker, where you review it, and an AI assistant can score each one against your resume and learn from your notes.

**What it does:** Find boards → Collect jobs → Filter → Skip jobs you already track → Score → Shortlist

**Where it looks:** the career sites of the companies on your list, on Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Workday. It does not search LinkedIn, Indeed or other job sites, so keep using those to discover new companies and add them to your list.

Everything runs on your own computer. Nothing is sent anywhere except requests to the job boards' public job lists.

---

## Getting started

### Step 0. What you need

- A Mac, Windows or Linux computer
- **Python 3.10 or newer.** Check by opening Terminal (Mac) or Command Prompt (Windows) and typing `python3 --version` (on Windows, `python --version`). If it's missing, install it from [python.org](https://www.python.org/downloads/).
- A GitHub account if you want your own copy online (optional)
- A Google account, only if your tracker is a Google Sheet

### Step 1. Get your own copy

Pick one:

- **On GitHub:** click **Use this template → Create a new repository**, choose **Private**, then download it with **Code → Download ZIP** (or `git clone`).
- **Without GitHub:** download the ZIP from this page and unzip it.

Keep your copy **private**. Once you add your tracker, the config folder holds your application history.

Open Terminal in the project folder for every command below. On Windows, type `python` wherever you see `python3`.

### Step 2. Set your criteria

Run the setup wizard:

```bash
python3 setup_wizard.py
```

It asks about 15 questions (job titles, words to exclude, industries and companies to avoid, your home city and nearby cities, which kinds of remote, hybrid and onsite jobs to keep, your lowest and target salary, your top skills, and how strict the shortlist should be), shows a summary, and writes `config/profile.json`. Press Enter to accept a suggestion. Run it again any time; your previous settings are saved to `config/profile.backup.json`. At the end it offers to set up your tracker (step 3) and, if your company list is short, to find companies for you (step 4).

Industry shortcuts you can type: healthcare, pharma, defense, government, gambling, crypto, insurance. Each expands to a set of keywords, which are checked against the job title, the company name ("Spring Health"), and how the posting describes the company in its opening lines ("FreedomCare is a healthcare company").

**Prefer to edit by hand?** Everything the wizard writes lives in `config/profile.json`:

| Section | Setting | What it means |
|---|---|---|
| `search` | `titles` | Job titles to look for. A job matches if its title *contains* one of these, so "Data Analyst" also matches "Senior Data Analyst, Marketing". |
| | `excluded_title_words` | Skip titles containing any of these whole words (for example Junior, Intern, Manager). Whole words only, so "Intern" does not skip "Internal Audit Analyst". |
| | `excluded_title_exceptions` | Phrases kept even though they contain an excluded word, for example "Senior Associate" when "Associate" is excluded. |
| | `excluded_industry_words` | Skip jobs where one of these appears in the title, the company name, or the posting's opening description of the company (for example "clinical", "pharma"). Benefits text further down, like "Healthcare Plan", doesn't count. Leave empty to allow all industries. |
| | `exclude_clearance_required` | `true` skips postings that require a security clearance ("Clearance Required: None" is fine). Set `false` if you hold one. |
| | `excluded_companies` | Companies never to show. |
| `location` | `home_metro_name`, `home_metro_patterns` | Your metro area and the words that identify it in a job location (city names, state, `, co\\b` for ", CO"). |
| | `accept` | Which job types to keep: `remote`, `hybrid_home`, `onsite_home` (in your metro), `hybrid_other`, `onsite_other` (elsewhere). `true` keeps, `false` drops. |
| | `home_min_salary` | Optional. Minimum salary for hybrid or onsite jobs in your metro (worth the commute). `null` for none. |
| | (note) | Home-area jobs that don't state remote, hybrid or onsite count as hybrid and are flagged `check if hybrid`. Jobs that say onsite count as onsite. |
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

Your tracker is the spreadsheet where you log applications. It can be an **Excel file**, a **Google Sheet**, or a
**CSV file**. The setup wizard asks which one you use and sets it up. It offers this at the end of step 2, or you
can run just this part any time:

```bash
python3 setup_wizard.py --tracker
```

Your answers are saved in `config/tracker_map.json` (where the tracker is, which tab, and your column names).
After that, every tool uses your tracker without being told where it is.

**Excel**

- **Starting fresh?** The wizard creates `tracker/my_job_tracker.xlsx` from the template. Its second tab explains
  each column.
- **Already tracking your applications?** Bring them over, so your history and every company in it are included
  from day one:

  ```bash
  python3 tools/migrate_tracker.py ~/path/to/your_tracker.xlsx --dry-run   # shows how your columns will be matched
  python3 tools/migrate_tracker.py ~/path/to/your_tracker.xlsx             # creates tracker/my_job_tracker.xlsx
  ```

  It matches common column names automatically ("Employer", "Position", "Applied On", "URL", "Stage" and so on),
  standardizes statuses (keeping your original wording in Assistant Notes when it had to guess), converts dates,
  keeps links, and copies any extra columns to the right. A CSV export works too. Your original file is never
  changed. Use `--sheet "Tab name"` if your tracker isn't on the first tab.
- **Prefer to keep your own tracker as it is?** Point the wizard at it. If it can't find "Company" and "Job Title"
  headers, it asks for your column names.
- Excel needs one package: `pip3 install openpyxl`.

**Google Sheets:** see [Using Google Sheets](#using-google-sheets) below. About 10 minutes, once.

**CSV** (for example an export from Notion or Airtable): the pipeline reads it to skip jobs you already track. It
doesn't write CSV files, so each day `tools/export_shortlist.py` saves the new jobs as rows you can paste in.

The `tracker/` folder is excluded from git, so your tracker isn't uploaded by accident.

#### Using Google Sheets

The pipeline signs in to Google with a **service account**: a robot Google account that can open only the sheets
you share with it. You set it up once.

1. **Create a Google Cloud project and turn on the Sheets API.**
   - Go to [console.cloud.google.com](https://console.cloud.google.com) and sign in with your Google account.
   - Click the project picker at the top, then **New Project**. Name it (for example `job-hunter`) and click **Create**.
   - With that project selected, open **APIs & Services → Library**, search for **Google Sheets API**, and click
     **Enable**.
2. **Create a service account and download its key.**
   - Open **APIs & Services → Credentials → Create credentials → Service account**. Give it a name and click
     **Done** (the optional steps can be skipped).
   - Click the new service account, open the **Keys** tab, then **Add key → Create new key → JSON**. A key file
     downloads.
   - Move that file into this project's `config` folder and rename it `google_service_account.json`. It's excluded
     from git. Treat it like a password: anyone with it can edit the sheets you share with the service account.
   - Some work or school Google accounts don't allow keys. If yours refuses, use a personal Google account.
3. **Share your sheet with the service account.** Open the key file and copy the `client_email` value (it ends in
   `iam.gserviceaccount.com`; the wizard also shows it). In your Google Sheet, click **Share**, paste it, choose
   **Editor**, and send.
4. **Install the package:** `pip3 install gspread`
5. **Run the wizard:** `python3 setup_wizard.py --tracker`, choose **Google Sheets**, and paste your sheet's link
   from the browser address bar. It tests the connection. If the tab is empty, it offers to add the template's
   column headers.

**Moving an Excel tracker to Google Sheets?** If it isn't in the template's layout yet, run `migrate_tracker.py`
first (above). Then in Google Sheets choose **File → Import → Upload**, pick the `.xlsx`, and run the wizard.

With a Google Sheet, `add_to_tracker.py` writes new rows straight into the sheet (dates as dates, a clickable
Link). Before each change it saves a CSV copy in `tracker/backups/`, and Google keeps its own history under
**File → Version history**.

### Step 4. Build your company list

The pipeline searches only companies on your list. Add them any of these ways:

```bash
python3 tools/import_tracker.py                                 # every company in your tracker
python3 tools/add_companies.py "Acme Corp" "Globex"              # specific companies
python3 tools/add_companies.py --file my_companies.txt           # one name per line
python3 tools/add_companies.py --file list.csv --source "Built In NYC" --dry-run   # a list from a job site
```

`import_tracker.py` also records every job already in your tracker so they never show up as new.

**Starting with no list, or want companies you've never heard of?** Let the pipeline find them:

```bash
python3 tools/discover_companies.py              # find boards, check them, add companies with matching jobs
python3 tools/discover_companies.py --dry-run    # same, but only reports what it would add
```

It reads the index of [Common Crawl](https://commoncrawl.org), a free public archive of the web, to find
Greenhouse, Lever and Ashby job boards (tens of thousands of them). It then reads each board's current jobs once
and adds every company with at least one job that passes your title, location and industry rules, with its board
already filled in. The setup wizard offers this when your list is short.

- The first run is slow, often an hour or more, because the index is large. Ctrl+C is safe: run the same command
  again and it continues where it stopped. `--max-pages 20` makes a quicker, partial first pass.
- Run it again about once a month. Boards that had no match are checked again after 30 days
  (`--recheck-days`), so companies that start hiring for your titles get added.
- Lever and Ashby don't report a company name, so those companies are named from their board name (for example
  "Zeta Labs") and marked `unverified`. Fix any odd names in `config/companies.json`.
- Progress is saved in `data/discovery/`, which isn't uploaded to git.
- It only finds companies on Greenhouse, Lever and Ashby. Companies on Workday and other systems still come from
  your tracker or `add_companies.py`.

**Find companies on any job site, with an AI assistant.** Sites like Built In, Wellfound, Indeed, Dice,
ZipRecruiter or your city's tech job board aren't searched by the pipeline, but they're a good source of
employers to add. Ask your assistant (Claude, ChatGPT or another) to "collect companies from <site> for my
titles". AGENTS.md walks it through the process:

1. It searches the site for your titles and locations, using a browser, a connector, or results pages you paste in.
2. It keeps employers with a recent, relevant listing you could take, and drops recruiters, staffing firms,
   industries you avoid and companies already on your list.
3. It shows you the list. Nothing is added until you approve it.
4. It saves the approved companies to a CSV and runs `add_companies.py --file ... --source "<site>"` (dry run
   first). When the site shows apply links that go to Greenhouse, Lever, Ashby, SmartRecruiters, Workable or
   Workday, the company's job board is filled in directly.
5. You run `find_boards.py` and `run_daily.py` as usual.

You can do it without an assistant too: put the companies in a text file (one per line) or a CSV with a
`company` column (and optionally a `link` column with an apply link), then run the `add_companies.py` command
above. Sites differ in how much they show without signing in, and some show a security check when browsed
quickly; the assistant is told to go slowly and stop at any check rather than get around it.

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
python3 run_daily.py
```

This collects from every known board, scores the results, and saves a report to `reports/report_YYYY-MM-DD.md`
(set `JOB_REPORT_DIR` to save it somewhere else, such as a folder you share with Claude). The report shows:

- **Summary:** jobs found (titles matching your search), excluded by your criteria, already in your tracker, and the number that qualify for your tracker. The numbers add up, so you can see where every job went.
- **Excluded, by reason:** for example "Outside the US: 8", "Onsite in home area: 5", "Pay tops out under $90,000: 3".
- **Qualifying jobs:** Fit Score, link, location, pay and flags.
- **Excluded jobs (detail):** every excluded job and why, so you can spot a rule that's too strict.
- **Job descriptions** of the qualifying jobs, ready for Resume Match (step 7).

`python3 run_daily.py --report` rebuilds the report without collecting again. The individual steps still work on their own:

```bash
python3 collectors/collect.py         # pull new jobs from every known board (add --debug to see every decision)
python3 scoring/score.py              # print the ranked shortlist (add --all to include jobs below your gate)
python3 tools/add_to_tracker.py       # add every qualifying job to your tracker (Status New)
python3 tools/export_shortlist.py     # CSV trackers: the shortlist in your tracker's format, in exports/
```

Flags you may see on a job:

- `salary unknown`: no pay listed. Check the posting.
- `single figure, check`: only one dollar amount was found, so it may not be the salary.
- `check location`: listed as remote, but the country isn't clear.
- `check if hybrid`: in your home area, but the posting doesn't say remote, hybrid or onsite. It is scored like a hybrid job.

### Step 7. Add to your tracker, review, and tune

You don't pick jobs one by one before they're tracked. Everything that qualifies goes in, and you review it there.

1. **Add every qualifying job:** `python3 tools/add_to_tracker.py` (Excel or Google Sheets). It backs up your
   tracker to `tracker/backups/`, adds each job with Status New, and updates the list of tracked jobs so they don't
   come back. `--dry-run` shows what it would add. CSV tracker? Use `tools/export_shortlist.py` and paste.
2. **Resume Match:** your assistant fills in Resume Match (0 to 100) and writes its reasoning and any flags in the
   **Assistant Notes** column. Without an assistant, [docs/RESUME_MATCH.md](docs/RESUME_MATCH.md) has a prompt to copy.
3. **Review:** go through the New rows when it suits you. Set Status (Applied, Did Not Apply, Saved, ...) and
   write your reasons in **Notes**. That column is yours; the assistant never writes there.
4. **Tune:** when you're done reviewing, tell your assistant. It reads your Notes, asks about patterns (for
   example, several jobs skipped as "too junior"), and suggests changes to `config/profile.json`.

---

## Using an AI assistant (Claude, ChatGPT and others)

An assistant can walk you through setup, carry over your existing tracker, read your daily report, score
Resume Match, and keep your tracker current. This repository includes what it needs:

- **`AGENTS.md`**: a complete guide for AI assistants. Coding assistants that open this folder (Cursor,
  Copilot and others) read it automatically. In a chat assistant, upload it at the start of the conversation.
- **`CLAUDE.md`**: Claude Code loads this automatically when you open the folder.
- **`skills/job-search-assistant/`**: a Claude skill. Install it (zip the folder and upload it under
  Customize, Skills in Claude) so any Claude conversation knows how to help with this project.

A good first message: *"Help me set up auto-job-hunter. Here's my resume and my current job tracker."* The
assistant will migrate your tracker, which also fills the company list, and walk you through your criteria.

---

## Changing your criteria later

Edit `config/profile.json` and run `python3 scoring/score.py`. Scoring re-applies your title, location, company and tracker rules to everything already collected, so you don't need to collect again. (Adding new titles does need a fresh `collect.py` run to pick up jobs that were skipped before.)

## Files

```
config/
  profile.json          Your criteria: titles, location, salary, scoring
  tracker_map.json      Where your tracker is (Excel, Google Sheets or CSV) and which columns hold each field
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
  migrate_tracker.py    Copies an existing tracker (any layout) into the template
  import_tracker.py     Reads your tracker: skip tracked jobs, add new companies
  add_companies.py      Adds companies by name or from a list collected on a job site
  discover_companies.py Finds Greenhouse, Lever and Ashby companies with jobs matching your titles
  add_to_tracker.py     Adds every qualifying job to your Excel or Google Sheets tracker (Status New)
  tracker_io.py         Reads and writes Excel, CSV and Google Sheets trackers
  export_shortlist.py   Shortlist as a tracker-ready CSV
templates/              Blank tracker (.xlsx and .csv)
docs/RESUME_MATCH.md    How to score the shortlist against your resume with Claude
setup_wizard.py         Asks your criteria and which tracker you use; writes config/profile.json and tracker_map.json
AGENTS.md, CLAUDE.md    Guide for AI assistants (Claude, ChatGPT, Cursor and others)
skills/                 Claude skill for this project
run_daily.py            One-command daily run and report
init_db.py              Creates data/jobs.db
data/jobs.db            Your collected jobs (local only, never uploaded)
```

## Known limits

- US job searches only. Jobs located outside the US are dropped.
- Only companies on your list are searched. `tools/discover_companies.py` fills the list with Greenhouse, Lever and Ashby companies that have matching jobs.
- Board names are guessed from company names. Unusual names may need a manual entry in `companies.json` (`"ats": "greenhouse", "token": "boardname"`).
- Salary is read from the posting text when the board has no pay field. Ranges that combine several locations or levels should be checked.
- LinkedIn, Indeed, Built In and similar sites are not searched directly. You can use them to find companies to add (Step 4, "Find companies on any job site").

## Troubleshooting

| Problem | Fix |
|---|---|
| `command not found: python3` | Install Python from python.org, or use `python` on Windows. |
| `No module named openpyxl` | `pip3 install openpyxl`, or save your tracker as CSV. |
| `Could not find the 'Company' and 'Job Title' headers` | Run `python3 setup_wizard.py --tracker` and enter your column names, or edit `config/tracker_map.json`. Check the tab name too. |
| `Google Sheets needs one package` | `pip3 install gspread` |
| `Google service account key not found` | Save the key file as `config/google_service_account.json` ([Using Google Sheets](#using-google-sheets), step 2). |
| `Couldn't open the Google Sheet` | Share the sheet with the service account's email as an Editor (step 3), and check the link in `config/tracker_map.json`. |
| `The Google Sheets API isn't turned on` | Enable the Google Sheets API in the same Google Cloud project as the key (step 1). Changes can take a few minutes. |
| `no such table: jobs` | Run `python3 init_db.py` first. |
| A wrong company's jobs appear | Remove that company's `ats` and `token` in `config/companies.json`, or add it to `excluded_companies`. |
| Too few jobs | Check the report's "Excluded, by reason" table. Run `python3 tools/discover_companies.py`, add companies, loosen `excluded_title_words`, or set more `accept` options to `true`. `python3 collectors/collect.py --debug` shows every decision. |
| Too many jobs | Raise `gate_min` or `floor_high_end`, or narrow `titles`. |

## What's new

See [CHANGELOG.md](CHANGELOG.md) for what changed in each version.

## License

MIT. Free to use, change and share. See [LICENSE](LICENSE).
