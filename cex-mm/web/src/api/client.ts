import type { ApiErrorBody } from './types'

export const API_BASE =
  import.meta.env.VITE_OEMS_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8791'

export const DEFAULT_LIMIT = 100

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(status: number, body: ApiErrorBody | null, fallback: string) {
    super(body?.message || fallback)
    this.name = 'ApiError'
    this.status = status
    this.code = body?.code || 'unknown'
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null
  try {
    body = (await res.json()) as ApiErrorBody
  } catch {
    body = null
  }
  return new ApiError(res.status, body, `Request failed (${res.status})`)
}

export type ListParams = {
  strategy_id: string
  limit?: number
}

function withListQuery(path: string, params: ListParams): string {
  const q = new URLSearchParams()
  q.set('strategy_id', params.strategy_id)
  q.set('limit', String(params.limit ?? DEFAULT_LIMIT))
  return `${path}?${q.toString()}`
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw await parseError(res)
  return (await res.json()) as T
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

export function listPath(path: string, params: ListParams): string {
  return withListQuery(path, params)
}
