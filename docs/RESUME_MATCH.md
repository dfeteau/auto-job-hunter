# Resume Match with Claude

The pipeline ranks jobs by salary and location (Fit Score). It does not read your resume. Resume Match is the second score: how well each shortlisted job fits your actual experience. You get it by giving Claude your resume and the shortlist.

## What to give Claude

1. Your current resume (PDF, Word, or pasted text).
2. The shortlist: either the output of `python3 scoring/score.py`, or the CSV from `python3 tools/export_shortlist.py` in the `exports/` folder.
3. The job descriptions. The easiest way is to attach `data/jobs.db` (Claude can read it), or open each posting link and paste the text.

## Prompt to copy

```
Here is my resume, my job-search shortlist, and the job descriptions.

For each job, score Resume Match from 0 to 100: how well my experience matches what
the job actually asks for. Weigh required qualifications more than nice-to-haves.
Use this scale:
  85-100  Strong: most requirements are clear strengths on my resume
  70-84   Good: core skills match, one or two real gaps
  50-69   Partial: some overlap, but a required skill or domain is missing
  below 50  Weak: the role needs things my resume does not show

Give me a table sorted by Resume Match with: score, company, title, Fit Score, pay.
Under it, one or two sentences per job: the best overlap and the biggest gap.
Flag anything to check before applying (unclear location, pay range that looks
like several bands combined, a repost of a job I already have).

Do not invent experience I do not have.
```

## After scoring

- Add the jobs worth tracking to your tracker with Status "New" and their Resume Match.
- Run `python3 tools/import_tracker.py your_tracker.xlsx` so they are not shown again.
