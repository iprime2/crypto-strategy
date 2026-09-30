type Tone = 'error' | 'success'

type ToastInput = {
  title: string
  description?: string
  tone: Tone
}

type Listener = (toast: ToastInput) => void

const listeners = new Set<Listener>()

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

function emit(toast: ToastInput) {
  for (const listener of listeners) listener(toast)
}

export function toastError(title: string, description?: string): void {
  emit({ title, description, tone: 'error' })
}

export function toastSuccess(title: string, description?: string): void {
  emit({ title, description, tone: 'success' })
}
