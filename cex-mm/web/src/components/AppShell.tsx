import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Bot, ChartCandlestick, ChartLine, List, Moon, OctagonX, ShieldAlert, Sun, TriangleAlert } from 'lucide-react'
import { stopStrategy } from '@/api/oems'
import { ConfirmDialog } from '@/components/ConfirmDialog'
import { ErrorBoundary, StatusPill } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Toaster } from '@/components/ui/toaster'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useApp } from '@/context/AppContext'
import { fmtDuration, fmtNum, fmtSignedUsd, fmtUsd, signTone } from '@/lib/format'
import { apiCheck, botCheck, venueChecks, worst } from '@/lib/health'
import { toastSuccess } from '@/lib/toast'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: 'Trade', icon: ChartCandlestick, end: true },
  { to: '/performance', label: 'Performance', icon: ChartLine },
  { to: '/blotter', label: 'Blotter', icon: List },
  { to: '/risk', label: 'Risk', icon: ShieldAlert },
  { to: '/strategy', label: 'Strategy', icon: Bot },
] as const

function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

function Metric({ label, value, tone, title }: { label: string; value: string; tone?: string; title?: string }) {
  return (
    <div className="flex min-w-0 flex-col justify-center px-3" title={title}>
      <span className="text-[10px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className={cn('num text-[13px] font-semibold whitespace-nowrap', tone)}>{value}</span>
    </div>
  )
}

/** Pick the strategy every page shows; real-money ones are labelled in words, not just colour. */
function StrategySwitcher() {
  const { strategyId, setStrategyId, strategies } = useApp()
  const list = strategies.length ? strategies : [{ id: strategyId, name: strategyId, env: undefined }]
  return (
    <Select value={strategyId} onValueChange={setStrategyId}>
      <SelectTrigger size="sm" aria-label="Strategy" className="h-7 min-w-36 text-[13px] font-semibold">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {list.map((s) => (
          <SelectItem key={s.id} value={s.id}>
            <span className="font-semibold">{s.id}</span>
            <span className={cn('text-[11px]', s.env === 'mainnet' ? 'font-semibold text-down' : 'text-muted-foreground')}>
              {s.env === 'mainnet' ? 'real money' : s.env === 'demo' ? 'demo' : ''}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function TopBar() {
  const { overview: o, overviewError, overviewUpdatedAt, strategyId, isReal, refreshOverview, theme, toggleTheme } = useApp()
  const [killOpen, setKillOpen] = useState(false)
  const now = useNow()
  const running = o?.strategy.desired_state === 'running'
  const bal = o?.balance
  const marginUsed = bal && bal.equity > 0 ? (bal.blocked_margin / bal.equity) * 100 : null
  const venue = venueChecks(o, now)
  const venueLevel = worst(venue.map((c) => c.level))
  const bot = botCheck(o, now)
  const api = apiCheck(overviewError, overviewUpdatedAt, now)
  const isLive = isReal

  return (
    <header className="sticky top-0 z-20 flex h-14 items-stretch border-b bg-background/95 backdrop-blur">
      <div className="flex items-center gap-2 border-r px-3">
        <span className="text-sm font-bold tracking-tight">OEMS</span>
        <span
          className={cn(
            'rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider',
            isLive ? 'bg-down text-white' : 'bg-warn/20 text-warn',
          )}
          title={isLive ? 'Delta India mainnet: real money' : 'Delta India demo account'}
        >
          {o || isLive ? (isLive ? 'REAL MONEY' : 'DEMO') : '…'}
        </span>
      </div>

      <div className="flex items-center gap-2 border-r px-3">
        <span
          className={cn('size-2.5 rounded-full', running ? 'bg-ok' : 'bg-muted-foreground/50')}
          aria-hidden
        />
        <div className="flex flex-col gap-0.5 leading-tight">
          <span className="flex items-center gap-1.5 text-[13px] font-semibold">
            <StrategySwitcher />
            {running ? 'Running' : 'Stopped'}
          </span>
          <span className="num text-[11px] text-muted-foreground">
            {running
              ? `up ${fmtDuration(o?.strategy.uptime_s)}${o?.strategy.pid ? ` · pid ${o.strategy.pid}` : ''}`
              : o?.strategy.last_exit
                ? `last exit code ${o.strategy.last_exit.code ?? '?'}`
                : 'idle'}
          </span>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 items-stretch overflow-x-auto">
        <Metric label="Equity" value={fmtUsd(bal?.equity)} />
        <Metric
          label="Day PnL"
          value={fmtSignedUsd(o?.day.pnl)}
          tone={signTone(o?.day.pnl)}
          title="Equity change since local midnight (first snapshot after it)"
        />
        <Metric label="Unrealized" value={fmtSignedUsd(o?.unrealized)} tone={signTone(o?.unrealized)} />
        <Metric label="Available" value={fmtUsd(bal?.available)} />
        <Metric label="Margin used" value={marginUsed === null ? '—' : `${fmtNum(marginUsed, 1)}%`} title="Blocked margin / equity" />
        <Metric label="Open orders" value={o ? String(o.open_orders) : '—'} />
      </div>

      <div className="flex items-center gap-1.5 border-l px-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <button type="button" className="hidden rounded-full focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none md:block">
              <StatusPill level={worst([api.level, venueLevel, bot.level === 'idle' ? 'ok' : bot.level])} label="Health" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-sm">
            <ul className="space-y-1 text-xs">
              {[api, ...venue.map((c) => ({ ...c, label: `Venue ${c.label.toLowerCase()}` })), bot].map((c) => (
                <li key={c.label} className="flex gap-2">
                  <span className="w-3 shrink-0 font-bold">{c.level === 'ok' ? '✓' : c.level === 'idle' ? '–' : c.level === 'warn' ? '!' : '✕'}</span>
                  <span className="font-medium">{c.label}</span>
                  <span className="opacity-80">{c.detail}</span>
                </li>
              ))}
            </ul>
          </TooltipContent>
        </Tooltip>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => setKillOpen(true)}
          disabled={!running}
          title={running ? 'Stop the bot and cancel all its orders' : 'Bot is not running'}
        >
          <OctagonX /> Kill
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
          {theme === 'dark' ? <Sun /> : <Moon />}
        </Button>
      </div>

      <ConfirmDialog
        open={killOpen}
        onOpenChange={setKillOpen}
        title="Kill switch"
        destructive
        confirmLabel="Stop bot and cancel orders"
        description={
          <>
            <p>
              Stops <span className="font-semibold text-foreground">{strategyId}</span> (SIGTERM, then SIGKILL after 5 s) and
              cancels every open order for its symbols on Delta.
            </p>
            <p>Positions stay open. Close them from the Risk page if needed.</p>
          </>
        }
        onConfirm={async () => {
          await stopStrategy(strategyId)
          toastSuccess('Bot stopped', 'Orders cancelled; positions left open.')
          refreshOverview()
        }}
      />
    </header>
  )
}

function NavRail() {
  return (
    <nav aria-label="Main" className="flex shrink-0 flex-col gap-1 border-r p-1.5 max-md:fixed max-md:inset-x-0 max-md:bottom-0 max-md:z-20 max-md:flex-row max-md:justify-around max-md:border-t max-md:border-r-0 max-md:bg-background">
      {NAV.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={'end' in item ? item.end : false}
            className={({ isActive }) =>
              cn(
                'flex w-16 flex-col items-center gap-0.5 rounded-md py-2 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                isActive && 'bg-muted text-foreground',
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {item.label}
          </NavLink>
        )
      })}
    </nav>
  )
}

function RealMoneyBanner() {
  const { isReal, strategyId } = useApp()
  if (!isReal) return null
  return (
    <div role="note" className="flex items-center gap-2 border-b border-down/40 bg-down/10 px-4 py-1.5 text-xs font-medium text-down">
      <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
      <span>
        Real money: <span className="font-semibold">{strategyId}</span> trades on Delta India mainnet. Start, stop,
        cancel and close act on real funds.
      </span>
    </div>
  )
}

function StaleBackendBanner() {
  const { overviewError, overview } = useApp()
  if (overview || !overviewError) return null
  const outdated = /404|not found/i.test(overviewError)
  return (
    <div role="alert" className="border-b border-down/40 bg-down/10 px-4 py-2 text-xs text-down">
      {outdated
        ? 'The OEMS backend is older than this UI (no /api/overview). Restart mm-oems with the new build.'
        : `Cannot reach the OEMS: ${overviewError}`}
    </div>
  )
}

export function AppShell() {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-svh flex-col">
        <TopBar />
        <RealMoneyBanner />
        <StaleBackendBanner />
        <div className="flex min-h-0 flex-1">
          <NavRail />
          <main className="min-w-0 flex-1 p-2 max-md:pb-20 md:p-3">
            <ErrorBoundary label="Page">
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
