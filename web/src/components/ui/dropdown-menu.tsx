/**
 * The menu that drops out of the top bar.
 *
 * Sized and coloured like every other surface in the system — `rounded-panel`,
 * `shadow-raised`, a `border-line` hairline — rather than like shadcn's
 * defaults, so an open menu is recognisably the same material as the card it
 * is floating over. Items are `h-control-sm` so a menu of four does not
 * become a column half the height of the screen at courier density.
 */

import { DropdownMenu as Primitive } from "radix-ui"
import { CheckIcon, ChevronRightIcon } from "lucide-react"

import { cn } from "@/lib/cn"

const DropdownMenu = Primitive.Root
const DropdownMenuTrigger = Primitive.Trigger
const DropdownMenuGroup = Primitive.Group
const DropdownMenuSub = Primitive.Sub

function DropdownMenuContent({
  className,
  sideOffset = 8,
  ...props
}: React.ComponentProps<typeof Primitive.Content>) {
  return (
    <Primitive.Portal>
      <Primitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-56 overflow-hidden rounded-panel border border-line bg-surface p-1 text-ink shadow-raised",
          "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          className,
        )}
        {...props}
      />
    </Primitive.Portal>
  )
}

function DropdownMenuSubTrigger({
  className,
  children,
  ...props
}: React.ComponentProps<typeof Primitive.SubTrigger>) {
  return (
    <Primitive.SubTrigger
      className={cn(
        "flex h-control-sm cursor-default select-none items-center gap-2 rounded-control px-2 text-small outline-none",
        "data-[state=open]:bg-line-soft focus:bg-line-soft",
        "[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-ink-faint",
        className,
      )}
      {...props}
    >
      {children}
      <ChevronRightIcon className="ml-auto" />
    </Primitive.SubTrigger>
  )
}

function DropdownMenuSubContent({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.SubContent>) {
  return (
    <Primitive.Portal>
      <Primitive.SubContent
        className={cn(
          "z-50 min-w-44 overflow-hidden rounded-panel border border-line bg-surface p-1 text-ink shadow-raised",
          className,
        )}
        {...props}
      />
    </Primitive.Portal>
  )
}

function DropdownMenuItem({
  className,
  tone = "neutral",
  ...props
}: React.ComponentProps<typeof Primitive.Item> & {
  /** `danger` for the one item somebody has to mean — signing out, deleting. */
  tone?: "neutral" | "danger"
}) {
  return (
    <Primitive.Item
      className={cn(
        "flex h-control-sm cursor-default select-none items-center gap-2 rounded-control px-2 text-small outline-none",
        "focus:bg-line-soft data-[disabled]:pointer-events-none data-[disabled]:opacity-45",
        "[&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-ink-faint",
        tone === "danger" &&
          "text-danger focus:bg-danger-soft [&_svg]:text-danger",
        className,
      )}
      {...props}
    />
  )
}

/** An item that shows which of a set is the current one — the theme, say. */
function DropdownMenuCheckItem({
  className,
  checked,
  children,
  ...props
}: React.ComponentProps<typeof Primitive.Item> & { checked?: boolean }) {
  return (
    <DropdownMenuItem className={className} {...props}>
      {children}
      {checked ? <CheckIcon className="ml-auto text-brand!" /> : null}
    </DropdownMenuItem>
  )
}

function DropdownMenuLabel({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Label>) {
  return (
    <Primitive.Label
      className={cn("px-2 py-1.5 text-micro font-medium text-ink-faint", className)}
      {...props}
    />
  )
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof Primitive.Separator>) {
  return (
    <Primitive.Separator
      className={cn("-mx-1 my-1 h-px bg-line", className)}
      {...props}
    />
  )
}

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuCheckItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
}
