-- TimescaleDB hypertables for the time-series tables.
-- Requires the timescale/timescaledb image (port 55432 in docker-compose).

CREATE EXTENSION IF NOT EXISTS timescaledb;

ALTER TABLE positions DROP CONSTRAINT IF EXISTS positions_pkey;
ALTER TABLE positions ADD PRIMARY KEY (id, ts);
SELECT create_hypertable('positions', 'ts', if_not_exists => TRUE, migrate_data => TRUE);

ALTER TABLE balances DROP CONSTRAINT IF EXISTS balances_pkey;
ALTER TABLE balances ADD PRIMARY KEY (id, ts);
SELECT create_hypertable('balances', 'ts', if_not_exists => TRUE, migrate_data => TRUE);

ALTER TABLE pnl_snapshots DROP CONSTRAINT IF EXISTS pnl_snapshots_pkey;
ALTER TABLE pnl_snapshots ADD PRIMARY KEY (id, ts);
SELECT create_hypertable('pnl_snapshots', 'ts', if_not_exists => TRUE, migrate_data => TRUE);
