import * as React from "react"
import { ScanLine } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

/**
 * The input a barcode scanner types into.
 *
 * A scanner is a keyboard that types very fast and presses Enter. So there is
 * no scanner API to integrate — there is only one requirement, and it is that
 * the caret is already in the right place when the trigger is pulled. Somebody
 * holding a scanner in one hand and a box in the other is not going to click
 * into a field first, and a scan that lands on the page instead of in the
 * field is a line silently not counted.
 *
 * So this takes the focus and keeps taking it back: on blur, on a click
 * anywhere else, and when the window comes forward again.
 */
export function ScanInput({
  onScan,
  label = "Skanerlang",
  hint,
  disabled,
}: {
  onScan: (code: string) => void
  label?: string
  hint?: React.ReactNode
  disabled?: boolean
}) {
  const field = React.useRef<HTMLInputElement>(null)
  const [value, setValue] = React.useState("")

  const grab = React.useCallback(() => {
    if (!disabled) field.current?.focus()
  }, [disabled])

  React.useEffect(() => {
    grab()
    window.addEventListener("focus", grab)
    return () => window.removeEventListener("focus", grab)
  }, [grab])

  return (
    <div
      className="rounded-lg border-2 border-brand/40 bg-brand-soft/60 p-3"
      // Clicking the panel — or fumbling near it with a glove on — puts the
      // caret back rather than taking it away.
      onMouseDown={(event) => {
        if (event.target !== field.current) {
          event.preventDefault()
          grab()
        }
      }}
    >
      <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-brand">
        <ScanLine className="size-4" />
        {label}
      </label>
      <input
        ref={field}
        value={value}
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
        // A scanner ends with Enter, which is the whole protocol.
        onKeyDown={(event) => {
          if (event.key !== "Enter") return
          event.preventDefault()
          const code = value.trim()
          setValue("")
          if (code) onScan(code)
        }}
        onChange={(event) => setValue(event.target.value)}
        onBlur={() => window.setTimeout(grab, 0)}
        className={cn(
          "w-full rounded border-2 border-line bg-surface px-3 py-2.5 font-mono",
          "text-[17px] tracking-wide text-ink outline-none",
          "focus:border-brand focus:ring-4 focus:ring-brand/20",
          "disabled:bg-line-soft disabled:text-ink-faint",
        )}
        placeholder="SKU yoki kod"
      />
      {hint ? <p className="mt-1.5 text-[12px] text-ink-soft">{hint}</p> : null}
    </div>
  )
}

/**
 * A quantity a gloved thumb can drive.
 *
 * Two big targets and a field wide enough to read across a warehouse aisle.
 * The keyboard is numeric, because typing a letter into a count is never what
 * was meant.
 */
export function CountStepper({
  value,
  onChange,
  max,
  autoFocus,
}: {
  value: number
  onChange: (next: number) => void
  max?: number
  autoFocus?: boolean
}) {
  const clamp = (next: number) => Math.max(0, max === undefined ? next : Math.min(next, max))
  return (
    <div className="flex items-stretch gap-1">
      <Button
        type="button"
        size="lg"
        variant="outline"
        className="w-11 shrink-0 text-[18px]"
        aria-label="Kamaytirish"
        onClick={() => onChange(clamp(value - 1))}
      >
        −
      </Button>
      <input
        inputMode="numeric"
        pattern="[0-9]*"
        autoFocus={autoFocus}
        value={String(value)}
        onChange={(event) => onChange(clamp(Number(event.target.value.replace(/\D/g, "")) || 0))}
        onFocus={(event) => event.target.select()}
        className={cn(
          "tabular w-16 rounded border border-line bg-surface text-center",
          "text-[17px] font-semibold text-ink outline-none",
          "focus:border-brand focus:ring-2 focus:ring-brand/25",
        )}
      />
      <Button
        type="button"
        size="lg"
        variant="outline"
        className="w-11 shrink-0 text-[18px]"
        aria-label="Ko'paytirish"
        disabled={max !== undefined && value >= max}
        onClick={() => onChange(clamp(value + 1))}
      >
        +
      </Button>
    </div>
  )
}
