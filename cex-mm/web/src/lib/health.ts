import type { Overview, StreamHealth } from '@/api/types'
import type { Level } from '@/components/kit'
import { ageSeconds, fmtAge } from './format'

export type Check = { level: Level; label: string; detail: string }

const STREAM_MAX_AGE: Record<string, number> = { orders: 30, ticker: 30, fills: 90 }

function streamLevel(name: string, h: StreamHealth | undefined, now: number): Check {
  const label = name[0].toUpperCase() + name.slice(1)
  if (!h || (!h.last_ok && !h.last_error)) return { level: 'idle', label, detail: 'waiting for first response' }
  const okAge = ageSeconds(h.last_ok, now)
  const errNewer = h.last_error_at && (!h.last_ok || Date.parse(h.last_error_at) > Date.parse(h.last_ok))
  const max = STREAM_MAX_AGE[name] ?? 30
  if (okAge !== null && okAge <= max && !errNewer) {
    return { level: 'ok', label, detail: `ok ${fmtAge(h.last_ok, now)}${h.rtt_ms ? ` · ${h.rtt_ms} ms` : ''}` }
  }
  if (okAge !== null && okAge <= max * 4) {
    return { level: 'warn', label, detail: h.last_error ?? `last ok ${fmtAge(h.last_ok, now)}` }
  }
  return { level: 'bad', label, detail: h.last_error ?? `no response ${fmtAge(h.last_ok, now)}` }
}

export function venueChecks(o: Overview | undefined, now = Date.now()): Check[] {
  if (!o) return []
  return (['orders', 'fills', 'ticker'] as const).map((s) => streamLevel(s, o.venue.health[s], now))
}

export function worst(levels: Level[]): Level {
  if (levels.includes('bad')) return 'bad'
  if (levels.includes('warn')) return 'warn'
  if (levels.includes('ok')) return 'ok'
  return 'idle'
}

export function botCheck(o: Overview | undefined, now = Date.now()): Check {
  if (!o) return { level: 'idle', label: 'Bot', detail: 'unknown' }
  if (o.strategy.desired_state !== 'running') {
    const exit = o.strategy.last_exit
    return {
      level: exit && exit.code !== 0 && exit.code !== null ? 'warn' : 'idle',
      label: 'Bot stopped',
      detail: exit ? `exited ${fmtAge(exit.at, now)}${exit.code !== null ? ` (code ${exit.code})` : ''}` : 'not running',
    }
  }
  if (!o.telemetry.attached) {
    return { level: 'warn', label: 'Bot running', detail: 'no telemetry: started before output logging; restart to attach' }
  }
  const age = ageSeconds(o.telemetry.last_line_at, now)
  if (age === null || age > 15) return { level: 'warn', label: 'Bot running', detail: `telemetry stale (${fmtAge(o.telemetry.last_line_at, now)})` }
  return { level: 'ok', label: 'Bot running', detail: `telemetry ${fmtAge(o.telemetry.last_line_at, now)}` }
}

export function apiCheck(error: string | null, updatedAt: number | null, now = Date.now()): Check {
  if (error && (!updatedAt || now - updatedAt > 10_000)) return { level: 'bad', label: 'OEMS', detail: error }
  if (!updatedAt) return { level: 'idle', label: 'OEMS', detail: 'connecting' }
  if (now - updatedAt > 10_000) return { level: 'warn', label: 'OEMS', detail: `last update ${fmtAge(updatedAt, now)}` }
  return { level: 'ok', label: 'OEMS', detail: 'connected' }
}
