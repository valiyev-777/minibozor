import * as Primitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

export const Dialog = Primitive.Root
export const DialogClose = Primitive.Close

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
      <Primitive.Overlay className="fixed inset-0 z-40 bg-ink/30 backdrop-blur-[2px]" />
      <Primitive.Content
        className={cn(
          "fixed top-1/2 left-1/2 z-50 flex max-h-[90vh] w-[min(94vw,32rem)] " +
            "-translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border " +
            "border-line bg-surface shadow-2xl outline-none",
          className,
        )}
      >
        <header className="flex items-start justify-between gap-3 px-5 pt-5 pb-3">
          <div className="min-w-0">
            <Primitive.Title className="text-[18px] font-semibold text-ink">
              {title}
            </Primitive.Title>
            {description ? (
              <Primitive.Description className="mt-1 text-[14px] text-ink-soft">
                {description}
              </Primitive.Description>
            ) : null}
          </div>
          <Primitive.Close
            className="rounded-lg p-1.5 text-ink-faint hover:bg-line-soft hover:text-ink"
            aria-label="Yopish"
          >
            <X className="size-5" />
          </Primitive.Close>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-1">{children}</div>
        {footer ? (
          <footer className="flex items-center justify-end gap-2 px-5 py-4">{footer}</footer>
        ) : null}
      </Primitive.Content>
    </Primitive.Portal>
  )
}
