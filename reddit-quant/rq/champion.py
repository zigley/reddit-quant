"""Champion / challenger / rejected manager. Paper only. There is deliberately no path to live trading."""
from . import ledger


def reject(con, cycle, family_id, spec_hash, failed, evidence=""):
    ledger.add_status(con, cycle, family_id, spec_hash, "REJECTED", "failed gates: " + "; ".join(failed), evidence)


def current_champion(con):
    rows = con.execute("""SELECT s.* FROM status_events s WHERE s.id IN
                          (SELECT MAX(id) FROM status_events GROUP BY family_id) AND s.status='CHAMPION'""").fetchall()
    return [dict(r) for r in rows]


def consider_for_champion(con, cycle, family_id, spec_hash, final_sharpe, evidence):
    """Called only for candidates that passed every dev and final gate. A challenger replaces the
    champion only if its final-test Sharpe is higher and it passed the same gates. Paper trading only."""
    champs = current_champion(con)
    if not champs:
        ledger.add_status(con, cycle, family_id, spec_hash, "CHAMPION",
                          "passed all pre-registered dev and final gates (paper trading only, config PROVISIONAL)",
                          evidence)
        return "CHAMPION"
    ledger.add_status(con, cycle, family_id, spec_hash, "CHALLENGER",
                      "passed all gates; existing champion must be compared on a fresh paper-trading clock", evidence)
    return "CHALLENGER"


def promote_to_live(*_a, **_k):
    raise PermissionError("Live trading is disabled. This framework never promotes a strategy to live.")
