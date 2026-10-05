import { useMemo, useState } from 'react'
import { fetchFills, fetchTelemetry, fetchVenueOrders } from '@/api/oems'
import { ErrorBoundary, Panel, Segmented } from '@/components/kit'
import { EventsList, FillsTable, OpenOrdersTable } from '@/components/tables'
import { CandleChart } from '@/components/trade/CandleChart'
import { OrderBook, TradesTape } from '@/components/trade/OrderBook'
import { decimals, PositionPanel, QuotePanel, SymbolBar, useTicker } from '@/components/trade/Panels'
import { useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtAge } from '@/lib/format'

type Tab = 'orders' | 'fills' | 'events'

export function TradePage() {
  const { symbol, strategyId, overview } = useApp()
  const ticker = useTicker(symbol)
  const orders = usePoll((s) => fetchVenueOrders(strategyId, s), 2000, [strategyId])
  const fills = usePoll((s) => fetchFills(strategyId, 200, s), 5000, [strategyId])
  const telemetry = usePoll((s) => fetchTelemetry(strategyId, 80, s), 2000, [strategyId])
  const [tab, setTab] = useState<Tab>('orders')

  const tick = ticker.data?.tick_size ?? 0
  const digits = ticker.data ? Math.max(2, decimals(tick)) : 2
  const openOrders = orders.data?.orders ?? []
  const position = overview?.positions?.find((p) => p.symbol === symbol)
  const quote = telemetry.data?.metrics[symbol]
  const mids = useMemo(() => {
    const t = ticker.data
    return t && t.best_bid && t.best_ask ? { [symbol]: (t.best_bid + t.best_ask) / 2 } : undefined
  }, [ticker.data, symbol])
  const symbolFills = useMemo(() => (fills.data ?? []).filter((f) => f.symbol === symbol), [fills.data, symbol])

  return (
    <div className="flex flex-col gap-2">
      <SymbolBar ticker={ticker.data} error={ticker.error} />

      <div className="grid gap-2 xl:grid-cols-[minmax(0,1fr)_300px_300px] lg:grid-cols-[minmax(0,1fr)_300px]">
        <Panel title="Chart" subtitle={`${symbol} · our quotes, fills and entry overlaid`} className="min-h-[460px] lg:row-span-2 xl:row-span-1" bodyClassName="flex flex-col">
          <ErrorBoundary label="Chart">
            <CandleChart
              symbol={symbol}
              orders={openOrders}
              fills={fills.data ?? []}
              entry={position && position.venue_qty !== 0 ? position.entry : null}
              fair={quote?.fair ?? null}
              priceDigits={digits}
            />
          </ErrorBoundary>
        </Panel>
        <Panel title="Order book" subtitle="Delta · 1 s" bodyClassName="overflow-hidden">
          <OrderBook symbol={symbol} orders={openOrders} tick={tick} digits={digits} />
        </Panel>
        <Panel title="Trades" subtitle="Delta tape" className="max-xl:hidden" bodyClassName="max-h-[520px] overflow-auto">
          <TradesTape symbol={symbol} digits={digits} />
        </Panel>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_300px_300px]">
        <Panel
          title="Blotter"
          actions={
            <Segmented<Tab>
              label="Blotter view"
              value={tab}
              onChange={setTab}
              options={[
                { value: 'orders', label: `Open orders (${openOrders.length})` },
                { value: 'fills', label: 'Fills' },
                { value: 'events', label: 'Bot events' },
              ]}
            />
          }
          className="md:col-span-2 xl:col-span-1"
          bodyClassName="max-h-[300px] overflow-auto"
        >
          {tab === 'orders' ? (
            <>
              <OpenOrdersTable orders={openOrders} highlight={symbol} mids={mids} />
              <p className="px-3 py-1 text-[10px] text-muted-foreground">
                From Delta · refreshed {fmtAge(orders.data?.fetched_at)}
                {orders.error ? ` · ${orders.error}` : ''}
              </p>
            </>
          ) : tab === 'fills' ? (
            <FillsTable fills={(fills.data ?? []).slice(0, 100)} />
          ) : (
            <EventsList events={telemetry.data?.events ?? []} />
          )}
        </Panel>
        <Panel title="Strategy quote" subtitle={quote ? `${symbol} · live` : undefined}>
          <QuotePanel q={quote} digits={digits} telemetryAttached={Boolean(telemetry.data?.attached)} />
        </Panel>
        <Panel title="Position" subtitle={symbolFills.length ? `${symbolFills.length} recent fills` : undefined}>
          <PositionPanel position={position} ticker={ticker.data} digits={digits} />
        </Panel>
      </div>
    </div>
  )
}
