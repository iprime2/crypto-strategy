import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { fetchEffectiveConfig, fetchOverview, fetchStrategies } from '@/api/oems'
import type { EffectiveConfig, Overview, Strategy } from '@/api/types'
import { usePoll } from '@/hooks/usePoll'

type Theme = 'dark' | 'light'

type AppContextValue = {
  strategyId: string
  setStrategyId: (id: string) => void
  /** Strategies the OEMS knows, with their Delta environment. */
  strategies: Strategy[]
  /** The selected strategy trades real money (Delta mainnet). */
  isReal: boolean
  overview: Overview | undefined
  overviewError: string | null
  overviewUpdatedAt: number | null
  refreshOverview: () => void
  config: EffectiveConfig | undefined
  refreshConfig: () => void
  /** Symbols this strategy trades (effective MM_SYMBOLS), falling back to ETHUSDT. */
  symbols: string[]
  symbol: string
  setSymbol: (s: string) => void
  theme: Theme
  toggleTheme: () => void
}

const AppContext = createContext<AppContextValue | null>(null)

function readStored(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage may be unavailable; the choice just will not persist
  }
}

/** Numeric config value, trying the per-symbol override first (`KEY_ETHUSDT`). */
export function configNumber(cfg: EffectiveConfig | undefined, key: string, symbol?: string): number | null {
  if (!cfg) return null
  const raw = (symbol && cfg.values[`${key}_${symbol}`]?.value) ?? cfg.values[key]?.value
  const n = raw === undefined ? NaN : Number(raw)
  return Number.isFinite(n) ? n : null
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [strategyId, setStrategyIdState] = useState(() => readStored('oems.strategy', 'mm'))
  const strategiesPoll = usePoll((s) => fetchStrategies(s), 30_000, [])
  const strategies = strategiesPoll.data ?? []
  const overview = usePoll((s) => fetchOverview(strategyId, s), 2000, [strategyId])
  const config = usePoll((s) => fetchEffectiveConfig(strategyId, s), 30_000, [strategyId])
  const [symbol, setSymbolState] = useState(() => readStored('oems.symbol', ''))
  const [theme, setTheme] = useState<Theme>(() => (readStored('oems.theme', 'dark') === 'light' ? 'light' : 'dark'))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
  }, [theme])

  const symbols = useMemo(() => {
    const raw = config.data?.values.MM_SYMBOLS?.value ?? ''
    const list = raw.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean)
    for (const p of overview.data?.positions ?? []) if (!list.includes(p.symbol)) list.push(p.symbol)
    return list.length ? list : ['ETHUSDT']
  }, [config.data, overview.data])

  const activeSymbol = symbols.includes(symbol) ? symbol : symbols[0]

  const setSymbol = useCallback((s: string) => {
    setSymbolState(s)
    store('oems.symbol', s)
  }, [])

  const setStrategyId = useCallback((id: string) => {
    setStrategyIdState(id)
    store('oems.strategy', id)
  }, [])

  // A stored strategy the OEMS no longer has falls back to the demo market maker.
  useEffect(() => {
    if (strategies.length && !strategies.some((s) => s.id === strategyId)) setStrategyId('mm')
  }, [strategies, strategyId, setStrategyId])

  const isReal =
    strategies.find((s) => s.id === strategyId)?.env === 'mainnet' || overview.data?.venue_env === 'mainnet'

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === 'dark' ? 'light' : 'dark'
      store('oems.theme', next)
      return next
    })
  }, [])

  const value: AppContextValue = {
    strategyId,
    setStrategyId,
    strategies,
    isReal,
    overview: overview.data,
    overviewError: overview.error,
    overviewUpdatedAt: overview.updatedAt,
    refreshOverview: overview.refresh,
    config: config.data,
    refreshConfig: config.refresh,
    symbols,
    symbol: activeSymbol,
    setSymbol,
    theme,
    toggleTheme,
  }
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
