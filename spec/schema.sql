-- Congress Alpha V1 warehouse. All research tables are point-in-time:
-- a row dated as_of may only be produced from disclosures with disclosure_date <= as_of.

CREATE TABLE politicians (
    politician_id   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    chamber         TEXT NOT NULL CHECK (chamber IN ('house', 'senate')),
    party           TEXT,
    state           TEXT,
    seniority_years REAL
);

CREATE TABLE committees (
    committee_id    TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    chamber         TEXT NOT NULL,
    primary_sector  TEXT
);

CREATE TABLE politician_committees (
    politician_id   TEXT NOT NULL,
    committee_id    TEXT NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT,
    PRIMARY KEY (politician_id, committee_id, start_date)
);

CREATE TABLE securities (
    ticker              TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    sector              TEXT NOT NULL,
    industry            TEXT NOT NULL,
    avg_dollar_volume   REAL NOT NULL
);

-- One row per disclosed transaction. trade_date is NEVER a valid as-of timestamp.
-- The model may look at a row only when as_of >= disclosure_date.
CREATE TABLE trades (
    trade_id        TEXT PRIMARY KEY,
    politician_id   TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    disclosure_date TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    amount_min      REAL NOT NULL,
    amount_max      REAL NOT NULL,
    owner           TEXT NOT NULL DEFAULT 'self',
    source          TEXT NOT NULL,
    CHECK (disclosure_date >= trade_date)
);

CREATE TABLE prices (
    ticker      TEXT NOT NULL,
    date        TEXT NOT NULL,
    adj_close   REAL NOT NULL,
    volume      REAL,
    PRIMARY KEY (ticker, date)
);

-- Learned politician (and politician x sector) weights. Horizon skill is
-- always measured from disclosure_date, never trade_date.
CREATE TABLE skill_snapshots (
    as_of           TEXT NOT NULL,
    politician_id   TEXT NOT NULL,
    sector          TEXT,               -- NULL = overall
    horizon         INTEGER NOT NULL,
    alpha           REAL NOT NULL,
    hit_rate        REAL NOT NULL,
    n               REAL NOT NULL,
    weight          REAL NOT NULL,
    PRIMARY KEY (as_of, politician_id, sector, horizon)
);

CREATE TABLE delay_snapshots (
    as_of               TEXT NOT NULL,
    lag_bucket          TEXT NOT NULL,
    remaining_alpha     REAL NOT NULL,
    n                   REAL NOT NULL,
    PRIMARY KEY (as_of, lag_bucket)
);

CREATE TABLE signals (
    as_of                   TEXT NOT NULL,
    ticker                  TEXT NOT NULL,
    strategy                TEXT NOT NULL,
    signal                  REAL NOT NULL,
    n_politicians           INTEGER NOT NULL,
    n_predictive            INTEGER NOT NULL,
    n_relevant_committee    INTEGER NOT NULL,
    avg_lag_days            REAL,
    components_json         TEXT,
    PRIMARY KEY (as_of, ticker, strategy)
);

CREATE TABLE portfolios (
    as_of       TEXT NOT NULL,
    strategy    TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    weight      REAL NOT NULL,
    signal      REAL NOT NULL,
    PRIMARY KEY (as_of, strategy, ticker)
);

CREATE TABLE backtest_nav (
    date            TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    nav             REAL NOT NULL,
    daily_return    REAL NOT NULL,
    excess_return   REAL NOT NULL,
    n_holdings      INTEGER NOT NULL,
    invested        REAL NOT NULL,
    PRIMARY KEY (date, strategy)
);
