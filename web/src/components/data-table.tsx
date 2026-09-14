/**
 * The list screen, as one object.
 *
 * ------------------------------------------------------------------- why
 *
 * Every screen in this app that shows rows was being written from scratch:
 * its own search box, its own filter row, its own idea of what an empty list
 * says, its own pagination or — more often — none at all, and its own answer
 * to what happens when a cell is null. Eleven lists, no two of them the same
 * object, and the family resemblance the owner is asking for is *mostly this
 * one component*. A back office is a set of tables; if the tables match,
 * the application matches.
 *
 * So a page is a list of columns and nothing else. Everything that is the
 * same on every list — the toolbar, the row number, the stripes, the empty
 * state, the skeleton, the pager — lives here, once.
 *
 * ------------------------------------------------------------------- the card
 *
 * Toolbar, filter drawer, rows and pager are **one card**, not four stacked
 * ones. A search box floating above a table in its own panel is two objects
 * where there is one thing: a list you are looking through.
 *
 * ------------------------------------------------------------------- the URL
 *
 * The page, the page size, the query, the sort and every filter live in the
 * query string. Not a preference — it is what makes a filtered list
 * something one person can send another. "The three orders that are stuck"
 * is a link; without this it is a sentence describing where to click.
 *
 * ------------------------------------------------------------------- actions
 *
 * A list screen's primary action goes in `afterSearch`, on the toolbar's
 * right end — **not** in the `PageHeader`. On a table screen the header is
 * the page's name and the toolbar is where the work is; a button sixty
 * pixels above the thing it adds a row to is a button in the wrong place.
 */

import { Download, Filter as FilterGlyph, Search, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { Empty, Problem, type Tone } from "@/components/page"
import { cn } from "@/lib/cn"
import { groups } from "@/lib/format"

/* --------------------------------------------------------------- the columns */

export type Column<T> = {
  /** Stable name — also the sort key sent to the server. */
  key: string
  header: React.ReactNode
  /** The cell. Return `null` and the table writes an em dash. */
  cell: (row: T, index: number) => React.ReactNode
  align?: "start" | "center" | "end"
  /** A column of figures: right-aligned and tabular, always. */
  numeric?: boolean
  /** A CSS width. `"1%"` for a column that should shrink to its content. */
  width?: string
  /** What this column writes into an export, when the cell is not text. */
  export?: (row: T) => React.ReactNode
  /** A column of pictures or buttons: nothing to export. */
  hideExport?: boolean
  className?: string
  /** Sortable, by `key`, through the URL. */
  sortable?: boolean
  /** How this row sorts locally, when the table is not server-paginated. */
  sortValue?: (row: T) => string | number
}

/** A field in the filter drawer. Declarative, because a filter row written
 *  by hand is a filter row that drifts from the next screen's. */
export type Filter =
  | { key: string; label: string; kind: "text"; placeholder?: string }
  | {
      key: string
      label: string
      kind: "select"
      options: Array<{ value: string; label: string }>
      placeholder?: string
    }
  | {
      key: string
      label: string
      kind: "custom"
      render: (value: string, set: (next: string) => void) => React.ReactNode
    }

/* ------------------------------------------------------------- the URL state */

const PAGE_SIZES = [10, 20, 50, 100]

export type TableState = ReturnType<typeof useTableState>

/**
 * Everything about *which* rows, kept in the query string.
 *
 * A page calls this to build its request; the table calls it to draw the
 * controls. They agree because neither of them holds the state — the address
 * bar does.
 */
export function useTableState(namespace?: string) {
  const [params, setParams] = useSearchParams()
  const at = (name: string) => (namespace ? `${namespace}_${name}` : name)

  const read = (name: string) => params.get(at(name)) ?? ""
  const patch = (changes: Record<string, string | number | null>) => {
    const next = new URLSearchParams(params)
    for (const [name, value] of Object.entries(changes)) {
      if (value === null || value === "") next.delete(at(name))
      else next.set(at(name), String(value))
    }
    setParams(next, { replace: true })
  }

  const size = Number(read("size")) || PAGE_SIZES[1]
  const page = Math.max(1, Number(read("page")) || 1)

  return {
    namespace,
    q: read("q"),
    page,
    size,
    sort: read("sort"),
    /** `asc` unless it says otherwise. */
    direction: read("dir") === "desc" ? ("desc" as const) : ("asc" as const),
    filter: (key: string) => params.get(at(key)) ?? "",
    /** Every filter that is set, for a request body. */
    filters: (keys: string[]) =>
      Object.fromEntries(
        keys.map((key) => [key, params.get(at(key)) ?? ""]).filter(([, v]) => v),
      ) as Record<string, string>,

    // A new query or a new filter puts you back on page one. Staying on page
    // seven of a list that now has two pages shows an empty table and reads
    // as "nothing matched".
    setQ: (value: string) => patch({ q: value, page: null }),
    setPage: (value: number) => patch({ page: value <= 1 ? null : value }),
    setSize: (value: number) => patch({ size: value, page: null }),
    setFilter: (key: string, value: string) => patch({ [key]: value, page: null }),
    setSort: (key: string, dir: "asc" | "desc") => patch({ sort: key, dir }),
    clearFilters: (keys: string[]) =>
      patch({ ...Object.fromEntries(keys.map((key) => [key, null])), page: null }),
  }
}

/* ------------------------------------------------------------------ the table */

export type Indicator<T> = {
  /** The colour of this row's bar, or `null` for no bar. */
  of: (row: T) => Tone | null
  /** What the colours mean, drawn beside the pager. */
  legend: Array<{ tone: Tone; label: string }>
}

const BAR: Record<Tone, string> = {
  neutral: "bg-line",
  good: "bg-good",
  warn: "bg-warn",
  danger: "bg-danger",
  brand: "bg-brand",
}

const RING: Record<Tone, string> = {
  neutral: "border-line",
  good: "border-good",
  warn: "border-warn",
  danger: "border-danger",
  brand: "border-brand",
}

export function DataTable<T>({
  title,
  rows,
  columns,
  rowKey,
  total,
  count,
  loading = false,
  error,
  onRowClick,
  filters = [],
  beforeSearch,
  afterSearch,
  searchPlaceholder = "Qidirish",
  empty,
  indicator,
  namespace,
  search,
  searchable = true,
  exportable = true,
  className,
}: {
  title: string
  rows: T[]
  columns: Array<Column<T>>
  rowKey: (row: T, index: number) => React.Key
  /** How many records there are in all. Given it, the caller is paging on
   *  the server and this table slices nothing. Omitted, the table searches,
   *  sorts and pages the rows it was handed. */
  total?: number
  /** The line under the title. `(n) => "12 ta xodim"`. */
  count?: (n: number) => string
  loading?: boolean
  error?: unknown
  onRowClick?: (row: T) => void
  filters?: Filter[]
  beforeSearch?: React.ReactNode
  afterSearch?: React.ReactNode
  searchPlaceholder?: string
  /** What this particular list says when it has nothing in it. */
  empty: {
    icon?: React.ComponentType<{ className?: string }>
    title: string
    what: string
  }
  indicator?: Indicator<T>
  /** A prefix for the query-string keys, for two tables on one screen. */
  namespace?: string
  /** The text a local search looks in. Only used when `total` is omitted. */
  search?: (row: T) => string
  /**
   * Whether this list can be searched at all.
   *
   * True for every list a person would type into, and it is the default — but
   * the stock ledger cannot be: the server takes a variant, a kind and a page
   * and has no free-text door, and the rows on screen are one page of
   * thousands, so searching them locally would answer about the page rather
   * than about the ledger. A box that looks like a search and answers the
   * wrong question is worse than no box, so that table says so here.
   */
  searchable?: boolean
  /** A list nobody would take away from the screen — a pick queue, a shelf. */
  exportable?: boolean
  className?: string
}) {
  const state = useTableState(namespace)
  const [drawer, setDrawer] = useState(false)
  const field = useRef<HTMLInputElement | null>(null)
  const [typed, setTyped] = useState(state.q)

  // `s`, the way the rail's own search is `/`. A one-letter shortcut is only
  // safe because it stands down the moment the caret is in any field — and
  // it is printed on the control, which is the only reason anybody presses
  // a shortcut they were never told about.
  useEffect(() => {
    // And it stands down entirely on a list with nothing to type into, or
    // pressing `s` on the ledger would swallow the letter and focus nothing.
    if (!searchable) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "s" || event.metaKey || event.ctrlKey || event.altKey) return
      const tag = (document.activeElement?.tagName ?? "").toLowerCase()
      if (tag === "input" || tag === "textarea" || tag === "select") return
      event.preventDefault()
      field.current?.focus()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [searchable])

  // The URL is the truth, but a field that round-trips through it on every
  // keystroke loses characters on a slow render. The field holds the letters
  // and hands them over a beat later.
  useEffect(() => setTyped(state.q), [state.q])
  useEffect(() => {
    if (typed === state.q) return
    const id = setTimeout(() => state.setQ(typed), 250)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typed])

  const filterKeys = useMemo(() => filters.map((one) => one.key), [filters])
  const serverPaged = total !== undefined

  // Local search, sort and paging, for the lists whose endpoint hands over
  // everything it has — which, today, is most of them.
  const shown = useMemo(() => {
    if (serverPaged) return rows
    const needle = state.q.trim().toLowerCase()
    let out = needle && search
      ? rows.filter((row) => search(row).toLowerCase().includes(needle))
      : rows.slice()
    const column = columns.find((one) => one.key === state.sort)
    if (column?.sortValue) {
      const sign = state.direction === "desc" ? -1 : 1
      out = out.sort((a, b) => {
        const left = column.sortValue!(a)
        const right = column.sortValue!(b)
        return left === right ? 0 : (left < right ? -1 : 1) * sign
      })
    }
    return out
  }, [rows, serverPaged, state.q, state.sort, state.direction, columns, search])

  const records = total ?? shown.length
  const page = shown.slice(
    serverPaged ? 0 : (state.page - 1) * state.size,
    serverPaged ? undefined : state.page * state.size,
  )
  const first = (state.page - 1) * state.size

  const body = columns
  const span = body.length + 1 + (indicator ? 1 : 0)

  return (
    <section
      className={cn(
        "rounded-panel border border-panel-edge bg-surface p-4",
        className,
      )}
    >
      {/* ---------------------------------------------------------- toolbar */}
      <div className="no-print flex min-h-11 flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-small font-semibold tracking-tight">{title}</h2>
          <p className="truncate text-micro text-ink-soft">
            {loading
              ? "Yuklanmoqda"
              : (count?.(records) ?? `${groups(records)} ta yozuv`)}
          </p>
        </div>

        <div className="flex flex-1 flex-wrap items-center justify-end gap-3">
          {beforeSearch}

          {filters.length > 0 ? (
            <>
              {drawer ? (
                <button
                  type="button"
                  onClick={() => {
                    state.clearFilters(filterKeys)
                    setDrawer(false)
                  }}
                  className="inline-flex h-control shrink-0 items-center gap-2 rounded-control bg-warn-soft px-3 text-small font-medium text-warn-ink transition-colors hover:brightness-95"
                >
                  <X className="size-4" />
                  Tozalash
                </button>
              ) : null}
              <FilterToggle open={drawer} onToggle={() => setDrawer((was) => !was)} />
            </>
          ) : null}

          {searchable ? (
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
            <input
              ref={field}
              type="search"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className={cn(
                "h-control w-56 rounded-control border border-transparent bg-line-soft ps-9 pe-11 text-small text-ink",
                "outline-none transition-[background-color,border-color,box-shadow]",
                "placeholder:text-ink-faint",
                "focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/25",
                "[&::-webkit-search-cancel-button]:hidden",
              )}
            />
            <kbd
              aria-hidden
              className={cn(
                "pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded-[4px]",
                "border border-line bg-surface px-1.5 py-0.5 text-micro font-medium text-ink-faint",
                "transition-opacity",
                typed ? "opacity-0" : "opacity-100",
              )}
            >
              S
            </kbd>
          </div>
          ) : null}

          {/* Every list can leave the screen. The boilerplate puts this on
              each table and so does this one — once, here, rather than as a
              thing each screen remembers. */}
          {exportable && records > 0 ? (
            <button
              type="button"
              onClick={() => download(title, shown, columns)}
              title="Ko'rinib turgan ro'yxatni yuklab olish"
              className="inline-flex h-control shrink-0 items-center gap-2 rounded-control bg-good-soft px-3 text-small font-medium text-good transition-colors hover:brightness-95"
            >
              <Download className="size-4" />
              Yuklab olish
            </button>
          ) : null}

          {afterSearch}
        </div>
      </div>

      {/* ----------------------------------------------------- filter drawer */}
      {filters.length > 0 ? (
        <div
          className={cn(
            "no-print grid transition-[grid-template-rows] duration-200 ease-out",
            drawer ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
          )}
        >
          <div className="overflow-hidden">
            <div
              aria-hidden={!drawer}
              className="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 rounded-control bg-line-soft p-4 sm:grid-cols-2 lg:grid-cols-4"
            >
              {filters.map((one) => (
                <label key={one.key} className="block min-w-0">
                  <span className="mb-1 block text-micro font-medium text-ink-soft">
                    {one.label}
                  </span>
                  <FilterField
                    filter={one}
                    value={state.filter(one.key)}
                    onChange={(next) => state.setFilter(one.key, next)}
                    disabled={!drawer}
                  />
                </label>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="mt-4">
          <Problem error={error} />
        </div>
      ) : null}

      {/* ------------------------------------------------------------- rows */}
      <div className="scroll-slim mt-4 overflow-x-auto">
        <table className="table-striped w-full border-collapse text-small">
          <thead>
            <tr
              className={cn(
                "bg-line-soft text-micro font-medium text-ink-soft",
                // The header is a band inside the card, not a lid on it: its
                // outer corners are the control radius so it sits in the
                // padding rather than butting up against nothing.
                "[&>th:first-child]:rounded-s-control [&>th:last-child]:rounded-e-control",
              )}
            >
              {indicator ? <th className="w-1 px-0" /> : null}
              <th className="w-1 whitespace-nowrap px-2 py-2.5 text-center font-medium">
                №
              </th>
              {body.map((column) => (
                <th
                  key={column.key}
                  style={column.width ? { width: column.width } : undefined}
                  className={cn(
                    "whitespace-nowrap px-4 py-2.5 font-medium",
                    column.numeric || column.align === "end"
                      ? "text-right"
                      : column.align === "center"
                        ? "text-center"
                        : "text-left",
                  )}
                >
                  {column.sortable ? (
                    <button
                      type="button"
                      onClick={() =>
                        state.setSort(
                          column.key,
                          state.sort === column.key && state.direction === "asc"
                            ? "desc"
                            : "asc",
                        )
                      }
                      className={cn(
                        "inline-flex items-center gap-1 transition-colors hover:text-ink",
                        state.sort === column.key && "text-brand",
                      )}
                    >
                      {column.header}
                      <span aria-hidden className="text-micro">
                        {state.sort === column.key
                          ? state.direction === "asc"
                            ? "↑"
                            : "↓"
                          : "↕"}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {loading ? (
              <Skeleton columns={body.length + (indicator ? 1 : 0)} />
            ) : page.length === 0 ? (
              // Not a row: the stripe and the hover belong to records, and
              // a tinted band behind an empty state reads as one grey row.
              <tr className="bg-surface!">
                <td colSpan={span}>
                  <Empty
                    bare
                    icon={empty.icon}
                    title={empty.title}
                    what={empty.what}
                  />
                </td>
              </tr>
            ) : (
              page.map((row, at) => (
                // A row that opens a panel is reachable from the keyboard, and
                // that is not only for whoever cannot use a mouse: a panel
                // opened from an element that cannot hold focus has nowhere to
                // put focus back when it closes, so `Esc` out of a customer
                // used to drop the caret on `<body>` and the next `Tab`
                // started again at the top of the rail.
                <tr
                  key={rowKey(row, at)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onKeyDown={
                    onRowClick
                      ? (event) => {
                          if (event.key !== "Enter" && event.key !== " ") return
                          if (event.target !== event.currentTarget) return
                          event.preventDefault()
                          onRowClick(row)
                        }
                      : undefined
                  }
                  className={cn(
                    "transition-colors",
                    onRowClick &&
                      "cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
                  )}
                >
                  {indicator ? (
                    <td className="w-1 px-0 align-middle">
                      <Bar tone={indicator.of(row)} />
                    </td>
                  ) : null}
                  <td className="w-1 whitespace-nowrap px-2 py-cell text-center text-ink-soft tabular">
                    {first + at + 1}.
                  </td>
                  {body.map((column) => {
                    const value = column.cell(row, first + at)
                    return (
                      <td
                        key={column.key}
                        className={cn(
                          "px-4 py-cell align-middle",
                          column.numeric && "text-right tabular",
                          !column.numeric && column.align === "end" && "text-right",
                          column.align === "center" && "text-center",
                          column.className,
                        )}
                      >
                        {value === null || value === undefined || value === "" ? (
                          <span className="text-ink-faint">—</span>
                        ) : (
                          value
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* -------------------------------------------------- legend and pager */}
      {(indicator && page.length > 0) || (!loading && state.size < records) ? (
        <div className="no-print mt-4 flex flex-wrap items-center justify-between gap-3">
          {indicator && page.length > 0 ? (
            <ul className="flex flex-wrap items-center gap-4" aria-label="Ranglar">
              {indicator.legend.map((one) => (
                <li key={one.label} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={cn(
                      "size-4 shrink-0 rounded-full border-[3px] bg-surface",
                      RING[one.tone],
                    )}
                  />
                  <span className="text-micro font-medium">{one.label}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span />
          )}
          <Pager
            page={state.page}
            size={state.size}
            total={records}
            onPage={state.setPage}
            onSize={state.setSize}
          />
        </div>
      ) : null}
    </section>
  )
}

/* --------------------------------------------------------------- the pieces */

/** The row's colour, as a 4px bar rounded away from the edge it grows from. */
function Bar({ tone }: { tone: Tone | null }) {
  if (!tone) return null
  return (
    <span
      aria-hidden
      className={cn("block h-8 w-1 rounded-e-full", BAR[tone])}
      role="presentation"
    />
  )
}

/**
 * Funnel into cross, because it is one button in two states rather than two
 * buttons. A glyph that swaps instantly reads as the toolbar redrawing; a
 * quarter-second crossfade reads as the same control turning over.
 */
function FilterToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-label={open ? "Saralashni yopish" : "Saralash"}
      className={cn(
        "grid size-control shrink-0 place-items-center rounded-control transition-colors",
        open
          ? "bg-brand/20 text-brand"
          : "bg-line-soft text-ink-soft hover:bg-line hover:text-ink",
      )}
    >
      <span className="relative block size-5">
        <FilterGlyph
          className={cn(
            "absolute inset-0 size-5 transition-all duration-[250ms] ease-in-out",
            open ? "rotate-90 scale-50 opacity-0" : "rotate-0 scale-100 opacity-100",
          )}
        />
        <X
          className={cn(
            "absolute inset-0 size-5 transition-all duration-[250ms] ease-in-out",
            open ? "rotate-0 scale-100 opacity-100" : "-rotate-90 scale-50 opacity-0",
          )}
        />
      </span>
    </button>
  )
}

const FIELD = [
  "h-control w-full min-w-0 rounded-control border border-line bg-surface px-3 text-small text-ink",
  "outline-none transition-[border-color,box-shadow]",
  "placeholder:text-ink-faint focus:border-brand focus:ring-2 focus:ring-brand/25",
].join(" ")

function FilterField({
  filter,
  value,
  onChange,
  disabled,
}: {
  filter: Filter
  value: string
  onChange: (next: string) => void
  disabled: boolean
}) {
  if (filter.kind === "custom") return <>{filter.render(value, onChange)}</>
  if (filter.kind === "select") {
    return (
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={FIELD}
      >
        <option value="">{filter.placeholder ?? "Hammasi"}</option>
        {filter.options.map((one) => (
          <option key={one.value} value={one.value}>
            {one.label}
          </option>
        ))}
      </select>
    )
  }
  return (
    <input
      type="text"
      value={value}
      disabled={disabled}
      placeholder={filter.placeholder}
      onChange={(event) => onChange(event.target.value)}
      className={FIELD}
    />
  )
}

/**
 * Waiting, drawn as the table that is coming.
 *
 * A spinner in the middle of a card says "something is happening"; a
 * skeleton with the real column headers above it says *what* is happening,
 * and the page does not jump when the rows land because the shape was
 * already right.
 */
function Skeleton({ columns }: { columns: number }) {
  return (
    <>
      {Array.from({ length: 8 }).map((_, row) => (
        <tr key={row}>
          <td className="px-2 py-cell">
            <span className="block h-4 w-4 animate-pulse rounded-control bg-line-soft" />
          </td>
          {Array.from({ length: columns }).map((__, cell) => (
            <td key={cell} className="px-4 py-cell">
              <span
                className="block h-4 animate-pulse rounded-control bg-line-soft"
                style={{ width: `${45 + ((row * 7 + cell * 13) % 50)}%` }}
              />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}

/**
 * The pager, and it **disappears** when there is nothing to page.
 *
 * Twelve rows under a row of page buttons that all do nothing is furniture
 * pretending to be a control. The size chooser is on the left, away from the
 * numbers, because "how many" and "which" are different questions and side
 * by side they get confused for each other.
 */
function Pager({
  page,
  size,
  total,
  onPage,
  onSize,
}: {
  page: number
  size: number
  total: number
  onPage: (next: number) => void
  onSize: (next: number) => void
}) {
  const last = Math.max(1, Math.ceil(total / size))
  if (size >= total) return null

  const steps = pages(page, last)

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <label className="flex items-center gap-2 text-micro text-ink-soft">
        Ko'rsatish
        <select
          value={size}
          onChange={(event) => onSize(Number(event.target.value))}
          className="h-control-sm rounded-control border border-line bg-surface px-2 text-micro text-ink outline-none focus:border-brand"
        >
          {PAGE_SIZES.map((one) => (
            <option key={one} value={one}>
              {one}
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-center gap-1">
        <Step label="‹" title="Oldingi" disabled={page <= 1} onClick={() => onPage(page - 1)} />
        {steps.map((step, at) =>
          step === null ? (
            <span key={`gap-${at}`} className="px-1 text-micro text-ink-faint">
              …
            </span>
          ) : (
            <Step
              key={step}
              label={String(step)}
              on={step === page}
              onClick={() => onPage(step)}
            />
          ),
        )}
        <Step
          label="›"
          title="Keyingi"
          disabled={page >= last}
          onClick={() => onPage(page + 1)}
        />
      </div>
    </div>
  )
}

function Step({
  label,
  title,
  on = false,
  disabled = false,
  onClick,
}: {
  label: string
  title?: string
  on?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-current={on ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "grid size-control-sm place-items-center rounded-control text-micro tabular transition-colors",
        on
          ? "bg-brand font-semibold text-brand-ink"
          : "text-ink-soft hover:bg-line-soft hover:text-ink",
        disabled && "pointer-events-none opacity-40",
      )}
    >
      {label}
    </button>
  )
}

/** First, last, and a window round where you are. `null` is an ellipsis. */
function pages(page: number, last: number): Array<number | null> {
  if (last <= 7) return Array.from({ length: last }, (_, at) => at + 1)
  const out: Array<number | null> = [1]
  const from = Math.max(2, page - 1)
  const to = Math.min(last - 1, page + 1)
  if (from > 2) out.push(null)
  for (let at = from; at <= to; at += 1) out.push(at)
  if (to < last - 1) out.push(null)
  out.push(last)
  return out
}

/* ------------------------------------------------------------------ export */

/**
 * The rows on screen, as a file.
 *
 * **What is exported is what is displayed** — the same columns, in the same
 * order, filtered and sorted the same way. An export that quietly hands back
 * the unfiltered table is how somebody sends a supplier a list of everything.
 *
 * The text comes out of the *cells*, not out of the data: a cell that renders
 * "Qora / 42" from two fields should export "Qora / 42" and not make the
 * reader reassemble it. Cells are React nodes, so the tree is walked for its
 * strings; a column whose cell is a picture or a button gives an empty
 * string, which is the honest answer for a column that has no text in it.
 *
 * CSV with a semicolon and a byte-order mark: that is the pair Excel opens
 * into columns on a machine set to Uzbek or Russian, where a comma is a
 * decimal point. `utf-8` alone gives one column of mojibake.
 */
function text(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return ""
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(text).join(" ")
  if (typeof node === "object" && "props" in (node as { props?: unknown })) {
    const props = (node as { props?: { children?: React.ReactNode } }).props
    return text(props?.children)
  }
  return ""
}

function download<T>(name: string, rows: T[], columns: Column<T>[]) {
  const wanted = columns.filter((column) => !column.hideExport)
  const lines = [
    wanted.map((column) => text(column.header)),
    ...rows.map((row, index) =>
      wanted.map((column) => text(column.export?.(row) ?? column.cell(row, index))),
    ),
  ]
  const csv = lines
    .map((line) =>
      line
        .map((cell) => {
          const clean = cell.replace(/\s+/g, " ").trim()
          return /[";\n]/.test(clean) ? `"${clean.replace(/"/g, '""')}"` : clean
        })
        .join(";"),
    )
    .join("\r\n")

  const stamp = new Date().toISOString().slice(0, 10)
  const file = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(file)
  const link = document.createElement("a")
  link.href = url
  link.download = `${name} ${stamp}.csv`.replace(/[\\/:*?"<>|]/g, "-")
  link.click()
  URL.revokeObjectURL(url)
}
