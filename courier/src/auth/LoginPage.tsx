import * as React from "react"
import { toast } from "sonner"
import { ApiError } from "@/api/client"
import type { OtpRequested } from "@/api/types"
import { Button, Field, Panel } from "@/components/ui"
import { prettyPhone, toApiPhone } from "@/lib/format"
import { useSession } from "./session"

/**
 * The same OTP every customer uses. The role is the only difference, which is
 * why there is no second password store and no second login screen to drift
 * from the first.
 */
export function LoginPage() {
  const session = useSession()
  const reason = session.status === "anonymous" ? session.reason : undefined

  const [phone, setPhone] = React.useState("")
  const [code, setCode] = React.useState("")
  const [sent, setSent] = React.useState<OtpRequested | null>(null)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const digits = phone.replace(/\D/g, "")
  const phoneReady = digits.length === 9 || digits.length === 12

  async function requestCode(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      setSent(await session.requestCode(toApiPhone(phone)))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Kod yuborilmadi.")
    } finally {
      setBusy(false)
    }
  }

  async function signIn(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await session.signIn(toApiPhone(phone), code)
    } catch (e) {
      // A role refusal is not a typo to correct on this screen — it is a
      // different account. Say it and send them back to the number field.
      if (e instanceof ApiError && e.status === 403) {
        setSent(null)
        setCode("")
        toast.error(e.message, { duration: 10_000 })
        setError(e.message)
      } else {
        setError(e instanceof ApiError ? e.message : "Kirish amalga oshmadi.")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-md flex-col justify-between p-5 pb-safe">
      <div>
        <h1 className="mt-8 text-4xl font-bold">MiniBozor</h1>
        <p className="mt-1 text-xl font-semibold text-ink-soft">Kuryer</p>

        {reason ? (
          <Panel tone="bad" className="mt-6">
            <p className="text-lg font-semibold text-danger">{reason}</p>
          </Panel>
        ) : null}

        {!sent ? (
          <form onSubmit={requestCode} className="mt-8 space-y-5">
            <Field
              label="Telefon raqami"
              inputMode="tel"
              autoComplete="tel"
              placeholder="90 123 45 67"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              error={error}
            />
            <Button type="submit" busy={busy} disabled={!phoneReady}>
              Kod olish
            </Button>
          </form>
        ) : (
          <form onSubmit={signIn} className="mt-8 space-y-5">
            <p className="text-lg text-ink-soft">
              Kod yuborildi: <span className="font-semibold text-ink">{prettyPhone(toApiPhone(phone))}</span>
            </p>
            {/* The dev server echoes the code back rather than sending an SMS,
                so a tester need not own the SIM. It is null in production. */}
            {sent.dev_code ? (
              <Panel tone="cash">
                <p className="text-base text-ink-soft">Test kodi</p>
                <p className="text-3xl font-bold tracking-widest">{sent.dev_code}</p>
              </Panel>
            ) : null}
            <Field
              label="SMS kod"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              error={error}
            />
            <Button type="submit" busy={busy} disabled={code.length < 4}>
              Kirish
            </Button>
            <Button
              type="button"
              tone="ghost"
              onClick={() => {
                setSent(null)
                setCode("")
                setError(null)
              }}
            >
              Raqamni o'zgartirish
            </Button>
          </form>
        )}
      </div>

      <p className="pt-8 text-center text-base text-ink-soft">
        Kirish uchun internet kerak. Kirgandan keyin ilova tarmoqsiz ham ishlaydi.
      </p>
    </div>
  )
}
