import * as React from "react"
import { Plus } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { SellerAdmin } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { date, num } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * Taking a seller on, and standing one down.
 *
 * Two rows in the database and one form: a `sellers` row for the shop, and the
 * `users` row it is linked to by telephone number. Linking by phone rather
 * than by picking from a list of accounts is deliberate — the admin has the
 * number in front of them on a piece of paper, and the account may not exist
 * yet.
 *
 * Standing a seller down is a switch and not a delete. Their offers come off
 * the shop with them and their statements stay: a shop that stopped trading
 * still sold what it sold, and deleting the row would take a settlement's own
 * history with it.
 */
export function SellersPage() {
  const sellers = useQuery({
    queryKey: ["sellers"],
    queryFn: () => api<SellerAdmin[]>("/staff/sellers"),
  })

  const toggle = useAction<{ id: number; active: boolean }, SellerAdmin>({
    run: ({ id, active }) =>
      api<SellerAdmin>(`/staff/sellers/${id}`, { method: "PATCH", json: { active } }),
    invalidate: [["sellers"]],
    success: t.sellerSaved,
  })

  return (
    <>
      <PageTitle action={<NewSeller />}>{t.sellers}</PageTitle>

      <Panel>
        <div className="hidden border-b border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
          <span className="flex-1">{t.name}</span>
          <span className="w-40">{t.linkedAccount}</span>
          <span className="w-20 text-right">{t.commission}</span>
          <span className="w-20 text-right">Takliflar</span>
          <span className="w-28">{t.active}</span>
        </div>
        <Async
          query={sellers}
          lines={5}
          empty={<Empty title={t.sellersEmpty} hint="Yangi sotuvchi qo'shing." />}
        >
          {(rows) => (
            <>
              {rows.map((seller) => (
                <Row key={seller.id} className="sm:flex-nowrap">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{seller.name}</p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {seller.phone} · {date(seller.created_at)}
                    </p>
                  </div>
                  <div className="w-40 min-w-0">
                    <p className="truncate text-[length:var(--text-small)] text-ink">
                      {seller.user_name || "—"}
                    </p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {seller.user_phone || "bog'lanmagan"}
                    </p>
                  </div>
                  <span className="tabular w-20 text-right text-ink">
                    {seller.commission_percent}%
                  </span>
                  <span className="tabular w-20 text-right text-ink-soft">
                    {num(seller.offer_count)}
                  </span>
                  <div className="flex w-28 items-center gap-2">
                    <Badge tone={seller.active ? "good" : "neutral"}>
                      {seller.active ? t.active : t.standDown}
                    </Badge>
                    <Button
                      size="sm"
                      variant={seller.active ? "quiet" : "outline"}
                      disabled={toggle.isPending}
                      onClick={() =>
                        toggle.mutate({ id: seller.id, active: !seller.active })
                      }
                    >
                      {seller.active ? t.standDown : t.reinstate}
                    </Button>
                  </div>
                </Row>
              ))}
            </>
          )}
        </Async>
      </Panel>
    </>
  )
}

function NewSeller() {
  const [open, setOpen] = React.useState(false)
  const [name, setName] = React.useState("")
  const [phone, setPhone] = React.useState("")
  const [userPhone, setUserPhone] = React.useState("")
  const [commission, setCommission] = React.useState("5")

  const create = useAction<void, SellerAdmin>({
    run: () =>
      api<SellerAdmin>("/staff/sellers", {
        method: "POST",
        json: {
          name: name.trim(),
          phone: phone.trim(),
          commission_percent: Number(commission) || 0,
          ...(userPhone.trim() ? { user_phone: userPhone.trim() } : {}),
        },
      }),
    invalidate: [["sellers"]],
    success: t.sellerCreated,
    onDone: () => {
      setOpen(false)
      setName("")
      setPhone("")
      setUserPhone("")
    },
  })

  if (!open) {
    return (
      <Button variant="primary" size="sm" onClick={() => setOpen(true)}>
        <Plus />
        {t.newSeller}
      </Button>
    )
  }

  return (
    <form
      className="w-full space-y-3 rounded-[var(--radius-panel)] border border-line bg-surface p-4"
      onSubmit={(event) => {
        event.preventDefault()
        create.mutate()
      }}
    >
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1.5">
          <Label htmlFor="seller-name">{t.name}</Label>
          <Input
            id="seller-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Chorsu Bozori"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seller-phone">{t.phone}</Label>
          <Input
            id="seller-phone"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            placeholder="+998781112233"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seller-user">{t.linkedAccount}</Label>
          <Input
            id="seller-user"
            value={userPhone}
            onChange={(event) => setUserPhone(event.target.value)}
            placeholder="+998900000005"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seller-commission">{t.commission}</Label>
          <Input
            id="seller-commission"
            inputMode="numeric"
            value={commission}
            onChange={(event) => setCommission(event.target.value.replace(/\D/g, ""))}
          />
        </div>
      </div>
      {/* Linking the account is what lets somebody sign in to the cabinet. A
          shop with no account behind it is a shop nobody can open, which is a
          legitimate state — an admin taking on a seller before they have a
          telephone number for them — so it is optional here. */}
      <Hint>
        Bog'langan hisob — sotuvchi kabinetiga kiradigan telefon raqami. Keyin ham
        qo'shish mumkin.
      </Hint>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={!name.trim() || create.isPending}>
          {t.add}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          {t.back}
        </Button>
      </div>
    </form>
  )
}
