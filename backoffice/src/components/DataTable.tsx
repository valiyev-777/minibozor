import * as React from "react"
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Empty, Failed } from "@/ui/states"
import { cn } from "@/lib/utils"

/**
 * The one table.
 *
 * Four more panels are coming — warehouse, admin, seller, and a courier app —
 * and they all show lists of the same kind. So sorting, paging, the empty
 * state and the loading state are settled here once, and a page contributes
 * only its columns.
 *
 * Paging comes in two shapes because the API does: `/staff/orders` answers
 * with a `Page`, and the returns, reviews and slots queues answer with plain
 * lists. Pass `server` for the first and nothing for the second.
 */
export type Column<T> = {
  key: string
  header: React.ReactNode
  cell: (row: T) => React.ReactNode
  /** Present makes the column sortable, and says what to sort on. */
  sortValue?: (row: T) => string | number
  className?: string
  headClassName?: string
}

export type ServerPaging = {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

type Props<T> = {
  rows: T[] | undefined
  columns: Column<T>[]
  rowKey: (row: T) => React.Key
  loading?: boolean
  error?: unknown
  onRetry?: () => void
  onRowClick?: (row: T) => void
  emptyTitle?: string
  emptyHint?: string
  /** What to do about the emptiness. A screen with nothing and no next step
   *  leaves the reader to guess whether it is broken or simply empty. */
  emptyAction?: React.ReactNode
  server?: ServerPaging
  clientPageSize?: number
  /** Rendered under the header row — a filter bar, usually. */
  toolbar?: React.ReactNode
}

const CLIENT_PAGE_SIZE = 25

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  loading,
  error,
  onRetry,
  onRowClick,
  emptyTitle = "Hech narsa yo'q",
  emptyHint,
  emptyAction,
  server,
  clientPageSize = CLIENT_PAGE_SIZE,
  toolbar,
}: Props<T>) {
  const [sort, setSort] = React.useState<{ key: string; desc: boolean } | null>(null)
  const [clientPage, setClientPage] = React.useState(1)

  const sorted = React.useMemo(() => {
    if (!rows || !sort) return rows ?? []
    const column = columns.find((c) => c.key === sort.key)
    if (!column?.sortValue) return rows
    const read = column.sortValue
    return [...rows].sort((a, b) => {
      const left = read(a)
      const right = read(b)
      const order = left === right ? 0 : left < right ? -1 : 1
      return sort.desc ? -order : order
    })
  }, [rows, sort, columns])

  // Sorting or filtering under a reader who is on page three is disorienting.
  React.useEffect(() => setClientPage(1), [sort, rows?.length])

  const paged = server
    ? sorted
    : sorted.slice((clientPage - 1) * clientPageSize, clientPage * clientPageSize)

  const total = server?.total ?? sorted.length
  const page = server?.page ?? clientPage
  const pageSize = server?.pageSize ?? clientPageSize
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const goto = server?.onPageChange ?? setClientPage

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface">
      {toolbar ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
          {toolbar}
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line bg-line-soft/60">
              {columns.map((column) => {
                const sortable = Boolean(column.sortValue)
                const active = sort?.key === column.key
                return (
                  <th
                    key={column.key}
                    className={cn(
                      "px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-soft",
                      column.headClassName,
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() =>
                          setSort(
                            active
                              ? { key: column.key, desc: !sort.desc }
                              : { key: column.key, desc: false },
                          )
                        }
                        className="inline-flex items-center gap-1 hover:text-ink"
                      >
                        {column.header}
                        {active ? (
                          sort.desc ? (
                            <ArrowDown className="size-3" />
                          ) : (
                            <ArrowUp className="size-3" />
                          )
                        ) : null}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {loading && !rows
              ? Array.from({ length: 6 }, (_, i) => (
                  <tr key={i} className="border-b border-line-soft">
                    {columns.map((column) => (
                      <td key={column.key} className="px-3 py-2.5">
                        <span className="block h-3 w-full max-w-40 animate-pulse rounded bg-line" />
                      </td>
                    ))}
                  </tr>
                ))
              : paged.map((row) => (
                  <tr
                    key={rowKey(row)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    // A clickable row has to be reachable without a mouse.
                    // It was a bare `<tr onClick>`: no tab stop, no keyboard
                    // handler and no announced role, so every dialog behind a
                    // row — the shelf reading, a statement, an order — was
                    // unreachable from the keyboard. `Enter` and `Space` both,
                    // because a row is being used as a button and that is what
                    // a button answers to.
                    {...(onRowClick
                      ? {
                          tabIndex: 0,
                          role: "button" as const,
                          onKeyDown: (event: React.KeyboardEvent) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault()
                              onRowClick(row)
                            }
                          },
                        }
                      : {})}
                    className={cn(
                      "border-b border-line-soft last:border-0",
                      onRowClick &&
                        "cursor-pointer hover:bg-brand-soft/50 " +
                          "focus-visible:outline-2 focus-visible:-outline-offset-2 " +
                          "focus-visible:outline-brand",
                    )}
                  >
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        className={cn("px-3 py-2 align-middle", column.className)}
                      >
                        {column.cell(row)}
                      </td>
                    ))}
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {/* One failure and one emptiness, shared with the seller cabinet and the
          courier app — this table used to draw its own, slightly differently.
          `emptyAction` is the slot that stops an empty screen being a dead
          end: whoever is looking at it either wants the filter off or wants
          the button that makes the first row. */}
      {error ? <Failed error={error} {...(onRetry ? { onRetry } : {})} /> : null}

      {!loading && !error && rows && rows.length === 0 ? (
        <Empty
          title={emptyTitle}
          {...(emptyHint ? { hint: emptyHint } : {})}
          {...(emptyAction ? { action: emptyAction } : {})}
        />
      ) : null}

      {total > pageSize ? (
        <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2">
          <p className="tabular text-[12px] text-ink-soft">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} / {total}
          </p>
          <div className="flex items-center gap-1">
            <Button
              size="icon"
              disabled={page <= 1}
              onClick={() => goto(page - 1)}
              aria-label="Oldingi"
            >
              <ChevronLeft />
            </Button>
            <span className="tabular px-1 text-[12px] text-ink-soft">
              {page} / {pages}
            </span>
            <Button
              size="icon"
              disabled={page >= pages}
              onClick={() => goto(page + 1)}
              aria-label="Keyingi"
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
