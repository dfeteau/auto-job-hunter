# Changelog

Notable changes to auto-job-hunter, newest first. If you made your own copy from the template,
compare this list with your copy to see what's new. Full history is on the Commits page on GitHub.

## 1.3.0 (2026-10-22)

### Added
- **Bring your existing tracker** (`tools/migrate_tracker.py`). Copies any tracker (Excel or CSV, any column layout) into the template: matches common column names automatically, standardizes statuses and dates, keeps links and extra columns, and never changes the original. `--dry-run` shows the column matches first. Then `import_tracker.py` carries your history over and adds every company in it to the search list.
- **Guide for AI assistants** (`AGENTS.md`): what the project does, a step-by-step setup conversation (including asking for and migrating an existing tracker), the daily routine, Resume Match scoring, tracker columns and status mapping, and rules (never apply or contact anyone without permission, don't overwrite the person's tracker, keep personal data out of git).
- **`CLAUDE.md`** so Claude Code loads the guide automatically, and a **Claude skill** (`skills/job-search-assistant/`) people can install.
- README sections: "Already tracking your applications somewhere?" and "Using an AI assistant".

### Changed
- `tracker/` is excluded from git, and is now the suggested home for your tracker.

## 1.2.0 (2026-10-21)

### Added
- **One-command daily run with a report** (`python3 run_daily.py`). Collects from every board, scores, and saves `reports/report_YYYY-MM-DD.md` with jobs found, excluded by your criteria (with a count per reason), already in your tracker, and qualifying for your tracker. It also lists every excluded job with its reason and includes the full descriptions of the qualifying jobs for Resume Match. Set `JOB_REPORT_DIR` to save reports somewhere else. `--report` rebuilds the report without collecting again.
- **Security clearance setting.** `exclude_clearance_required` in `config/profile.json` (default `true`) skips postings that require a clearance. "Clearance Required: None" is not treated as a requirement. The setup wizard now asks whether you hold an active clearance.
- **Title exclusion exceptions.** `excluded_title_exceptions` in `profile.json` keeps phrases such as Senior Associate, Associate Principal and Associate Director even when "Associate" is an excluded word.
- **Diagnostic mode.** `python3 collectors/collect.py --debug` prints every matching job and why it was kept or excluded, and for Workday how many matching titles each site returned.

### Changed
- **Home-area jobs that don't state remote, hybrid or onsite are kept,** flagged `check if hybrid`, and scored as hybrid. Jobs that say onsite are treated as onsite. Previously these were treated as onsite and usually dropped.
- **Each board is searched once per run,** even if two company entries point to the same board.
- **Scoring re-applies all collection rules,** including title exclusions, industry words and clearance, so changes to `profile.json` take effect without collecting again.
- **Collection summary** now prints found, excluded, already in tracker, and kept for scoring.

### Fixed
- **Title exclusions match whole words only.** "Intern" no longer excludes "Internal Audit Data Analyst".
- **Workday postings marked onsite** in Workday's own work-type field are now recognized as onsite.

## 1.1.1 (2026-10-21)

### Fixed
- **False Workable matches.** Workable returns a company name even for boards that don't exist, so `find_boards.py` now requires at least one real job posting.
- **Board finder appearing to hang.** Each guess times out after 8 seconds with no retries.

## 1.1.0 (2026-10-21)

### Added
- **Setup wizard** (`python3 setup_wizard.py`). About 15 plain-language questions that write `config/profile.json`, with answer checking, a summary with example scores, and a backup of your previous settings.
- **MIT license.** Free to use, change and share.

## 1.0.0 (2026-10-21)

### Added
- First release: collectors for Greenhouse, Lever, Ashby, SmartRecruiters, Workable and Workday; board finder and Workday address finder; Fit Score scoring from a single `config/profile.json`; tracker template (Excel and CSV); tracker import, company import and shortlist export tools; Resume Match guide for Claude; getting-started README.
