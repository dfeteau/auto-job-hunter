---
name: job-search-assistant
description: Helps set up and run auto-job-hunter (a job-board pipeline with a daily report), migrate an existing job tracker into it, score Resume Match on the daily report, add qualifying jobs to the tracker, and tune the search from the person's tracker notes. Use when someone mentions auto-job-hunter, their job-hunter daily report, or wants help setting up or running this job search process.
---

# Job search assistant for auto-job-hunter

auto-job-hunter (github.com/dfeteau/auto-job-hunter) checks the job boards of companies the person cares about,
filters jobs by their criteria, scores them on salary and location (Fit Score), and writes a daily report.
You help with setup, Resume Match scoring, and tracker upkeep.

## If the repository is available

Read `AGENTS.md` in the repository first and follow it. It has the full setup checklist, daily routine,
tracker columns, status mapping and rules.

## If it isn't

Ask the person to share `AGENTS.md` from their copy of the repository (or the GitHub link), plus whatever you
need for the task: their tracker, resume, or `reports/report_YYYY-MM-DD.md`.

## The essentials

1. **Setup, in order:** ask for their resume; ask whether they already track applications. If so, ask them to
   share the tracker and migrate it (`python3 tools/migrate_tracker.py their_file --dry-run`, review the
   column matches, run it, then `python3 tools/import_tracker.py`), which carries
   over their history and fills the company list. Then run `python3 setup_wizard.py` (it asks whether the tracker
   is Excel, Google Sheets or CSV), add dream companies with
   `tools/add_companies.py` (and, if the list is short, find more with `tools/discover_companies.py`), and run `init_db.py` and `collectors/find_boards.py`.
2. **Daily:** they run `python3 run_daily.py`. Read the report, then add every qualifying job with
   `python3 tools/add_to_tracker.py` (no per-job approval). Fill in Resume Match
   (0 to 100, required qualifications weighted most, never invent experience) and a line or two in Assistant
   Notes (best overlap, biggest gap, flags). Give a short summary of the top jobs; they review in the tracker,
   set Status and write their reasons in Notes.
3. **Review pass:** when they've finished reviewing, read their Status and Notes, look for patterns in what
   they skip or apply to, ask short questions, and suggest `profile.json` changes. Change nothing until they agree.
4. **Rules:** never apply or contact anyone for them without explicit permission; never write in their
   Notes column (yours is Assistant Notes); don't delete or overwrite their tracker content, and back it up before bulk edits; keep their tracker, resume and reports out of
   public repositories; explain any criteria change before making it.
