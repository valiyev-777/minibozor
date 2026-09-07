import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { FulfilmentTariff } from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Hint } from "@/components/ui/field"
import { money } from "@/lib/utils"

/**
 * The weight bands, and the two rates each one carries.
 *
 * Read-only, because the API is: `GET /staff/payouts/tariffs` is the only
 * door on to this table and there is no write endpoint behind it. A form that
 * looked editable and could not save would be worse than a table that says
 * what the rates are — see the README for the gap.
 *
 * Worth reading beside a statement. The two rates are the whole reason a
 * marketplace needs more than a commission: one follows what a thing is
 * worth, these follow how big it is. A pair of earphones and a washing
 * machine cost the same percentage and nothing like the same to move or hold.
 */
export function Tariffs() {
  const query = useQuery({
    queryKey: ["staff", "payouts", "tariffs"],
    queryFn: () => api<FulfilmentTariff[]>("/staff/payouts/tariffs"),
  })

  const columns: Column<FulfilmentTariff>[] = [
    {
      key: "band",
      header: "Og'irlik guruhi",
      sortValue: (row) => row.max_grams,
      cell: (row) => (
        <>
          <span className="block font-medium text-ink">{row.label}</span>
          <span className="tabular block text-[12px] text-ink-faint">
            {row.max_grams >= 1_000_000
              ? "yuqori chegarasiz"
              : `${money(row.max_grams)} g gacha`}
          </span>
        </>
      ),
    },
    {
      key: "fee",
      header: "Yig'ish-yetkazish",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.fee,
      cell: (row) => (
        <>
          <span className="block text-ink">{money(row.fee)}</span>
          <span className="block text-[12px] text-ink-faint">jo'natma uchun</span>
        </>
      ),
    },
    {
      key: "storage",
      header: "Saqlash",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.storage_per_day,
      cell: (row) => (
        <>
          <span className="block text-ink">{money(row.storage_per_day)}</span>
          <span className="block text-[12px] text-ink-faint">dona-kun uchun</span>
        </>
      ),
    },
    {
      key: "month",
      header: "Oyiga (30 kun)",
      headClassName: "text-right",
      className: "text-right tabular text-ink-soft",
      sortValue: (row) => row.storage_per_day,
      // The figure a seller actually feels: a daily rate is unreadable until
      // it is a month of one unit on a shelf.
      cell: (row) => money(row.storage_per_day * 30),
    },
  ]

  return (
    <DataTable
      rows={query.data}
      columns={columns}
      rowKey={(row) => row.id}
      loading={query.isPending}
      error={query.error}
      onRetry={() => void query.refetch()}
      emptyTitle="Tarif belgilanmagan"
      emptyHint="Guruh yo'q bo'lsa yig'ish haqi olinmaydi — server belgilanmagan haqni undirmaydi."
      toolbar={
        <Hint>
          Faqat ko'rish: bu jadvalni tahrirlash endpointi hozircha yo'q.
          Guruh — tovarning og'irligi bo'yicha, narxidan qat'i nazar. Mahsulot
          og'irligi ko'rsatilmagan bo'lsa 1 kg guruhi qo'llanadi.
        </Hint>
      }
    />
  )
}
