import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { startStrategy, stopStrategy } from '@/api/oems'
import { toastError } from '@/lib/toast'
import { StrategyConfigDialog } from '@/components/StrategyConfigDialog'
import { useStrategy } from '@/context/StrategyContext'
import { fmtTs } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const TITLES: Record<string, string> = {
  '/': 'Overview',
  '/positions': 'Positions',
  '/orders': 'Orders',
  '/reconcile': 'Reconcile',
  '/tca': 'TCA',
  '/control': 'Control',
}

function pageTitle(pathname: string): string {
  return TITLES[pathname] ?? 'OEMS'
}

export function Header() {
  const location = useLocation()
  const {
    strategyId,
    setStrategyId,
    strategies,
    status,
    snapshot,
    headerError,
    refreshHeader,
  } = useStrategy()
  const [configOpen, setConfigOpen] = useState(false)
  const [actionPending, setActionPending] = useState(false)

  const running = status === 'running'
  const statusLabel = running ? 'running' : 'stopped'
  const asOfTs = snapshot?.ts ?? snapshot?.balance?.ts

  useEffect(() => {
    if (headerError) {
      toastError('Could not refresh status', headerError)
    }
  }, [headerError])

  async function onToggle() {
    setActionPending(true)
    try {
      if (running) await stopStrategy(strategyId)
      else await startStrategy(strategyId)
      await refreshHeader()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Start or stop failed'
      toastError(running ? 'Stop failed' : 'Start failed', message)
    } finally {
      setActionPending(false)
    }
  }

  return (
    <header className="flex h-(--header-height) shrink-0 flex-col border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full flex-1 items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mx-2 data-[orientation=vertical]:h-4"
        />
        <h1 className="text-base font-medium">{pageTitle(location.pathname)}</h1>
        {asOfTs ? (
          <span className="text-sm text-muted-foreground">As of {fmtTs(asOfTs)}</span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <Badge
            variant={running ? 'default' : 'secondary'}
            className={
              running
                ? 'bg-emerald-700 text-emerald-50 hover:bg-emerald-700'
                : ''
            }
            aria-label={`Strategy status: ${statusLabel}`}
          >
            {statusLabel}
          </Badge>
          <Label htmlFor="strategy-id" className="sr-only">
            Strategy
          </Label>
          <Select
            value={strategyId}
            onValueChange={(value) => {
              if (value) setStrategyId(value)
            }}
          >
            <SelectTrigger id="strategy-id" size="sm" className="w-[12rem]">
              <SelectValue placeholder="Strategy" />
            </SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.id}
                  {s.name ? ` — ${s.name}` : ''}
                </SelectItem>
              ))}
              {!strategies.some((s) => s.id === strategyId) && (
                <SelectItem value={strategyId}>{strategyId}</SelectItem>
              )}
            </SelectContent>
          </Select>
          <Button
            type="button"
            size="sm"
            variant={running ? 'destructive' : 'default'}
            onClick={() => void onToggle()}
            disabled={actionPending}
          >
            {actionPending
              ? running
                ? 'Stopping…'
                : 'Starting…'
              : running
                ? 'Stop'
                : 'Start'}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setConfigOpen(true)}
          >
            Configure
          </Button>
        </div>
      </div>
      <StrategyConfigDialog
        strategyId={strategyId}
        open={configOpen}
        onOpenChange={setConfigOpen}
      />
    </header>
  )
}
