import { useMemo, useState } from 'react'
import { OctagonX, XCircle } from 'lucide-react'
import { cancelAllOrders, closePosition, fetchTelemetry, fetchVenueOrders, stopStrategy } from '@/api/oems'
import type { Overview, Position, VenueOrder } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DataTable, Empty, Panel, Stat, StatusPill, Td, Th, type Level } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { configNumber, useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtNum, fmtPct, fmtPrice, fmtQty, fmtSignedUsd, fmtUsd, signTone } from '@/lib/format'
import { apiCheck, botCheck, venueChecks } from '@/lib/health'
import { toastSuccess } from '@/lib/toast'
import { cn } from '@/lib/utils'

type Alert = { level: Exclude<Level, 'idle' | 'ok'>; title: string; detail: string }

function deriveAlerts(
  o: Overview | undefined,
  orders: VenueOrder[],
  lossLimit: number | null,
  caps: Record<string, number | null>,
  apiErr: string | null,
  apiAt: number | null,
): Alert[] {
  const out: Alert[] = []
  const now = Date.now()
  const api = apiCheck(apiErr, apiAt, now)
  if (api.level === 'bad' || api.level === 'warn') out.push({ level: api.level, title: 'OEMS connection', detail: api.detail })
  if (!o) return out
  for (const c of venueChecks(o, now)) {
    if (c.level === 'bad' || c.level === 'warn') out.push({ level: c.level, title: `Venue ${c.label.toLowerCase()} feed`, detail: c.detail })
  }
  const bot = botCheck(o, now)
  if (bot.level === 'warn' || bot.level === 'bad') out.push({ level: bot.level, title: bot.label, detail: bot.detail })
  const running = o.strategy.desired_state === 'running'
  if (!running && orders.length) {
    out.push({ level: 'bad', title: 'Orders resting without the bot', detail: `${orders.length} open order(s) at Delta and no bot managing them. Cancel them.` })
  }
  for (const p of o.positions ?? []) {
    const cap = caps[p.symbol]
    if (cap && Math.abs(p.venue_qty) > cap * 1.0001) {
      out.push({ level: 'bad', title: `${p.symbol} over inventory cap`, detail: `${fmtQty(p.venue_qty)} vs cap ${fmtQty(cap)}` })
    }
    if (p.mismatch) {
      out.push({ level: 'warn', title: `${p.symbol} bot ≠ venue`, detail: `bot ${fmtQty(p.bot_qty)} · venue ${fmtQty(p.venue_qty)}` })
    }
    if (p.liq_price && p.mark) {
      const dist = (Math.abs(p.liq_price - p.mark) / p.mark) * 100
      if (dist < 15) out.push({ level: dist < 7 ? 'bad' : 'warn', title: `${p.symbol} near liquidation`, detail: `${fmtNum(dist, 1)}% from liq. price ${fmtPrice(p.liq_price)}` })
    }
  }
  if (lossLimit && o.day.pnl !== null && o.day.pnl < 0) {
    const used = (-o.day.pnl / lossLimit) * 100
    if (used >= 50) {
      out.push({
        level: used >= 100 ? 'bad' : 'warn',
        title: 'Daily loss',
        detail: `${fmtSignedUsd(o.day.pnl)} is ${fmtNum(used, 0)}% of the ${fmtUsd(lossLimit)} limit. The bot's own daily-loss halt is not wired; act here.`,
      })
    }
  }
  const notPostOnly = orders.filter((x) => x.post_only !== true && !x.reduce_only)
  if (notPostOnly.length) {
    out.push({
      level: 'warn',
      title: 'Post-only flag not reported',
      detail: `${notPostOnly.length} resting quote(s) show post_only ≠ true at Delta. A crossing edit could fill as taker (≈5.3 bps).`,
    })
  }
  return out
}

function ExposureTable({ o, caps }: { o: Overview; caps: Record<string, number | null> }) {
  const { strategyId, refreshOverview } = useApp()
  const [closing, setClosing] = useState<Position | null>(null)
  const running = o.strategy.desired_state === 'running'
  const equity = o.balance?.equity ?? null
  const positions = o.positions ?? []
  if (!positions.length) return <Empty>Flat: no open positions at Delta</Empty>
  return (
    <>
      <DataTable>
        <thead>
          <tr>
            <Th align="left">Symbol</Th>
            <Th>Venue qty</Th>
            <Th>Bot qty</Th>
            <Th>Notional</Th>
            <Th>% equity</Th>
            <Th>% of cap</Th>
            <Th>Entry</Th>
            <Th>Mark</Th>
            <Th>Unrealized</Th>
            <Th>Liq. distance</Th>
            <Th />
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const notional = Math.abs(p.venue_qty) * p.mark
            const cap = caps[p.symbol]
            const capPct = cap ? (Math.abs(p.venue_qty) / cap) * 100 : null
            const liq = p.liq_price ? (Math.abs(p.liq_price - p.mark) / p.mark) * 100 : null
            return (
              <tr key={p.symbol}>
                <Td align="left" className="font-medium">{p.symbol}</Td>
                <Td className={signTone(p.venue_qty)}>{fmtQty(p.venue_qty)}</Td>
                <Td className={cn(p.mismatch && 'text-warn')} title={p.bot_qty === null ? 'Bot is not reporting inventory' : undefined}>
                  {p.bot_qty === null ? 'n/a' : fmtQty(p.bot_qty)}
                  {p.mismatch ? ' !' : ''}
                </Td>
                <Td>{fmtUsd(notional)}</Td>
                <Td>{equity ? fmtPct((notional / equity) * 100, 1) : '—'}</Td>
                <Td className={cn(capPct !== null && capPct > 100 && 'text-down')}>{capPct === null ? '—' : fmtPct(capPct, 0)}</Td>
                <Td>{fmtPrice(p.entry)}</Td>
                <Td>{fmtPrice(p.mark)}</Td>
                <Td className={signTone(p.unrealized)}>{fmtSignedUsd(p.unrealized)}</Td>
                <Td>{liq === null ? '—' : fmtPct(liq, 1)}</Td>
                <Td>
                  <Button size="xs" variant="outline" disabled={running} onClick={() => setClosing(p)} title={running ? 'Stop the bot first' : 'Reduce-only market close'}>
                    Close
                  </Button>
                </Td>
              </tr>
            )
          })}
        </tbody>
      </DataTable>
      {running ? <p className="px-3 py-1.5 text-[11px] text-muted-foreground">Closing is disabled while the bot runs: it would re-quote against the close. Use the kill switch first.</p> : null}
      <ConfirmDialog
        open={closing !== null}
        onOpenChange={(v) => !v && setClosing(null)}
        title={`Close ${closing?.symbol ?? ''} position`}
        destructive
        typeToConfirm={closing?.symbol}
        confirmLabel="Send reduce-only market order"
        description={
          <p>
            Market {closing && closing.venue_qty > 0 ? 'sell' : 'buy'} of {fmtQty(Math.abs(closing?.venue_qty ?? 0))}, reduce-only. Pays the taker fee and the spread.
          </p>
        }
        onConfirm={async () => {
          if (!closing) return
          const r = await closePosition(closing.symbol, strategyId)
          toastSuccess('Close order sent', `${r.side} ${r.contracts} contracts`)
          refreshOverview()
        }}
      />
    </>
  )
}

export function RiskPage() {
  const { overview: o, config, symbols, strategyId, refreshOverview, overviewError, overviewUpdatedAt } = useApp()
  const orders = usePoll((s) => fetchVenueOrders(s), 3000, [])
  const telemetry = usePoll((s) => fetchTelemetry(1, s), 5000, [])
  const [dialog, setDialog] = useState<'kill' | 'cancel' | null>(null)
  const lossLimit = configNumber(config, 'MM_DAILY_LOSS_LIMIT_USD')
  const caps = useMemo(() => {
    const out: Record<string, number | null> = {}
    for (const s of [...symbols, ...(o?.positions ?? []).map((p) => p.symbol)]) out[s] = configNumber(config, 'MM_MAX_INVENTORY', s)
    return out
  }, [symbols, o?.positions, config])
  const alerts = deriveAlerts(o, orders.data?.orders ?? [], lossLimit, caps, overviewError, overviewUpdatedAt)
  const bal = o?.balance
  const running = o?.strategy.desired_state === 'running'
  const marginPct = bal && bal.equity > 0 ? (bal.blocked_margin / bal.equity) * 100 : null
  const lossUsed = lossLimit && o?.day.pnl !== null && o?.day.pnl !== undefined ? Math.max(0, (-o.day.pnl / lossLimit) * 100) : null
  const c = telemetry.data?.counters

  return (
    <div className="flex flex-col gap-2">
      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="Alerts" subtitle={alerts.length ? `${alerts.length} active` : 'all clear'}>
          {alerts.length ? (
            <ul className="divide-y divide-border/60">
              {alerts.map((a) => (
                <li key={a.title} className="flex items-start gap-3 px-3 py-2">
                  <StatusPill level={a.level} label={a.level === 'bad' ? 'Critical' : 'Warning'} />
                  <div className="min-w-0 text-xs">
                    <div className="font-semibold">{a.title}</div>
                    <div className="text-muted-foreground">{a.detail}</div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="px-3 py-4">
              <StatusPill level="ok" label="No active alerts" />
            </div>
          )}
        </Panel>
        <Panel title="Emergency actions">
          <div className="flex flex-col gap-2 p-3">
            <Button variant="destructive" onClick={() => setDialog('kill')} disabled={!running}>
              <OctagonX /> Kill switch: stop bot and cancel orders
            </Button>
            <Button variant="outline" onClick={() => setDialog('cancel')} disabled={!orders.data?.orders.length}>
              <XCircle /> Cancel all open orders ({orders.data?.orders.length ?? 0})
            </Button>
            <p className="text-[11px] text-muted-foreground">
              {running
                ? 'While the bot runs it will place new quotes right after a cancel-all. Use the kill switch to stop quoting.'
                : 'Bot stopped. Positions can be closed from the exposure table.'}
            </p>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-2 gap-3 rounded-lg border bg-panel p-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Equity" value={fmtUsd(bal?.equity)} />
        <Stat label="Available" value={fmtUsd(bal?.available)} />
        <Stat label="Blocked margin" value={fmtUsd(bal?.blocked_margin)} sub={marginPct === null ? undefined : `${fmtNum(marginPct, 1)}% of equity`} />
        <Stat label="Day PnL" value={fmtSignedUsd(o?.day.pnl)} tone={signTone(o?.day.pnl)} sub={lossLimit ? `limit ${fmtUsd(lossLimit)} · ${fmtNum(lossUsed, 0)}% used` : undefined} />
        <Stat label="Rejects / regime pauses" value={c ? `${c.rejects} / ${c.regime_pauses}` : '—'} sub="since telemetry attached" />
        <Stat label="Warnings / errors" value={c ? `${c.warnings} / ${c.errors}` : '—'} sub="bot log" />
      </div>

      <Panel title="Exposure" subtitle="Venue positions vs caps (MM_MAX_INVENTORY) and equity">
        {o ? <ExposureTable o={o} caps={caps} /> : <Empty>Loading…</Empty>}
      </Panel>

      <ConfirmDialog
        open={dialog === 'kill'}
        onOpenChange={(v) => !v && setDialog(null)}
        title="Kill switch"
        destructive
        confirmLabel="Stop bot and cancel orders"
        description={<p>Stops {strategyId} and cancels all its orders at Delta. Positions stay open.</p>}
        onConfirm={async () => {
          await stopStrategy(strategyId)
          toastSuccess('Bot stopped', 'Orders cancelled; positions left open.')
          refreshOverview()
        }}
      />
      <ConfirmDialog
        open={dialog === 'cancel'}
        onOpenChange={(v) => !v && setDialog(null)}
        title="Cancel all open orders"
        confirmLabel="Cancel orders"
        destructive
        description={
          <p>
            Cancels every open order for {symbols.join(', ')} at Delta.
            {running ? ' The bot is running and will quote again on its next loop.' : ''}
          </p>
        }
        onConfirm={async () => {
          await cancelAllOrders(strategyId)
          toastSuccess('Cancel-all sent')
          orders.refresh()
        }}
      />
    </div>
  )
}
