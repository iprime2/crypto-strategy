import { Component, type ErrorInfo, type ReactNode } from 'react'
import { CircleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'

/** Dense terminal panel: title row with optional actions, then content. */
export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <section className={cn('flex min-w-0 flex-col rounded-lg border bg-panel', className)}>
      <header className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 border-b px-3 py-1.5">
        <h2 className="text-[13px] font-semibold tracking-tight">{title}</h2>
        {subtitle ? <span className="text-xs text-muted-foreground">{subtitle}</span> : null}
        {actions ? <div className="ml-auto flex items-center gap-1.5">{actions}</div> : null}
      </header>
      <div className={cn('min-h-0 flex-1', bodyClassName)}>{children}</div>
    </section>
  )
}

export function Stat({
  label,
  value,
  sub,
  tone,
  className,
}: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  tone?: string
  className?: string
}) {
  return (
    <div className={cn('min-w-0', className)}>
      <div className="truncate text-[11px] text-muted-foreground">{label}</div>
      <div className={cn('num truncate text-sm font-semibold', tone)}>{value}</div>
      {sub ? <div className="truncate text-[11px] text-muted-foreground">{sub}</div> : null}
    </div>
  )
}

export type Level = 'ok' | 'warn' | 'bad' | 'idle'

const LEVEL_COLOR: Record<Level, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  bad: 'bg-down',
  idle: 'bg-muted-foreground/60',
}
const LEVEL_ICON: Record<Level, string> = { ok: '✓', warn: '!', bad: '✕', idle: '–' }

/** Status is never color alone: dot + symbol + words. */
export function StatusPill({ level, label, detail, title }: { level: Level; label: string; detail?: string; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex h-6 items-center gap-1.5 rounded-full border px-2 text-[11px] whitespace-nowrap text-muted-foreground"
    >
      <span className={cn('size-2 rounded-full', LEVEL_COLOR[level])} aria-hidden />
      <span className="font-semibold text-foreground" aria-hidden>
        {LEVEL_ICON[level]}
      </span>
      <span className="text-foreground">{label}</span>
      {detail ? <span>· {detail}</span> : null}
    </span>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="px-3 py-8 text-center text-xs text-muted-foreground">{children}</div>
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-2 px-3 py-3 text-xs text-down">
      <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">{message}</span>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="shrink-0 underline underline-offset-2 hover:text-foreground">
          Retry
        </button>
      ) : null}
    </div>
  )
}

/** Segmented control for small option sets (resolution, range, tabs). */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: readonly { value: T; label: string }[]
  onChange: (v: T) => void
  label: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-md border p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={cn(
            'h-6 rounded px-2 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
            o.value === value && 'bg-muted text-foreground',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Compact table primitives for dense blotters. */
export function DataTable({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('overflow-auto', className)}>
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  )
}

export function Th({
  children,
  align = 'right',
  className,
  title,
}: {
  children?: ReactNode
  align?: 'left' | 'right'
  className?: string
  title?: string
}) {
  return (
    <th
      title={title}
      className={cn(
        'sticky top-0 z-[1] border-b bg-panel px-2 py-1.5 font-medium whitespace-nowrap text-muted-foreground',
        align === 'left' ? 'text-left' : 'text-right',
        className,
      )}
    >
      {children}
    </th>
  )
}

export function Td({ children, align = 'right', className, title }: { children?: ReactNode; align?: 'left' | 'right'; className?: string; title?: string }) {
  return (
    <td
      title={title}
      className={cn('border-b border-border/60 px-2 py-1 whitespace-nowrap', align === 'left' ? 'text-left' : 'num text-right', className)}
    >
      {children}
    </td>
  )
}

/** Keeps one failing panel from blanking the page; shows the error and a retry. */
export class ErrorBoundary extends Component<{ children: ReactNode; label?: string }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.label ?? 'panel'}]`, error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorNote
          message={`${this.props.label ?? 'This panel'} failed: ${this.state.error.message}`}
          onRetry={() => this.setState({ error: null })}
        />
      )
    }
    return this.props.children
  }
}
