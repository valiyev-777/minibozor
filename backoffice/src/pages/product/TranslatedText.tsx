import { Hint, Input, Label, Textarea } from "@/components/ui/field"
import { cn } from "@/lib/utils"

/**
 * One card's words, in the three languages the apps ask for.
 *
 * A language switcher rather than three forms side by side. The three are not
 * three independent documents — they are one card said three ways, and the
 * thing an editor does most often is look at the Uzbek while typing the
 * Russian. Three forms would put the answer off-screen; three columns would
 * make every field a third as wide as the prose it holds.
 *
 * **Uzbek is the row; the other two are the translation table.** That is not
 * a detail of storage, it is what the fallback means: a card with no Russian
 * description shows the Uzbek one, and shows it correctly. So a blank field
 * here is never an error and never marked as one — it is a card that has not
 * been translated yet, which is the ordinary state of a catalogue somebody is
 * still filling in.
 */

export const LANGS = ["uz", "ru", "en"] as const
export type Lang = (typeof LANGS)[number]

export const LANG_NAME: Record<Lang, string> = {
  uz: "O'zbekcha",
  ru: "Русский",
  en: "English",
}

/** The fields of a card that carry words, and what to call them. */
export const TEXT_FIELDS = [
  { key: "title", label: "Nom", long: false, required: true },
  { key: "subtitle", label: "Izoh", long: false, required: false },
  { key: "description", label: "Tavsif", long: true, required: false },
  { key: "badge", label: "Yorliq", long: false, required: false },
  { key: "warranty", label: "Kafolat", long: false, required: false },
] as const

export type TextField = (typeof TEXT_FIELDS)[number]["key"]
export type Texts = Record<TextField, string>

export const EMPTY_TEXTS: Texts = {
  title: "",
  subtitle: "",
  description: "",
  badge: "",
  warranty: "",
}

/** How many of the Uzbek's filled fields this language has an answer for. */
export function translatedCount(uz: Texts, other: Texts): { done: number; of: number } {
  const filled = TEXT_FIELDS.filter((f) => uz[f.key].trim())
  return {
    done: filled.filter((f) => other[f.key].trim()).length,
    of: filled.length,
  }
}

export function LanguageTabs({
  lang,
  onChange,
  texts,
}: {
  lang: Lang
  onChange: (lang: Lang) => void
  texts: Record<Lang, Texts>
}) {
  return (
    <div role="tablist" className="flex items-center gap-0.5 rounded border border-line bg-surface p-0.5">
      {LANGS.map((value) => {
        const active = value === lang
        const progress = value === "uz" ? null : translatedCount(texts.uz, texts[value])
        return (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-[13px] transition-colors",
              active
                ? "bg-accent-soft font-medium text-accent"
                : "text-ink-soft hover:bg-line-soft hover:text-ink",
            )}
          >
            {LANG_NAME[value]}
            {progress ? (
              <span
                className={cn(
                  "tabular rounded px-1 text-[11px] font-semibold",
                  progress.done === progress.of
                    ? "bg-good-soft text-good"
                    : "bg-line-soft text-ink-faint",
                )}
                // Not a warning. An untranslated card works; it shows Uzbek.
                title="Tarjima qilingan maydonlar"
              >
                {progress.done}/{progress.of}
              </span>
            ) : null}
          </button>
        )
      })}
    </div>
  )
}

export function TextFields({
  lang,
  texts,
  onChange,
  idPrefix,
}: {
  lang: Lang
  texts: Record<Lang, Texts>
  onChange: (lang: Lang, field: TextField, value: string) => void
  idPrefix: string
}) {
  const current = texts[lang]
  const uz = texts.uz

  return (
    <div className="space-y-3">
      {lang === "uz" ? (
        <Hint>
          O'zbekchasi kartochkaning o'zida saqlanadi — bu asosiy matn. Ruscha va
          inglizcha alohida jadvalda, va bo'sh bo'lsa shu matn ko'rsatiladi.
        </Hint>
      ) : (
        <Hint>
          Bo'sh qoldirilgan maydon xato emas: ilova o'sha maydon uchun
          o'zbekchasini ko'rsatadi. To'ldirilgani esa faqat shu tilda chiqadi.
        </Hint>
      )}

      {TEXT_FIELDS.map((field) => {
        const id = `${idPrefix}-${lang}-${field.key}`
        const value = current[field.key]
        const source = uz[field.key]
        const Control = field.long ? Textarea : Input
        return (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={id}>
              {field.label}
              {field.required && lang === "uz" ? (
                <span className="ml-1 text-danger">*</span>
              ) : null}
            </Label>
            <Control
              id={id}
              value={value}
              // The Uzbek stands in the empty field, so what will actually be
              // shown is visible without switching tabs to check.
              placeholder={lang === "uz" ? "" : source}
              onChange={(event: { target: { value: string } }) =>
                onChange(lang, field.key, event.target.value)
              }
            />
            {lang !== "uz" && source ? (
              <p className="text-[12px] text-ink-faint">
                <span className="font-medium">uz:</span> {source}
              </p>
            ) : null}
            {lang !== "uz" && !source ? (
              <p className="text-[12px] text-ink-faint">
                O'zbekchasi bo'sh — bu maydon kartochkada umuman ko'rinmaydi.
              </p>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

/**
 * The `translations` half of a write payload.
 *
 * Uzbek is left out: it is on the row and travels in the payload's own
 * fields. Every other language goes as it stands, blanks included — an empty
 * string is how the backend is told to drop a translation, which is what
 * clearing a field on screen has to mean.
 */
export function translationsPayload(
  texts: Record<Lang, Texts>,
): Record<string, Record<string, string>> {
  const out: Record<string, Record<string, string>> = {}
  for (const lang of LANGS) {
    if (lang === "uz") continue
    out[lang] = Object.fromEntries(
      TEXT_FIELDS.map((field) => [field.key, texts[lang][field.key].trim()]),
    )
  }
  return out
}
