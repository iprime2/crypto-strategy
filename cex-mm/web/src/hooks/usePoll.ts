import { useCallback, useEffect, useRef, useState } from 'react'

export type Poll<T> = {
  data: T | undefined
  error: string | null
  loading: boolean
  /** When the last successful response arrived (ms). */
  updatedAt: number | null
  refresh: () => void
}

/**
 * Poll `fn` every `intervalMs` (0 = once) while the tab is visible. Keeps the
 * previous data while refetching so views do not flash, clears it only when `deps`
 * change (a different symbol or strategy), aborts in-flight requests on change or
 * unmount, and never overlaps two requests.
 */
export function usePoll<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  deps: readonly unknown[],
): Poll<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState<number | null>(null)
  const [nonce, setNonce] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  const depsKey = JSON.stringify(deps)

  useEffect(() => {
    setData(undefined)
    setError(null)
    setLoading(true)
    setUpdatedAt(null)
  }, [depsKey])

  useEffect(() => {
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | null = null

    const run = async () => {
      if (!alive) return
      if (document.visibilityState === 'hidden') {
        timer = setTimeout(run, Math.max(intervalMs, 1000))
        return
      }
      controller = new AbortController()
      try {
        const v = await fnRef.current(controller.signal)
        if (!alive) return
        setData(v)
        setError(null)
        setUpdatedAt(Date.now())
      } catch (e) {
        if (!alive || (e instanceof DOMException && e.name === 'AbortError')) return
        setError(e instanceof Error ? e.message : 'Request failed')
      } finally {
        if (alive) {
          setLoading(false)
          if (intervalMs > 0) timer = setTimeout(run, intervalMs)
        }
      }
    }
    void run()
    return () => {
      alive = false
      controller?.abort()
      if (timer) clearTimeout(timer)
    }
  }, [depsKey, intervalMs, nonce])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, updatedAt, refresh }
}
