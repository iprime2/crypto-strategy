import { useCallback, useEffect, useState } from 'react'
import { fetchLatestSnapshot, fetchPnl, fetchPositions, snapshotStreamUrl } from '@/api/oems'
import type { LatestSnapshot, PnlSnapshot, Position, SnapshotStreamEvent } from '@/api/types'
import { DataState } from '@/components/DataState'
import { InfoTip } from '@/components/InfoTip'
import { PnlChart, PnlSeriesSelect, type ChartSeries } from '@/components/PnlChart'
import {
  POSITIONS_PAGE_SIZE,
  TablePagination,
  pageCount,
  slicePage,
} from '@/components/TablePagination'
import { Badge } from '@/components/ui/badge'
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
  const [posPage, setPosPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [snap, series, pos] = await Promise.all([
        fetchLatestSnapshot(strategyId),
        fetchPnl({ strategy_id: strategyId, limit: 100 }),
        fetchPositions({ strategy_id: strategyId, limit: 20 }),
      ])
      setSnapshot(snap)
      setPnl(series)
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
          if (point?.ts) {
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
              ].slice(0, 100)
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
  }, [strategyId, setSnapshot])

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
              PnL
              <InfoTip label="About PnL chart">
                Equity, realized, and unrealized over time, in USD.
              </InfoTip>
            </CardTitle>
            <CardDescription>Equity, realized, and unrealized over time</CardDescription>
            <CardAction>
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
