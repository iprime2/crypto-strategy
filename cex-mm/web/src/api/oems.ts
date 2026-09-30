import { apiGet, apiPost, query } from './client'
import type {
  Book,
  BotTelemetry,
  Candle,
  EffectiveConfig,
  Fill,
  MarketTrade,
  Overview,
  Performance,
  PnlSnapshot,
  TcaRow,
  Ticker,
  VenueOrders,
} from './types'

const enc = encodeURIComponent

/** Local midnight as RFC3339, for day PnL. */
export function localDayStart(now = new Date()): string {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString()
}

export const fetchOverview = (strategyId: string, signal?: AbortSignal) =>
  apiGet<Overview>(`/api/overview${query({ strategy_id: strategyId, day_start: localDayStart() })}`, signal)

export const fetchVenueOrders = (signal?: AbortSignal) => apiGet<VenueOrders>('/api/venue/orders', signal)

export const fetchTelemetry = (events = 150, signal?: AbortSignal) =>
  apiGet<BotTelemetry>(`/api/bot/telemetry${query({ events })}`, signal)

export const fetchFills = (strategyId: string, limit = 200, signal?: AbortSignal) =>
  apiGet<Fill[]>(`/api/fills${query({ strategy_id: strategyId, limit })}`, signal)

export const fetchTca = (strategyId: string, limit = 200, signal?: AbortSignal) =>
  apiGet<TcaRow[]>(`/api/tca${query({ strategy_id: strategyId, limit })}`, signal)

export const fetchPnlRange = (strategyId: string, from: string, to: string, signal?: AbortSignal) =>
  apiGet<PnlSnapshot[]>(`/api/pnl${query({ strategy_id: strategyId, from, to })}`, signal)

export const fetchPerformance = (strategyId: string, from: string, to: string, signal?: AbortSignal) =>
  apiGet<Performance>(
    `/api/performance${query({
      strategy_id: strategyId,
      from,
      to,
      tz_offset_min: -new Date().getTimezoneOffset(),
    })}`,
    signal,
  )

export const fetchEffectiveConfig = (strategyId: string, signal?: AbortSignal) =>
  apiGet<EffectiveConfig>(`/api/strategies/${enc(strategyId)}/effective-config`, signal)

export const fetchTicker = (symbol: string, signal?: AbortSignal) =>
  apiGet<Ticker>(`/api/market/${enc(symbol)}/ticker`, signal)

export const fetchBook = (symbol: string, depth = 20, signal?: AbortSignal) =>
  apiGet<Book>(`/api/market/${enc(symbol)}/book${query({ depth })}`, signal)

export const fetchTrades = (symbol: string, signal?: AbortSignal) =>
  apiGet<MarketTrade[]>(`/api/market/${enc(symbol)}/trades`, signal)

export const fetchCandles = (symbol: string, resolution: string, from: number, to: number, signal?: AbortSignal) =>
  apiGet<Candle[]>(`/api/market/${enc(symbol)}/candles${query({ resolution, from, to })}`, signal)

export const startStrategy = (id: string) => apiPost<{ pid: number }>(`/api/strategies/${enc(id)}/start`)

export const stopStrategy = (id: string) =>
  apiPost<{ signaled: boolean; cancel: unknown }>(`/api/strategies/${enc(id)}/stop`)

export const cancelAllOrders = (id: string) => apiPost<{ cancel: unknown }>(`/api/strategies/${enc(id)}/cancel-all`)

export const closePosition = (symbol: string, strategyId: string) =>
  apiPost<{ side: string; contracts: number }>(`/api/positions/${enc(symbol)}/close`, {
    confirm: symbol,
    strategy_id: strategyId,
  })

export const saveOverrides = (id: string, body: Record<string, string | number>) =>
  apiPost<{ version: number; restarted: { ok: boolean; error?: string } | null }>(
    `/api/strategies/${enc(id)}/config`,
    body,
  )
