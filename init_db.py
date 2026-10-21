"""Create the local SQLite database. Run once: python3 init_db.py"""
import sqlite3, pathlib
DB = pathlib.Path(__file__).parent / "data" / "jobs.db"
DB.parent.mkdir(exist_ok=True)
con = sqlite3.connect(DB)
con.executescript("""
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    company TEXT, title TEXT, source TEXT,
    location TEXT, remote_type TEXT,
    salary_min INTEGER, salary_max INTEGER,
    url TEXT UNIQUE,
    description TEXT,
    discovered_date DATE, last_seen_date DATE,
    fit_score REAL, title_rank INTEGER, skills_tiebreak INTEGER,
    flags TEXT,
    status TEXT DEFAULT 'NEW',
    dedupe_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
""")
con.commit(); print("ready:", DB)
