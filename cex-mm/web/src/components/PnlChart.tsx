import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from 'recharts'
import type { PnlSnapshot } from '@/api/types'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { fmtSignedUsd, fmtUsd } from '@/lib/format'

const SERIES = {
  equity: {
    label: 'Equity',
    color: 'var(--chart-1)',
    signed: false,
  },
  realized: {
    label: 'Realized PnL',
    color: 'var(--chart-2)',
    signed: true,
  },
  unrealized: {
    label: 'Unrealized PnL',
    color: 'var(--chart-3)',
    signed: true,
  },
} as const

export type ChartSeries = keyof typeof SERIES

const chartConfig = {
  equity: {
    label: SERIES.equity.label,
    color: SERIES.equity.color,
  },
  realized: {
    label: SERIES.realized.label,
    color: SERIES.realized.color,
  },
  unrealized: {
    label: SERIES.unrealized.label,
    color: SERIES.unrealized.color,
  },
} satisfies ChartConfig

/**
 * Pad the Y domain around data min/max so a nearly flat series is not stuck to a
 * zero baseline. Equal min/max still get a small band centered on that value.
 */
export function yAxisDomain(values: number[]): [number, number] {
  const finite = values.filter((v) => Number.isFinite(v))
  if (finite.length === 0) return [-1, 1]
  const min = Math.min(...finite)
  const max = Math.max(...finite)
  const span = max - min
  if (span === 0) {
    const pad = Math.max(Math.abs(min) * 0.02, 0.01)
    return [min - pad, max + pad]
  }
  const pad = span * 0.1
  return [min - pad, max + pad]
}

type Props = {
  points: PnlSnapshot[]
  /** When true, omit the series select (parent renders it in the card header). */
  hideSeriesSelect?: boolean
  series?: ChartSeries
  onSeriesChange?: (series: ChartSeries) => void
}

export function PnlSeriesSelect({
  series,
  onSeriesChange,
  id = 'pnl-series',
}: {
  series: ChartSeries
  onSeriesChange: (series: ChartSeries) => void
  id?: string
}) {
  return (
    <>
      <Label htmlFor={id} className="sr-only">
        Chart series
      </Label>
      <Select
        value={series}
        onValueChange={(value) => {
          if (value === 'equity' || value === 'realized' || value === 'unrealized') {
            onSeriesChange(value)
          }
        }}
      >
        <SelectTrigger id={id} size="sm" className="w-[12rem]">
          <SelectValue placeholder="Series" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="equity">{SERIES.equity.label}</SelectItem>
          <SelectItem value="realized">{SERIES.realized.label}</SelectItem>
          <SelectItem value="unrealized">{SERIES.unrealized.label}</SelectItem>
        </SelectContent>
      </Select>
    </>
  )
}

export function PnlChart({
  points,
  hideSeriesSelect = false,
  series: seriesProp,
  onSeriesChange,
}: Props) {
  const [internalSeries, setInternalSeries] = useState<ChartSeries>('equity')
  const series = seriesProp ?? internalSeries
  const setSeries = onSeriesChange ?? setInternalSeries
  const meta = SERIES[series]

  const data = useMemo(
    () =>
      [...points].reverse().map((p) => ({
        ts: p.ts,
        value: p[series],
      })),
    [points, series],
  )

  const domain = useMemo(
    () => yAxisDomain(data.map((d) => d.value).filter((v): v is number => v != null && Number.isFinite(v))),
    [data],
  )

  const tickFormatter = (value: number) =>
    meta.signed ? fmtSignedUsd(value) : fmtUsd(value)

  return (
    <div className="flex flex-col gap-4">
      {!hideSeriesSelect ? (
        <div className="flex items-center gap-2 px-2 sm:px-0">
          <PnlSeriesSelect series={series} onSeriesChange={setSeries} />
        </div>
      ) : null}

      <ChartContainer config={chartConfig} className="aspect-auto h-[250px] w-full">
        <AreaChart data={data} accessibilityLayer>
          <defs>
            <linearGradient id="fillSeries" x1="0" y1="0" x2="0" y2="1">
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
            tickFormatter={tickFormatter}
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
                  const formatted = meta.signed ? fmtSignedUsd(n) : fmtUsd(n)
                  return (
                    <div className="flex flex-1 justify-between gap-8 leading-none">
                      <span className="text-muted-foreground">{meta.label}</span>
                      <span className="font-mono font-medium tabular-nums text-foreground">
                        {formatted}
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
            name={series}
            type="natural"
            fill="url(#fillSeries)"
            stroke={meta.color}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  )
}
