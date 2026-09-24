import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { fetchLatestSnapshot, fetchStrategies, fetchStrategy } from '../api/oems'
import type { LatestSnapshot, Strategy, StrategyStatus } from '../api/types'

const DEFAULT_STRATEGY_ID = 'mm'

type StrategyContextValue = {
  strategyId: string
  setStrategyId: (id: string) => void
  strategies: Strategy[]
  status: StrategyStatus
  snapshot: LatestSnapshot | null
  headerError: string | null
  refreshHeader: () => Promise<void>
}

const StrategyContext = createContext<StrategyContextValue | null>(null)

function normalizeStatus(s: Strategy | LatestSnapshot | null): StrategyStatus {
  if (!s) return 'stopped'
  if ('desired_state' in s && (s.desired_state === 'running' || s.desired_state === 'stopped')) {
    return s.desired_state
  }
  if ('status' in s && (s.status === 'running' || s.status === 'stopped')) {
    return s.status
  }
  return 'stopped'
}

export function StrategyProvider({ children }: { children: ReactNode }) {
  const [strategyId, setStrategyId] = useState(DEFAULT_STRATEGY_ID)
  const [strategies, setStrategies] = useState<Strategy[]>([
    { id: 'mm', name: 'Market maker', desired_state: 'stopped' },
  ])
  const [status, setStatus] = useState<StrategyStatus>('stopped')
  const [snapshot, setSnapshot] = useState<LatestSnapshot | null>(null)
  const [headerError, setHeaderError] = useState<string | null>(null)

  const refreshHeader = useCallback(async () => {
    try {
      const [list, snap, strat] = await Promise.all([
        fetchStrategies().catch(() => null),
        fetchLatestSnapshot(strategyId),
        fetchStrategy(strategyId).catch(() => null),
      ])
      if (list && list.length > 0) {
        const ids = new Set(list.map((s) => s.id))
        if (!ids.has('mm')) {
          setStrategies([{ id: 'mm', name: 'Market maker', desired_state: 'stopped' }, ...list])
        } else {
          setStrategies(list)
        }
      }
      setSnapshot(snap)
      setStatus(normalizeStatus(strat ?? snap))
      setHeaderError(null)
    } catch (err) {
      setHeaderError(err instanceof Error ? err.message : 'Failed to load header')
    }
  }, [strategyId])

  useEffect(() => {
    void refreshHeader()
    const id = window.setInterval(() => {
      void refreshHeader()
    }, 15_000)
    return () => window.clearInterval(id)
  }, [refreshHeader])

  const value = useMemo(
    () => ({
      strategyId,
      setStrategyId,
      strategies,
      status,
      snapshot,
      headerError,
      refreshHeader,
    }),
    [strategyId, strategies, status, snapshot, headerError, refreshHeader],
  )

  return <StrategyContext.Provider value={value}>{children}</StrategyContext.Provider>
}

export function useStrategy(): StrategyContextValue {
  const ctx = useContext(StrategyContext)
  if (!ctx) throw new Error('useStrategy must be used within StrategyProvider')
  return ctx
}
