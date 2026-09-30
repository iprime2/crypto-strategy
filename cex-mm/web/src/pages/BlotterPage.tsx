import { useMemo, useState } from 'react'
import { Download } from 'lucide-react'
import { fetchFills, fetchTca, fetchTelemetry, fetchVenueOrders } from '@/api/oems'
import type { Fill } from '@/api/types'
import { ErrorNote, Panel, Segmented } from '@/components/kit'
import { EventsList, FillsTable, OpenOrdersTable, TcaTable } from '@/components/tables'
import { Button } from '@/components/ui/button'
import { useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtAge, fmtUsd } from '@/lib/format'

type Tab = 'orders' | 'fills' | 'tca' | 'events'

function toCsv(fills: Fill[]): string {
  const cols = ['created_at', 'symbol', 'side', 'role', 'price', 'qty', 'notional', 'fee', 'fee_bps', 'mid_at_fill', 'capture_bps', 'trade_id', 'order_id'] as const
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [cols.join(','), ...fills.map((f) => cols.map((c) => esc(f[c])).join(','))].join('\n')
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export function BlotterPage() {
  const { strategyId } = useApp()
  const [tab, setTab] = useState<Tab>('orders')
  const [symbol, setSymbol] = useState('all')
  const [side, setSide] = useState<'all' | 'buy' | 'sell'>('all')
  const [role, setRole] = useState<'all' | 'maker' | 'taker'>('all')

  const orders = usePoll((s) => fetchVenueOrders(s), 2000, [])
  const fills = usePoll((s) => fetchFills(strategyId, 500, s), tab === 'fills' ? 5000 : 30_000, [strategyId, tab === 'fills'])
  const tca = usePoll((s) => fetchTca(strategyId, 300, s), tab === 'tca' ? 5000 : 0, [strategyId, tab === 'tca'])
  const telemetry = usePoll((s) => fetchTelemetry(400, s), tab === 'events' ? 2000 : 0, [tab === 'events'])

  const symbols = useMemo(() => [...new Set((fills.data ?? []).map((f) => f.symbol))].sort(), [fills.data])
  const filtered = useMemo(
    () =>
      (fills.data ?? []).filter(
        (f) => (symbol === 'all' || f.symbol === symbol) && (side === 'all' || f.side === side) && (role === 'all' || f.role === role),
      ),
    [fills.data, symbol, side, role],
  )
  const totals = useMemo(
    () => filtered.reduce((a, f) => ({ notional: a.notional + f.notional, fee: a.fee + f.fee }), { notional: 0, fee: 0 }),
    [filtered],
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-panel px-3 py-2">
        <h1 className="text-sm font-semibold">Blotter</h1>
        <Segmented<Tab>
          label="Blotter view"
          value={tab}
          onChange={setTab}
          options={[
            { value: 'orders', label: `Open orders (${orders.data?.orders.length ?? 0})` },
            { value: 'fills', label: 'Fills' },
            { value: 'tca', label: 'Fill quality' },
            { value: 'events', label: 'Bot events' },
          ]}
        />
      </div>

      {tab === 'orders' ? (
        <Panel title="Open orders at Delta" subtitle={`refreshed ${fmtAge(orders.data?.fetched_at)}`}>
          {orders.error && !orders.data ? <ErrorNote message={orders.error} onRetry={orders.refresh} /> : <OpenOrdersTable orders={orders.data?.orders ?? []} />}
        </Panel>
      ) : null}

      {tab === 'fills' ? (
        <Panel
          title="Fills"
          subtitle={`${filtered.length} shown · ${fmtUsd(totals.notional)} notional · ${fmtUsd(totals.fee)} fees`}
          actions={
            <>
              <select aria-label="Symbol" value={symbol} onChange={(e) => setSymbol(e.target.value)} className="h-7 rounded-md border bg-background px-2 text-xs">
                <option value="all">All symbols</option>
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              <Segmented label="Side" value={side} onChange={setSide} options={[{ value: 'all', label: 'All' }, { value: 'buy', label: 'Buy' }, { value: 'sell', label: 'Sell' }]} />
              <Segmented label="Role" value={role} onChange={setRole} options={[{ value: 'all', label: 'All' }, { value: 'maker', label: 'Maker' }, { value: 'taker', label: 'Taker' }]} />
              <Button size="sm" variant="outline" onClick={() => download(`fills-${strategyId}.csv`, toCsv(filtered))} disabled={!filtered.length}>
                <Download /> CSV
              </Button>
            </>
          }
          bodyClassName="max-h-[calc(100svh-190px)] overflow-auto"
        >
          {fills.error && !fills.data ? <ErrorNote message={fills.error} onRetry={fills.refresh} /> : <FillsTable fills={filtered} />}
          <p className="px-3 py-1 text-[10px] text-muted-foreground">Latest 500 fills from Delta. Capture is the spread earned against the mid at the fill.</p>
        </Panel>
      ) : null}

      {tab === 'tca' ? (
        <Panel title="Fill quality" subtitle="Capture, price move after the fill, and net per fill" bodyClassName="max-h-[calc(100svh-190px)] overflow-auto">
          {tca.error && !tca.data ? <ErrorNote message={tca.error} onRetry={tca.refresh} /> : <TcaTable rows={tca.data ?? []} />}
        </Panel>
      ) : null}

      {tab === 'events' ? (
        <Panel
          title="Bot events"
          subtitle={telemetry.data?.attached ? `from ${telemetry.data.log_path}` : 'no bot log attached'}
          bodyClassName="max-h-[calc(100svh-190px)] overflow-auto"
        >
          <EventsList events={telemetry.data?.events ?? []} />
        </Panel>
      ) : null}
    </div>
  )
}
