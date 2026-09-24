import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchAnalytics } from '@/api/oems'
import type { AnalyticsResponse } from '@/api/types'
import {
  AnalyticsHeatmap,
  type HeatmapMetric,
} from '@/components/AnalyticsHeatmap'
import {
  ANALYTICS_CHART_METRICS,
  AnalyticsSeriesChart,
  seriesMetricLabel,
} from '@/components/AnalyticsSeriesChart'
import { DataState } from '@/components/DataState'
import { InfoTip } from '@/components/InfoTip'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useStrategy } from '@/context/StrategyContext'

type Preset = '1d' | '7d' | '30d' | 'custom'

function toDateInputValue(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function startOfLocalDay(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d, 0, 0, 0, 0)
}

function endOfLocalDay(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d, 23, 59, 59, 999)
}

function rangeForPreset(preset: Preset, customFrom: string, customTo: string): {
  from: string
  to: string
} {
  const now = new Date()
  if (preset === 'custom') {
    return {
      from: startOfLocalDay(customFrom).toISOString(),
      to: endOfLocalDay(customTo).toISOString(),
    }
  }
  const ms =
    preset === '1d'
      ? 24 * 60 * 60 * 1000
      : preset === '7d'
        ? 7 * 24 * 60 * 60 * 1000
        : 30 * 24 * 60 * 60 * 1000
  return {
    from: new Date(now.getTime() - ms).toISOString(),
    to: now.toISOString(),
  }
}

export function TcaAnalyticsSection() {
  const { strategyId } = useStrategy()
  const [preset, setPreset] = useState<Preset>('1d')
  const today = useMemo(() => toDateInputValue(new Date()), [])
  const [customFrom, setCustomFrom] = useState(today)
  const [customTo, setCustomTo] = useState(today)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [heatMetric, setHeatMetric] = useState<HeatmapMetric>('slippage_bps')

  const range = useMemo(
    () => rangeForPreset(preset, customFrom, customTo),
    [preset, customFrom, customTo],
  )

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setData(
        await fetchAnalytics({
          strategy_id: strategyId,
          from: range.from,
          to: range.to,
        }),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics')
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [strategyId, range.from, range.to])

  useEffect(() => {
    void load()
  }, [load])

  const heatCells = data?.heatmap[heatMetric] ?? []

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Analytics range
            <InfoTip label="About analytics range">
              1D, 7D (one week), 30D, or a custom from/to. Server buckets hourly for ranges of 2
              days or less, otherwise daily.
            </InfoTip>
          </CardTitle>
          <CardDescription>Funding is not recorded yet.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            {(
              [
                ['1d', '1D'],
                ['7d', '7D'],
                ['30d', '30D'],
                ['custom', 'Custom'],
              ] as const
            ).map(([id, label]) => (
              <Button
                key={id}
                type="button"
                size="sm"
                variant={preset === id ? 'default' : 'outline'}
                onClick={() => setPreset(id)}
              >
                {label}
              </Button>
            ))}
          </div>
          {preset === 'custom' ? (
            <div className="flex flex-wrap items-end gap-4">
              <div className="grid gap-1.5">
                <Label htmlFor="analytics-from">From</Label>
                <Input
                  id="analytics-from"
                  type="date"
                  value={customFrom}
                  onChange={(e) => setCustomFrom(e.target.value)}
                  className="w-[11rem]"
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="analytics-to">To</Label>
                <Input
                  id="analytics-to"
                  type="date"
                  value={customTo}
                  onChange={(e) => setCustomTo(e.target.value)}
                  className="w-[11rem]"
                />
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <DataState
        loading={loading}
        error={error}
        empty={false}
        onRetry={load}
      >
        {data ? (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  Heatmap
                  <InfoTip label="About heatmap">
                    Columns are calendar days (UTC); rows are hours 0–23. One metric at a time.
                    Empty hours stay blank.
                  </InfoTip>
                </CardTitle>
                <CardDescription>
                  Bucket: {data.bucket} · {data.series.length} series points
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AnalyticsHeatmap
                  metric={heatMetric}
                  onMetricChange={setHeatMetric}
                  cells={heatCells}
                />
              </CardContent>
            </Card>

            {ANALYTICS_CHART_METRICS.map((metric) => (
              <Card key={metric}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {seriesMetricLabel(metric)}
                    <InfoTip label={`About ${seriesMetricLabel(metric)}`}>
                      Values from OEMS analytics for the selected range. Bps are averaged within
                      each bucket; fees and volume are summed; equity and PnL use the last
                      snapshot in the bucket.
                    </InfoTip>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <AnalyticsSeriesChart points={data.series} metric={metric} />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}
      </DataState>
    </div>
  )
}
