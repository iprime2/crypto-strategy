-- Venue-sourced fills, per-symbol price ticks for markouts, richer positions.

ALTER TABLE fills ADD COLUMN IF NOT EXISTS role TEXT NULL;
ALTER TABLE fills ADD COLUMN IF NOT EXISTS order_id TEXT NULL;
ALTER TABLE fills ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'bot';
CREATE INDEX IF NOT EXISTS fills_strategy_created_idx ON fills (strategy_id, created_at DESC);

ALTER TABLE tca_fills ADD COLUMN IF NOT EXISTS markout_60s_bps DOUBLE PRECISION NULL;

ALTER TABLE positions ADD COLUMN IF NOT EXISTS liq_price DOUBLE PRECISION NULL;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS margin DOUBLE PRECISION NULL;

CREATE TABLE IF NOT EXISTS ticks (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    mark DOUBLE PRECISION NOT NULL,
    bid DOUBLE PRECISION NULL,
    ask DOUBLE PRECISION NULL,
    last DOUBLE PRECISION NULL,
    spot DOUBLE PRECISION NULL,
    PRIMARY KEY (symbol, ts)
);
SELECT create_hypertable('ticks', 'ts', if_not_exists => TRUE, migrate_data => TRUE);

-- Bot inventory comes from bot telemetry; unknown when the bot is not reporting.
ALTER TABLE positions ALTER COLUMN bot_qty DROP NOT NULL;
