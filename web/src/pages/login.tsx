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
    <div className="density-cozy grid min-h-full place-items-center bg-canvas p-6">
      <form
        onSubmit={sent ? verify : ask}
        className="w-full max-w-sm space-y-5 rounded-panel border bg-surface p-6"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="grid size-8 place-items-center rounded-control bg-brand text-brand-ink">
              MB
            </span>
            <span className="text-lg font-semibold tracking-tight">Mini Bozor</span>
          </div>
          <p className="text-small text-ink-soft">
            {sent ? "SMS kodini kiriting" : "Telefon raqamingiz bilan kiring"}
          </p>
        </div>

        <div className="space-y-2">
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
            className="h-control"
          />
        </div>

        {sent ? (
          <div className="space-y-2">
            <Label htmlFor="code">SMS kod</Label>
            <Input
              id="code"
              name="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="123456"
              className="h-control tabular tracking-widest"
            />
            <button
              type="button"
              className="text-micro text-ink-soft underline underline-offset-2"
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
          <p role="alert" className="rounded-control bg-danger-soft p-3 text-small text-danger">
            {error}
          </p>
        ) : null}

        <Button type="submit" disabled={busy} className="h-control w-full">
          {busy ? "..." : sent ? "Kirish" : "Kod olish"}
        </Button>
      </form>
    </div>
  )
}

function message(problem: unknown): string {
  if (problem instanceof ApiError) return problem.message
  // A failed fetch has no status and no body — the API is not answering at
  // all, which is a different problem to a refusal and reads as one.
  return "Server javob bermayapti. Ulanishni tekshiring."
}
