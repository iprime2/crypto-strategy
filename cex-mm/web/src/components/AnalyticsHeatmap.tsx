import { useMemo, type CSSProperties } from 'react'
import type { HeatmapCell } from '@/api/types'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { fmtBps, fmtNum, fmtUsd } from '@/lib/format'
import { cn } from '@/lib/utils'

export type HeatmapMetric = 'slippage_bps' | 'fee_quote' | 'volume_quote' | 'equity'

const METRIC_LABELS: Record<HeatmapMetric, string> = {
  slippage_bps: 'Slippage (bps)',
  fee_quote: 'Fee (USD)',
  volume_quote: 'Volume (quote)',
  equity: 'Equity (USD)',
}

type Props = {
  metric: HeatmapMetric
  onMetricChange: (metric: HeatmapMetric) => void
  cells: HeatmapCell[]
}

function formatCell(metric: HeatmapMetric, value: number): string {
  if (metric === 'slippage_bps') return fmtBps(value, 1)
  if (metric === 'fee_quote') return fmtUsd(value, 2)
  if (metric === 'volume_quote') return fmtUsd(value, 0)
  return fmtUsd(value, 0)
}

/** Map value into a cool→warm alpha on the chart-1 hue. */
function cellStyle(value: number, min: number, max: number): CSSProperties {
  if (!Number.isFinite(value) || max === min) {
    return { backgroundColor: 'color-mix(in oklch, var(--chart-1) 35%, transparent)' }
  }
  const t = Math.min(1, Math.max(0, (value - min) / (max - min)))
  const alpha = 0.15 + t * 0.75
  return {
    backgroundColor: `color-mix(in oklch, var(--chart-1) ${Math.round(alpha * 100)}%, transparent)`,
  }
}

export function AnalyticsHeatmap({ metric, onMetricChange, cells }: Props) {
  const { grid, days, min, max } = useMemo(() => {
    const daySet = new Set<string>()
    const map = new Map<string, number>()
    let lo = Infinity
    let hi = -Infinity
    for (const c of cells) {
      daySet.add(c.day)
      map.set(`${c.day}|${c.hour}`, c.value)
      if (Number.isFinite(c.value)) {
        lo = Math.min(lo, c.value)
        hi = Math.max(hi, c.value)
      }
    }
    const daysSorted = [...daySet].sort()
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) {
      lo = 0
      hi = 0
    }
    return { grid: map, days: daysSorted, min: lo, max: hi }
  }, [cells])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Label htmlFor="heatmap-metric">Metric</Label>
        <Select
          value={metric}
          onValueChange={(v) => {
            if (
              v === 'slippage_bps' ||
              v === 'fee_quote' ||
              v === 'volume_quote' ||
              v === 'equity'
            ) {
              onMetricChange(v)
            }
          }}
        >
          <SelectTrigger id="heatmap-metric" size="sm" className="w-[14rem]">
            <SelectValue placeholder="Metric" />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(METRIC_LABELS) as HeatmapMetric[]).map((key) => (
              <SelectItem key={key} value={key}>
                {METRIC_LABELS[key]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {days.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No heatmap cells in this range
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <div
              className="inline-grid gap-0.5"
              style={{
                gridTemplateColumns: `2.5rem repeat(${days.length}, minmax(2.25rem, 1fr))`,
              }}
            >
              <div />
              {days.map((day) => (
                <div
                  key={day}
                  className="px-0.5 text-center text-[10px] text-muted-foreground"
                  title={day}
                >
                  {day.slice(5)}
                </div>
              ))}
              {Array.from({ length: 24 }, (_, hour) => (
                <div key={`row-${hour}`} className="contents">
                  <div className="flex items-center justify-end pr-1 text-[10px] tabular-nums text-muted-foreground">
                    {String(hour).padStart(2, '0')}
                  </div>
                  {days.map((day) => {
                    const value = grid.get(`${day}|${hour}`)
                    if (value === undefined) {
                      return (
                        <div
                          key={`${day}-${hour}`}
                          className="h-4 rounded-[2px] bg-transparent"
                          aria-hidden
                        />
                      )
                    }
                    return (
                      <div
                        key={`${day}-${hour}`}
                        className={cn('h-4 rounded-[2px] border border-border/40')}
                        style={cellStyle(value, min, max)}
                        title={`${day} ${String(hour).padStart(2, '0')}:00 UTC — ${formatCell(metric, value)}`}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>Legend (UTC)</span>
            <div className="flex items-center gap-2">
              <span className="tabular-nums">{formatCell(metric, min)}</span>
              <div
                className="h-2 w-24 rounded-sm border border-border/40"
                style={{
                  background:
                    'linear-gradient(to right, color-mix(in oklch, var(--chart-1) 15%, transparent), color-mix(in oklch, var(--chart-1) 90%, transparent))',
                }}
              />
              <span className="tabular-nums">{formatCell(metric, max)}</span>
            </div>
            <span className="text-muted-foreground/80">
              Empty hours stay blank · {fmtNum(cells.length, 0)} cells
            </span>
          </div>
        </>
      )}
    </div>
  )
}
