import * as React from "react"
import { cn } from "@/lib/utils"

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn("block text-[12px] font-medium text-ink-soft", className)}
      {...props}
    />
  )
}

const box =
  "w-full rounded border border-line bg-surface px-2 py-1.5 text-[13px] text-ink " +
  "placeholder:text-ink-faint outline-none focus:border-accent focus:ring-2 " +
  "focus:ring-accent/25 disabled:bg-line-soft disabled:text-ink-faint"

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(box, className)} {...props} />
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(box, "min-h-16 resize-y", className)} {...props} />
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(box, "pr-6", className)} {...props} />
}

export function Hint({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-[12px] text-ink-faint", className)} {...props} />
}

export function FieldError({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <p className="text-[12px] font-medium text-danger">{children}</p>
}
