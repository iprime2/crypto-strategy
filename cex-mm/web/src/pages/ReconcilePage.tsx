import { useCallback, useEffect, useState } from 'react'
import { fetchReconcile } from '@/api/oems'
import type { ReconcileRow } from '@/api/types'
import { DataState } from '@/components/DataState'
import { InfoTip } from '@/components/InfoTip'
import {
  POSITIONS_PAGE_SIZE,
  TablePagination,
  pageCount,
  slicePage,
} from '@/components/TablePagination'
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
import { fmtNum, fmtSignedUsd, fmtTs, positionMismatch } from '@/lib/format'

export function ReconcilePage() {
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<ReconcileRow[]>([])
  const [mismatches, setMismatches] = useState<ReconcileRow[]>([])
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchReconcile({ strategy_id: strategyId, limit: 100 })
      setRows(data.latest_by_symbol)
      setMismatches(data.mismatches)
      setPage(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load reconcile')
    } finally {
      setLoading(false)
    }
  }, [strategyId])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [strategyId])

  const totalPages = pageCount(rows.length, POSITIONS_PAGE_SIZE)
  const safePage = Math.min(page, totalPages)
  const pageRows = slicePage(rows, safePage, POSITIONS_PAGE_SIZE)
  const mismatchSymbols = [...new Set(mismatches.map((row) => row.symbol))]

  return (
    <div className="space-y-4 px-4 lg:px-6">
      <DataState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        emptyMessage="No snapshots yet"
        onRetry={load}
      >
        {mismatches.length > 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Mismatches
                <InfoTip label="About mismatches">
                  Positions where bot qty differs from venue qty. Venue size is treated as truth.
                </InfoTip>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-wrap gap-2">
                {mismatchSymbols.map((symbol) => (
                  <li key={`mm-${symbol}`}>
                    <Badge
                      variant="outline"
                      className="border-amber-500/50 text-amber-200"
                    >
                      {symbol}: bot ≠ venue
                    </Badge>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Reconcile
              <InfoTip label="About Reconcile">
                Latest bot vs venue size per symbol from position snapshots.
              </InfoTip>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="min-w-[40rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Symbol
                      <InfoTip label="About Symbol">Trading symbol.</InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Venue qty
                      <InfoTip label="About Venue qty">
                        Size reported by the exchange.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Bot qty
                      <InfoTip label="About Bot qty">
                        Size the quote bot thinks it holds.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Unrealized
                      <InfoTip label="About Unrealized">
                        Unrealized PnL in USD for this position.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Mismatch
                      <InfoTip label="About Mismatch">
                        Warning when bot qty and venue qty differ.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>As of</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageRows.map((row) => {
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
                          'ok'
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {fmtTs(row.ts)}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
            <TablePagination
              page={safePage}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </CardContent>
        </Card>
      </DataState>
    </div>
  )
}
