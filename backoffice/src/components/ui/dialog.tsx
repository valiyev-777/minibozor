import * as React from "react"
import * as Primitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export const Dialog = Primitive.Root
export const DialogTrigger = Primitive.Trigger

export function DialogPanel({
  className,
  title,
  description,
  children,
  footer,
}: {
  className?: string
  title: React.ReactNode
  description?: React.ReactNode
  children?: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <Primitive.Portal>
      <Primitive.Overlay className="fixed inset-0 z-40 bg-ink/25 backdrop-blur-[1px]" />
      <Primitive.Content
        className={cn(
          "fixed top-1/2 left-1/2 z-50 flex max-h-[88vh] w-[min(94vw,44rem)] " +
            "-translate-x-1/2 -translate-y-1/2 flex-col rounded-lg border " +
            "border-line bg-surface shadow-xl outline-none",
          className,
        )}
      >
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0">
            <Primitive.Title className="truncate text-[14px] font-semibold text-ink">
              {title}
            </Primitive.Title>
            {description ? (
              <Primitive.Description className="mt-0.5 text-[12px] text-ink-soft">
                {description}
              </Primitive.Description>
            ) : null}
          </div>
          <Primitive.Close
            className="rounded p-1 text-ink-faint hover:bg-line-soft hover:text-ink"
            aria-label="Yopish"
          >
            <X className="size-4" />
          </Primitive.Close>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">{children}</div>
        {footer ? (
          <footer className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
            {footer}
          </footer>
        ) : null}
      </Primitive.Content>
    </Primitive.Portal>
  )
}

export const DialogClose = Primitive.Close
