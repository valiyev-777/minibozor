import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Link2, Plus } from "lucide-react"
import { api } from "@/api/client"
import type { AdminSeller } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "sellers"]

export function SellersPage() {
  const [creating, setCreating] = React.useState(false)
  const [editing, setEditing] = React.useState<AdminSeller | null>(null)
  const [linking, setLinking] = React.useState<AdminSeller | null>(null)
  const [standingDown, setStandingDown] = React.useState<AdminSeller | null>(null)

  const query = useQuery({
    queryKey: KEY,
    queryFn: () => api<AdminSeller[]>("/staff/sellers"),
  })

  const columns: Column<AdminSeller>[] = [
    {
      key: "name",
      header: "Sotuvchi",
      sortValue: (row) => row.name,
      cell: (row) => (
        <>
          <span className="block truncate font-medium text-ink">{row.name}</span>
          <span className="tabular block text-[12px] text-ink-faint">{row.phone || "—"}</span>
        </>
      ),
    },
    {
      key: "account",
      header: "Hisob",
      sortValue: (row) => row.user_phone ?? "",
      cell: (row) =>
        row.user_phone ? (
          <>
            <span className="block truncate text-ink">{row.user_name || "—"}</span>
            <span className="tabular block text-[12px] text-ink-faint">{row.user_phone}</span>
          </>
        ) : (
          <span className="text-ink-faint">Bog'lanmagan</span>
        ),
    },
    {
      key: "commission",
      header: "Komissiya",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.commission_percent,
      cell: (row) => `${row.commission_percent}%`,
    },
    {
      key: "offers",
      header: "Takliflar",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.offer_count,
      cell: (row) => row.offer_count,
    },
    {
      key: "active",
      header: "Holat",
      sortValue: (row) => String(row.active),
      cell: (row) =>
        row.active ? (
          <Badge tone="good">Ishlayapti</Badge>
        ) : (
          <Badge tone="neutral">To'xtatilgan</Badge>
        ),
    },
    {
      key: "created",
      header: "Qo'shilgan",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <div className="flex justify-end gap-1.5">
          <Button size="sm" onClick={() => setEditing(row)}>
            Tahrirlash
          </Button>
          {row.user_phone ? null : (
            <Button size="sm" onClick={() => setLinking(row)}>
              <Link2 />
              Hisob bog'lash
            </Button>
          )}
          {row.active ? (
            <Button size="sm" variant="quiet" onClick={() => setStandingDown(row)}>
              To'xtatish
            </Button>
          ) : (
            <ResumeButton seller={row} />
          )}
        </div>
      ),
    },
  ]

  return (
    <Page
      title="Sotuvchilar"
      hint="Katalog platformaniki: sotuvchi mavjud kartochkaga taklif qo'shadi, o'z nusxasini ochmaydi."
      actions={
        <Button variant="primary" onClick={() => setCreating(true)}>
          <Plus />
          Sotuvchi qo'shish
        </Button>
      }
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Hali sotuvchi yo'q"
        emptyHint="«Sotuvchi qo'shish» — keyin unga kirish uchun hisob bog'lanadi."
      />

      {creating ? <CreateSeller onClose={() => setCreating(false)} /> : null}
      {editing ? <EditSeller seller={editing} onClose={() => setEditing(null)} /> : null}
      {linking ? <LinkAccount seller={linking} onClose={() => setLinking(null)} /> : null}
      {standingDown ? (
        <StandDown seller={standingDown} onClose={() => setStandingDown(null)} />
      ) : null}
    </Page>
  )
}

function CreateSeller({ onClose }: { onClose: () => void }) {
  const [name, setName] = React.useState("")
  const [phone, setPhone] = React.useState("")
  const [commission, setCommission] = React.useState("10")
  const [userPhone, setUserPhone] = React.useState("")

  const create = useAction<void, AdminSeller>({
    run: () =>
      api<AdminSeller>("/staff/sellers", {
        method: "POST",
        json: {
          name: name.trim(),
          phone: phone.trim(),
          commission_percent: Number(commission) || 0,
          ...(userPhone.trim() ? { user_phone: userPhone.trim() } : {}),
        },
      }),
    invalidate: [KEY],
    success: (seller) => `${seller.name} qo'shildi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Sotuvchi qo'shish"
      confirmLabel="Qo'shish"
      disabled={!name.trim()}
      pending={create.isPending}
      onConfirm={() => create.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="seller-name">Nomi</Label>
          <Input
            id="seller-name"
            autoFocus
            value={name}
            placeholder="Chorsu Bozori"
            onChange={(event) => setName(event.target.value)}
          />
          <Hint>Nom yagona bo'lishi kerak — takrorlansa server 409 qaytaradi.</Hint>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="seller-phone">Aloqa telefoni</Label>
            <Input
              id="seller-phone"
              value={phone}
              placeholder="+998781112233"
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>
          <div className="w-32 space-y-1">
            <Label htmlFor="seller-commission">Komissiya %</Label>
            <Input
              id="seller-commission"
              type="number"
              min={0}
              max={100}
              value={commission}
              onChange={(event) => setCommission(event.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="seller-account">Kirish hisobi (ixtiyoriy)</Label>
          <Input
            id="seller-account"
            value={userPhone}
            placeholder="+998901234567"
            onChange={(event) => setUserPhone(event.target.value)}
          />
          <Hint>
            Hisob bog'lash — aynan shu odamni sotuvchiga aylantiradi: roli ham shu bilan
            beriladi. Hozir kiritilmasa, keyin ro'yxatdan bog'lanadi.
          </Hint>
        </div>
      </div>
    </ConfirmDialog>
  )
}

function EditSeller({ seller, onClose }: { seller: AdminSeller; onClose: () => void }) {
  const [name, setName] = React.useState(seller.name)
  const [phone, setPhone] = React.useState(seller.phone)
  const [commission, setCommission] = React.useState(String(seller.commission_percent))

  const save = useAction<void, AdminSeller>({
    run: () =>
      api<AdminSeller>(`/staff/sellers/${seller.id}`, {
        method: "PATCH",
        json: {
          name: name.trim(),
          phone: phone.trim(),
          commission_percent: Number(commission) || 0,
        },
      }),
    invalidate: [KEY],
    success: "Saqlandi",
    onDone: onClose,
  })

  const rate = Number(commission)

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={seller.name}
      description="Shartnoma shartlari"
      confirmLabel="Saqlash"
      disabled={!name.trim()}
      pending={save.isPending}
      onConfirm={() => save.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="edit-name">Nomi</Label>
          <Input
            id="edit-name"
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="edit-phone">Aloqa telefoni</Label>
            <Input
              id="edit-phone"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
          </div>
          <div className="w-32 space-y-1">
            <Label htmlFor="edit-commission">Komissiya %</Label>
            <Input
              id="edit-commission"
              type="number"
              min={0}
              max={100}
              value={commission}
              onChange={(event) => setCommission(event.target.value)}
            />
          </div>
        </div>
        {rate !== seller.commission_percent ? (
          <Hint>
            Stavka o'zgarishi audit jurnaliga yoziladi. Allaqachon sotilgani o'zi sotilgan
            stavkada qoladi — u raqam buyurtma qatorida saqlangan.
          </Hint>
        ) : null}
      </div>
    </ConfirmDialog>
  )
}

function LinkAccount({ seller, onClose }: { seller: AdminSeller; onClose: () => void }) {
  const [phone, setPhone] = React.useState("")

  const link = useAction<void, AdminSeller>({
    run: () =>
      api<AdminSeller>(`/staff/sellers/${seller.id}`, {
        method: "PATCH",
        json: { user_phone: phone.trim() },
      }),
    invalidate: [KEY, ["staff", "users"]],
    success: (row) => `${row.user_phone} — endi sotuvchi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Hisob bog'lash"
      description={seller.name}
      confirmLabel="Bog'lash"
      disabled={!phone.trim()}
      pending={link.isPending}
      onConfirm={() => link.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="link-phone">Telefon raqami</Label>
          <Input
            id="link-phone"
            autoFocus
            value={phone}
            placeholder="+998901234567"
            onChange={(event) => setPhone(event.target.value)}
          />
          <Hint>
            Odam avval oddiy mijoz sifatida ro'yxatdan o'tgan bo'lishi kerak — kirish
            o'sha SMS orqali, rol esa yagona farq.
          </Hint>
        </div>
        <p className="rounded border border-line bg-line-soft/60 px-2.5 py-2 text-[12px] text-ink-soft">
          Bog'lash bilan hisobning roli <span className="font-medium text-ink">sotuvchi</span>{" "}
          bo'ladi. Bu alohida qadam emas: hisob sotuvchiga biriktirilib, sotuvchi sifatida
          ishlay olmaydigan holat yo'q.
        </p>
      </div>
    </ConfirmDialog>
  )
}

function StandDown({ seller, onClose }: { seller: AdminSeller; onClose: () => void }) {
  const stop = useAction<void, AdminSeller>({
    run: () =>
      api<AdminSeller>(`/staff/sellers/${seller.id}`, {
        method: "PATCH",
        json: { active: false },
      }),
    invalidate: [KEY, ["staff", "catalog"]],
    success: `${seller.name} to'xtatildi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={`${seller.name} — to'xtatish`}
      confirmLabel="To'xtatish"
      destructive
      pending={stop.isPending}
      onConfirm={() => stop.mutate()}
    >
      <div className="space-y-2">
        {/* Not a side effect to be discovered afterwards: it is the decision. */}
        <p className="text-[13px] text-ink">
          Bu sotuvchining{" "}
          <span className="font-semibold">{seller.offer_count} ta taklifi</span> ham
          o'chiriladi — ular narx yarishida qatnashmaydi va kartochkalardagi narx qayta
          hisoblanadi.
        </p>
        <p className="text-[12px] text-ink-soft">
          Aks holda do'kondagi eng arzon kartochka biz ish to'xtatgan odamniki bo'lib
          qolardi. Qaytadan ishga tushirilganda takliflar avtomatik tiklanmaydi —
          har birini sotuvchi yoki admin qayta yoqadi.
        </p>
        <p className="text-[12px] text-ink-soft">
          Kirish hisobi va roli tegilmaydi. Odamni tizimdan chiqarish kerak bo'lsa, u
          «Foydalanuvchilar» ekranidagi alohida qaror.
        </p>
      </div>
    </ConfirmDialog>
  )
}

function ResumeButton({ seller }: { seller: AdminSeller }) {
  const resume = useAction<void, AdminSeller>({
    run: () =>
      api<AdminSeller>(`/staff/sellers/${seller.id}`, {
        method: "PATCH",
        json: { active: true },
      }),
    invalidate: [KEY],
    success: `${seller.name} qayta ishga tushdi`,
  })

  return (
    <Button size="sm" disabled={resume.isPending} onClick={() => resume.mutate()}>
      Ishga tushirish
    </Button>
  )
}
