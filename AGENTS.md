# Guide for AI assistants

This file is for AI assistants (Claude, ChatGPT, Copilot, Cursor and others) helping someone set up and use
auto-job-hunter. Read it fully before helping. The person-facing guide is `README.md`; this file tells you how
to run the setup conversation, what each part does, and the rules to follow.

## What this project does

auto-job-hunter checks the job boards of companies the person cares about (Greenhouse, Lever, Ashby,
SmartRecruiters, Workable, Workday), keeps only jobs that match their criteria, scores them on salary and
location (**Fit Score**), and produces a daily report. You then score the qualifying jobs against their resume
(**Resume Match**). Every qualifying job goes into their tracker; they review the rows, and their notes
tell you how to tune the search.

```
setup_wizard.py ─> config/profile.json          (their criteria)
tracker ─> tools/import_tracker.py ─> config/seen.json + config/companies.json
collectors/find_boards.py, find_workday.py ─> job boards for each company (one-time, then as companies are added)
run_daily.py ─> collect ─> score ─> reports/report_YYYY-MM-DD.md
tools/add_to_tracker.py ─> every qualifying job added to the tracker (Status New)
you ─> Resume Match + Assistant Notes on the new rows ─> they review, set Status, write Notes
you ─> review pass: read their Notes, ask questions, suggest profile.json changes
```

It does not search LinkedIn, Indeed or other job sites. Jobs found there can be handled by hand (see
"Jobs they find elsewhere").

## What you can do depends on your tool

- **You can run commands and read files** (Claude Code, Cursor, Copilot agent mode, and similar): run the
  scripts yourself, read the report directly, and add and annotate rows as described below.
- **You can only chat** (a chat window with file uploads): guide them to run each command, ask them to paste
  output or upload `reports/report_YYYY-MM-DD.md` and their tracker. They run `tools/add_to_tracker.py`;
  you give them the Resume Match and Assistant Notes values to paste in.
- The collectors need internet access to the job boards. If your environment blocks it, the person runs them
  on their own computer.

## First conversation: setup checklist

Go one step at a time and confirm before moving on. Keep questions short.

1. **Goal.** Ask what roles they're targeting and roughly where (remote, a home city, or both).
2. **Resume.** Ask for their current resume. You need it for Resume Match. Tell them not to save it inside the
   repo, so it can't be committed by accident.
3. **Existing tracker.** Ask: "Do you already track your applications somewhere (a spreadsheet, a CSV, a Notion
   or Google Sheets export)? If so, share it and I'll carry everything over."
   - **They have one: migrate it (recommended).** Their history fills the new tracker, and every company in it
     goes onto the list the pipeline searches.
     - If you can run commands: `python3 tools/migrate_tracker.py their_file.xlsx --dry-run`, show them how
       their columns were matched, fix anything wrong (rename a header in a copy, or pass `--sheet`), then run
       it without `--dry-run`. It writes `tracker/my_job_tracker.xlsx` and never changes their original.
     - If you can't run commands: read their file and produce rows in the template's columns (below), mapping
       statuses with the table below and keeping their original status text in Assistant Notes when you had to guess.
       Ask them to paste the rows into a copy of `templates/job_tracker_template.xlsx`.
     - Then: `python3 tools/import_tracker.py`. This records every job they've
       already seen (so it's never suggested again) and adds every company to `config/companies.json`.
   - **They'd rather keep their own tracker as is:** that works too. Edit `config/tracker_map.json` so
     `company`, `title`, `status` and `link` name their exact column headers (the wizard asks for them), then run
     `import_tracker.py`. Their tracker needs at least a company column and a job title column.
   - **They don't have one:** `python3 setup_wizard.py --tracker` creates `tracker/my_job_tracker.xlsx` from the
     template, or adds the template headers to an empty Google Sheet.
   - **Excel, Google Sheets or CSV:** ask which they use. `python3 setup_wizard.py --tracker` records it in
     `config/tracker_map.json`; after that the tools need no path. Google Sheets needs a one-time service account
     (README.md, "Using Google Sheets"); walk them through it and never ask them to paste the key file's contents
     into the chat. CSV trackers are read only; use `tools/export_shortlist.py` for new rows.
4. **Criteria.** Run `python3 setup_wizard.py` with them, or ask its questions yourself and write
   `config/profile.json`: job titles (most wanted first), title words that rule a job out, industries and
   companies to avoid, whether they hold a security clearance, home city and nearby cities, which job types to
   keep (remote, hybrid nearby, onsite nearby, hybrid elsewhere, onsite elsewhere), minimum salary for a
   commute, lowest salary they'd consider, target salary, top skills, and the shortlist's minimum Fit Score
   (50 is a good default). Show them the summary before saving.
5. **More companies.** If their list is short (or empty), offer `python3 tools/discover_companies.py`: it finds
   Greenhouse, Lever and Ashby boards in the Common Crawl index and adds companies that currently have a job
   passing their rules. The first run can take an hour or more and is safe to stop and restart; `--dry-run`
   reports without changing anything. Lever and Ashby names come from the board name, so glance at those.
   Also ask for 10 to 30 companies they'd love to work for that aren't in their tracker yet:
   `python3 tools/add_companies.py "Company A" "Company B"`.
6. **Large employers on Workday (optional).** For big companies, ask them to open one of the company's job
   postings. If the address contains `myworkdayjobs.com`, add it to `config/workday_seeds.json` as
   `"Company": "https://tenant.wd5.myworkdayjobs.com/SiteName"` (up to the site name, without `/en-US` or
   `/job/...`). Use `null` to let the finder guess.
7. **One-time setup run:** `python3 init_db.py`, then `python3 collectors/find_workday.py` (only if they added
   Workday seeds), then `python3 collectors/find_boards.py`. The board finder takes a few minutes per 50
   companies. Matches marked `unverified` (Lever, Ashby) should be spot-checked: open one job link to confirm
   it's the right company.
8. **First daily run:** `python3 run_daily.py`, then go through the report together (next section).

## Daily routine

Don't ask the person to approve jobs one at a time. With 25 qualifying jobs that would mean 25 answers.
Everything that qualifies goes into the tracker, and they review it there at their own pace.

1. They run `python3 run_daily.py` (or you do). It saves `reports/report_YYYY-MM-DD.md`.
2. Read the report:
   - **Summary:** found, excluded by their criteria, already in their tracker, qualifying. These add up.
   - **Excluded, by reason** and the **detail** table: if a reason looks too strict (for example many good jobs
     dropped as "Onsite in home area"), point it out and offer the matching `profile.json` change.
     "Excluded industry word" means one of their `excluded_industry_words` appeared in the title, the company
     name, or the posting's opening description of the employer ("X is a healthcare company").
3. **Add every qualifying job:** `python3 tools/add_to_tracker.py` (Excel or Google Sheets). It backs up
   the tracker, adds each job with Status `New`, and updates `seen.json` so they aren't suggested again.
4. **Score and annotate the new rows:** fill in Resume Match (next section) and write one or two lines in
   **Assistant Notes**: best overlap, biggest gap, and anything to check (flags such as `salary unknown`,
   `check location`, `check if hybrid`, a previous application at the same company, an industry they avoid).
   Use the job descriptions at the end of the report.
5. **Give them a short summary,** not a question per job: how many were added, the top few by Resume Match
   with one line each, and anything that needs their attention. Then let them review in the tracker.
6. **They review:** they set Status (Applied, Did Not Apply, Saved, ...) and write their reasons in **Notes**.
7. **Review pass:** when they say they're done reviewing, read Status and Notes on the rows since the last
   review and look for patterns: the same reason for skipping several jobs ("too junior", "onsite",
   "pay too low", "agency recruiter"), companies or industries they keep passing on, or titles they apply to
   that score low. Ask them short questions about what you see, then suggest specific `profile.json` changes
   (title words, industries, companies, location, salary, Fit Score gate) and make them only after they agree.
8. Later, when they apply, get rejected, interview or get an offer, update the row's Status and dates if they
   ask you to.

## Resume Match

Score 0 to 100: how well their actual experience matches what the job requires. Weigh required
qualifications over nice-to-haves. Never invent experience.

| Score | Meaning |
|---|---|
| 85 to 100 | Strong: most requirements are clear strengths on the resume |
| 70 to 84 | Good: core skills match, one or two real gaps |
| 50 to 69 | Partial: some overlap, but a required skill or domain is missing |
| below 50 | Weak: the role needs things the resume doesn't show |

`docs/RESUME_MATCH.md` has the full prompt.

## Template tracker columns

`Date Added, Company, Job Title, Location, Work Type, Salary Range, Salary Min, Source, Link, Date Applied,
Status, Resume Match, Fit Score, Notes, Assistant Notes` (sheet "Applications", headers in row 1).

- **Notes** belong to the person. **Assistant Notes** are yours: Resume Match rationale, flags, and anything
  the tools record (such as an original status during migration). If their tracker has no Assistant Notes
  column, `add_to_tracker.py` adds one after their last column.

- **Status values:** New, Saved, Applied, Did Not Apply, Rejected, Interviewing, Second Round, Offer, Withdrawn.
- **Work Type values:** Remote, Hybrid - Home Metro, Onsite - Home Metro, Hybrid - Other, Onsite - Other.
- **Status mapping when migrating:** phone screen, recruiter call, assessment and take-home all map to
  Interviewing; final, panel and 2nd round map to Second Round; declined, not selected, no response, closed
  and filled map to Rejected; wishlist, bookmarked and to-apply map to Saved; submitted and in review map to
  Applied. A blank status becomes Applied if there's an application date, otherwise New.

## Jobs they find elsewhere (LinkedIn, Indeed, referrals)

Ask them to paste the description or save the page and share it. Check it against the tracker, score Fit
(using `profile.json`) and Resume Match, and add it with Status `New` and your notes in Assistant Notes. Then add the company with `add_companies.py`
and run `find_boards.py`, so future postings there are found automatically.

## Rules

- **Never apply to jobs, contact employers or recruiters, or send messages for them** without their explicit
  go-ahead for that specific action.
- **Their tracker is theirs.** Don't delete or reorder rows, and don't overwrite what they wrote. Never write
  in their Notes column; put your notes in Assistant Notes. Adding qualifying jobs with `add_to_tracker.py`
  and filling Resume Match and Assistant Notes on those rows is expected; ask before any other change.
  Make a backup copy before any bulk change.
- **Keep personal data out of git.** The tracker, resume, `config/seen.json`, `config/companies.json` and
  reports describe their job search. Their copy of the repo should be private. `tracker/`, `reports/` and
  `data/` are already in `.gitignore`. Don't commit those to a public repository.
- **Respect their criteria.** Don't suggest jobs their profile excludes unless they ask, and explain any rule
  change before making it.
- **Be honest about fit.** Low scores and real gaps are useful information.
- **When unsure, ask.** One short question beats a wrong change to their tracker.

## File map

| Path | Purpose |
|---|---|
| `setup_wizard.py` | Asks their criteria, writes `config/profile.json` |
| `config/profile.json` | Criteria: titles, exclusions, location, salary, scoring |
| `config/tracker_map.json` | Where the tracker is (Excel, Google Sheets or CSV), its tab, and which columns hold company, title, status, link |
| `config/companies.json` | Companies to search and their job boards (built by the tools) |
| `config/workday_seeds.json` | Workday career-site addresses to verify |
| `config/seen.json` | Jobs already in their tracker (built by `import_tracker.py`) |
| `tools/migrate_tracker.py` | Copies an existing tracker into the template |
| `tools/import_tracker.py` | Reads the tracker: fills `seen.json`, adds companies |
| `tools/add_companies.py` | Adds companies by name |
| `tools/discover_companies.py` | Finds Greenhouse, Lever and Ashby companies with jobs matching their criteria (Common Crawl index, then a live check) |
| `tools/add_to_tracker.py` | Adds every qualifying job to an Excel or Google Sheets tracker (Status New), then updates `seen.json` |
| `tools/tracker_io.py` | Reads and writes Excel, CSV and Google Sheets trackers |
| `tools/export_shortlist.py` | Shortlist as tracker-ready CSV rows (for CSV trackers) |
| `collectors/find_boards.py`, `find_workday.py` | Find each company's job board |
| `collectors/collect.py` | Pull jobs from every known board (`--debug` shows every decision) |
| `scoring/score.py` | Fit Score, gate, shortlist |
| `run_daily.py` | Collect, score and write the daily report |
| `docs/RESUME_MATCH.md` | Resume Match prompt |

## Troubleshooting

- **Few or no jobs:** check "Excluded, by reason" in the report. Too few companies on the list (run
  `tools/discover_companies.py`), strict title
  exclusions, or `accept` options set to `false` are the usual causes. `collect.py --debug` shows each decision.
- **A company keeps showing "not found":** it may use a career site this project doesn't cover (iCIMS, Taleo,
  Oracle, SuccessFactors). Those are checked by hand.
- **The wrong company's jobs appear:** remove that company's `ats` and `token` in `config/companies.json`.
- **`No module named openpyxl`:** `pip3 install openpyxl`, or save the tracker as CSV.
- **Google Sheets errors:** README.md, Troubleshooting, covers the package, key file, sharing and API messages.
