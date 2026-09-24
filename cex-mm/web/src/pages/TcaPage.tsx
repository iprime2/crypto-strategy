import { useCallback, useEffect, useState } from 'react'
import { fetchTca } from '@/api/oems'
import type { TcaRow } from '@/api/types'
import { DataState } from '@/components/DataState'
import { InfoTip } from '@/components/InfoTip'
import {
  POSITIONS_PAGE_SIZE,
  TablePagination,
  pageCount,
  slicePage,
} from '@/components/TablePagination'
import { TcaAnalyticsSection } from '@/components/TcaAnalyticsSection'
import {
  Card,
  CardContent,
  CardDescription,
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
import { fmtBps } from '@/lib/format'

export function TcaPage() {
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<TcaRow[]>([])
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRows(await fetchTca({ strategy_id: strategyId, limit: 100 }))
      setPage(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load TCA')
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

  return (
    <div className="space-y-6 px-4 lg:px-6">
      <TcaAnalyticsSection />

      <DataState
        loading={loading}
        error={error}
        empty={rows.length === 0}
        emptyMessage="No TCA rows yet"
        onRetry={load}
      >
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              TCA fills
              <InfoTip label="About TCA">
                Per-fill transaction costs computed in the OEMS when fills are stored. Sorted by
                trade id.
              </InfoTip>
            </CardTitle>
            <CardDescription>
              Events appear after the quote bot is pointed at this OEMS.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table className="min-w-[48rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>Trade id</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Slippage (bps)
                      <InfoTip label="About Slippage">
                        Side × (arrival mid − fill) / arrival mid × 10,000. Negative means worse
                        than arrival mid.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Eff spread (bps)
                      <InfoTip label="About effective spread">
                        Uses mid at fill, not arrival mid.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Fee (bps)
                      <InfoTip label="About fee bps">Fee as basis points of fill notional.</InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Markout 5s (bps)
                      <InfoTip label="About markout 5s">
                        Mid move vs arrival mid after 5 seconds.
                      </InfoTip>
                    </span>
                  </TableHead>
                  <TableHead>
                    <span className="inline-flex items-center gap-1">
                      Net 5s (bps)
                      <InfoTip label="About net 5s">
                        Effective spread minus fee bps minus adverse 5s markout.
                      </InfoTip>
                    </span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pageRows.map((row) => (
                  <TableRow key={row.trade_id}>
                    <TableCell className="font-mono text-xs">{row.trade_id}</TableCell>
                    <TableCell>{row.symbol ?? '—'}</TableCell>
                    <TableCell className="tabular-nums">
                      {fmtBps(row.slippage_bps)}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {fmtBps(row.effective_spread_bps)}
                    </TableCell>
                    <TableCell className="tabular-nums">{fmtBps(row.fee_bps)}</TableCell>
                    <TableCell className="tabular-nums">
                      {fmtBps(row.markout_5s_bps)}
                    </TableCell>
                    <TableCell className="tabular-nums font-medium">
                      {fmtBps(row.net_5s_bps)}
                    </TableCell>
                  </TableRow>
                ))}
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
