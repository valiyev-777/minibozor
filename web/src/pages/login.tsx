/**
 * One login screen for all three jobs.
 *
 * A phone number and the code that follows it, which is the only way anybody
 * signs in to anything here — customers included. There is no password store,
 * no second screen, and no way for the two to drift apart.
 *
 * In dev the API answers the request with the code it sent, and this screen
 * fills it in. That is not a shortcut past anything: there is no SMS gateway
 * yet, and a developer typing 123456 forty times a day is a developer who
 * eventually hard-codes a token somewhere worse.
 */

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError, api } from "@/lib/api"
import { useSession } from "@/lib/session"

type Asked = { dev_code?: string | null; expires_in?: number }

export function LoginPage() {
  const { signIn } = useSession()
  const [phone, setPhone] = useState("+998")
  const [code, setCode] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function ask(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      const asked = await api<Asked>("/auth/otp/request", {
        body: { phone },
        anonymous: true,
      })
      setSent(true)
      if (asked.dev_code) setCode(asked.dev_code)
    } catch (problem) {
      setError(message(problem))
    } finally {
      setBusy(false)
    }
  }

  async function verify(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      const me = await signIn(phone, code)
      if (me.role === "customer") {
        // Refused here rather than by an empty screen: a customer's account is
        // perfectly valid, it is just not what this application is for.
        setError("Bu ilova xodimlar uchun. Xarid uchun Mini Bozor ilovasidan foydalaning.")
      }
    } catch (problem) {
      setError(message(problem))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="density-cozy grid min-h-full md:grid-cols-2">
      {/* ------------------------------------------------------------- the wall
       *
       * The half of the screen that is not the form. It is the same near-black
       * as the rail with the same blurred wash of the accent behind the mark,
       * so signing in is recognisably the front door of *this* building — and
       * so the first thing anybody sees each morning is not a white page with
       * a box floating in the middle of it.
       *
       * Hidden on a phone. A decorative half-screen on a 5" display is the
       * form pushed below the fold. */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-rail p-10 text-rail-ink md:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-24 -top-24 size-96 rounded-full bg-brand opacity-50 blur-[120px]"
        />
        <div className="relative z-10 flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-control bg-brand text-body font-bold text-brand-ink">
            MB
          </span>
          <span className="text-body font-semibold tracking-tight text-rail-ink">
            Mini Bozor
          </span>
        </div>
        <div className="relative z-10 max-w-sm">
          <p className="display text-rail-ink">Ombor. Do'kon. Yo'l.</p>
          <p className="mt-3 text-small text-rail-ink/70">
            Bitta hisob — uchala ish uchun. Nima qila olishingizni rolingiz
            hal qiladi.
          </p>
        </div>
        <p className="relative z-10 text-micro text-rail-ink/50">
          Xodimlar uchun. Xarid uchun Mini Bozor ilovasi bor.
        </p>
      </aside>

      {/* ------------------------------------------------------------- the form */}
      <div className="grid place-items-center bg-canvas p-6">
        <form
          onSubmit={sent ? verify : ask}
          className="w-full max-w-sm space-y-5 rounded-panel border border-panel-edge bg-surface p-6"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2 md:hidden">
              <span className="grid size-8 place-items-center rounded-control bg-brand text-brand-ink">
                MB
              </span>
              <span className="text-body font-semibold tracking-tight">Mini Bozor</span>
            </div>
            <h1 className="text-figure font-bold leading-tight tracking-tight">
              {sent ? "SMS kod" : "Kirish"}
            </h1>
            <p className="text-small text-ink-soft">
              {sent ? "Yuborilgan kodni kiriting" : "Telefon raqamingiz bilan kiring"}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="phone">Telefon</Label>
            <Input
              id="phone"
              name="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={phone}
              disabled={sent}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+998901234567"
              className="tabular"
            />
          </div>

          {sent ? (
            <div className="space-y-1.5">
              <Label htmlFor="code">SMS kod</Label>
              <Input
                id="code"
                name="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="123456"
                className="tabular tracking-widest"
              />
              <button
                type="button"
                className="text-micro text-ink-soft underline underline-offset-2 hover:text-ink"
                onClick={() => {
                  setSent(false)
                  setCode("")
                  setError("")
                }}
              >
                Raqamni o'zgartirish
              </button>
            </div>
          ) : null}

          {error ? (
            <p
              role="alert"
              className="rounded-control border border-danger/25 bg-danger-soft p-3 text-small text-danger"
            >
              {error}
            </p>
          ) : null}

          <Button type="submit" size="lg" disabled={busy} className="w-full">
            {busy ? "..." : sent ? "Kirish" : "Kod olish"}
          </Button>
        </form>
      </div>
    </div>
  )
}

function message(problem: unknown): string {
  if (problem instanceof ApiError) return problem.message
  // A failed fetch has no status and no body — the API is not answering at
  // all, which is a different problem to a refusal and reads as one.
  return "Server javob bermayapti. Ulanishni tekshiring."
}
