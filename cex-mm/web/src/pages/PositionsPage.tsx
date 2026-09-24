import { useCallback, useEffect, useState } from 'react'
import { fetchPositions } from '@/api/oems'
import type { Position } from '@/api/types'
import { DataState } from '@/components/DataState'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
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
import { fmtNum, fmtSigned, fmtTs, positionMismatch } from '@/lib/format'

export function PositionsPage() {
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<Position[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRows(await fetchPositions({ strategy_id: strategyId, limit: 100 }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load positions')
    } finally {
      setLoading(false)
    }
  }, [strategyId])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="px-4 lg:px-6">
      <DataState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        emptyMessage="No snapshots yet"
        onRetry={load}
      >
        <Card>
          <CardHeader>
            <CardTitle>Positions</CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="min-w-[40rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Venue qty</TableHead>
                  <TableHead>Bot qty</TableHead>
                  <TableHead>Mark</TableHead>
                  <TableHead>Unrealized</TableHead>
                  <TableHead>As of</TableHead>
                  <TableHead>Note</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const mismatch = positionMismatch(row)
                  return (
                    <TableRow
                      key={`${row.symbol}-${row.ts ?? ''}`}
                      className={mismatch ? 'bg-amber-500/10' : undefined}
                    >
                      <TableCell className="font-medium">{row.symbol}</TableCell>
                      <TableCell className="tabular-nums">
                        {fmtNum(row.venue_qty, 6)}
                      </TableCell>
                      <TableCell className="tabular-nums">
                        {fmtNum(row.bot_qty, 6)}
                      </TableCell>
                      <TableCell className="tabular-nums">{fmtNum(row.mark)}</TableCell>
                      <TableCell className="tabular-nums">
                        {fmtSigned(row.unrealized)}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {fmtTs(row.ts)}
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
          </CardContent>
        </Card>
      </DataState>
    </div>
  )
}
