import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Role, StaffUser, StaffUserPage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Input, Select } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { useFilter } from "@/lib/useFilter"
import { date } from "@/lib/format"
import { roleName, t } from "@/lib/labels"

/**
 * Who works here, and what they may do.
 *
 * A role is the whole of the difference between a picker and an operator, so
 * this is the most privileged screen in the panel — and the note beside the
 * change is required by the server for that reason: a privilege change is the
 * kind of thing somebody asks about months later, and "who made me an
 * operator, and why" should have an answer that is not a shrug.
 *
 * Searching by the digits alone is enough, because an admin has the number in
 * front of them rather than a directory.
 */
const ROLES: readonly Role[] = [
  "customer",
  "operator",
  "warehouse",
  "courier",
  "seller",
  "admin",
]

const TONE: Partial<Record<Role, "brand" | "good" | "warn" | "neutral">> = {
  admin: "brand",
  operator: "good",
  warehouse: "good",
  courier: "warn",
  seller: "warn",
}

export function UsersPage() {
  // The needle lives in the URL so a search survives opening a row and
  // coming back; `typed` is the box, which should not fire a request per
  // keystroke against a fifty-row page.
  const [q, setQ] = useFilter<string>("q", "")
  const [typed, setTyped] = React.useState<string>(q)

  const users = useQuery({
    queryKey: ["users", q],
    queryFn: () =>
      api<StaffUserPage>("/staff/users", {
        query: { page_size: 50, ...(q ? { q } : {}) },
      }),
  })

  return (
    <>
      <PageTitle
        action={
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              setQ(typed)
            }}
          >
            <Input
              aria-label={t.search}
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder="900040001"
              className="w-48"
            />
            <Button type="submit">{t.search}</Button>
          </form>
        }
      >
        {t.users}
      </PageTitle>

      <Panel>
        <Async
          query={users}
          lines={6}
          empty={<Empty title={t.usersEmpty} />}
        >
          {(page) =>
            page.items.length === 0 ? (
              <Empty title={t.usersEmpty} hint="Boshqa raqam bilan qidirib ko'ring." />
            ) : (
              <>
                {page.items.map((user) => (
                  <UserRow key={user.id} user={user} />
                ))}
              </>
            )
          }
        </Async>
      </Panel>
    </>
  )
}

function UserRow({ user }: { user: StaffUser }) {
  const [role, setRole] = React.useState<Role>(user.role)
  const [note, setNote] = React.useState("")

  const change = useAction<void, StaffUser>({
    run: () =>
      api<StaffUser>(`/staff/users/${user.id}/role`, {
        method: "PATCH",
        json: { role, note: note.trim() },
      }),
    invalidate: [["users"]],
    success: t.roleChanged,
    onDone: () => setNote(""),
  })

  const changed = role !== user.role

  return (
    <Row className="sm:flex-nowrap">
      <div className="min-w-0 flex-1">
        <p className="truncate text-ink">{user.full_name || "—"}</p>
        <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
          {user.phone} · {date(user.created_at)}
        </p>
      </div>
      <Badge tone={TONE[user.role] ?? "neutral"}>
        {roleName[user.role] ?? user.role}
      </Badge>
      <Select
        aria-label={`${user.phone} ${t.role}`}
        className="w-40"
        value={role}
        onChange={(event) => setRole(event.target.value as Role)}
      >
        {ROLES.map((option) => (
          <option key={option} value={option}>
            {roleName[option] ?? option}
          </option>
        ))}
      </Select>
      {changed ? (
        <>
          <Input
            aria-label={t.roleNote}
            className="w-40"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t.roleNote}
          />
          <Button
            size="sm"
            variant="primary"
            disabled={change.isPending}
            onClick={() => change.mutate()}
          >
            {t.save}
          </Button>
        </>
      ) : (
        <span className="w-40" />
      )}
    </Row>
  )
}
