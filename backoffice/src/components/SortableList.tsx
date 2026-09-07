import * as React from "react"
import { ChevronDown, ChevronUp, GripVertical } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * Rows dragged into the order they should appear in.
 *
 * Two things about the backend shape the whole component.
 *
 * **The order goes as a whole.** `POST .../order` takes every id, and answers
 * 400 to a list that repeats a row or leaves one out — see `_reorder` in
 * `app/routers/showcase.py`. So this holds the complete order locally while
 * somebody is arranging it and sends all of it in one request, rather than a
 * request per row that could be left half applied.
 *
 * **Arranging is not saving.** Dragging changes what is on screen; the change
 * reaches the shop when Save is pressed. That way a mis-drop is undone by
 * walking away, and the banner on the home screen never spends a second in an
 * order nobody chose.
 *
 * Pointer events rather than HTML5 drag-and-drop. `draggable` + `dragstart` is
 * the obvious way to write this and it is a dead end twice over: it does
 * nothing at all under a finger, and it cannot be driven by anything that
 * synthesises mouse events — so the one interaction on this screen would be
 * the one thing no test could touch. Pointer events are one code path for
 * mouse, touch and pen, and they are ordinary events.
 *
 * Dragging is also not the only way to move a row. A list that can only be
 * rearranged by dragging cannot be rearranged with a keyboard at all, so every
 * row carries up and down buttons — the same operation, reachable by tab.
 */
export function SortableList<T>({
  rows,
  rowKey,
  renderRow,
  onOrderChange,
  disabled,
}: {
  rows: T[]
  rowKey: (row: T) => number
  renderRow: (row: T, index: number) => React.ReactNode
  onOrderChange: (ordered: T[]) => void
  disabled?: boolean
}) {
  const list = React.useRef<HTMLUListElement>(null)
  const [dragging, setDragging] = React.useState<number | null>(null)

  function moved(source: T[], from: number, to: number): T[] | null {
    if (to < 0 || to >= source.length || from === to) return null
    const next = [...source]
    const [row] = next.splice(from, 1)
    if (row === undefined) return null
    next.splice(to, 0, row)
    return next
  }

  function step(from: number, to: number) {
    const next = moved(rows, from, to)
    if (next) onOrderChange(next)
  }

  /**
   * The row the pointer is inside, by the rows' own boxes.
   *
   * Measured on every move rather than once at the start: the list reorders
   * underneath the drag, so a set of rectangles taken at `pointerdown` stops
   * describing the list after the first swap.
   */
  function indexAt(y: number): number | null {
    const items = list.current?.children
    if (!items) return null
    for (let index = 0; index < items.length; index += 1) {
      const box = items[index]?.getBoundingClientRect()
      if (box && y >= box.top && y <= box.bottom) return index
    }
    return null
  }

  function startDrag(event: React.PointerEvent<HTMLButtonElement>, index: number) {
    if (disabled) return
    event.preventDefault()
    const grip = event.currentTarget
    grip.setPointerCapture(event.pointerId)
    setDragging(index)

    // The order being arranged is held here for the length of the drag rather
    // than read back from props. Two pointermoves can arrive inside one frame,
    // and the second would otherwise read the array from before the first —
    // undoing a swap that is already on screen.
    let working = rows
    let at = index

    const move = (event_: PointerEvent) => {
      const over = indexAt(event_.clientY)
      if (over === null || over === at) return
      const next = moved(working, at, over)
      if (!next) return
      working = next
      at = over
      onOrderChange(next)
      setDragging(over)
    }
    const end = () => {
      grip.releasePointerCapture(event.pointerId)
      grip.removeEventListener("pointermove", move)
      grip.removeEventListener("pointerup", end)
      grip.removeEventListener("pointercancel", end)
      setDragging(null)
    }

    grip.addEventListener("pointermove", move)
    grip.addEventListener("pointerup", end)
    grip.addEventListener("pointercancel", end)
  }

  return (
    <ul ref={list} className="divide-y divide-line-soft">
      {rows.map((row, index) => (
        <li
          key={rowKey(row)}
          className={cn(
            "flex items-center gap-2 px-3 py-2 transition-colors",
            dragging === index && "bg-brand-soft",
          )}
        >
          <button
            type="button"
            disabled={disabled}
            aria-label="Sudrash"
            onPointerDown={(event) => startDrag(event, index)}
            className={cn(
              "shrink-0 rounded p-0.5 text-ink-faint outline-none",
              "focus-visible:ring-2 focus-visible:ring-brand/40",
              // `touch-none` is load-bearing under a finger: without it the
              // browser claims the gesture as a scroll and the row never moves.
              disabled ? "cursor-not-allowed" : "cursor-grab touch-none active:cursor-grabbing",
            )}
          >
            <GripVertical className="size-3.5" />
          </button>

          <span className="tabular w-5 shrink-0 text-[12px] text-ink-faint">{index + 1}</span>
          <div className="min-w-0 flex-1">{renderRow(row, index)}</div>

          <div className="flex shrink-0 items-center gap-0.5">
            <Button
              size="icon"
              variant="ghost"
              disabled={disabled || index === 0}
              aria-label="Yuqoriga"
              onClick={() => step(index, index - 1)}
            >
              <ChevronUp />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              disabled={disabled || index === rows.length - 1}
              aria-label="Pastga"
              onClick={() => step(index, index + 1)}
            >
              <ChevronDown />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}

/**
 * Whether an arrangement differs from the order it was loaded in.
 *
 * Save stays disabled until it does: sending an unchanged order is a write to
 * the audit trail that records nothing having happened.
 */
export function orderChanged(before: number[], after: number[]): boolean {
  return before.length !== after.length || before.some((id, index) => id !== after[index])
}
