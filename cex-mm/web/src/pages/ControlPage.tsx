import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertCircleIcon } from 'lucide-react'
import { fetchConfig, postConfig, startStrategy, stopStrategy } from '@/api/oems'
import type { StrategyConfigBody } from '@/api/types'
import { DataState } from '@/components/DataState'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useStrategy } from '@/context/StrategyContext'

const DEFAULT_CONFIG: StrategyConfigBody = {
  symbols: 'BTCUSDT,ETHUSDT',
  order_qty: 0.001,
  max_inventory: 0.01,
  half_spread_bps: 20,
  min_half_spread_bps: 12,
  max_half_spread_bps: 80,
  inv_spread_widen: 0.5,
  reject_kill_count: 20,
  l3_jump_bps: 50,
}

export function ControlPage() {
  const { strategyId, status, refreshHeader } = useStrategy()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [version, setVersion] = useState<number | null>(null)
  const [form, setForm] = useState<StrategyConfigBody>(DEFAULT_CONFIG)

  const [actionPending, setActionPending] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const [savePending, setSavePending] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveOk, setSaveOk] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const cfg = await fetchConfig(strategyId)
      if (cfg?.body) {
        setForm({ ...DEFAULT_CONFIG, ...cfg.body })
        setVersion(cfg.version)
      } else {
        setForm(DEFAULT_CONFIG)
        setVersion(null)
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load config')
    } finally {
      setLoading(false)
    }
  }, [strategyId])

  useEffect(() => {
    void load()
  }, [load])

  async function onToggle() {
    setActionPending(true)
    setActionError(null)
    try {
      if (status === 'running') {
        await stopStrategy(strategyId)
      } else {
        await startStrategy(strategyId)
      }
      await refreshHeader()
    } catch (err) {
      setActionError(
        err instanceof Error
          ? err.message
          : status === 'running'
            ? 'Stop failed'
            : 'Start failed',
      )
    } finally {
      setActionPending(false)
    }
  }

  async function onSave(e: FormEvent) {
    e.preventDefault()
    setSavePending(true)
    setSaveError(null)
    setSaveOk(null)
    try {
      const body: StrategyConfigBody = {
        symbols: form.symbols,
        order_qty: Number(form.order_qty),
        max_inventory: Number(form.max_inventory),
        half_spread_bps: Number(form.half_spread_bps),
        min_half_spread_bps: Number(form.min_half_spread_bps),
        max_half_spread_bps: Number(form.max_half_spread_bps),
        inv_spread_widen: Number(form.inv_spread_widen),
        reject_kill_count: Number(form.reject_kill_count),
        l3_jump_bps: Number(form.l3_jump_bps),
      }
      const res = await postConfig(strategyId, body)
      setVersion(res.version)
      setForm({ ...DEFAULT_CONFIG, ...res.body })
      setSaveOk(`Saved config version ${res.version}`)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Config save failed')
    } finally {
      setSavePending(false)
    }
  }

  function setNum(key: keyof Omit<StrategyConfigBody, 'symbols'>, raw: string) {
    const n = Number(raw)
    if (Number.isNaN(n)) return
    setForm((prev) => ({ ...prev, [key]: n }))
  }

  const running = status === 'running'

  return (
    <div className="flex flex-col gap-4 px-4 lg:px-6">
      <Card>
        <CardHeader>
          <CardTitle>Strategy control</CardTitle>
          <CardDescription>
            Status: {status}
            {version !== null ? ` · config v${version}` : ''}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button
            type="button"
            variant={running ? 'destructive' : 'default'}
            onClick={onToggle}
            disabled={actionPending}
          >
            {actionPending
              ? running
                ? 'Stopping…'
                : 'Starting…'
              : running
                ? `Stop ${strategyId}`
                : `Start ${strategyId}`}
          </Button>
          {actionError && (
            <Alert variant="destructive">
              <AlertCircleIcon />
              <AlertTitle>Action failed</AlertTitle>
              <AlertDescription>{actionError}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <DataState loading={loading} error={loadError} empty={false} onRetry={load}>
        <Card>
          <CardHeader>
            <CardTitle>Strategy config</CardTitle>
            <CardDescription>
              Active version: {version !== null ? `v${version}` : 'none'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSave} className="max-w-xl space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="symbols">Symbols (comma-separated)</Label>
                <Input
                  id="symbols"
                  type="text"
                  value={form.symbols}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, symbols: e.target.value }))
                  }
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="order_qty">Order qty</Label>
                  <Input
                    id="order_qty"
                    type="number"
                    step="any"
                    value={form.order_qty}
                    onChange={(e) => setNum('order_qty', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="max_inventory">Max inventory</Label>
                  <Input
                    id="max_inventory"
                    type="number"
                    step="any"
                    value={form.max_inventory}
                    onChange={(e) => setNum('max_inventory', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="half_spread_bps">Half spread bps</Label>
                  <Input
                    id="half_spread_bps"
                    type="number"
                    step="any"
                    value={form.half_spread_bps}
                    onChange={(e) => setNum('half_spread_bps', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="inv_spread_widen">Inv spread widen</Label>
                  <Input
                    id="inv_spread_widen"
                    type="number"
                    step="any"
                    value={form.inv_spread_widen}
                    onChange={(e) => setNum('inv_spread_widen', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="min_half_spread_bps">Min half spread bps</Label>
                  <Input
                    id="min_half_spread_bps"
                    type="number"
                    step="any"
                    value={form.min_half_spread_bps}
                    onChange={(e) =>
                      setNum('min_half_spread_bps', e.target.value)
                    }
                    className="tabular-nums"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="max_half_spread_bps">Max half spread bps</Label>
                  <Input
                    id="max_half_spread_bps"
                    type="number"
                    step="any"
                    value={form.max_half_spread_bps}
                    onChange={(e) =>
                      setNum('max_half_spread_bps', e.target.value)
                    }
                    className="tabular-nums"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="reject_kill_count">Reject kill count</Label>
                  <Input
                    id="reject_kill_count"
                    type="number"
                    step="1"
                    min="0"
                    value={form.reject_kill_count}
                    onChange={(e) => setNum('reject_kill_count', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="l3_jump_bps">L3 jump bps</Label>
                  <Input
                    id="l3_jump_bps"
                    type="number"
                    step="any"
                    value={form.l3_jump_bps}
                    onChange={(e) => setNum('l3_jump_bps', e.target.value)}
                    className="tabular-nums"
                    required
                  />
                </div>
              </div>

              <Button type="submit" disabled={savePending}>
                {savePending ? 'Saving…' : 'Save config'}
              </Button>
              {saveError && (
                <Alert variant="destructive">
                  <AlertCircleIcon />
                  <AlertTitle>Save failed</AlertTitle>
                  <AlertDescription>{saveError}</AlertDescription>
                </Alert>
              )}
              {saveOk && <p className="text-sm text-muted-foreground">{saveOk}</p>}
            </form>
          </CardContent>
        </Card>
      </DataState>
    </div>
  )
}
