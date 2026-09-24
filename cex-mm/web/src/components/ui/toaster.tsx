import { useEffect, useState } from 'react'
import { subscribeToasts } from '@/lib/toast'

type Item = {
  id: number
  title: string
  description?: string
}

let nextId = 1

export function Toaster() {
  const [items, setItems] = useState<Item[]>([])

  useEffect(() => {
    return subscribeToasts((toast) => {
      const id = nextId++
      setItems((prev) => [...prev, { id, ...toast }])
      window.setTimeout(() => {
        setItems((prev) => prev.filter((item) => item.id !== id))
      }, 6000)
    })
  }, [])

  if (items.length === 0) return null

  return (
    <div className="pointer-events-none fixed top-4 right-4 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          role="status"
          className="pointer-events-auto rounded-lg border border-destructive/40 bg-popover px-3 py-2 text-popover-foreground shadow-lg"
        >
          <p className="text-sm font-medium text-destructive">{item.title}</p>
          {item.description && (
            <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}
