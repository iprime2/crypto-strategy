const DASH = '—'

const isNum = (v: number | null | undefined): v is number =>
  v !== null && v !== undefined && Number.isFinite(v)

export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH
  return value.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtUsd(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH
  return `${value < 0 ? '−' : ''}$${fmtNum(Math.abs(value), digits)}`
}

export function fmtSignedUsd(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH
  if (value === 0) return `$${fmtNum(0, digits)}`
  return `${value > 0 ? '+' : '−'}$${fmtNum(Math.abs(value), digits)}`
}

export function fmtSigned(value: number | null | undefined, digits = 2): string {
  if (!isNum(value)) return DASH
  if (value === 0) return fmtNum(0, digits)
  return `${value > 0 ? '+' : '−'}${fmtNum(Math.abs(value), digits)}`
}

export function fmtBps(value: number | null | undefined, digits = 2, signed = true): string {
  if (!isNum(value)) return DASH
  return `${signed ? fmtSigned(value, digits) : fmtNum(value, digits)} bps`
}

export function fmtPct(value: number | null | undefined, digits = 1, signed = false): string {
  if (!isNum(value)) return DASH
  return `${signed ? fmtSigned(value, digits) : fmtNum(value, digits)}%`
}

/** Decimal places implied by a tick size (0.05 → 2, 0.00001 → 5). */
export function tickDigits(tick: number | null | undefined, fallback = 2): number {
  if (!isNum(tick) || tick <= 0) return fallback
  const s = tick.toString()
  if (s.includes('e-')) return Number(s.split('e-')[1])
  return s.includes('.') ? s.split('.')[1].replace(/0+$/, '').length || 0 : 0
}

/** Price digits from magnitude when the tick is unknown. */
export function priceDigits(v: number | null | undefined): number {
  if (!isNum(v) || v === 0) return 2
  const mag = Math.floor(Math.log10(Math.abs(v)))
  return Math.min(8, Math.max(2, 4 - mag))
}

export function fmtPrice(value: number | null | undefined, digits?: number): string {
  if (!isNum(value)) return DASH
  return fmtNum(value, digits ?? priceDigits(value))
}

export function fmtQty(value: number | null | undefined): string {
  if (!isNum(value)) return DASH
  const abs = Math.abs(value)
  const digits = abs === 0 ? 2 : abs >= 100 ? 0 : abs >= 1 ? 2 : Math.min(6, Math.max(2, 2 - Math.floor(Math.log10(abs))))
  return fmtNum(value, digits)
}

export function fmtCompactUsd(value: number | null | undefined): string {
  if (!isNum(value)) return DASH
  return `${value < 0 ? '−' : ''}$${Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(Math.abs(value))}`
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (!isNum(seconds)) return DASH
  const s = Math.max(0, Math.floor(seconds))
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s % 60}s`
  return `${s}s`
}

export function ageSeconds(ts: string | number | null | undefined, now = Date.now()): number | null {
  if (ts === null || ts === undefined) return null
  const t = typeof ts === 'number' ? ts : Date.parse(ts)
  return Number.isFinite(t) ? Math.max(0, (now - t) / 1000) : null
}

export function fmtAge(ts: string | number | null | undefined, now = Date.now()): string {
  const s = ageSeconds(ts, now)
  if (s === null) return DASH
  if (s < 1) return 'now'
  if (s < 60) return `${Math.floor(s)}s ago`
  return `${fmtDuration(s)} ago`
}

export function fmtTime(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return DASH
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return DASH
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

export function fmtDateTime(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return DASH
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return DASH
  return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

/** Tailwind text class for a signed number (text also carries the sign). */
export function signTone(value: number | null | undefined): string {
  if (!isNum(value) || value === 0) return 'text-foreground'
  return value > 0 ? 'text-up' : 'text-down'
}

export function sideTone(side: string | null | undefined): string {
  return side?.toLowerCase() === 'buy' ? 'text-up' : 'text-down'
}

export function sideLabel(side: string | null | undefined): string {
  return side?.toLowerCase() === 'buy' ? 'Buy' : 'Sell'
}

/** Compact timestamp for blotters: "29 Sep 18:20:15" (local). */
export function fmtStamp(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return DASH
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return DASH
  const day = d.toLocaleDateString([], { day: '2-digit', month: 'short' })
  return `${day} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`
}
