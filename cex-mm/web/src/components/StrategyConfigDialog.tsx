import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertCircleIcon } from 'lucide-react'
import { fetchConfig, postConfig } from '@/api/oems'
import type { StrategyConfigBody } from '@/api/types'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const DEFAULT_CONFIG: StrategyConfigBody = {
  symbols: 'ETHUSDT',
  order_qty: 0.01,
  max_inventory: 0.01,
  half_spread_bps: 8,
  min_half_spread_bps: 8,
  max_half_spread_bps: 12,
  inv_spread_widen: 0.5,
  reject_kill_count: 500,
  l3_jump_bps: 120,
}

type Props = {
  strategyId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function StrategyConfigDialog({ strategyId, open, onOpenChange }: Props) {
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [version, setVersion] = useState<number | null>(null)
  const [form, setForm] = useState<StrategyConfigBody>(DEFAULT_CONFIG)
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
    if (!open) return
    setSaveError(null)
    setSaveOk(null)
    void load()
  }, [open, load])

  function setNum(key: keyof Omit<StrategyConfigBody, 'symbols'>, raw: string) {
    const n = Number(raw)
    if (Number.isNaN(n)) return
    setForm((prev) => ({ ...prev, [key]: n }))
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Configure {strategyId}</DialogTitle>
          <DialogDescription>
            Active version: {version !== null ? `v${version}` : 'none'}. No API
            keys.
          </DialogDescription>
        </DialogHeader>
        {loading && (
          <p className="text-sm text-muted-foreground">Loading config…</p>
        )}
        {loadError && (
          <Alert variant="destructive">
            <AlertCircleIcon />
            <AlertTitle>Could not load config</AlertTitle>
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
        )}
        <form onSubmit={onSave} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="dlg-symbols">Symbols</Label>
            <Input
              id="dlg-symbols"
              value={form.symbols}
              onChange={(e) =>
                setForm((p) => ({ ...p, symbols: e.target.value }))
              }
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field
              id="dlg-order-qty"
              label="Order qty"
              value={form.order_qty}
              onChange={(v) => setNum('order_qty', v)}
            />
            <Field
              id="dlg-max-inv"
              label="Max inventory"
              value={form.max_inventory}
              onChange={(v) => setNum('max_inventory', v)}
            />
            <Field
              id="dlg-half"
              label="Half spread bps"
              value={form.half_spread_bps}
              onChange={(v) => setNum('half_spread_bps', v)}
            />
            <Field
              id="dlg-min-half"
              label="Min half spread bps"
              value={form.min_half_spread_bps}
              onChange={(v) => setNum('min_half_spread_bps', v)}
            />
            <Field
              id="dlg-max-half"
              label="Max half spread bps"
              value={form.max_half_spread_bps}
              onChange={(v) => setNum('max_half_spread_bps', v)}
            />
            <Field
              id="dlg-widen"
              label="Inv spread widen"
              value={form.inv_spread_widen}
              onChange={(v) => setNum('inv_spread_widen', v)}
            />
            <Field
              id="dlg-reject"
              label="Reject kill count"
              value={form.reject_kill_count}
              onChange={(v) => setNum('reject_kill_count', v)}
            />
            <Field
              id="dlg-l3"
              label="L3 jump bps"
              value={form.l3_jump_bps}
              onChange={(v) => setNum('l3_jump_bps', v)}
            />
          </div>
          <Button type="submit" disabled={savePending || loading}>
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
      </DialogContent>
    </Dialog>
  )
}

function Field({
  id,
  label,
  value,
  onChange,
}: {
  id: string
  label: string
  value: number
  onChange: (raw: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        step="any"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="tabular-nums"
        required
      />
    </div>
  )
}
