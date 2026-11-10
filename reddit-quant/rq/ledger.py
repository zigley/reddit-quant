"""SQLite ledger. Append-only for trials, results, evaluations, final_test_access and status events.

Section 3 fields are stored in `ideas`, with the four-way separation kept in distinct columns:
  A  source_says_json        what the source explicitly says
  B  interpretation          the agent's reading
  C  proposed_modifications  the agent's proposed changes
  D  test_results_json       what our own tests actually establish (filled only from result artifacts)
"""
import json
import sqlite3
import time
from pathlib import Path

from .config import ROOT

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_posts(
  post_id TEXT PRIMARY KEY, subreddit TEXT, title TEXT, selftext TEXT, url TEXT,
  created_utc INTEGER, created_date TEXT, score INTEGER, num_comments INTEGER, flair TEXT,
  retrieved_at TEXT, access_method TEXT);
CREATE TABLE IF NOT EXISTS raw_comments(
  comment_id TEXT PRIMARY KEY, post_id TEXT, body TEXT, url TEXT, created_utc INTEGER,
  created_date TEXT, score INTEGER, retrieved_at TEXT, access_method TEXT);
CREATE TABLE IF NOT EXISTS families(
  family_id TEXT PRIMARY KEY, name TEXT, template TEXT, description TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ideas(
  idea_id TEXT PRIMARY KEY,
  family_id TEXT,
  source_url TEXT, source_post_id TEXT, publication_date TEXT, date_discovered TEXT,
  summary TEXT,
  claimed_market TEXT, claimed_timeframe TEXT,
  source_says_json TEXT,           -- A: explicit rules as extracted from the source text
  interpretation TEXT,             -- B
  proposed_modifications TEXT,     -- C
  test_results_json TEXT,          -- D (summary pointers to result artifacts, filled after tests)
  missing_or_ambiguous TEXT,
  claimed_results TEXT, claimed_results_evidence TEXT,
  critical_objections TEXT,
  required_data_infra TEXT, implementation_complexity TEXT,
  economic_rationale TEXT, edge_decay_reasons TEXT,
  duplicate_of TEXT, duplicates_family INTEGER,
  testability_score REAL, score_breakdown_json TEXT,
  flags_json TEXT);
CREATE TABLE IF NOT EXISTS specs(
  spec_hash TEXT PRIMARY KEY, family_id TEXT, version TEXT, kind TEXT,  -- kind: family | candidate
  path TEXT, frozen_at TEXT, gates_hash TEXT, data_manifest_hash TEXT, content_json TEXT);
CREATE TABLE IF NOT EXISTS trials(
  trial_id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER, family_id TEXT, spec_hash TEXT,
  params_json TEXT, segment TEXT, metrics_json TEXT, artifact_path TEXT, wall_seconds REAL,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS evaluations(
  eval_id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER, family_id TEXT, spec_hash TEXT,
  kind TEXT, params_json TEXT, result_json TEXT, artifact_path TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS final_test_access(
  access_id INTEGER PRIMARY KEY AUTOINCREMENT, spec_hash TEXT UNIQUE, family_id TEXT,
  accessed_at TEXT, cycle INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS gate_results(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER, family_id TEXT, spec_hash TEXT,
  stage TEXT, gate TEXT, passed INTEGER, detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS status_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER, family_id TEXT, spec_hash TEXT,
  status TEXT,  -- CHAMPION | CHALLENGER | REJECTED | UNTESTED
  reason TEXT, evidence_path TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cycles(
  cycle INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS access_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER, method TEXT, target TEXT, status TEXT,
  detail TEXT, created_at TEXT);
"""

APPEND_ONLY = ["trials", "evaluations", "final_test_access", "gate_results", "status_events", "specs"]


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def connect(path=None):
    path = Path(path) if path else ROOT / "ledger" / "ledger.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    for t in APPEND_ONLY:
        for op in ("UPDATE", "DELETE"):
            con.execute(f"""CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t}
                            BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;""")
    con.commit()
    return con


def log_access(con, cycle, method, target, status, detail=""):
    con.execute("INSERT INTO access_log(cycle,method,target,status,detail,created_at) VALUES(?,?,?,?,?,?)",
                (cycle, method, target, status, str(detail)[:500], now()))
    con.commit()


def add_status(con, cycle, family_id, spec_hash, status, reason, evidence_path=""):
    con.execute("INSERT INTO status_events(cycle,family_id,spec_hash,status,reason,evidence_path,created_at) "
                "VALUES(?,?,?,?,?,?,?)", (cycle, family_id, spec_hash, status, reason, evidence_path, now()))
    con.commit()


def add_trial(con, cycle, family_id, spec_hash, params, segment, metrics, artifact, wall):
    con.execute("INSERT INTO trials(cycle,family_id,spec_hash,params_json,segment,metrics_json,artifact_path,"
                "wall_seconds,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (cycle, family_id, spec_hash, json.dumps(params, sort_keys=True), segment,
                 json.dumps(metrics, sort_keys=True), artifact, wall, now()))
    con.commit()


def add_evaluation(con, cycle, family_id, spec_hash, kind, params, result, artifact=""):
    con.execute("INSERT INTO evaluations(cycle,family_id,spec_hash,kind,params_json,result_json,artifact_path,"
                "created_at) VALUES(?,?,?,?,?,?,?,?)",
                (cycle, family_id, spec_hash, kind, json.dumps(params, sort_keys=True),
                 json.dumps(result, sort_keys=True, default=str), artifact, now()))
    con.commit()


def add_gate(con, cycle, family_id, spec_hash, stage, gate, passed, detail):
    con.execute("INSERT INTO gate_results(cycle,family_id,spec_hash,stage,gate,passed,detail,created_at) "
                "VALUES(?,?,?,?,?,?,?,?)", (cycle, family_id, spec_hash, stage, gate, int(bool(passed)),
                                            str(detail), now()))
    con.commit()


def trial_count(con, family_id):
    """Number of parameter-trial rows for a family on the dev segment (the DSR trial counter)."""
    r = con.execute("SELECT COUNT(DISTINCT spec_hash || params_json) AS n FROM trials "
                    "WHERE family_id=? AND segment='dev'", (family_id,)).fetchone()
    return r["n"]


def latest_status(con, family_id):
    r = con.execute("SELECT * FROM status_events WHERE family_id=? ORDER BY id DESC LIMIT 1",
                    (family_id,)).fetchone()
    return dict(r) if r else None
