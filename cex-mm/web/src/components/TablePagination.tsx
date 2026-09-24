import { Button } from '@/components/ui/button'

export const POSITIONS_PAGE_SIZE = 10

type Props = {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function TablePagination({ page, totalPages, onPageChange }: Props) {
  return (
    <div className="mt-4 flex items-center justify-end gap-3">
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </Button>
      <span className="text-sm tabular-nums text-muted-foreground">
        {page} / {totalPages}
      </span>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </div>
  )
}

/** Clamp page into [1, totalPages] given a row count. */
export function pageCount(rowCount: number, pageSize = POSITIONS_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(rowCount / pageSize))
}

export function slicePage<T>(
  rows: T[],
  page: number,
  pageSize = POSITIONS_PAGE_SIZE,
): T[] {
  const total = pageCount(rows.length, pageSize)
  const safe = Math.min(Math.max(1, page), total)
  const start = (safe - 1) * pageSize
  return rows.slice(start, start + pageSize)
}
