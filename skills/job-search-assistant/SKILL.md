---
name: job-search-assistant
description: Helps set up and run auto-job-hunter (a job-board pipeline with a daily report), migrate an existing job tracker into it, score Resume Match on the daily report, and keep the tracker up to date. Use when someone mentions auto-job-hunter, their job-hunter daily report, or wants help setting up or running this job search process.
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
   column matches, run it, then `python3 tools/import_tracker.py tracker/my_job_tracker.xlsx`), which carries
   over their history and fills the company list. Then run `python3 setup_wizard.py`, add dream companies with
   `tools/add_companies.py`, and run `init_db.py` and `collectors/find_boards.py`.
2. **Daily:** they run `python3 run_daily.py`. Read the report, score Resume Match (0 to 100, required
   qualifications weighted most, never invent experience), present a short table with the best overlap and
   biggest gap for each job, then log the jobs they choose with Status `New` and re-run `import_tracker.py`.
3. **Rules:** never apply or contact anyone for them without explicit permission; don't delete or overwrite
   their tracker content, and back it up before bulk edits; keep their tracker, resume and reports out of
   public repositories; explain any criteria change before making it.
