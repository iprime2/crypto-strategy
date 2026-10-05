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
  Strategy,
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

export const fetchStrategies = (signal?: AbortSignal) => apiGet<Strategy[]>('/api/strategies', signal)

export const fetchVenueOrders = (strategyId: string, signal?: AbortSignal) =>
  apiGet<VenueOrders>(`/api/venue/orders${query({ strategy_id: strategyId })}`, signal)

export const fetchTelemetry = (strategyId: string, events = 150, signal?: AbortSignal) =>
  apiGet<BotTelemetry>(`/api/bot/telemetry${query({ strategy_id: strategyId, events })}`, signal)

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

/** Market data comes from the strategy's environment: demo and mainnet prices differ. */
export const fetchTicker = (strategyId: string, symbol: string, signal?: AbortSignal) =>
  apiGet<Ticker>(`/api/market/${enc(symbol)}/ticker${query({ strategy_id: strategyId })}`, signal)

export const fetchBook = (strategyId: string, symbol: string, depth = 20, signal?: AbortSignal) =>
  apiGet<Book>(`/api/market/${enc(symbol)}/book${query({ strategy_id: strategyId, depth })}`, signal)

export const fetchTrades = (strategyId: string, symbol: string, signal?: AbortSignal) =>
  apiGet<MarketTrade[]>(`/api/market/${enc(symbol)}/trades${query({ strategy_id: strategyId })}`, signal)

export const fetchCandles = (
  strategyId: string,
  symbol: string,
  resolution: string,
  from: number,
  to: number,
  signal?: AbortSignal,
) =>
  apiGet<Candle[]>(
    `/api/market/${enc(symbol)}/candles${query({ strategy_id: strategyId, resolution, from, to })}`,
    signal,
  )

/** A real-money (mainnet) strategy needs `confirm` = MAINNET_CONFIRM; the OEMS refuses it otherwise. */
export const startStrategy = (id: string, confirm?: string) =>
  apiPost<{ pid: number }>(`/api/strategies/${enc(id)}/start`, confirm ? { confirm } : undefined)

export const stopStrategy = (id: string) =>
  apiPost<{ signaled: boolean; cancel: unknown }>(`/api/strategies/${enc(id)}/stop`)

export const cancelAllOrders = (id: string) => apiPost<{ cancel: unknown }>(`/api/strategies/${enc(id)}/cancel-all`)

export const closePosition = (symbol: string, strategyId: string) =>
  apiPost<{ side: string; contracts: number }>(`/api/positions/${enc(symbol)}/close`, {
    confirm: symbol,
    strategy_id: strategyId,
  })

export const saveOverrides = (id: string, body: Record<string, string | number>) =>
  apiPost<{ version: number; restarted: { ok: boolean; error?: string } | null; restart_required?: boolean }>(
    `/api/strategies/${enc(id)}/config`,
    body,
  )
