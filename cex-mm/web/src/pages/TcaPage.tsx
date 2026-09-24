import { useCallback, useEffect, useState } from 'react'
import { fetchTca } from '@/api/oems'
import type { TcaRow } from '@/api/types'
import { DataState } from '@/components/DataState'
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
import { fmtNum } from '@/lib/format'

export function TcaPage() {
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rows, setRows] = useState<TcaRow[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setRows(await fetchTca({ strategy_id: strategyId, limit: 100 }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load TCA')
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
        emptyMessage="No TCA rows yet"
        onRetry={load}
      >
        <Card>
          <CardHeader>
            <CardTitle>TCA</CardTitle>
          </CardHeader>
          <CardContent>
            <Table className="min-w-[48rem]">
              <TableHeader>
                <TableRow>
                  <TableHead>Trade id</TableHead>
                  <TableHead>Symbol</TableHead>
                  <TableHead>Slippage bps</TableHead>
                  <TableHead>Eff spread bps</TableHead>
                  <TableHead>Fee bps</TableHead>
                  <TableHead>Markout 5s bps</TableHead>
                  <TableHead>Net 5s bps</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.trade_id}>
                    <TableCell className="font-mono text-xs">{row.trade_id}</TableCell>
                    <TableCell>{row.symbol ?? '—'}</TableCell>
                    <TableCell className="tabular-nums">
                      {fmtNum(row.slippage_bps, 2)}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {fmtNum(row.effective_spread_bps, 2)}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {fmtNum(row.fee_bps, 2)}
                    </TableCell>
                    <TableCell className="tabular-nums">
                      {fmtNum(row.markout_5s_bps, 2)}
                    </TableCell>
                    <TableCell className="tabular-nums font-medium">
                      {fmtNum(row.net_5s_bps, 2)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </DataState>
    </div>
  )
}
