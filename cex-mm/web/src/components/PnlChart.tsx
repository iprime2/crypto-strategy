import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, XAxis } from 'recharts'
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

type Props = {
  points: PnlSnapshot[]
}

export function PnlChart({ points }: Props) {
  const [series, setSeries] = useState<ChartSeries>('equity')
  const meta = SERIES[series]

  const data = useMemo(
    () =>
      [...points].reverse().map((p) => ({
        ts: p.ts,
        value: p[series],
      })),
    [points, series],
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 px-2 sm:px-0">
        <Label htmlFor="pnl-series" className="sr-only">
          Chart series
        </Label>
        <Select
          value={series}
          onValueChange={(value) => {
            if (value === 'equity' || value === 'realized' || value === 'unrealized') {
              setSeries(value)
            }
          }}
        >
          <SelectTrigger id="pnl-series" size="sm" className="w-[12rem]">
            <SelectValue placeholder="Series" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="equity">{SERIES.equity.label}</SelectItem>
            <SelectItem value="realized">{SERIES.realized.label}</SelectItem>
            <SelectItem value="unrealized">{SERIES.unrealized.label}</SelectItem>
          </SelectContent>
        </Select>
      </div>

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
