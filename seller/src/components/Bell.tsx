import * as React from "react"
import * as Popover from "@radix-ui/react-popover"
import { Bell as BellIcon, X } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { NotificationGroup, UnreadCount } from "@/api/types"
import { Button } from "@/ui/button"
import { Async } from "@/ui/states"
import { moment } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * The bell, and the only place this panel polls.
 *
 * A seller is told things by somebody else's action — the warehouse refused a
 * batch, a parcel came back and needs a decision within the week — and none
 * of those happen while they are looking at the screen. So the count is
 * refetched on an interval; the list behind it is not, because opening the
 * popover is itself the request.
 *
 * Thirty seconds. Long enough that a cabinet left open all day is not a load
 * problem, short enough that somebody who was told by telephone to "look at
 * your notifications" does not have to reload the page.
 */
const POLL_MS = 30_000

export function Bell() {
  const [open, setOpen] = React.useState(false)
  const queryClient = useQueryClient()

  const unread = useQuery({
    queryKey: ["unread"],
    queryFn: () => api<UnreadCount>("/notifications/unread-count"),
    refetchInterval: POLL_MS,
  })

  const groups = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<NotificationGroup[]>("/notifications"),
    // Only while it is on screen. Reading them is what marks them read, so a
    // background fetch would clear the badge nobody had looked at.
    enabled: open,
  })

  const dismiss = useMutation({
    mutationFn: (id: number) => api(`/notifications/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] })
      void queryClient.invalidateQueries({ queryKey: ["unread"] })
    },
  })

  const count = unread.data?.unread ?? 0

  return (
    <Popover.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        // Reading them marks them read on the server, so the badge is asked
        // again on the way out rather than left showing what was true before.
        if (!next) void queryClient.invalidateQueries({ queryKey: ["unread"] })
      }}
    >
      <Popover.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label={t.notifications} className="relative">
          <BellIcon />
          {count > 0 ? (
            <span
              className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-danger px-1
                         text-[length:var(--text-micro)] font-semibold leading-4 text-danger-ink"
            >
              {count > 9 ? "9+" : count}
            </span>
          ) : null}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          className="z-50 w-[22rem] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-[var(--radius-panel)]
                     border border-line bg-surface shadow-lg"
        >
          <header className="px-4 py-3 text-[length:var(--text-body)] font-semibold text-ink">
            {t.notifications}
          </header>
          <div className="max-h-[26rem] overflow-y-auto">
            <Async query={groups} lines={2}>
              {(data) =>
                data.length === 0 ? (
                  <p className="border-t border-line-soft px-4 py-8 text-center text-[length:var(--text-small)] text-ink-soft">
                    {t.noNotifications}
                  </p>
                ) : (
                  <>
                    {data.map((group) => (
                      <div key={group.label}>
                        <p className="border-t border-line-soft bg-line-soft/60 px-4 py-1.5 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint">
                          {group.label}
                        </p>
                        {group.items.map((item) => (
                          <div
                            key={item.id}
                            className="flex items-start gap-2 border-t border-line-soft px-4 py-3"
                          >
                            <div className="min-w-0 flex-1 space-y-0.5">
                              <p className="text-[length:var(--text-small)] font-medium text-ink">
                                {item.title}
                              </p>
                              {item.text ? (
                                <p className="text-[length:var(--text-small)] text-ink-soft">
                                  {item.text}
                                </p>
                              ) : null}
                              <p className="text-[length:var(--text-micro)] text-ink-faint">
                                {moment(item.created_at)}
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label="O'chirish"
                              onClick={() => dismiss.mutate(item.id)}
                            >
                              <X />
                            </Button>
                          </div>
                        ))}
                      </div>
                    ))}
                  </>
                )
              }
            </Async>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
