import { useState } from 'react'
import { closePosition, fetchTicker } from '@/api/oems'
import type { Position, QuoteState, Ticker } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { Empty, ErrorNote, Stat } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { configNumber, useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import {
  fmtBps,
  fmtCompactUsd,
  fmtNum,
  fmtPct,
  fmtPrice,
  fmtQty,
  fmtSignedUsd,
  fmtUsd,
  signTone,
} from '@/lib/format'
import { toastSuccess } from '@/lib/toast'
import { cn } from '@/lib/utils'

export function useTicker(symbol: string) {
  const { strategyId } = useApp()
  return usePoll((s) => fetchTicker(strategyId, symbol, s), 1500, [strategyId, symbol])
}

export function SymbolBar({ ticker, error }: { ticker: Ticker | undefined; error: string | null }) {
  const { symbols, symbol, setSymbol } = useApp()
  const digits = ticker ? Math.max(2, decimals(ticker.tick_size)) : 2
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border bg-panel px-3 py-2">
      <label className="flex items-center gap-2">
        <span className="sr-only">Symbol</span>
        <select
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          className="h-8 rounded-md border bg-background px-2 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {symbols.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <span className="text-[11px] text-muted-foreground">{ticker?.venue_symbol ?? ''} perp</span>
      </label>
      {error && !ticker ? <span className="text-xs text-down">{error}</span> : null}
      <div className="num text-xl font-semibold" title="Mark price">
        {fmtPrice(ticker?.mark, digits)}
      </div>
      <Stat label="24h change" value={fmtPct(ticker?.change_24h_pct, 2, true)} tone={signTone(ticker?.change_24h_pct)} />
      <Stat label="Index" value={fmtPrice(ticker?.spot, digits)} />
      <Stat label="Last" value={fmtPrice(ticker?.last, digits)} />
      <Stat label="24h high / low" value={`${fmtPrice(ticker?.high_24h, digits)} / ${fmtPrice(ticker?.low_24h, digits)}`} />
      <Stat label="Spread" value={fmtBps(ticker?.spread_bps, 2, false)} />
      <Stat label="Funding / 8h" value={ticker ? `${fmtNum(ticker.funding_rate_pct, 4)}%` : '—'} sub={ticker ? (ticker.funding_rate_pct >= 0 ? 'longs pay' : 'shorts pay') : undefined} />
      <Stat label="Open interest" value={fmtCompactUsd(ticker?.oi_usd)} />
      <Stat label="24h turnover" value={fmtCompactUsd(ticker?.turnover_24h_usd)} />
    </div>
  )
}

export function decimals(tick: number | null | undefined): number {
  if (!tick || tick <= 0) return 2
  const s = tick.toString()
  if (s.includes('e-')) return Number(s.split('e-')[1])
  return s.includes('.') ? s.split('.')[1].length : 0
}

const REGIME = ['L0 calm', 'L1 elevated', 'L2 stressed', 'L3 crash'] as const

function Row({ label, children, tone }: { label: string; children: React.ReactNode; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-[3px] text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('num text-right', tone)}>{children}</span>
    </div>
  )
}

export function QuotePanel({ q, digits, telemetryAttached }: { q: QuoteState | undefined; digits: number; telemetryAttached: boolean }) {
  const { config, symbol, overview } = useApp()
  if (!q) {
    const running = overview?.strategy.desired_state === 'running'
    return (
      <Empty>
        {!running
          ? 'The bot is not running. Start it from the Strategy page to see live quote state.'
          : telemetryAttached
            ? `No quote state for ${symbol} from the bot yet.`
            : 'No bot telemetry. The bot was started before the OEMS captured its output; restart it from the Strategy page to see live quote state.'}
      </Empty>
    )
  }
  const maxInv = configNumber(config, 'MM_MAX_INVENTORY', q.symbol)
  const invPct = maxInv ? Math.min(100, (Math.abs(q.inventory) / maxInv) * 100) : null
  const half = q.fair > 0 ? ((q.ask - q.bid) / q.fair) * 1e4 / 2 : null
  const bidDist = q.fair > 0 ? ((q.fair - q.bid) / q.fair) * 1e4 : null
  const askDist = q.fair > 0 ? ((q.ask - q.fair) / q.fair) * 1e4 : null
  return (
    <div className="px-3 py-2">
      <div className="mb-2 grid grid-cols-2 gap-2">
        <div className={cn('rounded-md border px-2 py-1.5', !q.place_ask && 'opacity-50')}>
          <div className="text-[10px] text-muted-foreground uppercase">Our ask {q.place_ask ? '' : '(off)'}</div>
          <div className="num text-sm font-semibold text-down">{fmtPrice(q.ask, digits)}</div>
          <div className="num text-[11px] text-muted-foreground">+{fmtNum(askDist, 2)} bps from fair</div>
        </div>
        <div className={cn('rounded-md border px-2 py-1.5', !q.place_bid && 'opacity-50')}>
          <div className="text-[10px] text-muted-foreground uppercase">Our bid {q.place_bid ? '' : '(off)'}</div>
          <div className="num text-sm font-semibold text-up">{fmtPrice(q.bid, digits)}</div>
          <div className="num text-[11px] text-muted-foreground">−{fmtNum(bidDist, 2)} bps from fair</div>
        </div>
      </div>
      <Row label="Fair value">{fmtPrice(q.fair, digits + 1)}</Row>
      <Row label="Reservation (skewed)">{fmtPrice(q.reservation, digits + 1)}</Row>
      <Row label="Half-spread">{fmtBps(half, 2, false)}</Row>
      <Row label="Binance lead skew">{q.lead_skew_bps === null || q.lead_skew_bps === undefined ? 'no feed' : fmtBps(q.lead_skew_bps)}</Row>
      <Row label="Volatility (horizon)">{fmtBps(q.vol_bps, 1, false)}</Row>
      <Row label="Regime" tone={q.regime_level >= 2 ? 'text-down' : q.regime_level === 1 ? 'text-warn' : undefined}>
        {REGIME[q.regime_level] ?? `L${q.regime_level}`}
      </Row>
      <Row label="Markout widen (bid / ask)">
        {fmtNum(q.markout_extra_bid_bps, 1)} / {fmtNum(q.markout_extra_ask_bps, 1)} bps
      </Row>
      <div className="mt-2">
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Inventory vs cap</span>
          <span className="num">
            {fmtQty(q.inventory)} / {maxInv === null ? '—' : fmtQty(maxInv)}
          </span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted" role="meter" aria-valuenow={invPct ?? 0} aria-valuemin={0} aria-valuemax={100} aria-label="Inventory as percent of cap">
          <div
            className={cn('h-full rounded-full', (invPct ?? 0) >= 100 ? 'bg-down' : (invPct ?? 0) >= 60 ? 'bg-warn' : 'bg-s1')}
            style={{ width: `${invPct ?? 0}%` }}
          />
        </div>
      </div>
      <p className="mt-2 text-[10px] text-muted-foreground">Bot telemetry · {fmtNum(q.age_s, 1)} s old</p>
    </div>
  )
}

export function PositionPanel({ position, ticker, digits }: { position: Position | undefined; ticker: Ticker | undefined; digits: number }) {
  const { overview, strategyId, refreshOverview, symbol, config } = useApp()
  const [closeOpen, setCloseOpen] = useState(false)
  const running = overview?.strategy.desired_state === 'running'
  const qty = position?.venue_qty ?? 0
  const mark = ticker?.mark ?? position?.mark ?? null
  const notional = mark ? Math.abs(qty) * mark : null
  const equity = overview?.balance?.equity ?? null
  const liqDist = position?.liq_price && mark ? (Math.abs(position.liq_price - mark) / mark) * 100 : null
  const maxInv = configNumber(config, 'MM_MAX_INVENTORY', symbol)

  if (!overview) return <ErrorNote message="Waiting for account data…" />
  return (
    <div className="px-3 py-2">
      <div className="mb-2 flex items-baseline justify-between">
        <span className={cn('text-sm font-semibold', qty > 0 ? 'text-up' : qty < 0 ? 'text-down' : 'text-muted-foreground')}>
          {qty > 0 ? 'Long' : qty < 0 ? 'Short' : 'Flat'}
        </span>
        <span className="num text-sm font-semibold">{fmtQty(qty)}</span>
      </div>
      <Row label="Notional">{fmtUsd(notional)}</Row>
      <Row label="Entry">{qty ? fmtPrice(position?.entry, digits) : '—'}</Row>
      <Row label="Mark">{fmtPrice(mark, digits)}</Row>
      <Row label="Unrealized" tone={signTone(position?.unrealized)}>
        {fmtSignedUsd(qty ? position?.unrealized : 0)}
      </Row>
      <Row label="Liq. price">
        {position?.liq_price ? `${fmtPrice(position.liq_price, digits)} (${fmtNum(liqDist, 1)}% away)` : '—'}
      </Row>
      <Row label="Margin">{fmtUsd(position?.margin)}</Row>
      <Row label="Notional / equity">{notional && equity ? fmtPct((notional / equity) * 100, 1) : '—'}</Row>
      <Row label="Cap (MM_MAX_INVENTORY)">{maxInv === null ? '—' : fmtQty(maxInv)}</Row>
      {position?.mismatch ? (
        <p className="mt-1 text-[11px] text-warn">! Bot inventory ({fmtQty(position.bot_qty)}) differs from the venue.</p>
      ) : null}
      <Button
        size="sm"
        variant="outline"
        className="mt-2 w-full"
        disabled={!qty || running}
        onClick={() => setCloseOpen(true)}
        title={running ? 'Stop the bot first: it would re-quote against the close' : qty ? 'Close with a reduce-only market order' : 'No position'}
      >
        {running && qty ? 'Stop bot to close position' : 'Close position'}
      </Button>
      <ConfirmDialog
        open={closeOpen}
        onOpenChange={setCloseOpen}
        title={`Close ${symbol} position`}
        destructive
        typeToConfirm={symbol}
        confirmLabel="Send reduce-only market order"
        description={
          <>
            <p>
              Sends a reduce-only <span className="font-semibold text-foreground">market</span> {qty > 0 ? 'sell' : 'buy'} for{' '}
              <span className="num text-foreground">{fmtQty(Math.abs(qty))}</span> at the current book. It pays the taker fee
              (about 5.3 bps on Delta retail) and any spread.
            </p>
            <p>This is a risk decision, not a restart step.</p>
          </>
        }
        onConfirm={async () => {
          const r = await closePosition(symbol, strategyId)
          toastSuccess('Close order sent', `${r.side} ${r.contracts} contracts, reduce-only`)
          refreshOverview()
        }}
      />
    </div>
  )
}
