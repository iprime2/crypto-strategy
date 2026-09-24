import { useCallback, useEffect, useState } from 'react'
import { fetchFills, fetchOrders } from '@/api/oems'
import type { Fill, Order } from '@/api/types'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useStrategy } from '@/context/StrategyContext'
import { fmtNum, fmtTs } from '@/lib/format'

export function OrdersPage() {
  const { strategyId } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [orders, setOrders] = useState<Order[]>([])
  const [fills, setFills] = useState<Fill[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [o, f] = await Promise.all([
        fetchOrders({ strategy_id: strategyId, limit: 100 }),
        fetchFills({ strategy_id: strategyId, limit: 100 }),
      ])
      setOrders(o)
      setFills(f)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load orders and fills')
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
        empty={false}
        onRetry={load}
      >
        <Card>
          <CardHeader>
            <CardTitle>Orders and fills</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="orders">
              <TabsList>
                <TabsTrigger value="orders">Orders</TabsTrigger>
                <TabsTrigger value="fills">Fills</TabsTrigger>
              </TabsList>

              <TabsContent value="orders" className="mt-4">
                {orders.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No orders yet</p>
                ) : (
                  <Table className="min-w-[44rem]">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Client order id</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Price</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Reject</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {orders.map((row) => (
                        <TableRow key={row.client_order_id}>
                          <TableCell className="font-mono text-xs">
                            {row.client_order_id}
                          </TableCell>
                          <TableCell>{row.symbol}</TableCell>
                          <TableCell>{row.side}</TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.price)}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.qty, 6)}
                          </TableCell>
                          <TableCell>{row.status ?? '—'}</TableCell>
                          <TableCell className="text-muted-foreground">
                            {row.reject_code ?? '—'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </TabsContent>

              <TabsContent value="fills" className="mt-4">
                {fills.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No fills yet</p>
                ) : (
                  <Table className="min-w-[44rem]">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Trade id</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>Side</TableHead>
                        <TableHead>Price</TableHead>
                        <TableHead>Qty</TableHead>
                        <TableHead>Fee</TableHead>
                        <TableHead>Time</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fills.map((row) => (
                        <TableRow key={row.trade_id}>
                          <TableCell className="font-mono text-xs">
                            {row.trade_id}
                          </TableCell>
                          <TableCell>{row.symbol}</TableCell>
                          <TableCell>{row.side}</TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.price)}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.qty, 6)}
                          </TableCell>
                          <TableCell className="tabular-nums">
                            {fmtNum(row.fee, 4)}
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {fmtTs(row.created_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </DataState>
    </div>
  )
}
