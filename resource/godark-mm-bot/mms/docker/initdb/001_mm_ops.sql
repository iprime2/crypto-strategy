-- MM strategy time-series (bot MM_METRICS / PnL). Runs once on empty volume.
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Per-loop samples from vanilla-mm-rust (one row per symbol per quote loop).
CREATE TABLE IF NOT EXISTS mm_metric_samples (
    time                  TIMESTAMPTZ NOT NULL,
    stack                 TEXT NOT NULL CHECK (stack IN ('testnet', 'devnet')),
    symbol                TEXT NOT NULL,
    loop                  BIGINT NOT NULL,
    account_id            UUID,
    unrealized_pnl_usdc   DOUBLE PRECISION,
    realized_pnl_usdc     DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_realized_pnl_usdc DOUBLE PRECISION NOT NULL DEFAULT 0,
    fees_usdc             DOUBLE PRECISION NOT NULL DEFAULT 0,
    inventory             DOUBLE PRECISION,
    spread_bps            DOUBLE PRECISION,
    markout_extra_bps     DOUBLE PRECISION,
    fair                  DOUBLE PRECISION,
    inserted_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable(
    'mm_metric_samples',
    'time',
    if_not_exists => TRUE,
    migrate_data => FALSE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mm_metric_samples_dedupe
    ON mm_metric_samples (stack, symbol, loop, time);

CREATE INDEX IF NOT EXISTS idx_mm_metric_samples_stack_symbol_time
    ON mm_metric_samples (stack, symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_mm_metric_samples_stack_time
    ON mm_metric_samples (stack, time DESC);

SELECT add_retention_policy(
    'mm_metric_samples',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- Optional rollups for long-range dashboard queries (1M+).
CREATE MATERIALIZED VIEW IF NOT EXISTS mm_metric_samples_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    stack,
    symbol,
    last(unrealized_pnl_usdc, time) AS unrealized_pnl_usdc,
    last(realized_pnl_usdc, time) AS realized_pnl_usdc,
    last(net_realized_pnl_usdc, time) AS net_realized_pnl_usdc,
    last(fees_usdc, time) AS fees_usdc,
    last(inventory, time) AS inventory,
    avg(spread_bps) AS spread_bps_avg
FROM mm_metric_samples
GROUP BY bucket, stack, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'mm_metric_samples_1m',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);
