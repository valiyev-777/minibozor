/**
 * The four things a card is made of words about, as one set of controls.
 *
 * These once lived inside a separate "Sotuvga chiqarish" screen, which meant
 * a card could be corrected exactly while it was *not* on sale — a name typed
 * wrong at the receiving desk stayed wrong for the life of the card. That
 * screen is gone; the card in "Mahsulotlar" draws these wherever it needs
 * them: the publish panel takes the filing and the price, the editor takes
 * the words and the table. One set of controls, because two copies of a form
 * that writes the same fields disagree about what a card is by the third
 * change.
 *
 * Each is its own save because each is a different kind of decision: words are
 * the shop window, a category is where a customer finds it, a price is money,
 * and the specification table is what the phone draws as a table or not at all.
 */

import { Loader2, Plus, Table2, Tags, Trash2, Wallet } from "lucide-react"
import { useEffect, useState } from "react"

import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { money } from "@/lib/format"
import {
  useCategories,
  useFileCard,
  usePriceCard,
  useProduct,
  useSpecs,
  useVocab,
  useWriteCategory,
  useWriteSpecs,
} from "@/lib/queries"
import type { AdminProduct, Spec } from "@/lib/types"

// ------------------------------------------------------------------- the words

/**
 * The name, the line under it, the prose, the guarantee.
 *
 * One form and one save, because it is one job: somebody looking at the goods
 * writing what a customer needs to read. The name matters most — a card
 * arrives from the bench called `Krossovka · Nike · Qora`, which is a warehouse
 * label and not a thing anybody searches for.
 */
export function Words({ card }: { card: AdminProduct }) {
  const detail = useProduct(card.id)
  const write = useFileCard(card.id)

  const [title, setTitle] = useState(card.title)
  const [subtitle, setSubtitle] = useState("")
  const [description, setDescription] = useState("")
  const [warranty, setWarranty] = useState("")

  // Filled once the card arrives, and not on every render: typing into a field
  // whose value is being reset underneath is the classic form that fights back.
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    if (loaded || !detail.data) return
    setTitle(detail.data.title)
    setSubtitle(detail.data.subtitle)
    setDescription(detail.data.description)
    setWarranty(detail.data.warranty ?? "")
    setLoaded(true)
  }, [detail.data, loaded])

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        write.mutate({
          title: title.trim() || card.title,
          subtitle: subtitle.trim(),
          description: description.trim(),
          warranty: warranty.trim() || null,
        })
      }}
    >
      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Nomi — mijoz shuni o'qiydi va shuni qidiradi
        </span>
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Erkaklar krossovkasi Alfa"
          aria-label="Nomi"
          className="h-control-lg text-body" />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Qisqa izoh — nom ostidagi bir qator
        </span>
        <Input
          value={subtitle}
          onChange={(event) => setSubtitle(event.target.value)}
          placeholder="Qora, yengil, kunlik"
          aria-label="Qisqa izoh"
          className="h-control" />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">Tavsif</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          placeholder="Nimadan tikilgan, kimga to'g'ri keladi, qanday parvarish qilinadi."
          aria-label="Tavsif"
          className="w-full rounded-control border bg-surface p-2 text-small" />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Kafolat — bo'lmasa bo'sh qoldiring
        </span>
        <Input
          value={warranty}
          onChange={(event) => setWarranty(event.target.value)}
          placeholder="1 yil"
          aria-label="Kafolat"
          className="h-control" />
      </label>

      <Problem error={write.error} />
      <Button type="submit" variant="secondary" className="w-full" disabled={write.isPending} >
        {write.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
        Saqlash
      </Button>
    </form>
  )
}


// ------------------------------------------------------------------- the table

/**
 * The specification table, which the phone draws as a table or not at all.
 *
 * **The rows arrive already named.** Typing "Mato", "Ishlab chiqarilgan",
 * "Parvarish" from scratch for every card is how a table stays empty, and an
 * empty table is a block the apps do not draw — so the keys come from what was
 * written against this kind of goods last time, and from a starter set the
 * first time a kind is described at all. Whoever publishes the card fills the
 * values and deletes the row that does not apply, which is a faster thing to
 * do than thinking of the words.
 */
export function Specs({ card }: { card: AdminProduct }) {
  const stored = useSpecs(card.id)
  const vocab = useVocab()
  const write = useWriteSpecs(card.id)
  const [rows, setRows] = useState<Spec[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (loaded || !stored.data || !vocab.data) return
    if (stored.data.length) {
      setRows(stored.data)
    } else {
      const keys = vocab.data.spec_keys[card.kind] ?? []
      setRows(
        keys.length
          ? keys.map((key) => ({ key, value: "" }))
          : [{ key: "", value: "" }],
      )
    }
    setLoaded(true)
  }, [stored.data, vocab.data, card.kind, loaded])

  function set(index: number, patch: Partial<Spec>) {
    setRows((was) => was.map((row, at) => (at === index ? { ...row, ...patch } : row)))
  }

  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Table2 className="size-4 text-ink-soft" />
        Xususiyatlar
      </h4>

      <ul className="space-y-1">
        {rows.map((row, index) => (
          <li key={index} className="flex gap-1">
            <Input
              value={row.key}
              onChange={(event) => set(index, { key: event.target.value })}
              placeholder="Mato"
              aria-label={`${index + 1} — nomi`}
              className="h-control w-1/3" />
            <Input
              value={row.value}
              onChange={(event) => set(index, { value: event.target.value })}
              placeholder="Paxta"
              aria-label={`${index + 1} — qiymati`}
              className="h-control flex-1" />
            <Button type="button" variant="ghost" size="sm" aria-label="Qatorni o'chirish" onClick={() => setRows((was) => was.filter((_, at) => at !== index))}
            >
              <Trash2 className="size-4" />
            </Button>
          </li>
        ))}
      </ul>

      <div className="flex gap-2">
        <Button type="button" variant="ghost" className="gap-1" onClick={() => setRows((was) => [...was, { key: "", value: "" }])}
        >
          <Plus className="size-4" />
          Qator
        </Button>
        <Button type="button" variant="secondary" className="flex-1" disabled={write.isPending} onClick={() =>
            write.mutate(
              rows
                .map((row) => ({ key: row.key.trim(), value: row.value.trim() }))
                .filter((row) => row.key && row.value),
            )
          }
        >
          Saqlash
        </Button>
      </div>

      <Problem error={write.error} />
    </div>
  )
}


// ------------------------------------------------------------------- the filing

export function Filing({ card }: { card: AdminProduct }) {
  const categories = useCategories()
  const file = useFileCard(card.id)
  const write = useWriteCategory()
  const [name, setName] = useState("")

  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Tags className="size-4 text-ink-soft" />
        Kategoriya
        <span className="font-normal text-ink-faint">— mijoz shu orqali topadi</span>
      </h4>

      <div className="flex flex-wrap gap-1">
        {(categories.data ?? []).map((one) => (
          <button
            key={one.slug}
            type="button"
            disabled={file.isPending}
            onClick={() => file.mutate({ category_slug: one.slug })}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              card.category_slug === one.slug && "border-brand bg-brand text-brand-ink",
            )}
          >
            {one.name}
          </button>
        ))}
      </div>

      {/* Written here rather than on another screen: the first card ever
          written has nowhere to go, and sending somebody to a different menu
          to make one is where the old flow stopped dead. */}
      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          const wanted = name.trim()
          if (!wanted) return
          const slug =
            wanted
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-|-$/g, "") || `kat-${Date.now()}`
          write.mutate(
            { slug, name: wanted },
            {
              onSuccess: (made) => {
                setName("")
                file.mutate({ category_slug: made.slug })
              },
            },
          )
        }}
      >
        <label className="min-w-32 flex-1">
          <span className="mb-1 block text-micro text-ink-soft">Yangi kategoriya</span>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Oyoq kiyim"
            aria-label="Yangi kategoriya"
            className="h-control" />
        </label>
        <Button type="submit" variant="secondary">
          Qo'shish
        </Button>
      </form>

      <Problem error={file.error || write.error} />
    </section>
  )
}


// -------------------------------------------------------------------- the price

export function Pricing({ card }: { card: AdminProduct }) {
  const price = usePriceCard(card.id)
  const [sale, setSale] = useState(card.price ? String(card.price) : "")
  const [was, setWas] = useState(card.old_price ? String(card.old_price) : "")

  // What the goods cost is the one figure already known — it was written at the
  // bench with the sack open, and it lives on the market run's line rather than
  // on the cell, because a cell's price is what we sell at. So the markup is
  // offered rather than the price: "+75%" is how the person who bought them
  // thinks, and typing the answer outright is still there for when it is not.
  const cost = card.last_cost
  const wanted = Number(sale) || 0
  const markup = cost > 0 && wanted > 0 ? Math.round((wanted / cost - 1) * 100) : 0

  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Wallet className="size-4 text-ink-soft" />
        Sotuv narxi
        {cost > 0 ? (
          <span className="font-normal text-ink-faint">— tannarx {money(cost)}</span>
        ) : null}
      </h4>

      {cost > 0 ? (
        <div className="flex flex-wrap gap-1">
          {[40, 60, 75, 100].map((percent) => (
            <button
              key={percent}
              type="button"
              onClick={() =>
                setSale(String(Math.round((cost * (100 + percent)) / 100 / 1000) * 1000))
              }
              className="h-control rounded-control border px-3 text-small">
              +{percent}%
            </button>
          ))}
        </div>
      ) : null}

      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (wanted > 0) {
            price.mutate({ price: wanted, old_price: Number(was) || null })
          }
        }}
      >
        <label className="w-36">
          <span className="mb-1 block text-micro text-ink-soft">Narx</span>
          <Input
            value={sale}
            onChange={(event) => setSale(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="149 000"
            aria-label="Sotuv narxi"
            className="h-control-lg tabular text-body" />
        </label>
        <label className="w-36">
          <span className="mb-1 block text-micro text-ink-soft">
            Eski narx — chegirma
          </span>
          <Input
            value={was}
            onChange={(event) => setWas(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="199 000"
            aria-label="Eski narx"
            className="h-control tabular" />
        </label>
        <Button size="lg" type="submit" variant="secondary" disabled={wanted <= 0 || price.isPending} >
          Qo'yish
        </Button>
        {markup > 0 ? (
          <span className="pb-2 text-small text-ink-soft">+{markup}%</span>
        ) : null}
      </form>

      <Problem error={price.error} />
    </section>
  )
}
