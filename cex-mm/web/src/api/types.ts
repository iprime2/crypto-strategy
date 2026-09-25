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

export type PnlSnapshot = {
  strategy_id?: string
  ts: string
  equity: number
  realized: number
  unrealized: number
}

export type LatestSnapshot = {
  strategy_id?: string
  ts?: string | null
  equity?: number | null
  realized?: number | null
  unrealized?: number | null
  pnl?: PnlSnapshot | null
  balance?: {
    equity?: number | null
    available?: number | null
    blocked_margin?: number | null
    ts?: string | null
  } | null
  status?: StrategyStatus
}

/** Live event from GET /api/stream/snapshots. */
export type SnapshotStreamEvent = {
  strategy_id: string
  ts: string
  equity: number
  realized: number
  unrealized: number
  available?: number | null
  pnl?: PnlSnapshot | null
}

export type Position = {
  strategy_id?: string
  symbol: string
  ts?: string
  venue_qty: number
  bot_qty: number | null
  entry?: number | null
  mark?: number | null
  unrealized?: number | null
  realized?: number | null
  mismatch?: boolean
}

export type Order = {
  strategy_id?: string
  client_order_id: string
  symbol: string
  side: string
  price: number
  qty: number
  reduce_only?: boolean
  reject_code?: string | null
  status?: string
  created_at?: string
}

export type Fill = {
  strategy_id?: string
  trade_id: string
  client_order_id?: string | null
  symbol: string
  side: string
  price: number
  qty: number
  fee?: number | null
  limit_price?: number | null
  arrival_mid?: number | null
  mid_at_fill?: number | null
  created_at?: string
}

export type ReconcileRow = {
  strategy_id?: string
  symbol: string
  ts?: string
  venue_qty: number
  bot_qty: number | null
  mismatch: boolean
  entry?: number | null
  mark?: number | null
  unrealized?: number | null
}

export type TcaRow = {
  strategy_id?: string
  trade_id: string
  symbol?: string
  side?: string
  slippage_bps: number | null
  effective_spread_bps: number | null
  fee_bps: number | null
  fee_quote?: number | null
  markout_5s_bps: number | null
  net_5s_bps: number | null
  quoted_half_spread_bps?: number | null
}

export type ReconcileResponse = {
  latest_by_symbol: ReconcileRow[]
  mismatches: ReconcileRow[]
}

export type AnalyticsBucket = 'hour' | 'day'

export type AnalyticsSeriesPoint = {
  ts: string
  slippage_bps: number | null
  fee_quote: number
  volume_quote: number
  equity: number | null
  realized: number | null
  unrealized: number | null
  effective_spread_bps: number | null
  markout_5s_bps: number | null
  net_5s_bps: number | null
}

export type HeatmapCell = {
  day: string
  hour: number
  value: number
}

export type AnalyticsHeatmap = {
  slippage_bps: HeatmapCell[]
  fee_quote: HeatmapCell[]
  volume_quote: HeatmapCell[]
  equity: HeatmapCell[]
}

export type AnalyticsResponse = {
  from: string
  to: string
  bucket: AnalyticsBucket
  series: AnalyticsSeriesPoint[]
  heatmap: AnalyticsHeatmap
}

/** Strategy config body — no api key / secret / token fields. */
export type StrategyConfigBody = {
  symbols: string
  order_qty: number
  max_inventory: number
  half_spread_bps: number
  min_half_spread_bps: number
  max_half_spread_bps: number
  inv_spread_widen: number
  reject_kill_count: number
  l3_jump_bps: number
}

export type StrategyConfigResponse = {
  strategy_id: string
  version: number
  body: StrategyConfigBody
  created_at?: string
}
