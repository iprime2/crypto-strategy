import { useMemo, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, XAxis, YAxis } from 'recharts'
import { fetchPerformance, fetchPnlRange, fetchTca } from '@/api/oems'
import type { NetPoint, PerfDay } from '@/api/types'
import { DataTable, Empty, ErrorNote, Panel, Segmented, Stat, Td, Th } from '@/components/kit'
import { TcaTable } from '@/components/tables'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtBps, fmtCompactUsd, fmtNum, fmtPct, fmtSignedUsd, fmtUsd, signTone } from '@/lib/format'

type Range = '1d' | '7d' | '30d' | '90d'
const RANGES: { value: Range; label: string; days: number }[] = [
  { value: '1d', label: 'Today', days: 0 },
  { value: '7d', label: '7D', days: 7 },
  { value: '30d', label: '30D', days: 30 },
  { value: '90d', label: '90D', days: 90 },
]

function rangeBounds(r: Range): { from: string; to: string } {
  const now = new Date()
  const days = RANGES.find((x) => x.value === r)!.days
  const from = days === 0 ? new Date(now.getFullYear(), now.getMonth(), now.getDate()) : new Date(now.getTime() - days * 86400_000)
  return { from: from.toISOString(), to: now.toISOString() }
}

const HORIZON_LABEL: Record<number, string> = { 0: 'At fill', 1: '1 s', 5: '5 s', 30: '30 s', 60: '1 min' }

const equityConfig = { equity: { label: 'Equity', color: 'var(--s1)' } } satisfies ChartConfig
const ddConfig = { drawdown: { label: 'Drawdown', color: 'var(--down)' } } satisfies ChartConfig
const dailyConfig = { pnl: { label: 'Equity change', color: 'var(--s1)' } } satisfies ChartConfig
const edgeConfig = {
  all: { label: 'All fills', color: 'var(--s1)' },
  maker: { label: 'Maker fills', color: 'var(--s2)' },
} satisfies ChartConfig

function EquityCharts({ from, to }: { from: string; to: string }) {
  const { strategyId } = useApp()
  const pnl = usePoll((s) => fetchPnlRange(strategyId, from, to, s), 30_000, [strategyId, from, to])
  const points = useMemo(() => {
    const rows = [...(pnl.data ?? [])].sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts))
    let peak = -Infinity
    return rows.map((r) => {
      peak = Math.max(peak, r.equity)
      return { t: Date.parse(r.ts), equity: r.equity, drawdown: r.equity - peak }
    })
  }, [pnl.data])
  if (pnl.error && !pnl.data) return <ErrorNote message={pnl.error} onRetry={pnl.refresh} />
  if (!points.length) return <Empty>No equity snapshots in this range</Empty>
  const maxDd = Math.min(0, ...points.map((p) => p.drawdown))
  const lo = Math.min(...points.map((p) => p.equity))
  const hi = Math.max(...points.map((p) => p.equity))
  const pad = Math.max((hi - lo) * 0.1, 0.01)
  const spanDays = (points.at(-1)!.t - points[0].t) / 86400_000
  const tickFmt = (t: number) =>
    new Date(t).toLocaleString([], spanDays > 2 ? { month: 'short', day: 'numeric' } : { hour: '2-digit', minute: '2-digit', hour12: false })
  return (
    <div className="px-2 pt-2">
      <ChartContainer config={equityConfig} className="aspect-auto h-56 w-full">
        <AreaChart data={points} margin={{ left: 8, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={tickFmt} tickLine={false} axisLine={false} minTickGap={48} />
          <YAxis domain={[lo - pad, hi + pad]} tickFormatter={(v: number) => fmtUsd(v)} tickLine={false} axisLine={false} width={72} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => new Date(p?.[0]?.payload?.t).toLocaleString()} formatter={(v) => fmtUsd(Number(v))} />} />
          <Area dataKey="equity" type="stepAfter" stroke="var(--color-equity)" strokeWidth={2} fill="var(--color-equity)" fillOpacity={0.1} isAnimationActive={false} />
        </AreaChart>
      </ChartContainer>
      <div className="flex items-center justify-between px-2 pt-2 text-xs">
        <span className="font-medium">Drawdown from peak</span>
        <span className="num text-down">max {fmtSignedUsd(maxDd)}</span>
      </div>
      <ChartContainer config={ddConfig} className="aspect-auto h-24 w-full">
        <AreaChart data={points} margin={{ left: 8, right: 8, top: 4 }}>
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} hide />
          <YAxis tickFormatter={(v: number) => fmtUsd(v)} tickLine={false} axisLine={false} width={72} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, p) => new Date(p?.[0]?.payload?.t).toLocaleString()} formatter={(v) => fmtSignedUsd(Number(v))} />} />
          <Area dataKey="drawdown" type="stepAfter" stroke="var(--color-drawdown)" strokeWidth={1.5} fill="var(--color-drawdown)" fillOpacity={0.12} isAnimationActive={false} />
        </AreaChart>
      </ChartContainer>
    </div>
  )
}

function EdgeCurve({ all, maker }: { all: NetPoint[]; maker: NetPoint[] }) {
  const data = all.map((p, i) => ({ h: HORIZON_LABEL[p.h] ?? `${p.h}s`, all: p.net_bps, maker: maker[i]?.net_bps ?? null, n: p.n }))
  if (!data.some((d) => d.all !== null)) return <Empty>No fills in this range</Empty>
  const scored = all.find((p) => p.h === 60)?.n ?? 0
  return (
    <div className="px-2 pt-2">
      <ChartContainer config={edgeConfig} className="aspect-auto h-52 w-full">
        <LineChart data={data} margin={{ left: 8, right: 16, top: 12 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="h" tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(v: number) => fmtNum(v, 1)} tickLine={false} axisLine={false} width={40} />
          <ReferenceLine y={0} stroke="var(--muted-foreground)" />
          <ChartTooltip content={<ChartTooltipContent formatter={(v, name) => `${fmtBps(Number(v))} · ${name === 'all' ? 'all' : 'maker'}`} />} />
          <Line dataKey="all" stroke="var(--color-all)" strokeWidth={2} dot={{ r: 4 }} connectNulls isAnimationActive={false} />
          <Line dataKey="maker" stroke="var(--color-maker)" strokeWidth={2} dot={{ r: 4 }} connectNulls isAnimationActive={false} />
        </LineChart>
      </ChartContainer>
      <div className="flex flex-wrap items-center gap-4 px-2 pb-2 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-s1" /> All fills
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-s2" /> Maker fills
        </span>
        <span className="ml-auto">
          Net = spread captured + price move since fill − fee · {scored} fills scored at 1 min
        </span>
      </div>
    </div>
  )
}

function DailyTable({ days }: { days: PerfDay[] }) {
  if (!days.length) return <Empty>No activity in this range</Empty>
  const chart = days.map((d) => ({ day: d.day.slice(5), pnl: d.equity_change ?? 0 }))
  return (
    <>
      <div className="px-2 pt-2">
        <ChartContainer config={dailyConfig} className="aspect-auto h-40 w-full">
          <BarChart data={chart} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="day" tickLine={false} axisLine={false} />
            <YAxis tickFormatter={(v: number) => fmtUsd(v)} tickLine={false} axisLine={false} width={64} />
            <ReferenceLine y={0} stroke="var(--muted-foreground)" />
            <ChartTooltip content={<ChartTooltipContent formatter={(v) => fmtSignedUsd(Number(v))} />} />
            <Bar dataKey="pnl" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {chart.map((d) => (
                <Cell key={d.day} fill={d.pnl >= 0 ? 'var(--up)' : 'var(--down)'} />
              ))}
            </Bar>
          </BarChart>
        </ChartContainer>
      </div>
      <DataTable>
        <thead>
          <tr>
            <Th align="left">Day</Th>
            <Th>Equity change</Th>
            <Th>Fills</Th>
            <Th>Maker</Th>
            <Th>Volume</Th>
            <Th>Fees</Th>
            <Th>Capture</Th>
            <Th>Net at fill</Th>
            <Th>Net 1 min</Th>
          </tr>
        </thead>
        <tbody>
          {[...days].reverse().map((d) => (
            <tr key={d.day}>
              <Td align="left" className="num">{d.day}</Td>
              <Td className={signTone(d.equity_change)}>{fmtSignedUsd(d.equity_change)}</Td>
              <Td>{d.fills}</Td>
              <Td>{d.fills ? fmtPct(d.maker_share * 100, 0) : '—'}</Td>
              <Td>{fmtCompactUsd(d.volume)}</Td>
              <Td>{fmtUsd(d.fees)}</Td>
              <Td className={signTone(d.capture_bps)}>{fmtBps(d.capture_bps)}</Td>
              <Td className={signTone(d.net_curve[0]?.net_bps)}>{fmtBps(d.net_curve[0]?.net_bps)}</Td>
              <Td className={signTone(d.net_curve[4]?.net_bps)}>{d.net_curve[4]?.n ? fmtBps(d.net_curve[4]?.net_bps) : '—'}</Td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </>
  )
}

export function PerformancePage() {
  const { strategyId } = useApp()
  const [range, setRange] = useState<Range>('7d')
  const { from, to } = useMemo(() => rangeBounds(range), [range])
  const perf = usePoll((s) => fetchPerformance(strategyId, from, to, s), 30_000, [strategyId, from])
  const tca = usePoll((s) => fetchTca(strategyId, 100, s), 10_000, [strategyId])
  const t = perf.data?.totals

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-panel px-3 py-2">
        <h1 className="text-sm font-semibold">Performance</h1>
        <Segmented label="Range" value={range} onChange={setRange} options={RANGES.map((r) => ({ value: r.value, label: r.label }))} />
        <span className="text-[11px] text-muted-foreground">Days in local time · fills and fees from Delta</span>
        {perf.error && !perf.data ? <span className="text-xs text-down">{perf.error}</span> : null}
      </div>

      <div className="grid grid-cols-2 gap-2 rounded-lg border bg-panel p-3 sm:grid-cols-3 lg:grid-cols-7">
        <Stat
          label="Equity change"
          value={fmtSignedUsd(perf.data?.equity_change)}
          tone={signTone(perf.data?.equity_change)}
          sub="includes deposits and withdrawals"
        />
        <Stat label="Fees paid" value={fmtUsd(t?.fees)} sub={t ? `maker ${fmtUsd(t.maker_fees)} · taker ${fmtUsd(t.taker_fees)}` : undefined} />
        <Stat label="Volume" value={fmtCompactUsd(t?.volume)} />
        <Stat label="Fills" value={t ? String(t.fills) : '—'} sub={t?.fills ? `${fmtPct(t.maker_share * 100, 0)} maker` : undefined} />
        <Stat label="Avg fee" value={fmtBps(t?.fee_bps, 2, false)} />
        <Stat label="Spread captured" value={fmtBps(t?.capture_bps)} tone={signTone(t?.capture_bps)} sub="vs mid at fill" />
        <Stat
          label="Net edge at 1 min"
          value={t?.net_curve[4]?.n ? fmtBps(t.net_curve[4].net_bps) : '—'}
          tone={signTone(t?.net_curve[4]?.net_bps)}
          sub={t ? `${t.net_curve[4]?.n ?? 0} fills scored` : undefined}
        />
      </div>

      <div className="grid gap-2 lg:grid-cols-2">
        <Panel title="Equity" subtitle="Venue equity snapshots · steps can be deposits, not PnL">
          <EquityCharts from={from} to={to} />
        </Panel>
        <Panel title="Net edge per fill by time after the fill" subtitle="bps, notional-weighted">
          {t ? <EdgeCurve all={t.net_curve} maker={t.maker_net_curve} /> : <Empty>Loading…</Empty>}
        </Panel>
      </div>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel title="Daily" subtitle="Equity change per day and fill quality" bodyClassName="max-h-[520px] overflow-auto">
          <DailyTable days={perf.data?.daily ?? []} />
        </Panel>
        <Panel title="By symbol">
          {perf.data?.by_symbol.length ? (
            <DataTable>
              <thead>
                <tr>
                  <Th align="left">Symbol</Th>
                  <Th>Fills</Th>
                  <Th>Volume</Th>
                  <Th>Fees</Th>
                  <Th>Capture</Th>
                  <Th>Net at fill</Th>
                </tr>
              </thead>
              <tbody>
                {perf.data.by_symbol.map((s) => (
                  <tr key={s.symbol}>
                    <Td align="left" className="font-medium">{s.symbol}</Td>
                    <Td>{s.fills}</Td>
                    <Td>{fmtCompactUsd(s.volume)}</Td>
                    <Td>{fmtUsd(s.fees)}</Td>
                    <Td className={signTone(s.capture_bps)}>{fmtBps(s.capture_bps)}</Td>
                    <Td className={signTone(s.net_curve[0]?.net_bps)}>{fmtBps(s.net_curve[0]?.net_bps)}</Td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : (
            <Empty>No fills in this range</Empty>
          )}
        </Panel>
      </div>

      <Panel title="Fill quality (TCA)" subtitle="Latest 100 fills · markouts fill in over the first minute" bodyClassName="max-h-[480px] overflow-auto">
        {tca.error && !tca.data ? <ErrorNote message={tca.error} onRetry={tca.refresh} /> : <TcaTable rows={tca.data ?? []} />}
      </Panel>
    </div>
  )
}
