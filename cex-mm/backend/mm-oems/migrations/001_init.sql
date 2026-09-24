-- OEMS schema: strategy_id on every data row

CREATE TABLE IF NOT EXISTS strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    desired_state TEXT NOT NULL,
    last_pid BIGINT NULL
);

CREATE TABLE IF NOT EXISTS strategy_config (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    version INT NOT NULL,
    body JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS strategy_config_strategy_version_uidx
    ON strategy_config (strategy_id, version);

CREATE TABLE IF NOT EXISTS orders (
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    client_order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    reduce_only BOOLEAN NOT NULL DEFAULT FALSE,
    reject_code TEXT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_id, client_order_id)
);

CREATE TABLE IF NOT EXISTS fills (
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    trade_id TEXT NOT NULL,
    client_order_id TEXT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION NOT NULL,
    limit_price DOUBLE PRECISION NOT NULL,
    arrival_mid DOUBLE PRECISION NOT NULL,
    mid_at_fill DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (strategy_id, trade_id)
);

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    venue_qty DOUBLE PRECISION NOT NULL,
    bot_qty DOUBLE PRECISION NOT NULL,
    entry DOUBLE PRECISION NOT NULL,
    mark DOUBLE PRECISION NOT NULL,
    unrealized DOUBLE PRECISION NOT NULL,
    realized DOUBLE PRECISION NOT NULL,
    mismatch BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS positions_strategy_ts_idx ON positions (strategy_id, ts DESC);

CREATE TABLE IF NOT EXISTS balances (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    ts TIMESTAMPTZ NOT NULL,
    equity DOUBLE PRECISION NOT NULL,
    available DOUBLE PRECISION NOT NULL,
    blocked_margin DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS balances_strategy_ts_idx ON balances (strategy_id, ts DESC);

CREATE TABLE IF NOT EXISTS pnl_snapshots (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    ts TIMESTAMPTZ NOT NULL,
    realized DOUBLE PRECISION NOT NULL,
    unrealized DOUBLE PRECISION NOT NULL,
    equity DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS pnl_snapshots_strategy_ts_idx ON pnl_snapshots (strategy_id, ts DESC);

CREATE TABLE IF NOT EXISTS tca_fills (
    strategy_id TEXT NOT NULL REFERENCES strategies (id),
    trade_id TEXT NOT NULL,
    slippage_bps DOUBLE PRECISION NOT NULL,
    quoted_half_spread_bps DOUBLE PRECISION NOT NULL,
    effective_spread_bps DOUBLE PRECISION NOT NULL,
    fee_quote DOUBLE PRECISION NOT NULL,
    fee_bps DOUBLE PRECISION NOT NULL,
    markout_1s_bps DOUBLE PRECISION NULL,
    markout_5s_bps DOUBLE PRECISION NULL,
    markout_30s_bps DOUBLE PRECISION NULL,
    net_5s_bps DOUBLE PRECISION NULL,
    PRIMARY KEY (strategy_id, trade_id)
);

INSERT INTO strategies (id, name, desired_state, last_pid)
VALUES ('mm', 'Market maker', 'stopped', NULL)
ON CONFLICT (id) DO NOTHING;
