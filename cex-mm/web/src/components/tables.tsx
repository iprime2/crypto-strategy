import type { BotEvent, Fill, TcaRow, VenueOrder } from '@/api/types'
import { DataTable, Empty, Td, Th } from '@/components/kit'
import {
  fmtAge,
  fmtBps,
  fmtNum,
  fmtPrice,
  fmtQty,
  fmtStamp,
  fmtTime,
  fmtUsd,
  sideLabel,
  sideTone,
  signTone,
} from '@/lib/format'
import { cn } from '@/lib/utils'

export function OpenOrdersTable({
  orders,
  highlight,
  mids,
  className,
}: {
  orders: VenueOrder[]
  highlight?: string
  /** Current mid per symbol, to show how far each quote rests from the market. */
  mids?: Record<string, number>
  className?: string
}) {
  if (!orders.length) return <Empty>No open orders at the venue</Empty>
  const now = Date.now()
  return (
    <DataTable className={className}>
      <thead>
        <tr>
          <Th align="left">Symbol</Th>
          <Th align="left">Side</Th>
          <Th>Price</Th>
          <Th>From mid</Th>
          <Th>Size</Th>
          <Th>Unfilled</Th>
          <Th align="left">Flags</Th>
          <Th>Last change</Th>
          <Th align="left">Client id</Th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => {
          const mid = mids?.[o.symbol]
          const dist = mid ? ((o.side === 'buy' ? mid - o.price : o.price - mid) / mid) * 1e4 : null
          return (
            <tr key={o.id} className={cn(highlight === o.symbol && 'bg-muted/40')}>
              <Td align="left" className="font-medium">{o.symbol}</Td>
              <Td align="left" className={sideTone(o.side)}>{sideLabel(o.side)}</Td>
              <Td>{fmtPrice(o.price)}</Td>
              <Td title="Distance behind the mid; positive = passive">{dist === null ? '—' : fmtBps(dist, 1)}</Td>
              <Td>{fmtQty(o.size)}</Td>
              <Td>{fmtQty(o.unfilled)}</Td>
              <Td align="left" className="text-muted-foreground">
                {[o.post_only === false ? 'not post-only' : o.post_only ? 'post-only' : null, o.reduce_only ? 'reduce-only' : null, o.order_type !== 'limit_order' ? o.order_type : null]
                  .filter(Boolean)
                  .join(' · ') || 'limit'}
              </Td>
              <Td title={o.updated_at ?? ''}>{fmtAge(o.updated_at ?? o.created_at, now)}</Td>
              <Td align="left" className="num text-muted-foreground">{o.client_order_id ?? o.id}</Td>
            </tr>
          )
        })}
      </tbody>
    </DataTable>
  )
}

export function FillsTable({ fills, className, showSymbol = true }: { fills: Fill[]; className?: string; showSymbol?: boolean }) {
  if (!fills.length) return <Empty>No fills yet</Empty>
  return (
    <DataTable className={className}>
      <thead>
        <tr>
          <Th align="left">Time</Th>
          {showSymbol ? <Th align="left">Symbol</Th> : null}
          <Th align="left">Side</Th>
          <Th align="left">Role</Th>
          <Th>Price</Th>
          <Th>Qty</Th>
          <Th>Notional</Th>
          <Th>Fee</Th>
          <Th title="Spread earned vs the mid at the fill">Capture</Th>
        </tr>
      </thead>
      <tbody>
        {fills.map((f) => (
          <tr key={f.trade_id}>
            <Td align="left" className="num" title={f.created_at}>{fmtStamp(f.created_at)}</Td>
            {showSymbol ? <Td align="left" className="font-medium">{f.symbol}</Td> : null}
            <Td align="left" className={sideTone(f.side)}>{sideLabel(f.side)}</Td>
            <Td align="left" className={f.role === 'taker' ? 'text-warn' : 'text-muted-foreground'}>{f.role ?? '—'}</Td>
            <Td>{fmtPrice(f.price)}</Td>
            <Td>{fmtQty(f.qty)}</Td>
            <Td>{fmtUsd(f.notional)}</Td>
            <Td title={f.fee_bps === null ? '' : `${fmtNum(f.fee_bps, 2)} bps`}>{fmtUsd(f.fee, 4)}</Td>
            <Td className={signTone(f.capture_bps)}>{fmtBps(f.capture_bps, 2)}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  )
}

export function TcaTable({ rows, className }: { rows: TcaRow[]; className?: string }) {
  if (!rows.length) return <Empty>No fills with markouts yet</Empty>
  const now = Date.now()
  // Markouts are measured for 30 minutes after a fill; older fills without a price series stay n/a.
  const cell = (v: number | null, created: string) =>
    v === null ? (
      <span className="text-muted-foreground" title={now - Date.parse(created) > 35 * 60_000 ? 'No price series recorded for this fill' : 'Filled in as time passes'}>
        {now - Date.parse(created) > 35 * 60_000 ? 'n/a' : 'pending'}
      </span>
    ) : (
      fmtBps(v, 2)
    )
  return (
    <DataTable className={className}>
      <thead>
        <tr>
          <Th align="left">Time</Th>
          <Th align="left">Symbol</Th>
          <Th align="left">Side</Th>
          <Th align="left">Role</Th>
          <Th>Price</Th>
          <Th>Capture</Th>
          <Th>Move 1 s</Th>
          <Th>Move 5 s</Th>
          <Th>Move 30 s</Th>
          <Th>Move 60 s</Th>
          <Th>Fee</Th>
          <Th title="Capture + 60 s move − fee">Net 60 s</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.trade_id}>
            <Td align="left" className="num">{fmtStamp(r.created_at)}</Td>
            <Td align="left" className="font-medium">{r.symbol}</Td>
            <Td align="left" className={sideTone(r.side)}>{sideLabel(r.side)}</Td>
            <Td align="left" className={r.role === 'taker' ? 'text-warn' : 'text-muted-foreground'}>{r.role ?? '—'}</Td>
            <Td>{fmtPrice(r.price)}</Td>
            <Td className={signTone(r.capture_bps)}>{fmtBps(r.capture_bps, 2)}</Td>
            <Td className={signTone(r.markout_1s_bps)}>{cell(r.markout_1s_bps, r.created_at)}</Td>
            <Td className={signTone(r.markout_5s_bps)}>{cell(r.markout_5s_bps, r.created_at)}</Td>
            <Td className={signTone(r.markout_30s_bps)}>{cell(r.markout_30s_bps, r.created_at)}</Td>
            <Td className={signTone(r.markout_60s_bps)}>{cell(r.markout_60s_bps, r.created_at)}</Td>
            <Td>{fmtBps(r.fee_bps, 2, false)}</Td>
            <Td className={cn('font-semibold', signTone(r.net_60s_bps))}>{cell(r.net_60s_bps, r.created_at)}</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  )
}

const LEVEL_TONE: Record<BotEvent['level'], string> = { info: 'text-muted-foreground', warn: 'text-warn', error: 'text-down' }
const LEVEL_MARK: Record<BotEvent['level'], string> = { info: '·', warn: '!', error: '✕' }

export function EventsList({ events, className }: { events: BotEvent[]; className?: string }) {
  if (!events.length) return <Empty>No bot events yet</Empty>
  return (
    <ul className={cn('divide-y divide-border/60 overflow-auto text-xs', className)}>
      {events.map((e, i) => (
        <li key={`${e.ts}-${i}`} className="flex gap-2 px-3 py-1">
          <span className="num w-16 shrink-0 text-muted-foreground">{fmtTime(e.ts)}</span>
          <span className={cn('w-3 shrink-0 font-bold', LEVEL_TONE[e.level])} aria-label={e.level}>
            {LEVEL_MARK[e.level]}
          </span>
          <span className="w-24 shrink-0 text-muted-foreground">{e.kind.replace('_', ' ')}</span>
          {e.symbol ? <span className="w-20 shrink-0 font-medium">{e.symbol}</span> : null}
          <span className="min-w-0 flex-1 truncate" title={e.message}>
            {e.message}
          </span>
          {e.count > 1 ? <span className="num shrink-0 rounded bg-muted px-1 text-muted-foreground">×{e.count}</span> : null}
        </li>
      ))}
    </ul>
  )
}
