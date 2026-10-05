-- Each strategy runs against one Delta environment. A profile is a settings file under cex-mm/
-- that replaces quote-bot/.env's MM_* lines for that strategy (see supervisor::bot_env_pairs).

ALTER TABLE strategies ADD COLUMN IF NOT EXISTS env TEXT NOT NULL DEFAULT 'demo';
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS profile TEXT NULL;
ALTER TABLE strategies DROP CONSTRAINT IF EXISTS strategies_env_check;
ALTER TABLE strategies ADD CONSTRAINT strategies_env_check CHECK (env IN ('demo', 'mainnet'));

INSERT INTO strategies (id, name, desired_state, last_pid, env, profile)
VALUES ('dism', 'DISM pilot (real money)', 'stopped', NULL, 'mainnet', 'config/dism.env')
ON CONFLICT (id) DO NOTHING;

-- Demo and mainnet prices for the same symbol differ: ticks are per environment.
ALTER TABLE ticks ADD COLUMN IF NOT EXISTS env TEXT NOT NULL DEFAULT 'demo';
ALTER TABLE ticks DROP CONSTRAINT IF EXISTS ticks_pkey;
ALTER TABLE ticks ADD PRIMARY KEY (env, symbol, ts);
