"""Ledger lock tests. Run: python tests/test_ledger_locks.py"""
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rq import ledger

con = ledger.connect(Path(tempfile.mkdtemp()) / "t.sqlite")
con.execute("INSERT INTO final_test_access(spec_hash,family_id,accessed_at,cycle,note) VALUES('h','f','now',1,'x')")
try:
    con.execute("INSERT INTO final_test_access(spec_hash,family_id,accessed_at,cycle,note) VALUES('h','f','now',1,'x')")
    raise AssertionError("second final-test access must fail")
except sqlite3.IntegrityError:
    print("ok final test locked to one access per spec hash")
ledger.add_trial(con, 1, "f", "h", {"a": 1}, "dev", {}, "p", 0.1)
for op in ("UPDATE trials SET segment='x'", "DELETE FROM trials"):
    try:
        con.execute(op)
        raise AssertionError("append-only violated")
    except sqlite3.DatabaseError as e:
        assert "append-only" in str(e)
print("ok trials are append-only")
from rq import champion
try:
    champion.promote_to_live()
    raise AssertionError
except PermissionError:
    print("ok no live promotion path")
