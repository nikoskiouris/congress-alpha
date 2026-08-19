from datetime import date

from congress_alpha.backtest import cheat_backtest_on_trade_date
from congress_alpha.ingest import parse_amount_band
from congress_alpha.warehouse import connect, init_db


def test_amount_bands():
    lo, hi = parse_amount_band("$15,001 - $50,000")
    assert lo == 15001
    assert hi == 50000


def test_schema_applies(tmp_path):
    db = tmp_path / "t.db"
    con = connect(db)
    init_db(con)
    n = con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='trades'"
    ).fetchone()[0]
    assert n == 1
    con.close()


def test_trade_date_is_not_an_event_time():
    try:
        cheat_backtest_on_trade_date()
        raise AssertionError("should have refused")
    except RuntimeError as e:
        assert "trade_date" in str(e)
