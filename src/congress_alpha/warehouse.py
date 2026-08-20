from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from congress_alpha.types import (
    Committee,
    Politician,
    Security,
    TradeEvent,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "spec" / "schema.sql"


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    sql = SCHEMA_PATH.read_text()
    con.executescript(sql)
    con.commit()


def reset_db(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if path.exists():
        path.unlink()
    con = connect(path)
    init_db(con)
    return con


def _d(d: date | str) -> str:
    return d if isinstance(d, str) else d.isoformat()


def load_reference(
    con: sqlite3.Connection,
    politicians: list[Politician],
    committees: list[Committee],
    securities: list[Security],
) -> None:
    con.executemany(
        """INSERT INTO politicians(politician_id,name,chamber,party,state,seniority_years)
           VALUES(?,?,?,?,?,?)""",
        [
            (p.politician_id, p.name, p.chamber, p.party, p.state, p.seniority_years)
            for p in politicians
        ],
    )
    con.executemany(
        """INSERT INTO committees(committee_id,name,chamber,primary_sector)
           VALUES(?,?,?,?)""",
        [(c.committee_id, c.name, c.chamber, c.primary_sector) for c in committees],
    )
    rows = []
    for p in politicians:
        for cid in p.committee_ids:
            rows.append((p.politician_id, cid, "2021-01-01", None))
    con.executemany(
        """INSERT INTO politician_committees(politician_id,committee_id,start_date,end_date)
           VALUES(?,?,?,?)""",
        rows,
    )
    con.executemany(
        """INSERT INTO securities(ticker,name,sector,industry,avg_dollar_volume)
           VALUES(?,?,?,?,?)""",
        [
            (s.ticker, s.name, s.sector, s.industry, s.avg_dollar_volume)
            for s in securities
        ],
    )
    con.commit()


def upsert_politicians(con: sqlite3.Connection, politicians: list[Politician]) -> int:
    if not politicians:
        return 0
    con.executemany(
        """INSERT OR REPLACE INTO politicians(politician_id,name,chamber,party,state,seniority_years)
           VALUES(?,?,?,?,?,?)""",
        [
            (p.politician_id, p.name, p.chamber, p.party, p.state, p.seniority_years)
            for p in politicians
        ],
    )
    rows = []
    for p in politicians:
        for cid in p.committee_ids:
            rows.append((p.politician_id, cid, "2021-01-01", None))
    if rows:
        con.executemany(
            """INSERT OR IGNORE INTO politician_committees(politician_id,committee_id,start_date,end_date)
               VALUES(?,?,?,?)""",
            rows,
        )
    con.commit()
    return len(politicians)


def upsert_securities(con: sqlite3.Connection, securities: list[Security]) -> int:
    if not securities:
        return 0
    con.executemany(
        """INSERT OR REPLACE INTO securities(ticker,name,sector,industry,avg_dollar_volume)
           VALUES(?,?,?,?,?)""",
        [
            (s.ticker, s.name, s.sector, s.industry, s.avg_dollar_volume)
            for s in securities
        ],
    )
    con.commit()
    return len(securities)


def upsert_committees(con: sqlite3.Connection, committees: list[Committee]) -> int:
    if not committees:
        return 0
    con.executemany(
        """INSERT OR REPLACE INTO committees(committee_id,name,chamber,primary_sector)
           VALUES(?,?,?,?)""",
        [(c.committee_id, c.name, c.chamber, c.primary_sector) for c in committees],
    )
    con.commit()
    return len(committees)


def insert_trades(con: sqlite3.Connection, trades: list[TradeEvent]) -> None:
    con.executemany(
        """INSERT INTO trades(trade_id,politician_id,ticker,trade_date,disclosure_date,
                              side,amount_min,amount_max,owner,source)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                t.trade_id,
                t.politician_id,
                t.ticker,
                _d(t.trade_date),
                _d(t.disclosure_date),
                t.side,
                t.amount_min,
                t.amount_max,
                t.owner,
                t.source,
            )
            for t in trades
        ],
    )
    con.commit()


def insert_prices(con: sqlite3.Connection, prices: dict[tuple[str, date], float]) -> None:
    con.executemany(
        "INSERT INTO prices(ticker,date,adj_close,volume) VALUES(?,?,?,?)",
        [(tkr, _d(dt), px, None) for (tkr, dt), px in prices.items()],
    )
    con.commit()


def fetch_politicians(con: sqlite3.Connection) -> list[Politician]:
    comm = {}
    for row in con.execute(
        "SELECT politician_id, committee_id FROM politician_committees"
    ):
        comm.setdefault(row["politician_id"], []).append(row["committee_id"])
    out = []
    for row in con.execute("SELECT * FROM politicians"):
        out.append(
            Politician(
                politician_id=row["politician_id"],
                name=row["name"],
                chamber=row["chamber"],
                party=row["party"],
                state=row["state"],
                seniority_years=row["seniority_years"],
                committee_ids=tuple(comm.get(row["politician_id"], ())),
            )
        )
    return out


def fetch_committees(con: sqlite3.Connection) -> dict[str, Committee]:
    out = {}
    for row in con.execute("SELECT * FROM committees"):
        out[row["committee_id"]] = Committee(
            row["committee_id"], row["name"], row["chamber"], row["primary_sector"]
        )
    return out


def fetch_securities(con: sqlite3.Connection) -> dict[str, Security]:
    out = {}
    for row in con.execute("SELECT * FROM securities"):
        out[row["ticker"]] = Security(
            row["ticker"],
            row["name"],
            row["sector"],
            row["industry"],
            row["avg_dollar_volume"],
        )
    return out


def fetch_trades(con: sqlite3.Connection) -> list[TradeEvent]:
    out = []
    for row in con.execute("SELECT * FROM trades ORDER BY disclosure_date, trade_id"):
        out.append(
            TradeEvent(
                trade_id=row["trade_id"],
                politician_id=row["politician_id"],
                ticker=row["ticker"],
                trade_date=date.fromisoformat(row["trade_date"]),
                disclosure_date=date.fromisoformat(row["disclosure_date"]),
                side=row["side"],
                amount_min=row["amount_min"],
                amount_max=row["amount_max"],
                owner=row["owner"],
                source=row["source"],
            )
        )
    return out


def fetch_prices(con: sqlite3.Connection) -> dict[tuple[str, date], float]:
    out = {}
    for row in con.execute("SELECT ticker, date, adj_close FROM prices"):
        out[(row["ticker"], date.fromisoformat(row["date"]))] = float(row["adj_close"])
    return out


def replace_json_table(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    con.execute(f"DELETE FROM {table}")
    q = f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in cols)})"
    con.executemany(q, [tuple(r[c] for c in cols) for r in rows])
    con.commit()


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
