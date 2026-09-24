type ToastInput = {
  title: string
  description?: string
}

type Listener = (toast: ToastInput) => void

const listeners = new Set<Listener>()

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function toastError(title: string, description?: string): void {
  const toast = { title, description }
  for (const listener of listeners) listener(toast)
}
