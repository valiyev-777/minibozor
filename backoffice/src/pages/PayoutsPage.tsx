import * as React from "react"
import { useNavigate } from "react-router-dom"
import { Page } from "@/components/Layout"
import { Tabs } from "@/components/ui/tabs"
import { Periods } from "@/pages/payout/Periods"
import { Statements } from "@/pages/payout/Statements"
import { Tariffs } from "@/pages/payout/Tariffs"

/**
 * Money out: the runs, the accounts, and what the fees are.
 *
 * Three tables in one area rather than three sidebar rows, the way the
 * showcase and the catalogue are arranged. One account's detail is a screen
 * of its own — it is reached from a row and it is long — and lives at
 * `/payouts/statements/:id`.
 *
 * Picking a period on the Periods tab carries the filter over to Statements,
 * because "generate the run, then look at what it produced" is the one path
 * anybody walks here.
 */
type Tab = "periods" | "statements" | "tariffs"

export function PayoutsPage() {
  const navigate = useNavigate()
  const [tab, setTab] = React.useState<Tab>("periods")
  const [periodId, setPeriodId] = React.useState<number | null>(null)

  return (
    <Page
      title="Moliya"
      hint="Har bir raqam kimgadir to'lanadigan pul. Summalar so'mda, butun son — yumaloqlanmaydi."
    >
      <div className="mb-3">
        <Tabs
          value={tab}
          onChange={setTab}
          items={[
            { value: "periods", label: "Davrlar" },
            { value: "statements", label: "Hisobotlar" },
            { value: "tariffs", label: "Tariflar" },
          ]}
        />
      </div>

      {tab === "periods" ? (
        <Periods
          onOpenPeriod={(id) => {
            setPeriodId(id)
            setTab("statements")
          }}
        />
      ) : null}
      {tab === "statements" ? (
        <Statements
          periodId={periodId}
          onPeriodChange={setPeriodId}
          onOpen={(id) => navigate(`/payouts/statements/${id}`)}
        />
      ) : null}
      {tab === "tariffs" ? <Tariffs /> : null}
    </Page>
  )
}
