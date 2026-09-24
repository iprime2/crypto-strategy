export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function fmtUsd(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `$${fmtNum(value, digits)}`
}

export function fmtBps(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${fmtNum(value, digits)} bps`
}

export function fmtSigned(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const sign = value > 0 ? '+' : ''
  return sign + fmtNum(value, digits)
}

export function fmtSignedUsd(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (value > 0) return `+$${fmtNum(value, digits)}`
  if (value < 0) return `-$${fmtNum(Math.abs(value), digits)}`
  return `$${fmtNum(0, digits)}`
}

export function fmtTs(value: string | null | undefined): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString()
}

export function positionMismatch(row: {
  venue_qty: number
  bot_qty: number | null
  mismatch?: boolean
}): boolean {
  if (row.mismatch === true) return true
  if (row.bot_qty === null || row.bot_qty === undefined) return false
  return Math.abs(row.venue_qty - row.bot_qty) > 1e-5
}
