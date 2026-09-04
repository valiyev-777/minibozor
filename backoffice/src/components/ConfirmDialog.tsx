import * as React from "react"
import { Dialog, DialogClose, DialogPanel } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"

/**
 * The one confirmation.
 *
 * Anything irreversible goes through this: a refusal the customer will read, a
 * refund, a status that cannot be walked back. `children` is where a decision
 * puts its own fields — a reason, a restock choice — so there is one dialog
 * rather than one per verb.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Tasdiqlash",
  destructive,
  disabled,
  pending,
  onConfirm,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  description?: React.ReactNode
  confirmLabel?: string
  destructive?: boolean
  disabled?: boolean
  pending?: boolean
  onConfirm: () => void
  children?: React.ReactNode
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPanel
        className="w-[min(94vw,30rem)]"
        title={title}
        description={description}
        footer={
          <>
            <DialogClose asChild>
              <Button size="sm" variant="ghost">
                Bekor qilish
              </Button>
            </DialogClose>
            <Button
              size="sm"
              variant={destructive ? "danger" : "primary"}
              disabled={disabled || pending}
              onClick={onConfirm}
            >
              {pending ? "Yuborilmoqda…" : confirmLabel}
            </Button>
          </>
        }
      >
        {children}
      </DialogPanel>
    </Dialog>
  )
}
