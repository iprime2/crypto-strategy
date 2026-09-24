import { Area, AreaChart, CartesianGrid, XAxis } from 'recharts'
import type { PnlSnapshot } from '@/api/types'
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'

const chartConfig = {
  equity: {
    label: 'Equity',
    color: 'var(--chart-1)',
  },
  unrealized: {
    label: 'Unrealized',
    color: 'var(--chart-2)',
  },
} satisfies ChartConfig

type Props = {
  points: PnlSnapshot[]
}

export function PnlChart({ points }: Props) {
  const data = [...points]
    .reverse()
    .map((p) => ({
      ts: p.ts,
      equity: p.equity,
      unrealized: p.unrealized,
    }))

  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-[250px] w-full">
      <AreaChart data={data} accessibilityLayer>
        <defs>
          <linearGradient id="fillEquity" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-equity)" stopOpacity={0.8} />
            <stop offset="95%" stopColor="var(--color-equity)" stopOpacity={0.1} />
          </linearGradient>
          <linearGradient id="fillUnrealized" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="5%"
              stopColor="var(--color-unrealized)"
              stopOpacity={0.8}
            />
            <stop
              offset="95%"
              stopColor="var(--color-unrealized)"
              stopOpacity={0.1}
            />
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
              indicator="dot"
            />
          }
        />
        <Area
          dataKey="unrealized"
          type="natural"
          fill="url(#fillUnrealized)"
          stroke="var(--color-unrealized)"
          stackId="a"
        />
        <Area
          dataKey="equity"
          type="natural"
          fill="url(#fillEquity)"
          stroke="var(--color-equity)"
          stackId="a"
        />
        <ChartLegend content={<ChartLegendContent />} />
      </AreaChart>
    </ChartContainer>
  )
}
