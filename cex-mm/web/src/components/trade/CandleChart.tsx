import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { fetchCandles } from '@/api/oems'
import type { Fill, VenueOrder } from '@/api/types'
import { ErrorNote, Segmented } from '@/components/kit'
import { usePoll } from '@/hooks/usePoll'
import { useApp } from '@/context/AppContext'
import { fmtPrice } from '@/lib/format'

const RESOLUTIONS = [
  { value: '1m', label: '1m', seconds: 60, window: 6 * 3600 },
  { value: '5m', label: '5m', seconds: 300, window: 2 * 86400 },
  { value: '15m', label: '15m', seconds: 900, window: 5 * 86400 },
  { value: '1h', label: '1h', seconds: 3600, window: 20 * 86400 },
] as const
type Resolution = (typeof RESOLUTIONS)[number]['value']

let probe: CanvasRenderingContext2D | null = null

/** Theme colors can be oklch(), which lightweight-charts cannot parse: resolve to rgb via a 1-px canvas. */
function toRgb(color: string, fallback: string): string {
  if (!color) return fallback
  if (/^#|^rgb/i.test(color)) return color
  probe ??= document.createElement('canvas').getContext('2d', { willReadFrequently: true })
  if (!probe) return fallback
  probe.clearRect(0, 0, 1, 1)
  probe.fillStyle = fallback
  probe.fillStyle = color
  probe.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data
  return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`
}

function cssVar(name: string, fallback: string): string {
  return toRgb(getComputedStyle(document.documentElement).getPropertyValue(name).trim(), fallback)
}

function palette() {
  return {
    text: cssVar('--muted-foreground', '#999999'),
    grid: cssVar('--border', '#333333'),
    up: cssVar('--up', '#2ebd85'),
    down: cssVar('--down', '#f6465d'),
    s1: cssVar('--s1', '#3987e5'),
    s2: cssVar('--s2', '#d95926'),
  }
}

function withAlpha(rgb: string, alpha: number): string {
  const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (m) return `rgba(${m[1]}, ${m[2]}, ${m[3]}, ${alpha})`
  if (/^#[0-9a-f]{6}$/i.test(rgb)) return rgb + Math.round(alpha * 255).toString(16).padStart(2, '0')
  return rgb
}

const localTime = (t: Time) =>
  new Date((t as number) * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

export function CandleChart({
  symbol,
  orders,
  fills,
  entry,
  fair,
  priceDigits,
}: {
  symbol: string
  orders: VenueOrder[]
  fills: Fill[]
  entry: number | null
  fair: number | null
  priceDigits: number
}) {
  const { theme } = useApp()
  const [res, setRes] = useState<Resolution>('1m')
  const [showOrders, setShowOrders] = useState(true)
  const [showFills, setShowFills] = useState(true)
  const container = useRef<HTMLDivElement>(null)
  const chart = useRef<IChartApi | null>(null)
  const candles = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volume = useRef<ISeriesApi<'Histogram'> | null>(null)
  const markers = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const lines = useRef<IPriceLine[]>([])
  const fitted = useRef(false)
  const spec = RESOLUTIONS.find((r) => r.value === res)!

  const data = usePoll(
    (signal) => {
      const to = Math.floor(Date.now() / 1000)
      return fetchCandles(symbol, res, to - spec.window, to, signal)
    },
    res === '1m' ? 4000 : 15000,
    [symbol, res],
  )

  // Create the chart once per mount; theme changes only restyle it.
  useEffect(() => {
    if (!container.current) return
    const p = palette()
    const c = createChart(container.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: p.text,
        fontFamily: "'Geist Mono Variable', ui-monospace, monospace",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: p.grid, scaleMargins: { top: 0.08, bottom: 0.22 } },
      timeScale: { borderColor: p.grid, timeVisible: true, secondsVisible: false, tickMarkFormatter: localTime },
      localization: { timeFormatter: localTime },
    })
    candles.current = c.addSeries(CandlestickSeries, {
      upColor: p.up,
      downColor: p.down,
      borderUpColor: p.up,
      borderDownColor: p.down,
      wickUpColor: p.up,
      wickDownColor: p.down,
    })
    volume.current = c.addSeries(HistogramSeries, {
      priceScaleId: 'vol',
      priceFormat: { type: 'volume' },
      lastValueVisible: false,
      priceLineVisible: false,
    })
    c.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    markers.current = createSeriesMarkers(candles.current, [])
    chart.current = c
    return () => {
      c.remove()
      chart.current = null
      candles.current = null
      volume.current = null
      markers.current = null
      lines.current = []
    }
  }, [])

  useEffect(() => {
    const c = chart.current
    if (!c || !candles.current) return
    const p = palette()
    c.applyOptions({
      layout: { textColor: p.text },
      grid: { vertLines: { color: p.grid }, horzLines: { color: p.grid } },
      rightPriceScale: { borderColor: p.grid },
      timeScale: { borderColor: p.grid },
    })
    candles.current.applyOptions({
      upColor: p.up,
      downColor: p.down,
      borderUpColor: p.up,
      borderDownColor: p.down,
      wickUpColor: p.up,
      wickDownColor: p.down,
    })
  }, [theme])

  useEffect(() => {
    candles.current?.applyOptions({
      priceFormat: { type: 'price', precision: priceDigits, minMove: Math.pow(10, -priceDigits) },
    })
  }, [priceDigits])

  useEffect(() => {
    fitted.current = false
  }, [symbol, res])

  useEffect(() => {
    const rows = data.data
    if (!rows || !candles.current || !volume.current) return
    const p = palette()
    candles.current.setData(
      rows.map((r) => ({ time: r.time as UTCTimestamp, open: r.open, high: r.high, low: r.low, close: r.close })),
    )
    volume.current.setData(
      rows.map((r) => ({
        time: r.time as UTCTimestamp,
        value: r.volume,
        color: withAlpha(r.close >= r.open ? p.up : p.down, 0.33),
      })),
    )
    if (!fitted.current && rows.length) {
      const from = Math.max(0, rows.length - 180)
      chart.current?.timeScale().setVisibleLogicalRange({ from, to: rows.length + 4 })
      fitted.current = true
    }
  }, [data.data])

  const symbolOrders = useMemo(() => orders.filter((o) => o.symbol === symbol), [orders, symbol])

  // Price lines: our resting quotes, fair value, position entry.
  useEffect(() => {
    const s = candles.current
    if (!s) return
    for (const l of lines.current) s.removePriceLine(l)
    lines.current = []
    const p = palette()
    if (showOrders) {
      for (const o of symbolOrders) {
        lines.current.push(
          s.createPriceLine({
            price: o.price,
            color: o.side === 'buy' ? p.up : p.down,
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: o.side === 'buy' ? 'Our bid' : 'Our ask',
          }),
        )
      }
    }
    if (fair) {
      lines.current.push(
        s.createPriceLine({ price: fair, color: p.s2, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: 'Fair' }),
      )
    }
    if (entry) {
      lines.current.push(
        s.createPriceLine({ price: entry, color: p.s1, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: 'Entry' }),
      )
    }
  }, [symbolOrders, fair, entry, showOrders, theme])

  // Fill markers on the bar that contains them.
  useEffect(() => {
    if (!markers.current) return
    if (!showFills) {
      markers.current.setMarkers([])
      return
    }
    const p = palette()
    const start = data.data?.[0]?.time ?? 0
    const ms: SeriesMarker<Time>[] = fills
      .filter((f) => f.symbol === symbol)
      .map((f) => {
        const t = Math.floor(Date.parse(f.created_at) / 1000)
        return { f, bar: t - (t % spec.seconds) }
      })
      .filter(({ bar }) => bar >= start)
      .sort((a, b) => a.bar - b.bar)
      .map(({ f, bar }, i, all) => ({
        time: bar as UTCTimestamp,
        position: f.side === 'buy' ? 'belowBar' : 'aboveBar',
        shape: f.side === 'buy' ? 'arrowUp' : 'arrowDown',
        color: f.side === 'buy' ? p.up : p.down,
        // Label only the latest few; the Fills tab has every price.
        text: i >= all.length - 3 ? `${f.side === 'buy' ? 'B' : 'S'} ${fmtPrice(f.price, priceDigits)}${f.role === 'taker' ? ' T' : ''}` : undefined,
        size: 0.6,
      }))
    markers.current.setMarkers(ms)
  }, [fills, symbol, showFills, data.data, spec.seconds, priceDigits, theme])

  return (
    <div className="flex h-full min-h-[320px] flex-col">
      <div className="flex flex-wrap items-center gap-2 px-3 py-1.5">
        <Segmented label="Candle interval" value={res} onChange={setRes} options={RESOLUTIONS.map((r) => ({ value: r.value, label: r.label }))} />
        <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <input type="checkbox" className="accent-[var(--s1)]" checked={showOrders} onChange={(e) => setShowOrders(e.target.checked)} />
          Our quotes
        </label>
        <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <input type="checkbox" className="accent-[var(--s1)]" checked={showFills} onChange={(e) => setShowFills(e.target.checked)} />
          Fills
        </label>
        <span className="ml-auto text-[11px] text-muted-foreground">Times local · Delta candles</span>
      </div>
      {data.error && !data.data ? <ErrorNote message={data.error} onRetry={data.refresh} /> : null}
      <div ref={container} className="min-h-0 flex-1" role="img" aria-label={`${symbol} ${res} candlestick chart with our quotes and fills`} />
    </div>
  )
}
