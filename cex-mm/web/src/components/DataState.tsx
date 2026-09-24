import type { ReactNode } from 'react'
import { AlertCircleIcon } from 'lucide-react'
import { Alert, AlertAction, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

type Props = {
  loading: boolean
  error: string | null
  empty: boolean
  emptyMessage?: string
  onRetry: () => void
  children: ReactNode
}

export function DataState({
  loading,
  error,
  empty,
  emptyMessage = 'No data yet',
  onRetry,
  children,
}: Props) {
  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Loading">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-4 w-56" />
      </div>
    )
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircleIcon />
        <AlertTitle>Request failed</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
        <AlertAction>
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </AlertAction>
      </Alert>
    )
  }
  if (empty) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>
  }
  return <>{children}</>
}
