import { apiGet, apiPost, API_BASE, listPath, type ListParams } from './client'
import type {
  AnalyticsResponse,
  Fill,
  LatestSnapshot,
  Order,
  PnlSnapshot,
  Position,
  ReconcileResponse,
  ReconcileRow,
  SnapshotStreamEvent,
  Strategy,
  StrategyConfigBody,
  StrategyConfigResponse,
  TcaRow,
} from './types'

export type { SnapshotStreamEvent }

function asArray<T>(data: T[] | { items?: T[]; data?: T[] } | null | undefined): T[] {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.items)) return data.items
  if (data && Array.isArray(data.data)) return data.data
  return []
}

export async function fetchStrategies(): Promise<Strategy[]> {
  const data = await apiGet<Strategy[] | { strategies?: Strategy[] }>('/api/strategies')
  if (Array.isArray(data)) return data
  return data.strategies ?? []
}

export async function fetchStrategy(id: string): Promise<Strategy> {
  return apiGet<Strategy>(`/api/strategies/${encodeURIComponent(id)}`)
}

export async function fetchLatestSnapshot(strategyId: string): Promise<LatestSnapshot | null> {
  try {
    return await apiGet<LatestSnapshot>(
      `/api/snapshots/latest?strategy_id=${encodeURIComponent(strategyId)}`,
    )
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 404) {
      return null
    }
    throw err
  }
}

export async function fetchPnl(params: ListParams): Promise<PnlSnapshot[]> {
  return asArray(await apiGet(listPath('/api/pnl', params)))
}

/** SSE URL for live snapshot updates (use with EventSource). */
export function snapshotStreamUrl(strategyId: string): string {
  const q = new URLSearchParams()
  q.set('strategy_id', strategyId)
  return `${API_BASE}/api/stream/snapshots?${q.toString()}`
}

export async function fetchPositions(params: ListParams): Promise<Position[]> {
  return asArray(await apiGet(listPath('/api/positions', params)))
}

export async function fetchOrders(params: ListParams): Promise<Order[]> {
  return asArray(await apiGet(listPath('/api/orders', params)))
}

export async function fetchFills(params: ListParams): Promise<Fill[]> {
  return asArray(await apiGet(listPath('/api/fills', params)))
}

export async function fetchReconcile(params: ListParams): Promise<ReconcileResponse> {
  const data = await apiGet<ReconcileResponse | ReconcileRow[]>(listPath('/api/reconcile', params))
  if (Array.isArray(data)) {
    return {
      latest_by_symbol: data,
      mismatches: data.filter((r) => r.mismatch),
    }
  }
  return {
    latest_by_symbol: asArray(data?.latest_by_symbol),
    mismatches: asArray(data?.mismatches),
  }
}

export async function fetchTca(params: ListParams): Promise<TcaRow[]> {
  return asArray(await apiGet(listPath('/api/tca', params)))
}

export async function fetchAnalytics(params: {
  strategy_id: string
  from: string
  to: string
}): Promise<AnalyticsResponse> {
  const q = new URLSearchParams()
  q.set('strategy_id', params.strategy_id)
  q.set('from', params.from)
  q.set('to', params.to)
  return apiGet<AnalyticsResponse>(`/api/analytics?${q.toString()}`)
}

export async function fetchConfig(strategyId: string): Promise<StrategyConfigResponse | null> {
  try {
    return await apiGet<StrategyConfigResponse>(
      `/api/strategies/${encodeURIComponent(strategyId)}/config`,
    )
  } catch (err) {
    if (err && typeof err === 'object' && 'status' in err && (err as { status: number }).status === 404) {
      return null
    }
    throw err
  }
}

export async function postConfig(
  strategyId: string,
  body: StrategyConfigBody,
): Promise<StrategyConfigResponse> {
  return apiPost(`/api/strategies/${encodeURIComponent(strategyId)}/config`, body)
}

export async function startStrategy(strategyId: string): Promise<unknown> {
  return apiPost(`/api/strategies/${encodeURIComponent(strategyId)}/start`)
}

export async function stopStrategy(strategyId: string): Promise<unknown> {
  return apiPost(`/api/strategies/${encodeURIComponent(strategyId)}/stop`)
}
