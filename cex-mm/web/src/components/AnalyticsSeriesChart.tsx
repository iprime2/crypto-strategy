import { useMemo } from 'react'
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import type { AnalyticsSeriesPoint } from '@/api/types'
import { yAxisDomain } from '@/components/PnlChart'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { fmtBps, fmtNum, fmtSignedUsd, fmtUsd } from '@/lib/format'

export type SeriesMetricKey =
  | 'slippage_bps'
  | 'fee_quote'
  | 'volume_quote'
  | 'equity'
  | 'realized'
  | 'unrealized'
  | 'effective_spread_bps'
  | 'markout_5s_bps'

type Unit = 'usd' | 'usd_signed' | 'bps'

const METRICS: Record<
  SeriesMetricKey,
  { label: string; color: string; unit: Unit }
> = {
  slippage_bps: { label: 'Slippage', color: 'var(--chart-1)', unit: 'bps' },
  fee_quote: { label: 'Fees', color: 'var(--chart-2)', unit: 'usd' },
  volume_quote: { label: 'Volume', color: 'var(--chart-3)', unit: 'usd' },
  equity: { label: 'Equity', color: 'var(--chart-1)', unit: 'usd' },
  realized: { label: 'Realized PnL', color: 'var(--chart-2)', unit: 'usd_signed' },
  unrealized: { label: 'Unrealized PnL', color: 'var(--chart-3)', unit: 'usd_signed' },
  effective_spread_bps: {
    label: 'Effective spread',
    color: 'var(--chart-4)',
    unit: 'bps',
  },
  markout_5s_bps: { label: 'Markout 5s', color: 'var(--chart-5)', unit: 'bps' },
}

function formatValue(unit: Unit, n: number): string {
  if (unit === 'bps') return fmtBps(n)
  if (unit === 'usd_signed') return fmtSignedUsd(n)
  return fmtUsd(n)
}

function tickFormat(unit: Unit, n: number): string {
  if (unit === 'bps') return fmtNum(n, 1)
  if (unit === 'usd_signed') return fmtSignedUsd(n, 0)
  return fmtUsd(n, 0)
}

type Props = {
  points: AnalyticsSeriesPoint[]
  metric: SeriesMetricKey
}

export function AnalyticsSeriesChart({ points, metric }: Props) {
  const meta = METRICS[metric]
  const config = {
    value: { label: meta.label, color: meta.color },
  } satisfies ChartConfig

  const data = useMemo(
    () =>
      points.map((p) => ({
        ts: p.ts,
        value: p[metric],
      })),
    [points, metric],
  )

  const domain = useMemo(
    () =>
      yAxisDomain(
        data
          .map((d) => d.value)
          .filter((v): v is number => v != null && Number.isFinite(v)),
      ),
    [data],
  )

  const hasPoints = data.some((d) => d.value != null && Number.isFinite(d.value))

  if (!hasPoints) {
    return (
      <p className="px-2 py-8 text-center text-sm text-muted-foreground">
        No {meta.label.toLowerCase()} data in this range
      </p>
    )
  }

  const gradientId = `fill-${metric}`

  return (
    <ChartContainer config={config} className="aspect-auto h-[220px] w-full">
      <AreaChart data={data} accessibilityLayer>
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={meta.color} stopOpacity={0.8} />
            <stop offset="95%" stopColor={meta.color} stopOpacity={0.1} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="ts"
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          minTickGap={32}
          tickFormatter={(value) => {
            const date = new Date(value)
            if (Number.isNaN(date.getTime())) return String(value)
            return date.toLocaleString(undefined, {
              month: 'short',
              day: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })
          }}
        />
        <YAxis
          domain={domain}
          tickLine={false}
          axisLine={false}
          width={72}
          tickMargin={4}
          tickFormatter={(v) => tickFormat(meta.unit, Number(v))}
          label={{
            value: meta.unit === 'bps' ? 'bps' : 'USD',
            angle: -90,
            position: 'insideLeft',
            style: { fill: 'var(--muted-foreground)', fontSize: 11 },
          }}
        />
        <ChartTooltip
          cursor={false}
          content={
            <ChartTooltipContent
              labelFormatter={(value) => {
                const date = new Date(String(value))
                if (Number.isNaN(date.getTime())) return String(value)
                return date.toLocaleString()
              }}
              formatter={(value) => {
                const n = typeof value === 'number' ? value : Number(value)
                return (
                  <div className="flex flex-1 justify-between gap-8 leading-none">
                    <span className="text-muted-foreground">{meta.label}</span>
                    <span className="font-mono font-medium tabular-nums text-foreground">
                      {formatValue(meta.unit, n)}
                    </span>
                  </div>
                )
              }}
              indicator="dot"
            />
          }
        />
        <Area
          dataKey="value"
          name={metric}
          type="natural"
          connectNulls={false}
          fill={`url(#${gradientId})`}
          stroke={meta.color}
        />
      </AreaChart>
    </ChartContainer>
  )
}

export const ANALYTICS_CHART_METRICS: SeriesMetricKey[] = [
  'slippage_bps',
  'fee_quote',
  'volume_quote',
  'equity',
  'realized',
  'unrealized',
  'effective_spread_bps',
  'markout_5s_bps',
]

export function seriesMetricLabel(key: SeriesMetricKey): string {
  const m = METRICS[key]
  if (m.unit === 'bps') return `${m.label} (bps)`
  return `${m.label} (USD)`
}
