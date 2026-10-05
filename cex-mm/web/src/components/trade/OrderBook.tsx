import { useMemo } from 'react'
import { fetchBook, fetchTrades } from '@/api/oems'
import type { BookLevel, VenueOrder } from '@/api/types'
import { Empty, ErrorNote } from '@/components/kit'
import { useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtNum, fmtPrice, fmtQty, fmtTime } from '@/lib/format'
import { cn } from '@/lib/utils'

type Row = { price: number; size: number; total: number; ours: number }

function withTotals(levels: BookLevel[], ours: Map<number, number>, tick: number): Row[] {
  let total = 0
  return levels.map(([price, size]) => {
    total += size
    let mine = 0
    for (const [p, q] of ours) if (Math.abs(p - price) < tick / 2) mine += q
    return { price, size, total, ours: mine }
  })
}

function Level({ row, max, side, digits }: { row: Row; max: number; side: 'bid' | 'ask'; digits: number }) {
  const pct = max > 0 ? Math.min(100, (row.total / max) * 100) : 0
  return (
    <div className={cn('relative grid h-[19px] grid-cols-[1fr_1fr_1fr] items-center px-2 text-[11px]', row.ours > 0 && 'font-semibold')}>
      <div
        aria-hidden
        className={cn('absolute inset-y-0 right-0', side === 'bid' ? 'bg-up/12' : 'bg-down/12')}
        style={{ width: `${pct}%` }}
      />
      <span className={cn('num relative', side === 'bid' ? 'text-up' : 'text-down')}>
        {row.ours > 0 ? <span className="mr-1 text-s1" title={`Our order: ${fmtQty(row.ours)}`}>●</span> : null}
        {fmtPrice(row.price, digits)}
      </span>
      <span className="num relative text-right">{fmtQty(row.size)}</span>
      <span className="num relative text-right text-muted-foreground">{fmtQty(row.total)}</span>
    </div>
  )
}

export function OrderBook({
  symbol,
  orders,
  tick,
  digits,
  depth = 12,
}: {
  symbol: string
  orders: VenueOrder[]
  tick: number
  digits: number
  depth?: number
}) {
  const { strategyId } = useApp()
  const book = usePoll((s) => fetchBook(strategyId, symbol, depth, s), 1000, [strategyId, symbol, depth])
  const ours = useMemo(() => {
    const bids = new Map<number, number>()
    const asks = new Map<number, number>()
    for (const o of orders) {
      if (o.symbol !== symbol) continue
      const m = o.side === 'buy' ? bids : asks
      m.set(o.price, (m.get(o.price) ?? 0) + o.unfilled)
    }
    return { bids, asks }
  }, [orders, symbol])

  const b = book.data
  if (!b) return book.error ? <ErrorNote message={book.error} onRetry={book.refresh} /> : <Empty>Loading book…</Empty>
  const t = tick > 0 ? tick : Math.pow(10, -digits)
  const bids = withTotals(b.bids.slice(0, depth), ours.bids, t)
  const asks = withTotals(b.asks.slice(0, depth), ours.asks, t)
  const max = Math.max(bids.at(-1)?.total ?? 0, asks.at(-1)?.total ?? 0)
  const bestBid = b.bids[0]?.[0]
  const bestAsk = b.asks[0]?.[0]
  const mid = bestBid && bestAsk ? (bestBid + bestAsk) / 2 : null
  const spread = bestBid && bestAsk ? bestAsk - bestBid : null

  return (
    <div className="flex flex-col py-1" aria-label={`${symbol} order book`}>
      <div className="grid grid-cols-[1fr_1fr_1fr] px-2 pb-1 text-[10px] text-muted-foreground uppercase">
        <span>Price</span>
        <span className="text-right">Size</span>
        <span className="text-right">Total</span>
      </div>
      {[...asks].reverse().map((r) => (
        <Level key={`a${r.price}`} row={r} max={max} side="ask" digits={digits} />
      ))}
      <div className="my-0.5 flex items-center justify-between border-y bg-muted/40 px-2 py-1 text-[11px]">
        <span className="num font-semibold">{fmtPrice(mid, digits + 1)}</span>
        <span className="num text-muted-foreground">
          spread {fmtPrice(spread, digits)} · {mid && spread !== null ? `${fmtNum((spread / mid) * 1e4, 2)} bps` : '—'}
        </span>
      </div>
      {bids.map((r) => (
        <Level key={`b${r.price}`} row={r} max={max} side="bid" digits={digits} />
      ))}
      <p className="px-2 pt-1 text-[10px] text-muted-foreground">
        <span className="text-s1">●</span> our resting order · sizes in base units
      </p>
    </div>
  )
}

export function TradesTape({ symbol, digits }: { symbol: string; digits: number }) {
  const { strategyId } = useApp()
  const trades = usePoll((s) => fetchTrades(strategyId, symbol, s), 2000, [strategyId, symbol])
  const rows = trades.data?.slice(0, 40) ?? []
  if (!trades.data) return trades.error ? <ErrorNote message={trades.error} onRetry={trades.refresh} /> : <Empty>Loading trades…</Empty>
  if (!rows.length) return <Empty>No recent trades</Empty>
  return (
    <div className="flex flex-col py-1 text-[11px]">
      <div className="grid grid-cols-[1fr_1fr_1fr] px-2 pb-1 text-[10px] text-muted-foreground uppercase">
        <span>Price</span>
        <span className="text-right">Size</span>
        <span className="text-right">Time</span>
      </div>
      {rows.map((t, i) => (
        <div key={`${t.ts}-${i}`} className="grid h-[19px] grid-cols-[1fr_1fr_1fr] items-center px-2">
          <span className={cn('num', t.side === 'buy' ? 'text-up' : 'text-down')} title={t.side === 'buy' ? 'Aggressive buy' : 'Aggressive sell'}>
            {t.side === 'buy' ? '▲' : '▼'} {fmtPrice(t.price, digits)}
          </span>
          <span className="num text-right">{fmtQty(t.size)}</span>
          <span className="num text-right text-muted-foreground">{fmtTime(t.ts)}</span>
        </div>
      ))}
    </div>
  )
}
