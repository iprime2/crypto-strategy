import { useMemo, useState } from 'react'
import { Play, RotateCcw, Square } from 'lucide-react'
import { fetchTelemetry, saveOverrides, startStrategy, stopStrategy } from '@/api/oems'
import type { EffectiveConfig, QuoteState } from '@/api/types'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DataTable, Empty, Panel, Stat, StatusPill, Td, Th } from '@/components/kit'
import { EventsList } from '@/components/tables'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useApp } from '@/context/AppContext'
import { usePoll } from '@/hooks/usePoll'
import { fmtBps, fmtDateTime, fmtDuration, fmtNum, fmtPrice, fmtQty } from '@/lib/format'
import { botCheck } from '@/lib/health'
import { toastSuccess } from '@/lib/toast'
import { cn } from '@/lib/utils'

const GROUPS: { title: string; keys: RegExp }[] = [
  { title: 'Symbols and size', keys: /^MM_(SYMBOLS|TOP_N|ORDER_QTY|MAX_INVENTORY|INV_)/ },
  { title: 'Spread', keys: /^MM_(HALF_SPREAD|MIN_HALF|MAX_HALF|REQUOTE|MAKER_FEE|ADVERSE|AS_|KAPPA|CALM|VOL_)/ },
  { title: 'Markout guard', keys: /^MM_MARKOUT/ },
  { title: 'Fair value', keys: /^MM_(OFI|LEAD|BINANCE|MICROPRICE|FAIR)/ },
  { title: 'Risk and regime', keys: /^MM_(DAILY_LOSS|REJECT|REGIME|WARMUP)/ },
  { title: 'Operations', keys: /^(MM_(CANCEL|USE_VENUE|VENUE_RECONCILE|VENUE)|RUST_LOG)/ },
]

const KEY_RE = /^MM_[A-Z0-9_]+$/

function grouped(cfg: EffectiveConfig): { title: string; keys: string[] }[] {
  const keys = Object.keys(cfg.values).sort()
  const used = new Set<string>()
  const out = GROUPS.map((g) => {
    const ks = keys.filter((k) => g.keys.test(k) && !used.has(k))
    ks.forEach((k) => used.add(k))
    return { title: g.title, keys: ks }
  })
  const rest = keys.filter((k) => !used.has(k))
  if (rest.length) out.push({ title: 'Other', keys: rest })
  return out.filter((g) => g.keys.length)
}

function ConfigPanel({ cfg, running }: { cfg: EffectiveConfig; running: boolean }) {
  const { strategyId, refreshConfig, refreshOverview } = useApp()
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')
  const [confirm, setConfirm] = useState<'save' | 'reset' | null>(null)

  const changes = useMemo(() => {
    const out: Record<string, string> = {}
    for (const [k, v] of Object.entries(draft)) {
      if (v.trim() !== '' && v.trim() !== (cfg.values[k]?.value ?? '')) out[k] = v.trim()
    }
    return out
  }, [draft, cfg])
  const newKeyValid = KEY_RE.test(newKey.trim().toUpperCase()) && newVal.trim() !== ''

  function startEdit() {
    setDraft(Object.fromEntries(Object.entries(cfg.values).map(([k, v]) => [k, v.value])))
    setEditing(true)
  }

  function addKey() {
    const k = newKey.trim().toUpperCase()
    if (!newKeyValid) return
    setDraft((d) => ({ ...d, [k]: newVal.trim() }))
    setNewKey('')
    setNewVal('')
  }

  const overrides = (cfg.overrides ?? {}) as Record<string, unknown>
  const hasOverrides = Object.keys(overrides).length > 0

  return (
    <Panel
      title="Effective config"
      subtitle={`what the bot runs: ${cfg.env_file ?? 'env file'} + overrides${cfg.version ? ` (v${cfg.version})` : ''}`}
      actions={
        editing ? (
          <>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button size="sm" onClick={() => setConfirm('save')} disabled={!Object.keys(changes).length}>
              Review {Object.keys(changes).length} change{Object.keys(changes).length === 1 ? '' : 's'}
            </Button>
          </>
        ) : (
          <>
            {hasOverrides ? (
              <Button size="sm" variant="ghost" onClick={() => setConfirm('reset')}>
                Reset overrides
              </Button>
            ) : null}
            <Button size="sm" variant="outline" onClick={startEdit}>
              Edit
            </Button>
          </>
        )
      }
    >
      <div className="grid gap-x-6 gap-y-3 p-3 md:grid-cols-2 xl:grid-cols-3">
        {grouped(cfg).map((g) => (
          <div key={g.title}>
            <h3 className="mb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{g.title}</h3>
            <dl className="divide-y divide-border/50">
              {g.keys.map((k) => {
                const v = cfg.values[k]
                const editable = editing && k.startsWith('MM_')
                return (
                  <div key={k} className="flex items-center justify-between gap-2 py-1 text-xs">
                    <dt className="num min-w-0 truncate text-muted-foreground" title={k}>
                      {k.replace(/^MM_/, '')}
                    </dt>
                    <dd className="flex shrink-0 items-center gap-1.5">
                      {v.source === 'override' ? (
                        <span className="rounded bg-s1/15 px-1 text-[9px] font-semibold text-s1 uppercase" title="Set in the OEMS config, overrides the env file">
                          override
                        </span>
                      ) : null}
                      {editable ? (
                        <Input
                          aria-label={k}
                          value={draft[k] ?? ''}
                          onChange={(e) => setDraft((d) => ({ ...d, [k]: e.target.value }))}
                          className={cn('num h-6 w-36 px-1.5 text-right text-xs', changes[k] !== undefined && 'border-s1')}
                        />
                      ) : (
                        <span className="num max-w-48 truncate text-right" title={v.value}>
                          {v.value}
                        </span>
                      )}
                    </dd>
                  </div>
                )
              })}
            </dl>
          </div>
        ))}
      </div>
      {editing ? (
        <div className="flex flex-wrap items-end gap-2 border-t px-3 py-2">
          <label className="text-xs">
            <span className="mb-1 block text-muted-foreground">Add setting</span>
            <Input value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="MM_LEAD_BETA" className="num h-7 w-56 text-xs" />
          </label>
          <Input value={newVal} onChange={(e) => setNewVal(e.target.value)} placeholder="value" className="num h-7 w-40 text-xs" aria-label="New setting value" />
          <Button size="sm" variant="outline" onClick={addKey} disabled={!newKeyValid}>
            Add
          </Button>
          <span className="text-[11px] text-muted-foreground">Keys must be MM_* names the bot reads. Secrets are rejected.</span>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirm === 'save'}
        onOpenChange={(v) => !v && setConfirm(null)}
        title="Apply config changes"
        confirmLabel={running ? 'Save and restart bot' : 'Save'}
        description={
          <>
            <p>{running ? 'The bot restarts with the new settings: it stops, its orders are cancelled, then it starts again.' : 'Saved as a new version; used on the next start.'}</p>
            <table className="num w-full text-xs">
              <tbody>
                {Object.entries(changes).map(([k, v]) => (
                  <tr key={k}>
                    <td className="py-0.5 pr-2 text-muted-foreground">{k}</td>
                    <td className="py-0.5 text-right line-through opacity-60">{cfg.values[k]?.value ?? 'unset'}</td>
                    <td className="py-0.5 pl-2 text-right font-semibold text-foreground">{v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        }
        onConfirm={async () => {
          const body: Record<string, string> = {}
          for (const [k, v] of Object.entries(overrides)) if (KEY_RE.test(k)) body[k] = String(v)
          Object.assign(body, changes)
          const r = await saveOverrides(strategyId, body)
          if (r.restarted && !r.restarted.ok) throw new Error(`Saved v${r.version}, but restart failed: ${r.restarted.error ?? 'unknown'}`)
          toastSuccess(`Config v${r.version} saved`, r.restarted ? 'Bot restarted with the new settings.' : undefined)
          setEditing(false)
          refreshConfig()
          refreshOverview()
        }}
      />
      <ConfirmDialog
        open={confirm === 'reset'}
        onOpenChange={(v) => !v && setConfirm(null)}
        title="Reset overrides"
        confirmLabel={running ? 'Reset and restart bot' : 'Reset'}
        destructive
        description={<p>Drops all OEMS overrides so the bot runs with {cfg.env_file ?? 'the env file'} only.{running ? ' The bot restarts.' : ''}</p>}
        onConfirm={async () => {
          const r = await saveOverrides(strategyId, {})
          toastSuccess(`Config v${r.version}: overrides cleared`)
          refreshConfig()
          refreshOverview()
        }}
      />
    </Panel>
  )
}

function QuoteTable({ metrics }: { metrics: Record<string, QuoteState> }) {
  const rows = Object.values(metrics).sort((a, b) => a.symbol.localeCompare(b.symbol))
  if (!rows.length) return <Empty>No quote state from the bot</Empty>
  return (
    <DataTable>
      <thead>
        <tr>
          <Th align="left">Symbol</Th>
          <Th>Fair</Th>
          <Th>Bid</Th>
          <Th>Ask</Th>
          <Th>Half-spread</Th>
          <Th>Inventory</Th>
          <Th>Regime</Th>
          <Th>Lead skew</Th>
          <Th>Vol</Th>
          <Th>Age</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((q) => (
          <tr key={q.symbol}>
            <Td align="left" className="font-medium">{q.symbol}</Td>
            <Td>{fmtPrice(q.fair)}</Td>
            <Td className={cn('text-up', !q.place_bid && 'line-through opacity-50')}>{fmtPrice(q.bid)}</Td>
            <Td className={cn('text-down', !q.place_ask && 'line-through opacity-50')}>{fmtPrice(q.ask)}</Td>
            <Td>{fmtBps(q.fair ? ((q.ask - q.bid) / q.fair) * 1e4 / 2 : null, 2, false)}</Td>
            <Td>{fmtQty(q.inventory)}</Td>
            <Td className={q.regime_level >= 2 ? 'text-down' : q.regime_level === 1 ? 'text-warn' : undefined}>L{q.regime_level}</Td>
            <Td>{q.lead_skew_bps === null || q.lead_skew_bps === undefined ? 'no feed' : fmtBps(q.lead_skew_bps, 1)}</Td>
            <Td>{fmtBps(q.vol_bps, 1, false)}</Td>
            <Td>{fmtNum(q.age_s, 1)} s</Td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  )
}

export function StrategyPage() {
  const { overview: o, config, strategyId, refreshOverview } = useApp()
  const telemetry = usePoll((s) => fetchTelemetry(200, s), 2000, [])
  const [dialog, setDialog] = useState<'start' | 'stop' | 'restart' | null>(null)
  const running = o?.strategy.desired_state === 'running'
  const bot = botCheck(o)

  return (
    <div className="flex flex-col gap-2">
      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title="Process" subtitle={`strategy ${strategyId}`}>
          <div className="flex flex-col gap-3 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill level={running ? (bot.level === 'ok' ? 'ok' : 'warn') : 'idle'} label={running ? 'Running' : 'Stopped'} detail={bot.detail} />
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="PID" value={o?.strategy.pid ?? '—'} sub={o?.strategy.adopted ? 'adopted after OEMS restart' : undefined} />
              <Stat label="Uptime" value={running ? fmtDuration(o?.strategy.uptime_s) : '—'} />
              <Stat label="Started" value={o?.strategy.started_at ? fmtDateTime(o.strategy.started_at) : '—'} />
              <Stat
                label="Last exit"
                value={o?.strategy.last_exit ? `code ${o.strategy.last_exit.code ?? '?'}` : '—'}
                sub={o?.strategy.last_exit ? fmtDateTime(o.strategy.last_exit.at) : undefined}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setDialog('start')} disabled={running || !o}>
                <Play /> Start
              </Button>
              <Button variant="outline" onClick={() => setDialog('restart')} disabled={!running}>
                <RotateCcw /> Restart
              </Button>
              <Button variant="destructive" onClick={() => setDialog('stop')} disabled={!running}>
                <Square /> Stop
              </Button>
            </div>
            {running && o && !o.telemetry.attached ? (
              <p className="text-[11px] text-warn">
                ! This bot was started before the OEMS captured its output, so there is no quote state or event log. Restart it once to attach.
              </p>
            ) : null}
          </div>
        </Panel>
        <Panel title="Bot activity" subtitle={telemetry.data?.attached ? `log ${telemetry.data.log_path}` : 'no log attached'}>
          <div className="grid grid-cols-3 gap-3 p-3 sm:grid-cols-4">
            {telemetry.data
              ? Object.entries(telemetry.data.counters).map(([k, v]) => <Stat key={k} label={k.replace(/_/g, ' ')} value={String(v)} />)
              : null}
          </div>
        </Panel>
      </div>

      <Panel title="Live quotes" subtitle="from the bot's MM_METRICS · struck-through side is switched off">
        <QuoteTable metrics={telemetry.data?.metrics ?? {}} />
      </Panel>

      {config ? <ConfigPanel cfg={config} running={running} /> : <Panel title="Effective config"><Empty>Loading config…</Empty></Panel>}

      <Panel title="Bot events" bodyClassName="max-h-[360px] overflow-auto">
        <EventsList events={telemetry.data?.events ?? []} />
      </Panel>

      <ConfirmDialog
        open={dialog === 'start'}
        onOpenChange={(v) => !v && setDialog(null)}
        title={`Start ${strategyId}`}
        confirmLabel="Start bot"
        description={<p>Starts mm-bot on Delta {o?.venue_env === 'mainnet' ? 'MAINNET (real money)' : 'demo'} with the effective config. It cancels open orders first, then quotes.</p>}
        onConfirm={async () => {
          const r = await startStrategy(strategyId)
          toastSuccess('Bot started', `pid ${r.pid}`)
          refreshOverview()
        }}
      />
      <ConfirmDialog
        open={dialog === 'stop'}
        onOpenChange={(v) => !v && setDialog(null)}
        title={`Stop ${strategyId}`}
        destructive
        confirmLabel="Stop bot"
        description={<p>Stops the bot and cancels its open orders. Positions stay open.</p>}
        onConfirm={async () => {
          await stopStrategy(strategyId)
          toastSuccess('Bot stopped')
          refreshOverview()
        }}
      />
      <ConfirmDialog
        open={dialog === 'restart'}
        onOpenChange={(v) => !v && setDialog(null)}
        title={`Restart ${strategyId}`}
        confirmLabel="Restart bot"
        description={<p>Stops the bot, cancels its orders, and starts it again with the current build and config. Quoting pauses for a few seconds.</p>}
        onConfirm={async () => {
          await stopStrategy(strategyId)
          const r = await startStrategy(strategyId)
          toastSuccess('Bot restarted', `pid ${r.pid}`)
          refreshOverview()
        }}
      />
    </div>
  )
}
