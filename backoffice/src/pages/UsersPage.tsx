import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Search, ShieldAlert } from "lucide-react"
import { api } from "@/api/client"
import type { StaffUser, StaffUserPage, UserRole } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { useSession } from "@/auth/session"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { ROLE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "users"]
const PAGE_SIZE = 25

const ROLES: UserRole[] = ["customer", "operator", "warehouse", "courier", "seller", "admin"]

const FILTERS: { value: "" | UserRole; label: string }[] = [
  { value: "", label: "Hammasi" },
  ...ROLES.map((role) => ({ value: role, label: ROLE[role] })),
]

const TONE: Record<UserRole, "neutral" | "brand" | "good" | "warn" | "danger"> = {
  customer: "neutral",
  operator: "brand",
  warehouse: "brand",
  courier: "brand",
  seller: "warn",
  admin: "danger",
}

export function UsersPage() {
  const session = useSession()
  const me = session.status === "signed-in" ? session.user : null

  const [term, setTerm] = React.useState("")
  const [query_, setQuery] = React.useState("")
  const [role, setRole] = React.useState<"" | UserRole>("")
  const [page, setPage] = React.useState(1)
  const [changing, setChanging] = React.useState<StaffUser | null>(null)

  const query = useQuery({
    queryKey: [...KEY, query_, role, page],
    queryFn: () =>
      api<StaffUserPage>("/staff/users", {
        query: { q: query_, role, page, page_size: PAGE_SIZE },
      }),
  })

  function search(event: React.FormEvent) {
    event.preventDefault()
    setPage(1)
    setQuery(term.trim())
  }

  const columns: Column<StaffUser>[] = [
    {
      key: "phone",
      header: "Telefon",
      cell: (row) => (
        <span className="tabular font-medium text-ink">
          {row.phone}
          {row.id === me?.id ? <span className="ml-1.5 text-ink-faint">(siz)</span> : null}
        </span>
      ),
    },
    {
      key: "name",
      header: "Ism",
      cell: (row) => (
        <span className="block max-w-56 truncate text-ink-soft">{row.full_name || "—"}</span>
      ),
    },
    {
      key: "role",
      header: "Rol",
      cell: (row) => <Badge tone={TONE[row.role]}>{ROLE[row.role]}</Badge>,
    },
    {
      key: "active",
      header: "Hisob",
      cell: (row) =>
        row.is_active ? (
          <span className="text-ink-soft">Faol</span>
        ) : (
          <span className="font-medium text-danger">O'chirilgan</span>
        ),
    },
    {
      key: "created",
      header: "Ro'yxatdan o'tgan",
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <Button size="sm" onClick={() => setChanging(row)}>
          Rolni o'zgartirish
        </Button>
      ),
    },
  ]

  return (
    <Page
      title="Foydalanuvchilar va rollar"
      hint="Rol — yagona farq. Xodim ham mijoz kabi bir xil SMS orqali kiradi."
    >
      <DataTable
        rows={query.data?.items}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle={query_ ? "Bunday raqam topilmadi" : "Hech kim yo'q"}
        emptyHint={
          query_
            ? "Raqamning oxirgi bir necha xonasi ham yetadi — masalan 9001."
            : undefined
        }
        server={{
          page: query.data?.page ?? page,
          pageSize: query.data?.page_size ?? PAGE_SIZE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
        }}
        toolbar={
          <>
            <form onSubmit={search} className="flex items-center gap-1.5">
              <Label htmlFor="user-q" className="sr-only">
                Telefon bo'yicha qidirish
              </Label>
              <Input
                id="user-q"
                className="w-56"
                value={term}
                placeholder="Telefon yoki ism"
                onChange={(event) => setTerm(event.target.value)}
              />
              <Button size="sm" type="submit">
                <Search />
                Qidirish
              </Button>
            </form>
            <div className="flex items-center gap-1.5">
              <Label htmlFor="user-role">Rol</Label>
              <Select
                id="user-role"
                className="w-40"
                value={role}
                onChange={(event) => {
                  setPage(1)
                  setRole(event.target.value as "" | UserRole)
                }}
              >
                {FILTERS.map((filter) => (
                  <option key={filter.value} value={filter.value}>
                    {filter.label}
                  </option>
                ))}
              </Select>
            </div>
            <Hint>{query.data?.total ?? 0} ta hisob</Hint>
          </>
        }
      />

      {changing ? (
        <ChangeRole
          user={changing}
          isMe={changing.id === me?.id}
          onClose={() => setChanging(null)}
        />
      ) : null}
    </Page>
  )
}

function ChangeRole({
  user,
  isMe,
  onClose,
}: {
  user: StaffUser
  isMe: boolean
  onClose: () => void
}) {
  const session = useSession()
  const [role, setRole] = React.useState<UserRole>(user.role)
  const [note, setNote] = React.useState("")

  const change = useAction<void, StaffUser>({
    run: () =>
      api<StaffUser>(`/staff/users/${user.id}/role`, {
        method: "PATCH",
        json: { role, note: note.trim() },
      }),
    invalidate: [KEY, ["staff", "sellers"]],
    success: (row) => `${row.phone} — ${ROLE[row.role]}`,
    onDone: (row) => {
      onClose()
      // An admin who has just demoted themselves is looking at a panel they
      // may no longer be allowed in. Reloading is how they find out now,
      // rather than at the next request that 403s under them.
      if (isMe && row.role !== "admin") window.location.reload()
    },
  })

  // The rule the backend holds and the one place it is worth warning about
  // before the request: an admin standing themselves down. Whether they are
  // the *last* admin is the server's to know — it answers 409 with the
  // explanation, and that sentence is shown as it comes.
  const demotingSelf = isMe && user.role === "admin" && role !== "admin"

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Rolni o'zgartirish"
      description={`${user.phone}${user.full_name ? ` · ${user.full_name}` : ""}`}
      confirmLabel="O'zgartirish"
      destructive={demotingSelf}
      disabled={role === user.role}
      pending={change.isPending}
      onConfirm={() => change.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="role">Rol</Label>
          <Select
            id="role"
            autoFocus
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole)}
          >
            {ROLES.map((value) => (
              <option key={value} value={value}>
                {ROLE[value]}
              </option>
            ))}
          </Select>
          <Hint>
            Hozir: {ROLE[user.role]}. Sotuvchi roli hisobni sotuvchiga biriktirmaydi —
            buni «Sotuvchilar» ekranidagi bog'lash qiladi.
          </Hint>
        </div>

        <div className="space-y-1">
          <Label htmlFor="role-note">Sabab (ixtiyoriy)</Label>
          <Input
            id="role-note"
            value={note}
            placeholder="yangi smena · TKT-4410"
            onChange={(event) => setNote(event.target.value)}
          />
          <Hint>
            Har bir rol o'zgarishi audit jurnaliga tushadi — kim, qachon va nimadan
            nimaga. Sabab — bir yildan keyin o'sha yozuvni o'qishga arziydigan qiladi.
          </Hint>
        </div>

        {demotingSelf ? (
          <div className="flex gap-2 rounded border border-danger/30 bg-danger-soft px-2.5 py-2">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-danger" />
            <div className="space-y-1">
              <p className="text-[13px] font-medium text-danger">
                Siz o'zingizning admin rolingizni tushirmoqchisiz.
              </p>
              <p className="text-[12px] text-ink-soft">
                Rolni faqat admin beradi. Agar siz oxirgi admin bo'lsangiz server
                409 bilan rad etadi va sababni aytadi. Boshqa admin bo'lsa — o'tadi,
                lekin bu paneldan chiqib ketasiz va rolni faqat o'sha admin qaytara
                oladi.
              </p>
              <p className="text-[12px] text-ink-faint">
                Hozir kirgan: {session.status === "signed-in" ? session.user.phone : "—"}
              </p>
            </div>
          </div>
        ) : null}
      </div>
    </ConfirmDialog>
  )
}
