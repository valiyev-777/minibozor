import * as React from "react"
import { cn } from "@/lib/utils"

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label className={cn("block text-[14px] font-medium text-ink", className)} {...props} />
  )
}

const box =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-[15px] text-ink " +
  "placeholder:text-ink-faint outline-none focus:border-brand focus:ring-2 " +
  "focus:ring-brand/20 disabled:bg-line-soft disabled:text-ink-faint"

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(box, className)} {...props} />
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(box, "min-h-20 resize-y", className)} {...props} />
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(box, "pr-8", className)} {...props} />
}

export function Hint({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-[13px] text-ink-soft", className)} {...props} />
}

export function FieldError({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <p className="text-[13px] font-medium text-danger">{children}</p>
}
