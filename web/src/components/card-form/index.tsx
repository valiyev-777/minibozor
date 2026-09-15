/**
 * §5.2 — the card form. One column, one page, two entrances.
 *
 * **Progressive, not staged.** No wizard, no "2 of 3", no save-and-continue.
 * What is filled in is filled in, and the sections that cannot be answered yet
 * are simply not offered — the category comes first because it decides what
 * the rest offers, and the rest appears once it is settled.
 *
 * **Two entrances, one component.**
 * - `mode="receiving"` is `/qabul` with the goods in your hands: the category,
 *   the name, the make, the colours and the sizes. Everything a shop window
 *   needs and a receiving bench cannot know — the prose, the photographs, the
 *   price — is left for later, and the card exists in `draft` until it is.
 * - `mode="catalogue"` is the same card opened in Mahsulotlar, showing all ten
 *   sections with the publishing gate at the top.
 *
 * **Where each field lands.** Most of it is the card's own columns, written
 * through `PATCH /admin/products/{id}`. Four things have their own doors and
 * are written the moment they are answered, because each is a different kind
 * of decision with a different guard on the server: the category, the size
 * system, the colour × size grid, and the money.
 *
 * `description` is stored as HTML. The plain text the brief asks to keep
 * beside it for search has nowhere to go — `Product` has one description
 * column and `ProductUpdateIn` no second field — so `rich-text.tsx` exports
 * `plainText` ready for the day it does, and nothing writes it yet.
 *
 * The rest — the model, the country of manufacture, and the four folded-away
 * sections — are rows of `product_specs`, which is the table the phone app
 * already draws as a specification table. They are not new columns on
 * `Product`: a card with a `care_instructions` column and an empty one is the
 * same blank space as a spec row that was never written, and the spec table
 * costs nothing and is already rendered.
 */

import { Loader2, Plus, Trash2 } from "lucide-react"
import { useEffect, useState } from "react"

import { Counter, Folded, Required, Section, Swatch } from "@/components/card-form/bits"
import { Attributes } from "@/components/card-form/attributes"
import { CategoryStep } from "@/components/card-form/category-step"
import { GatePanel } from "@/components/card-form/gate-panel"
import { PriceTable } from "@/components/card-form/price-table"
import { RichText, isBlank, tidyHtml } from "@/components/card-form/rich-text"
import { Empty, Problem, Waiting } from "@/components/page"
import { Capture, Photos } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import {
  useAddImage,
  useBrands,
  useColours,
  useCreateProduct,
  useDeleteImage,
  useFileCard,
  useImages,
  useMakeCover,
  useProduct,
  useProductSizeSystem,
  usePublish,
  useSetGrid,
  useSetProductSizeSystem,
  useSpecs,
  useVariants,
  useWriteSpecs,
} from "@/lib/queries"
import type { Spec } from "@/lib/types"

/** §5.2 ·2: the phone app truncates a name past this, where it counts. */
const NAME_MAX = 90
/** §5.2 ·5: one spec value. */
const SPEC_MAX = 255

/**
 * The spec rows this form owns by name, so it can lift them out of the free
 * table and back into it. Everything else in `product_specs` is §5.2 ·5's,
 * typed by hand, and is left exactly where it was.
 */
const MODEL = "Model"
const COUNTRY = "Ishlab chiqarilgan mamlakat"
/** §5.2 ·9 — four buttons rather than eleven empty textareas. */
const FOLDED = ["O'lchovli to'r", "Tarkib", "Parvarish", "Sertifikatlar"] as const
const OWNED: string[] = [MODEL, COUNTRY, ...FOLDED]

/**
 * Where market goods in this shop are made.
 *
 * A short list rather than a `<select>` of two hundred countries, and a list
 * in code rather than a table, because there is no door for it on the server
 * and inventing one for a field with fourteen real answers is the wrong
 * trade. A country not on the list is typed — which is what the free row is
 * for, and unlike a colour it is not a word two people spell differently.
 */
const COUNTRIES = [
  "O'zbekiston",
  "Xitoy",
  "Turkiya",
  "Rossiya",
  "Qozog'iston",
  "Qirg'iziston",
  "Hindiston",
  "Vetnam",
  "Bangladesh",
  "Indoneziya",
  "Koreya",
  "Germaniya",
  "Italiya",
  "Polsha",
]

/**
 * The words this form is holding, boiled down to one string.
 *
 * Exactly what `saveWords` would send, so trailing spaces and an empty
 * paragraph in the editor are not "changes" — and so the comparison is against
 * what the server was actually given rather than against React state.
 */
type Words = {
  title: string
  subtitle: string
  description: string
  brand: string
  noBrand: boolean
  model: string
  noModel: boolean
  country: string
  noCountry: boolean
  folded: Record<string, string>
  rows: Spec[]
}

function fingerprint(words: Words): string {
  return JSON.stringify([
    words.title.trim(),
    words.subtitle.trim(),
    isBlank(words.description) ? "" : tidyHtml(words.description),
    words.noBrand ? "" : words.brand,
    words.noModel ? "" : words.model.trim(),
    words.noCountry ? "" : words.country.trim(),
    FOLDED.map((key) => (words.folded[key] ?? "").trim()),
    words.rows
      .map((row) => [row.key.trim(), row.value.trim()])
      .filter(([key, value]) => key && value),
  ])
}

export type CardFormProps = {
  /** The card being written. Absent = a new card, the /qabul entrance. */
  productId?: number
  /** Which entrance opened it. "receiving" shows only what is knowable with
   *  the goods in your hands; "catalogue" shows the whole form. */
  mode: "receiving" | "catalogue"
  /** What to call it, before anybody has. The search words somebody typed
   *  looking for a card that turned out not to exist are the best guess at
   *  the name of the card they are about to write, and retyping them is the
   *  step that made people give up. Optional: a form opened cold seeds
   *  nothing. */
  initialName?: string
  /** A new card was created. */
  onCreated?: (productId: number) => void
  /** Saved and finished. */
  onDone?: () => void
  /** The form is holding words nobody has saved. The screen around it owns
   *  the exits — a Back button, a drawer — and cannot warn about what it
   *  cannot see. */
  onDirtyChange?: (dirty: boolean) => void
}

export function CardForm({
  productId,
  mode,
  initialName,
  onCreated,
  onDone,
  onDirtyChange,
}: CardFormProps) {
  // A card made in this sitting. The prop stays the caller's word on which
  // card this is; this is what the form itself is holding once it has made
  // one, so `/qabul` opening with no id still gets the whole form afterwards.
  const [made, setMade] = useState<number | null>(null)
  const id = productId ?? made

  return id ? (
    <WritingACard id={id} mode={mode} onDone={onDone} onDirtyChange={onDirtyChange} />
  ) : (
    <StartingACard
      initialName={initialName}
      onCreated={(newId) => {
        setMade(newId)
        onCreated?.(newId)
      }}
    />
  )
}

/**
 * The first two answers, which are all it takes to have a card.
 *
 * Deliberately not the whole form greyed out: a card that does not exist yet
 * has nowhere to put a photograph, and showing ten disabled sections is a
 * screen that reads as broken rather than as sequenced.
 */
function StartingACard({
  initialName,
  onCreated,
}: {
  initialName?: string
  onCreated: (id: number) => void
}) {
  const create = useCreateProduct()
  const [category, setCategory] = useState<string | null>(null)
  // Seeded from what the person was searching for when they gave up looking.
  const [title, setTitle] = useState(initialName ?? "")
  // The snapshot goes in at creation or not at all: the bench may open a card
  // (`POST /admin/products` admits it) but may not edit one afterwards
  // (`PATCH` is CatalogWriter). Kind and make used to be asked here too; the
  // owner cut them — the category already files the card, and the make is the
  // catalogue's to fill in when the card is dressed for the shop.
  const [snapshot, setSnapshot] = useState("")

  return (
    <div className="w-full max-w-3xl space-y-4">
      <AsteriskLine />

      <Section step={1} title="Tovar toifasi" required>
        <CategoryStep value={category} onAccept={setCategory} />
      </Section>

      {category ? (
        <Section
          step={2}
          title="Tovar nomi"
          required
          hint="Mijoz shuni o'qiydi va shuni qidiradi."
          aside={<Counter value={title} max={NAME_MAX} />}
        >
          <Input
            value={title}
            maxLength={NAME_MAX}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Erkaklar krossovkasi Alfa"
            aria-label="Tovar nomi"
            className="h-control-lg text-body"
          />
        </Section>
      ) : null}

      {category ? (
        <Section
          step={3}
          title="Tanish uchun rasm"
          hint="Ixtiyoriy — lekin karta ochilgandan keyin stolda qo'shib bo'lmaydi. Tovar ustidan — oq fon shart emas."
        >
          <Capture
            colour=""
            current={snapshot || undefined}
            onTaken={(_, url) => setSnapshot(url)}
            guide="Shu tovarni keyin tanish uchun. Do'kon rasmi emas."
            placeholder="rasm olish"
          />
        </Section>
      ) : null}

      {/* **Last, because it is the irreversible one.** It used to sit beside
          the name in section 2, above a photograph section nobody had scrolled
          to yet — so the card was opened, and the snapshot, which can only go
          in at creation, was lost for good. Nothing that cannot be undone
          belongs above a field somebody has not seen. */}
      {category ? (
        <div className="space-y-2">
          <Button
            type="button"
            size="lg"
            className="w-full gap-2 sm:w-auto"
            disabled={!title.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  sku: "",
                  title: title.trim(),
                  category_slug: category,
                  price: 0,
                  snapshot_url: snapshot,
                },
                { onSuccess: (card) => onCreated(card.id) },
              )
            }
          >
            {create.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Kartani ochish
          </Button>
          <p className="text-micro text-ink-soft">
            {title.trim()
              ? "Karta ochilgandan keyin tanish uchun rasm qo'shib bo'lmaydi."
              : "Avval tovar nomini yozing."}
          </p>
          <Problem error={create.error} />
        </div>
      ) : null}
    </div>
  )
}

/** The line at the top that says what the asterisk means. */
function AsteriskLine() {
  return (
    <p className="text-small text-ink-soft">
      <Required /> belgisi — to'ldirilishi shart bo'lgan maydon.
    </p>
  )
}

function WritingACard({
  id,
  mode,
  onDone,
  onDirtyChange,
}: {
  id: number
  mode: "receiving" | "catalogue"
  onDone?: () => void
  onDirtyChange?: (dirty: boolean) => void
}) {
  const detail = useProduct(id)
  const specs = useSpecs(id)
  const grid = useVariants(id)
  const images = useImages(id)
  const palette = useColours()
  const brands = useBrands()
  const sized = useProductSizeSystem(id)

  const file = useFileCard(id)
  const writeSpecs = useWriteSpecs(id)
  const setGrid = useSetGrid(id)
  const setSystem = useSetProductSizeSystem(id)
  const publish = usePublish(id)
  const addImage = useAddImage(id)
  const deleteImage = useDeleteImage(id)
  const makeCover = useMakeCover(id)

  const full = mode === "catalogue"

  // ------------------------------------------------------------ the card's words
  const [title, setTitle] = useState("")
  const [subtitle, setSubtitle] = useState("")
  const [description, setDescription] = useState("")
  const [brand, setBrand] = useState("")
  const [noBrand, setNoBrand] = useState(false)
  const [model, setModel] = useState("")
  const [noModel, setNoModel] = useState(false)
  const [country, setCountry] = useState("")
  const [noCountry, setNoCountry] = useState(false)
  const [folded, setFolded] = useState<Record<string, string>>({})
  const [rows, setRows] = useState<Spec[]>([])

  // Colours and sizes as this form is holding them, which is not yet what the
  // grid holds: the grid is written on a button, because adding a colour
  // creates variants with barcodes on them.
  const [colours, setColours] = useState<string[]>([])
  const [sizes, setSizes] = useState<string[]>([])
  // Why the last tick did not take — see `chooseColours`.
  const [refusal, setRefusal] = useState<string | null>(null)

  // Filled once, when the card and its spec table have both landed. Typing
  // into a field whose value is being reset underneath is the classic form
  // that fights back.
  const [seeded, setSeeded] = useState(false)
  // The fingerprint of the words as last written to the server — `null` until
  // the card has landed, because nothing is unsaved before there is anything.
  const [saved, setSaved] = useState<string | null>(null)
  useEffect(() => {
    if (seeded || !detail.data || !specs.data || !grid.data) return
    setTitle(detail.data.title)
    setSubtitle(detail.data.subtitle)
    setDescription(tidyHtml(detail.data.description))
    setBrand(detail.data.brand_slug ?? "")

    const held = new Map(specs.data.map((row) => [row.key, row.value]))
    setModel(held.get(MODEL) ?? "")
    setCountry(held.get(COUNTRY) ?? "")
    setFolded(
      Object.fromEntries(
        FOLDED.filter((key) => held.get(key)).map((key) => [key, held.get(key) ?? ""]),
      ),
    )
    setRows(specs.data.filter((row) => !OWNED.includes(row.key)))

    setColours([...new Set(grid.data.map((one) => one.colour))].filter(Boolean))
    setSizes([...new Set(grid.data.map((one) => one.size))].filter(Boolean))
    // The words as the card holds them — what "unchanged" means from here on.
    setSaved(
      fingerprint({
        title: detail.data.title,
        subtitle: detail.data.subtitle,
        description: tidyHtml(detail.data.description),
        brand: detail.data.brand_slug ?? "",
        noBrand: false,
        model: held.get(MODEL) ?? "",
        noModel: false,
        country: held.get(COUNTRY) ?? "",
        noCountry: false,
        folded: Object.fromEntries(
          FOLDED.filter((key) => held.get(key)).map((key) => [key, held.get(key) ?? ""]),
        ),
        rows: specs.data.filter((row) => !OWNED.includes(row.key)),
      }),
    )
    setSeeded(true)
  }, [detail.data, specs.data, grid.data, seeded])

  // ------------------------------------------------------- unsaved or not
  //
  // The category, the size system, the grid and the money each save the moment
  // they are answered, which teaches the screen "it saves itself" — and then a
  // name and three paragraphs typed into the sections that do *not* save
  // themselves vanish on the way out, silently. So the form knows whether it
  // is holding anything, says so on the bar, warns the browser on the way out,
  // and saves before it publishes.
  const now = fingerprint({
    title,
    subtitle,
    description,
    brand,
    noBrand,
    model,
    noModel,
    country,
    noCountry,
    folded,
    rows,
  })
  const dirty = saved !== null && saved !== now

  useEffect(() => {
    onDirtyChange?.(dirty)
  }, [dirty, onDirtyChange])

  // Closing the tab, reloading, the phone's back gesture — everything the
  // browser owns rather than the router.
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      // Still required by Chrome for the native prompt to appear.
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [dirty])

  if (detail.isLoading || !detail.data) {
    return detail.error ? <Problem error={detail.error} /> : <Waiting what="Karta" />
  }

  const card = detail.data
  const hex = new Map((palette.data ?? []).map((row) => [row.name, row.hex]))
  const shots = images.data ?? []
  const photographed = new Set(shots.map((image) => image.colour))
  const gridColours = [...new Set((grid.data ?? []).map((one) => one.colour))].filter(
    Boolean,
  )
  const gridSizes = [...new Set((grid.data ?? []).map((one) => one.size))].filter(Boolean)
  // §5.2 ·7 is "one block per **chosen** colour", and chosen is not the same as
  // minted. Ticking three colours in the palette has to open three photograph
  // slots there and then: a photograph hangs on `product_images.colour`, which
  // is a name, so nothing is created by drawing the slot and no barcode is
  // spent. Reading the saved grid instead meant the slots only appeared after
  // somebody found "Rang × o'lcham to'rini saqlash" further up the page — so
  // picking a colour looked like it did nothing, which is what it was reported
  // as. The grid's own colours stay in the list: a colour unticked by mistake
  // must not take its photographs off the screen with it.
  const photoColours = [...new Set([...colours, ...gridColours])].filter(Boolean)
  // A colour ticked but not yet on the grid, or a size. The grid is additive on
  // the server — sending it again never renumbers what is already printed —
  // so this is the only thing that has to be true before the button appears.
  const gridStale =
    colours.some((one) => !gridColours.includes(one)) ||
    sizes.some((one) => !gridSizes.includes(one))

  /**
   * A colour ticked or unticked in the modal, checked against the shelf.
   *
   * Unticking `Qora` on a card with five black shoes on a shelf used to shrink
   * the chip row and change nothing else: the grid kept the colour, the photo
   * strip kept it, the gate kept it. A colour that has reached the variant
   * grid has barcodes printed against it and stock counted under it, and it
   * does not come off the card by unticking a box — so the tick is refused,
   * out loud, and the person is pointed at the table that can do it.
   */
  function chooseColours(next: string[]) {
    const held = gridColours.filter((one) => !next.includes(one))
    if (held.length) {
      const stocked = held.filter((one) =>
        (grid.data ?? []).some((cell) => cell.colour === one && cell.stock_left > 0),
      )
      const named = (list: string[]) => list.map((one) => `«${one}»`).join(", ")
      setRefusal(
        stocked.length
          ? `${named(stocked)} javonda bor — kartadan olib bo'lmaydi. Brak bo'lsa: Rang × o'lcham jadvalida.`
          : `${named(held)} rang × o'lcham to'rida bor — kartadan olib bo'lmaydi. Quyidagi «Rang × o'lcham» jadvalida olib tashlanadi.`,
      )
      // Kept ticked **and in the position they were in**: a refused change
      // must leave the control showing exactly what it showed before, or the
      // chip row re-orders itself and reads as though something did happen.
      next = [
        ...colours.filter((one) => next.includes(one) || held.includes(one)),
        ...next.filter((one) => !colours.includes(one)),
      ]
    } else {
      setRefusal(null)
    }

    const added = next.filter((one) => !colours.includes(one))
    setColours(next)
    // A ticked colour opens a photograph slot, and the slot is four sections
    // further down the page. Somebody who ticks `Oq` and sees nothing happen
    // is somebody who ticks it again.
    if (added.length) {
      window.setTimeout(
        () =>
          document
            .getElementById("card-form-photos")
            ?.scrollIntoView({ behavior: "smooth", block: "center" }),
        0,
      )
    }
  }

  /**
   * Everything the words-and-specs save writes, in one request each — and in
   * that order, awaited, so a card is never published with half its words
   * written. Either failure comes back as `false` and is already on screen
   * through `<Problem>`.
   */
  async function saveWords(finish = true): Promise<boolean> {
    const wanted = now
    try {
      await file.mutateAsync({
        title: title.trim() || card.title,
        subtitle: subtitle.trim(),
        description: isBlank(description) ? "" : tidyHtml(description),
        brand_slug: noBrand ? undefined : brand || undefined,
      })
      await writeSpecs.mutateAsync([
        ...(noModel || !model.trim() ? [] : [{ key: MODEL, value: model.trim() }]),
        ...(noCountry || !country.trim()
          ? []
          : [{ key: COUNTRY, value: country.trim() }]),
        ...FOLDED.filter((key) => (folded[key] ?? "").trim()).map((key) => ({
          key,
          value: (folded[key] ?? "").trim(),
        })),
        ...rows
          .map((row) => ({ key: row.key.trim(), value: row.value.trim() }))
          .filter((row) => row.key && row.value),
      ])
    } catch {
      // Shown by the panel's own `<Problem>`; the bar stays warn-toned,
      // because the words really are still unsaved.
      return false
    }
    setSaved(wanted)
    if (finish) onDone?.()
    return true
  }

  /**
   * Chiqarish, with the typed words saved first.
   *
   * The gate is about the category, the price and the photographs — none of
   * which the sticky bar writes — so a card could go into the shop under the
   * name it had before somebody retyped it. It saves, and only publishes if
   * the save landed.
   */
  async function publishCard() {
    if (dirty && !(await saveWords(false))) return
    publish.mutate("active")
  }

  return (
    <div className="w-full max-w-3xl space-y-4">
      {/* §5.4: the gate panel is at the top of the form and not a panel beside
          it — the three things holding a card out of the shop are the first
          thing somebody opening the card in the catalogue needs to see. */}
      {full ? (
        <GatePanel
          card={card}
          photographed={photographed}
          // The same list §7 draws slots for, or the gate would report "Oq ✗"
          // while three colours are chosen and two of them have no slot yet.
          colours={photoColours}
          publish={publish}
          dirty={dirty}
          onPublish={() => void publishCard()}
        />
      ) : null}

      <AsteriskLine />

      <Section step={1} title="Tovar toifasi" required>
        <div id="card-form-category">
          <CategoryStep
            value={card.category_slug}
            saving={file.isPending}
            error={file.error}
            onAccept={(slug) => file.mutate({ category_slug: slug })}
          />
        </div>
      </Section>

      <Section
        step={2}
        title="Tovar nomi"
        required
        hint="Mijoz shuni o'qiydi va shuni qidiradi."
        aside={<Counter value={title} max={NAME_MAX} />}
      >
        <Input
          value={title}
          maxLength={NAME_MAX}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Erkaklar krossovkasi Alfa"
          aria-label="Tovar nomi"
          className="h-control-lg text-body"
        />
        {full ? (
          <label className="mt-2 block">
            <span className="mb-1 block text-micro text-ink-soft">
              Qisqa izoh — nom ostidagi bir qator
            </span>
            <Input
              value={subtitle}
              onChange={(event) => setSubtitle(event.target.value)}
              placeholder="Qora, yengil, kunlik"
              aria-label="Qisqa izoh"
            />
          </label>
        ) : null}
      </Section>

      {/* §5.2 ·3. "Mavjud emas" beside each, because market goods genuinely
          often have no brand and the alternative is somebody typing "yo'q"
          into the box — which then becomes a brand, a filter and a facet. */}
      <Section step={3} title="Brend · Model · Ishlab chiqarilgan mamlakat">
        <div className="space-y-2">
          <Absent
            label="Brend"
            absent={noBrand}
            onAbsent={(on) => {
              setNoBrand(on)
              if (on) setBrand("")
            }}
          >
            <select
              value={brand}
              disabled={noBrand}
              onChange={(event) => setBrand(event.target.value)}
              aria-label="Brend"
              className={FIELD}
            >
              <option value="">Tanlang</option>
              {(brands.data ?? []).map((one) => (
                <option key={one.slug} value={one.slug}>
                  {one.name}
                </option>
              ))}
            </select>
          </Absent>

          <Absent
            label="Model"
            absent={noModel}
            onAbsent={(on) => {
              setNoModel(on)
              if (on) setModel("")
            }}
          >
            <Input
              value={model}
              disabled={noModel}
              maxLength={SPEC_MAX}
              onChange={(event) => setModel(event.target.value)}
              placeholder="Air 270"
              aria-label="Model"
            />
          </Absent>

          <Absent
            label="Ishlab chiqarilgan mamlakat"
            absent={noCountry}
            onAbsent={(on) => {
              setNoCountry(on)
              if (on) setCountry("")
            }}
          >
            <select
              value={COUNTRIES.includes(country) ? country : country ? "boshqa" : ""}
              disabled={noCountry}
              onChange={(event) =>
                setCountry(event.target.value === "boshqa" ? " " : event.target.value)
              }
              aria-label="Ishlab chiqarilgan mamlakat"
              className={FIELD}
            >
              <option value="">Tanlang</option>
              {COUNTRIES.map((one) => (
                <option key={one} value={one}>
                  {one}
                </option>
              ))}
              <option value="boshqa">Boshqa — yozaman</option>
            </select>
          </Absent>

          {!noCountry && country && !COUNTRIES.includes(country) ? (
            <Input
              value={country.trim()}
              autoFocus
              onChange={(event) => setCountry(event.target.value)}
              placeholder="Mamlakat nomi"
              aria-label="Boshqa mamlakat"
            />
          ) : null}

          <Problem error={brands.error} />
        </div>
      </Section>

      {full ? (
        <Section
          step={4}
          title="Tovar tavsifi"
          hint="Qalin, qiyshiq, ro'yxat va bitta sarlavha — telefon ilovasi shundan boshqasini chiza olmaydi."
        >
          <RichText
            value={description}
            onChange={(html) => setDescription(html)}
            placeholder="Nimadan tikilgan, kimga to'g'ri keladi, qanday parvarish qilinadi."
          />
        </Section>
      ) : null}

      {full ? (
        <Section
          step={5}
          title="Tovar xususiyatlari"
          hint="Telefon ilovasi buni jadval qilib chizadi."
        >
          <ul className="space-y-1">
            {rows.map((row, index) => (
              <li key={index} className="flex gap-1">
                <Input
                  value={row.key}
                  maxLength={SPEC_MAX}
                  onChange={(event) =>
                    setRows((was) =>
                      was.map((one, at) =>
                        at === index ? { ...one, key: event.target.value } : one,
                      ),
                    )
                  }
                  placeholder="Material"
                  aria-label={`${index + 1} — nomi`}
                  className="w-1/3"
                />
                <Input
                  value={row.value}
                  maxLength={SPEC_MAX}
                  onChange={(event) =>
                    setRows((was) =>
                      was.map((one, at) =>
                        at === index ? { ...one, value: event.target.value } : one,
                      ),
                    )
                  }
                  placeholder="Charm"
                  aria-label={`${index + 1} — qiymati`}
                  className="flex-1"
                />
                <span className="flex w-12 shrink-0 items-center justify-end gap-1">
                  <Counter value={row.value} max={SPEC_MAX} />
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Qatorni o'chirish"
                  onClick={() => setRows((was) => was.filter((_, at) => at !== index))}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mt-1 gap-1"
            onClick={() => setRows((was) => [...was, { key: "", value: "" }])}
          >
            <Plus className="size-4" />
            Qator qo'shish
          </Button>
        </Section>
      ) : null}

      {full ? (
      <Section
        step={6}
        title="Rang va o'lcham"
        hint="Rang palitradan tanlanadi, o'lcham esa o'z tizimidan — ikkalasi ham qo'lda yozilmaydi."
      >
        <Attributes
          colours={colours}
          onColours={chooseColours}
          refusal={refusal}
          system={sized.data?.size_system ?? null}
          sizeless={sized.data ? sized.data.size_system === null && !sizes.length : false}
          onSystem={(slug) => setSystem.mutate(slug)}
          sizes={sizes}
          onSizes={setSizes}
          saving={setSystem.isPending || setGrid.isPending}
          error={setSystem.error || setGrid.error}
        />

        {/* Writing the grid is its own act because it mints barcodes. The
            server adds and never renumbers, so this is safe to press twice —
            but it is not something that should happen on a tick. */}
        {gridStale ? (
          <Button
            type="button"
            variant="secondary"
            className="mt-2 gap-2"
            disabled={setGrid.isPending}
            onClick={() =>
              setGrid.mutate({
                colours: colours.map((name) => ({
                  colour: name,
                  hex: hex.get(name) ?? "",
                })),
                sizes,
                price: card.price,
              })
            }
          >
            {setGrid.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Rang × o'lcham to'rini saqlash
          </Button>
        ) : null}
      </Section>
      ) : null}

      {full ? (
        <>
          <Section
            step={7}
            title="Har bir rang uchun tovar fotosurati"
            required
            hint="Rangsiz rasm — do'konga chiqmaydigan rang."
          >
            <div id="card-form-photos" className="space-y-3">
              {photoColours.length ? (
                <Photos
                  colours={photoColours}
                  // Split from the card's own gallery below so one photograph
                  // is never drawn in two strips on one screen.
                  images={shots.filter((one) => one.colour)}
                  live={card.status === "active"}
                  onAdd={(colour, url) => addImage.mutate({ url, colour })}
                  onCover={(imageId) => makeCover.mutate(imageId)}
                  onDelete={(imageId) => deleteImage.mutate(imageId)}
                  covering={makeCover.isPending}
                  deleting={deleteImage.isPending}
                />
              ) : (
                <Empty
                  bare
                  what="Avval 6-bo'limda rang tanlang — rasm rangga osiladi."
                />
              )}

              <div className="flex flex-wrap items-center gap-2">
                {photoColours.map((one) => (
                  <span
                    key={one}
                    className="flex items-center gap-1 text-micro text-ink-soft"
                  >
                    <Swatch hex={hex.get(one)} />
                    {one}
                    {photographed.has(one) ? " ✓" : " ✗"}
                  </span>
                ))}
              </div>

              {/* Drawn and disabled rather than left out: the slot is in the
                  brief and the door is not built, and a person who was told
                  about it should find out here rather than by looking for it. */}
              <Button type="button" variant="ghost" size="sm" disabled className="gap-1">
                <Plus className="size-4" />
                Video qo'shish — hozircha yo'q
              </Button>
            </div>
          </Section>

          <Section step={8} title="Tovar bo'yicha umumiy rasmlar">
            {/* The rules where somebody photographing goods will read them,
                rather than in a paragraph they have to connect to a slot. */}
            <dl className="mb-3 grid gap-x-4 gap-y-1 text-micro text-ink-soft sm:grid-cols-[6rem_1fr]">
              <dt className="font-medium">Format</dt>
              <dd>PNG, JPEG. Tavsiya: 1080×1440</dd>
              <dt className="font-medium">Hajmi</dt>
              <dd>5 MB gacha</dd>
              <dt className="font-medium">Tartib</dt>
              <dd>birinchi rasm — karta muqovasi</dd>
              <dt className="font-medium">Fon</dt>
              <dd>oq fon, bitta tovar, qo'l ko'rinmasin</dd>
            </dl>
            <Photos
              colours={[""]}
              cardGallery
              images={shots.filter((one) => !one.colour)}
              live={card.status === "active"}
              onAdd={(colour, url) => addImage.mutate({ url, colour })}
              onCover={(imageId) => makeCover.mutate(imageId)}
              onDelete={(imageId) => deleteImage.mutate(imageId)}
              covering={makeCover.isPending}
              deleting={deleteImage.isPending}
            />
          </Section>

          <Section step={9} title="Qo'shimcha ma'lumot">
            <div className="space-y-2">
              {FOLDED.map((key) => (
                <Folded key={key} title={key} filled={Boolean(folded[key])}>
                  <textarea
                    value={folded[key] ?? ""}
                    maxLength={SPEC_MAX}
                    rows={3}
                    onChange={(event) =>
                      setFolded((was) => ({ ...was, [key]: event.target.value }))
                    }
                    aria-label={key}
                    className="w-full rounded-control border border-transparent bg-line-soft p-2 text-small text-ink outline-none focus-visible:border-brand focus-visible:bg-surface focus-visible:ring-2 focus-visible:ring-brand/25"
                  />
                </Folded>
              ))}
            </div>
          </Section>

          <Section step={10} title="Narx jadvali" required>
            <div id="card-form-price">
              <PriceTable card={card} />
            </div>
          </Section>
        </>
      ) : null}

      <Problem
        error={
          file.error ||
          writeSpecs.error ||
          addImage.error ||
          deleteImage.error ||
          makeCover.error ||
          images.error
        }
      />

      {/* One save for the words and the table. The category, the size system,
          the grid and the money each went the moment they were answered —
          they have their own doors and their own guards, and a card whose
          price waits on a button at the bottom of a long form is a card that
          gets published unpriced. */}
      {full ? (
        <div
          className={cn(
            "sticky bottom-[var(--bottom-nav)] z-10 rounded-panel border px-4 py-3 shadow-raised backdrop-blur",
            dirty ? "border-warn/50 bg-warn-soft/95" : "border-line bg-surface/95",
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p
              className={cn(
                "text-small",
                dirty ? "font-medium text-warn-ink" : "text-ink-soft",
              )}
            >
              {dirty ? "Saqlanmagan o'zgarishlar" : "Hammasi saqlangan"}
            </p>
            <Button
              type="button"
              className="w-full gap-2 sm:w-auto"
              variant={dirty ? "primary" : "secondary"}
              disabled={file.isPending || writeSpecs.isPending || !dirty}
              onClick={() => void saveWords()}
            >
              {file.isPending || writeSpecs.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : null}
              Saqlash
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

/** The filled-field classes, for the two `<select>`s this form draws by hand. */
const FIELD =
  "h-control w-full rounded-control border border-transparent bg-line-soft px-3 text-body text-ink outline-none focus-visible:border-brand focus-visible:bg-surface focus-visible:ring-2 focus-visible:ring-brand/25 disabled:opacity-50"

/**
 * A field with a **Mavjud emas** beside it.
 *
 * Ticking it clears and disables the field rather than writing the words "no
 * brand" anywhere: the point is to give somebody an answer to "this has no
 * make" that is not typing `yo'q` into a box that then becomes a brand, a
 * filter and a facet.
 */
function Absent({
  label,
  absent,
  onAbsent,
  children,
}: {
  label: string
  absent: boolean
  onAbsent: (absent: boolean) => void
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="min-w-48 flex-1">
        <span className="mb-1 block text-micro text-ink-soft">{label}</span>
        {children}
      </label>
      <label
        className={cn(
          "flex h-control cursor-pointer items-center gap-2 text-small",
          absent ? "text-ink" : "text-ink-soft",
        )}
      >
        <input
          type="checkbox"
          checked={absent}
          onChange={(event) => onAbsent(event.target.checked)}
          className="size-4 accent-brand"
        />
        Mavjud emas
      </label>
    </div>
  )
}
