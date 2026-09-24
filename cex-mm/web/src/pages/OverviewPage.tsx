import { useCallback, useEffect, useState } from 'react'
import { fetchLatestSnapshot, fetchPnl, fetchPositions, snapshotStreamUrl } from '@/api/oems'
import type { LatestSnapshot, PnlSnapshot, Position, SnapshotStreamEvent } from '@/api/types'
import { DataState } from '@/components/DataState'
import { PnlChart } from '@/components/PnlChart'
import { Badge } from '@/components/ui/badge'
import {
  Card,
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
import { fmtNum, fmtSignedUsd, fmtTs, fmtUsd, positionMismatch } from '@/lib/format'

function helperLine(latest: LatestSnapshot | null): string {
  if (!latest) return 'No snapshots yet'
  const ts = latest.ts ?? latest.balance?.ts
  if (ts) return `As of ${fmtTs(ts)}`
  return 'Latest venue snapshot'
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
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [latest, setLatest] = useState<LatestSnapshot | null>(null)
  const [pnl, setPnl] = useState<PnlSnapshot[]>([])
  const [positions, setPositions] = useState<Position[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [snap, series, pos] = await Promise.all([
        fetchLatestSnapshot(strategyId),
        fetchPnl({ strategy_id: strategyId, limit: 100 }),
        fetchPositions({ strategy_id: strategyId, limit: 20 }),
      ])
      setLatest(snap)
      setPnl(series)
      setPositions(pos)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load overview')
    } finally {
      setLoading(false)
    }
  }, [strategyId])

  useEffect(() => {
    void load()
  }, [load])

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
          setLatest((prev) => applyStreamEvent(prev, data))
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
  }, [strategyId])

  const asOf = helperLine(latest)
  const equity = latest?.equity ?? latest?.balance?.equity ?? null
  const available = latest?.balance?.available ?? null

  return (
    <DataState loading={loading} error={error} empty={false} onRetry={load}>
      <div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4">
        <Card className="@container/card">
          <CardHeader>
            <CardDescription>Equity</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtUsd(equity)}
            </CardTitle>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">{asOf}</CardFooter>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription>Unrealized PnL</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtSignedUsd(latest?.unrealized)}
            </CardTitle>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">{asOf}</CardFooter>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription>Realized PnL</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtSignedUsd(latest?.realized)}
            </CardTitle>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">{asOf}</CardFooter>
        </Card>

        <Card className="@container/card">
          <CardHeader>
            <CardDescription>Available margin</CardDescription>
            <CardTitle className="text-2xl font-semibold tabular-nums @[250px]/card:text-3xl">
              {fmtUsd(available)}
            </CardTitle>
          </CardHeader>
          <CardFooter className="text-sm text-muted-foreground">
            {latest?.balance ? 'Venue balance' : asOf}
          </CardFooter>
        </Card>
      </div>

      <div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <CardTitle>PnL</CardTitle>
            <CardDescription>Equity, realized, and unrealized over time</CardDescription>
          </CardHeader>
          <CardContent className="px-2 pt-4 sm:px-6 sm:pt-6">
            {pnl.length === 0 ? (
              <p className="text-sm text-muted-foreground">No snapshots yet</p>
            ) : (
              <PnlChart points={pnl} />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="px-4 lg:px-6">
        <Card>
          <CardHeader>
            <CardTitle>Positions</CardTitle>
            <CardDescription>Latest venue inventory</CardDescription>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No snapshots yet</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Venue qty</TableHead>
                    <TableHead>Unrealized</TableHead>
                    <TableHead>Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {positions.map((row) => {
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
            )}
          </CardContent>
        </Card>
      </div>
    </DataState>
  )
}
