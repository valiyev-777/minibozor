/**
 * §5.4 — Do'konga chiqarish: three gates, one button, at the top of the form.
 *
 * Ported out of `products.tsx`, where it had grown as a panel of its own with
 * its own copies of the filing and the pricing controls. Two copies of a form
 * that writes the same fields disagree about what a card is by the third
 * change, and the form under this panel already holds both — so the gates
 * here **say what is missing and point at it**, and the correction is made in
 * the section the pointer names.
 *
 * **The rule is the server's.** `card.unready` is the list, and the browser
 * branches on the key only to pick which section to scroll to. It keeps
 * neither the rule nor the wording: a gate added on the server appears here
 * without a deploy, as its own words.
 *
 * **The panel stays on a card that made it.** It used to be drawn only while
 * the card was held back, so pressing *Chiqarish* made the whole panel vanish
 * and nothing said the card had arrived — which a person meeting this screen
 * for the first time reads as an error. It is one panel with three faces
 * instead: the gates while the card is held back, `✓ Do'konda sotuvda` with
 * the gates still ticked once it is in the shop, and `Arxivda` with the way
 * back when somebody has filed it away. The archived face exists because the
 * alternative was three green ticks over a dead button.
 *
 * **And it is the one home of *Sotuvdan olish*.** Taking a card out of the
 * shop is the opposite of the act this panel exists for, so it lives in this
 * panel and nowhere else — and it sends the card to `draft`, which is what
 * "take it off sale" means. Archiving is a different and heavier act, and it
 * is in the catalogue's `⋯` menu with a confirmation on it.
 */

import { Check, Loader2, Undo2, X } from "lucide-react"

import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { money } from "@/lib/format"
import { useCategories, usePublish } from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

/** Which section of the form answers which gate — the jump target. */
const ANSWERED_BY: Record<string, string> = {
  needs_category: "card-form-category",
  needs_price: "card-form-price",
  needs_photo: "card-form-photos",
}

export function GatePanel({
  card,
  /** Which colours have a photograph — the gate's ✓ and ✗, and nothing else. */
  photographed,
  colours,
  publish,
  dirty = false,
  onPublish,
}: {
  card: AdminProduct
  photographed: Set<string>
  colours: string[]
  publish: ReturnType<typeof usePublish>
  /** The form is holding words nobody has saved yet. Publishing saves them
   *  first — see `onPublish` — and the button says so. */
  dirty?: boolean
  /** Save whatever the form is holding, then put the card in the shop. The
   *  sequence is the form's because only the form knows what is unsaved. */
  onPublish: () => void
}) {
  const categories = useCategories()

  const gate = new Set(card.unready.map((gap) => gap.key))
  const ready = gate.size === 0 && card.next_statuses.includes("active")
  const missing = card.unready.map((gap) => gap.label)

  const filedAs =
    (categories.data ?? []).find((one) => one.slug === card.category_slug)?.name ??
    card.category_slug
  const cost = card.last_cost
  // The owner's habitual markup, as a concrete figure rather than a formula —
  // rounded to the thousand the way every price here is.
  const suggested = cost > 0 ? Math.round((cost * 1.6) / 1000) * 1000 : 0

  const live = card.status === "active"
  const archived = card.status === "archived"

  // An archived card has no gates worth drawing: three green ticks over a
  // button that cannot be pressed is the screen saying "all done" about a card
  // nobody can buy. It says where the card is and how to get it back.
  if (archived) {
    return (
      <section className="rounded-panel border border-line bg-surface">
        <header className="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-small font-semibold tracking-tight">Arxivda</h2>
          <Button
            type="button"
            variant="secondary"
            className="gap-2"
            disabled={publish.isPending || !card.next_statuses.includes("draft")}
            onClick={() => publish.mutate("draft")}
          >
            {publish.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Undo2 className="size-4" />
            )}
            Arxivdan qaytarish
          </Button>
        </header>

        <div className="p-4">
          <p className="rounded-control bg-line-soft p-2 text-micro text-ink-soft">
            Bu karta arxivda — do'konda ko'rinmaydi va ro'yxatda faqat «Arxivda»
            filtrida chiqadi. Qaytarilsa «Do'konda yo'q» holatiga o'tadi, o'sha
            yerdan yana do'konga chiqariladi.
          </p>
          <Problem error={publish.error} />
        </div>
      </section>
    )
  }

  return (
    <section
      className={cn(
        "rounded-panel border bg-surface",
        live ? "border-good/40" : "border-line",
      )}
    >
      <header className="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-small font-semibold tracking-tight">
          {live ? (
            <>
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-good-soft text-good">
                <Check className="size-3.5" />
              </span>
              Do'konda sotuvda
            </>
          ) : (
            "Do'konga chiqarish"
          )}
        </h2>
        {live ? (
          // The one home of this act. It sends the card to `draft` — off sale,
          // name and words and photographs kept — and not to the archive,
          // which is somebody deliberately filing a card away.
          <Button
            type="button"
            variant="secondary"
            className="gap-2"
            disabled={publish.isPending || !card.next_statuses.includes("draft")}
            onClick={() => publish.mutate("draft")}
          >
            {publish.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Sotuvdan olish
          </Button>
        ) : (
          <Button
            type="button"
            className="gap-2"
            disabled={!ready || publish.isPending}
            onClick={onPublish}
          >
            {publish.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Check className="size-4" />
            )}
            Chiqarish
          </Button>
        )}
      </header>

      <div className="p-4">
        <div>
          <Gate
            ok={!gate.has("needs_category")}
            name="Kategoriya"
            jumpTo={ANSWERED_BY.needs_category}
            value={gate.has("needs_category") ? "tanlanmagan" : (filedAs ?? "")}
          />
          <Gate
            ok={!gate.has("needs_price")}
            name="Sotish narxi"
            jumpTo={ANSWERED_BY.needs_price}
            value={
              gate.has("needs_price")
                ? cost > 0
                  ? `tannarx ${money(cost)} · taklif +60% → ${money(suggested)}`
                  : "kiritilmagan"
                : cost > 0
                  ? `${money(card.price)} · tannarx ${money(cost)}`
                  : money(card.price)
            }
          />
          <Gate
            ok={!gate.has("needs_photo")}
            name="Rasm"
            jumpTo={ANSWERED_BY.needs_photo}
            value={(colours.length ? colours : [""])
              .map((one) => `${one || "umumiy"} ${photographed.has(one) ? "✓" : "✗"}`)
              .join(" · ")}
          />
        </div>

        {/* The button's reason, in the server's words, beside the button
            rather than in a tooltip nobody hovers on a phone. */}
        {live ? (
          <p className="mt-3 rounded-control bg-good-soft p-2 text-micro text-good">
            Karta do'konda — mijoz uni ko'radi va sotib ola oladi. «Sotuvdan
            olish» bosilsa do'kondan chiqadi, lekin yozilgani joyida qoladi.
          </p>
        ) : !ready ? (
          <p className="mt-3 rounded-control bg-warn-soft p-2 text-micro text-warn-ink">
            {missing.length
              ? `Chiqishi uchun yetishmayapti: ${missing.join(", ")}.`
              : "Bu kartani hozir sotuvga chiqarib bo'lmaydi."}
          </p>
        ) : (
          <p className="mt-3 rounded-control bg-good-soft p-2 text-micro text-good">
            Hammasi tayyor — «Chiqarish» bosilsa karta do'konda ko'rinadi.
            {dirty ? " Yozilgan so'zlar ham shunda saqlanadi." : ""}
          </p>
        )}

        <Problem error={publish.error} />
      </div>
    </section>
  )
}

/**
 * One gate: the mark, the name, the current answer, and where to go and fix it.
 *
 * It does not open a control of its own. The form under this panel has the
 * only copy of every one of these fields, and the jump is what connects the
 * complaint to the place the complaint is answered.
 */
function Gate({
  ok,
  name,
  value,
  jumpTo,
}: {
  ok: boolean
  name: string
  value: string
  jumpTo: string
}) {
  return (
    <button
      type="button"
      onClick={() =>
        document
          .getElementById(jumpTo)
          ?.scrollIntoView({ behavior: "smooth", block: "center" })
      }
      className="flex w-full items-center gap-2 border-t border-line py-2.5 text-left first:border-t-0"
    >
      <span
        className={cn(
          "grid size-5 shrink-0 place-items-center rounded-full",
          ok ? "bg-good-soft text-good" : "bg-warn-soft text-warn-ink",
        )}
      >
        {ok ? <Check className="size-3.5" /> : <X className="size-3.5" />}
      </span>
      <span className="w-28 shrink-0 text-small font-medium">{name}</span>
      <span
        className={cn(
          "min-w-0 flex-1 truncate text-small",
          ok ? "text-ink-soft" : "text-warn-ink",
        )}
      >
        {value}
      </span>
      {!ok ? (
        <span className="shrink-0 text-micro text-brand-deep">To'ldirish</span>
      ) : null}
    </button>
  )
}
