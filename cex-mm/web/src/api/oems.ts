import { apiGet, apiPost, listPath, type ListParams } from './client'
import type {
  Fill,
  LatestSnapshot,
  Order,
  PnlSnapshot,
  Position,
  ReconcileRow,
  Strategy,
  StrategyConfigBody,
  StrategyConfigResponse,
  TcaRow,
} from './types'

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

export async function fetchPositions(params: ListParams): Promise<Position[]> {
  return asArray(await apiGet(listPath('/api/positions', params)))
}

export async function fetchOrders(params: ListParams): Promise<Order[]> {
  return asArray(await apiGet(listPath('/api/orders', params)))
}

export async function fetchFills(params: ListParams): Promise<Fill[]> {
  return asArray(await apiGet(listPath('/api/fills', params)))
}

export async function fetchReconcile(params: ListParams): Promise<ReconcileRow[]> {
  return asArray(await apiGet(listPath('/api/reconcile', params)))
}

export async function fetchTca(params: ListParams): Promise<TcaRow[]> {
  return asArray(await apiGet(listPath('/api/tca', params)))
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
