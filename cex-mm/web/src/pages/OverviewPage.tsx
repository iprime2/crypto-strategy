import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchAnalytics, fetchLatestSnapshot, fetchPnl, fetchPositions, snapshotStreamUrl } from '@/api/oems'
import type { LatestSnapshot, PnlSnapshot, Position, SnapshotStreamEvent } from '@/api/types'
import { DataState } from '@/components/DataState'
import { InfoTip } from '@/components/InfoTip'
import { chartSeriesLabel, PnlChart, PnlSeriesSelect, type ChartSeries } from '@/components/PnlChart'
import {
  POSITIONS_PAGE_SIZE,
  TablePagination,
  pageCount,
  slicePage,
} from '@/components/TablePagination'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useStrategy } from '@/context/StrategyContext'
import { fmtNum, fmtSignedUsd, fmtUsd, positionMismatch } from '@/lib/format'

type ChartPreset = '1d' | '7d' | 'custom'

function toDateInputValue(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function startOfLocalDay(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d, 0, 0, 0, 0)
}

function endOfLocalDay(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d, 23, 59, 59, 999)
}

function chartRange(preset: ChartPreset, customFrom: string, customTo: string): {
  from: string
  to: string
} {
  const now = new Date()
  if (preset === 'custom') {
    return {
      from: startOfLocalDay(customFrom).toISOString(),
      to: endOfLocalDay(customTo).toISOString(),
    }
  }
  const ms = preset === '1d' ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000
  return { from: new Date(now.getTime() - ms).toISOString(), to: now.toISOString() }
}

function applyStreamEvent(
  prev: LatestSnapshot | null,
  data: SnapshotStreamEvent,
): LatestSnapshot {
  return {
    ...prev,
    strategy_id: data.strategy_id,
    ts: data.ts,
    equity: data.equity,
    realized: data.realized,
    unrealized: data.unrealized,
    balance: {
      ...prev?.balance,
      equity: data.equity,
      available: data.available ?? prev?.balance?.available ?? null,
      ts: data.ts,
    },
  }
}

export function OverviewPage() {
  const { strategyId, snapshot: latest, setSnapshot } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pnl, setPnl] = useState<PnlSnapshot[]>([])
  const [positions, setPositions] = useState<Position[]>([])
  const [chartSeries, setChartSeries] = useState<ChartSeries>('equity')
  const [chartPreset, setChartPreset] = useState<ChartPreset>('1d')
  const today = useMemo(() => toDateInputValue(new Date()), [])
  const [customFrom, setCustomFrom] = useState(today)
  const [customTo, setCustomTo] = useState(today)
  const range = useMemo(
    () => chartRange(chartPreset, customFrom, customTo),
    [chartPreset, customFrom, customTo],
  )
  const [posPage, setPosPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [snap, pos] = await Promise.all([
        fetchLatestSnapshot(strategyId),
        fetchPositions({ strategy_id: strategyId, limit: 20 }),
      ])
      setSnapshot(snap)
      setPositions(pos)
      setPosPage(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load overview')
    } finally {
      setLoading(false)
    }
  }, [strategyId, setSnapshot])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    let cancelled = false
    const fromMs = new Date(range.from).getTime()
    const toMs = new Date(range.to).getTime()
    const spanDays = (toMs - fromMs) / (24 * 60 * 60 * 1000)
    async function loadChart() {
      try {
        if (spanDays > 2) {
          const analytics = await fetchAnalytics({
            strategy_id: strategyId,
            from: range.from,
            to: range.to,
          })
          if (cancelled) return
          const points = analytics.series
            .filter((p) => p.equity != null || p.realized != null || p.unrealized != null)
            .map((p) => ({
              ts: p.ts,
              equity: p.equity ?? 0,
              realized: p.realized ?? 0,
              unrealized: p.unrealized ?? 0,
            }))
          setPnl(points.reverse())
        } else {
          const series = await fetchPnl({
            strategy_id: strategyId,
            from: range.from,
            to: range.to,
          })
          if (!cancelled) setPnl(series)
        }
      } catch {
        if (!cancelled) setPnl([])
      }
    }
    void loadChart()
    return () => {
      cancelled = true
    }
  }, [strategyId, range.from, range.to])

  useEffect(() => {
    setPosPage(1)
  }, [strategyId])

  useEffect(() => {
    let closed = false
    let es: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | undefined

    function connect() {
      if (closed) return
      es = new EventSource(snapshotStreamUrl(strategyId))
      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as SnapshotStreamEvent
          if (data.strategy_id && data.strategy_id !== strategyId) return
          setSnapshot((prev) => applyStreamEvent(prev, data))
          void fetchPositions({ strategy_id: strategyId, limit: 20 })
            .then(setPositions)
            .catch(() => {})
          const point = data.pnl
          const pointMs = point?.ts ? new Date(point.ts).getTime() : NaN
          const inRange =
            Number.isFinite(pointMs) &&
            pointMs >= new Date(range.from).getTime() &&
            pointMs <= new Date(range.to).getTime()
          if (point?.ts && inRange) {
            setPnl((prev) => {
              if (prev.some((p) => p.ts === point.ts)) return prev
              return [
                {
                  ts: point.ts,
                  equity: point.equity,
                  realized: point.realized,
                  unrealized: point.unrealized,
                },
                ...prev,
              ].slice(0, 2000)
            })
          }
        } catch {
          // ignore malformed events
        }
      }
      es.onerror = () => {
        es?.close()
        es = null
        if (closed) return
        retryTimer = setTimeout(connect, 2000)
      }
    }

    connect()
    return () => {
      closed = true
      if (retryTimer !== undefined) clearTimeout(retryTimer)
      es?.close()
    }
  }, [strategyId, setSnapshot, range.from, range.to])

  const equity = latest?.equity ?? latest?.balance?.equity ?? null
  const available = latest?.balance?.available ?? null
  const totalPosPages = pageCount(positions.length, POSITIONS_PAGE_SIZE)
  const safePosPage = Math.min(posPage, totalPosPages)
  const pageRows = slicePage(positions, safePosPage, POSITIONS_PAGE_SIZE)

  return (
    <DataState loading={loading} error={error} empty={false} onRetry={load}>
      <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        <Card className="@container/card">
          <CardHeader>
            <CardDescription className="flex items-center gap-1.5">
              Equity
              <InfoTip label="About Equity">
                Balance plus open PnL, in USD.
              </InfoTip>
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtUsd(equity)}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription className="flex items-center gap-1.5">
              Unrealized PnL
              <InfoTip label="About Unrealized PnL">
                Open-position mark-to-market PnL, in USD.
              </InfoTip>
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtSignedUsd(latest?.unrealized)}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription className="flex items-center gap-1.5">
              Realized PnL
              <InfoTip label="About Realized PnL">
                Closed-trade PnL, in USD.
              </InfoTip>
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtSignedUsd(latest?.realized)}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription className="flex items-center gap-1.5">
              Available margin
              <InfoTip label="About Available margin">
                Free margin at the venue, in USD.
              </InfoTip>
            </CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtUsd(available)}
            </CardTitle>
          </CardHeader>
          {latest?.balance ? (
            <CardFooter className="text-sm text-muted-foreground">
              Venue balance
            </CardFooter>
          ) : null}
        </Card>
      </div>

      <div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              {chartSeriesLabel(chartSeries)}
              <InfoTip label="About PnL chart">
                {`${chartSeriesLabel(chartSeries)} in USD for the selected range.`}
              </InfoTip>
            </CardTitle>
            <CardDescription>USD over the selected range</CardDescription>
            <CardAction className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                {(['1d', '7d', 'custom'] as const).map((preset) => (
                  <Button
                    key={preset}
                    type="button"
                    size="sm"
                    variant={chartPreset === preset ? 'default' : 'outline'}
                    onClick={() => setChartPreset(preset)}
                  >
                    {preset === '1d' ? '1D' : preset === '7d' ? '7D' : 'Custom'}
                  </Button>
                ))}
              </div>
              {chartPreset === 'custom' && (
                <>
                  <Input
                    type="date"
                    value={customFrom}
                    onChange={(e) => setCustomFrom(e.target.value)}
                    className="h-8 w-[9.5rem]"
                    aria-label="From date"
                  />
                  <Input
                    type="date"
                    value={customTo}
                    onChange={(e) => setCustomTo(e.target.value)}
                    className="h-8 w-[9.5rem]"
                    aria-label="To date"
                  />
                </>
              )}
              <PnlSeriesSelect series={chartSeries} onSeriesChange={setChartSeries} />
            </CardAction>
          </CardHeader>
          <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
            {pnl.length === 0 ? (
              <p className="text-sm text-muted-foreground">No snapshots yet</p>
            ) : (
              <PnlChart
                points={pnl}
                hideSeriesSelect
                series={chartSeries}
                onSeriesChange={setChartSeries}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5">
              Positions
              <InfoTip label="About Positions">
                Latest venue inventory for this strategy.
              </InfoTip>
            </CardTitle>
            <CardDescription>Latest venue inventory</CardDescription>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No snapshots yet</p>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <span className="inline-flex items-center gap-1.5">
                          Symbol
                          <InfoTip label="About Symbol">Trading symbol.</InfoTip>
                        </span>
                      </TableHead>
                      <TableHead>
                        <span className="inline-flex items-center gap-1.5">
                          Venue qty
                          <InfoTip label="About Venue qty">
                            Exchange position size.
                          </InfoTip>
                        </span>
                      </TableHead>
                      <TableHead>
                        <span className="inline-flex items-center gap-1.5">
                          Unrealized
                          <InfoTip label="About Unrealized">
                            Open-position mark-to-market PnL, in USD.
                          </InfoTip>
                        </span>
                      </TableHead>
                      <TableHead>
                        <span className="inline-flex items-center gap-1.5">
                          Note
                          <InfoTip label="About Note">
                            Flags when the bot size does not match the venue.
                          </InfoTip>
                        </span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pageRows.map((row) => {
                      const mismatch = positionMismatch(row)
                      return (
                        <TableRow key={`${row.symbol}-${row.ts ?? ''}`}>
                          <TableCell className="font-medium">{row.symbol}</TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.venue_qty, 6)}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {fmtSignedUsd(row.unrealized)}
                          </TableCell>
                          <TableCell>
                            {mismatch ? (
                              <span className="inline-flex items-center gap-2">
                                <span className="font-medium text-amber-200">
                                  bot ≠ venue
                                </span>
                                <Badge
                                  variant="outline"
                                  className="border-amber-500/50 text-amber-200"
                                >
                                  warning
                                </Badge>
                              </span>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
                <TablePagination
                  page={safePosPage}
                  totalPages={totalPosPages}
                  onPageChange={setPosPage}
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </DataState>
  )
}
