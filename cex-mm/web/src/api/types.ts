export type ApiErrorBody = {
  code: string
  message: string
}

export type StrategyStatus = 'running' | 'stopped'

export type Strategy = {
  id: string
  name: string
  desired_state: StrategyStatus
  last_pid?: number | null
}

export type StreamHealth = {
  last_ok: string | null
  last_error: string | null
  last_error_at: string | null
  rtt_ms: number | null
}

export type Position = {
  symbol: string
  ts: string
  venue_qty: number
  bot_qty: number | null
  entry: number
  mark: number
  unrealized: number
  realized: number
  mismatch: boolean
  liq_price: number | null
  margin: number | null
}

export type Balance = {
  ts: string
  equity: number
  available: number
  blocked_margin: number
}

export type BotCounters = {
  orders_placed: number
  orders_edited: number
  rejects: number
  regime_pauses: number
  risk_kills: number
  warnings: number
  errors: number
}

export type Overview = {
  strategy: Strategy & {
    pid: number | null
    started_at: string | null
    uptime_s: number | null
    adopted: boolean
    last_exit: { pid: number; code: number | null; at: string } | null
  }
  venue_env: 'demo' | 'mainnet'
  balance: Balance | null
  positions: Position[] | null
  unrealized: number
  day: { start_ts: string | null; start_equity: number | null; pnl: number | null }
  open_orders: number
  venue: {
    health: Partial<Record<'orders' | 'fills' | 'ticker', StreamHealth>>
    orders_at: string | null
    fills_backfilled: boolean
    fills_ingested: number
    active_symbols: string[]
  }
  telemetry: {
    attached: boolean
    last_line_at: string | null
    symbols: string[]
    counters: BotCounters
  }
  server_time: string
}

export type VenueOrder = {
  id: string
  client_order_id: string | null
  symbol: string
  side: string
  price: number
  size: number
  unfilled: number
  state: string
  order_type: string
  reduce_only: boolean
  post_only: boolean | null
  created_at: string | null
  updated_at: string | null
}

export type VenueOrders = {
  fetched_at: string | null
  orders: VenueOrder[]
}

export type Fill = {
  trade_id: string
  order_id: string | null
  client_order_id: string | null
  symbol: string
  side: string
  role: string | null
  source: string
  price: number
  qty: number
  notional: number
  fee: number
  fee_bps: number | null
  limit_price: number
  mid_at_fill: number
  capture_bps: number | null
  created_at: string
}

export type TcaRow = {
  trade_id: string
  symbol: string
  side: string
  role: string | null
  price: number
  qty: number
  created_at: string
  capture_bps: number | null
  fee_bps: number
  markout_1s_bps: number | null
  markout_5s_bps: number | null
  markout_30s_bps: number | null
  markout_60s_bps: number | null
  net_60s_bps: number | null
}

export type PnlSnapshot = {
  ts: string
  equity: number
  realized: number
  unrealized: number
}

export type Ticker = {
  symbol: string
  venue_symbol: string
  mark: number
  spot: number
  last: number
  open_24h: number
  high_24h: number
  low_24h: number
  change_24h_pct: number
  turnover_24h_usd: number
  oi_usd: number
  funding_rate_pct: number
  best_bid: number
  best_ask: number
  spread_bps: number
  tick_size: number
}

export type BookLevel = [number, number]

export type Book = {
  bids: BookLevel[]
  asks: BookLevel[]
  ts: number
}

export type MarketTrade = {
  ts: number
  price: number
  size: number
  side: 'buy' | 'sell'
}

export type Candle = {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

/** One `MM_METRICS` sample from the bot, plus how old it is. */
export type QuoteState = {
  symbol: string
  fair: number
  reservation: number
  bid: number
  ask: number
  spread_bps: number
  vol_bps: number
  inventory: number
  regime_level: number
  place_bid: boolean
  place_ask: boolean
  binance_mid?: number | null
  lead_skew_bps?: number | null
  markout_extra_bid_bps: number
  markout_extra_ask_bps: number
  rolling_adverse_bps: number
  book_bid?: number
  book_ask?: number
  age_s: number
}

export type BotEvent = {
  ts: string
  level: 'info' | 'warn' | 'error'
  kind: string
  symbol: string | null
  message: string
  count: number
}

export type BotTelemetry = {
  log_path: string | null
  attached: boolean
  last_line_at: string | null
  metrics: Record<string, QuoteState>
  counters: BotCounters
  events: BotEvent[]
}

export type ConfigValue = { value: string; source: 'env_file' | 'override' }

export type EffectiveConfig = {
  strategy_id: string
  version: number | null
  overrides: Record<string, unknown> | null
  values: Record<string, ConfigValue>
  env_file: string | null
}

export type NetPoint = { h: number; net_bps: number | null; n: number }

export type PerfStats = {
  fills: number
  maker_fills: number
  maker_share: number
  volume: number
  maker_volume: number
  fees: number
  maker_fees: number
  taker_fees: number
  fee_bps: number | null
  capture_bps: number | null
  net_curve: NetPoint[]
  maker_net_curve: NetPoint[]
}

export type PerfDay = PerfStats & {
  day: string
  equity_start: number | null
  equity_end: number | null
  equity_change: number | null
}

export type Performance = {
  from: string
  to: string
  tz_offset_min: number
  totals: PerfStats
  equity_change: number | null
  daily: PerfDay[]
  by_symbol: (PerfStats & { symbol: string })[]
}
