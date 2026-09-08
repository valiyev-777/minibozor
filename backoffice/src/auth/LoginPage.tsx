import * as React from "react"
import { Building2 } from "lucide-react"
import { Button } from "@/ui/button"
import { Field, Input } from "@/ui/field"
import { messageOf } from "@/ui/states"
import { useSession } from "./session"
import { t } from "@/lib/labels"

/**
 * Two steps, and the second one only exists once the first has succeeded.
 *
 * A single form with both boxes would be a form where the code box is dead
 * until somebody presses a button beside it, which is a worse thing to look
 * at than a form that changes. The phone stays on screen in step two with the
 * way back beside it, because the commonest reason to be stuck there is a
 * typo in the number.
 *
 * The same screen as the seller cabinet's, deliberately: one OTP flow, one
 * shape, and a member of staff who has seen one has seen the other.
 */
export function LoginPage() {
  const session = useSession()
  const [phone, setPhone] = React.useState("+998")
  const [code, setCode] = React.useState("")
  const [sent, setSent] = React.useState(false)
  const [devCode, setDevCode] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const request = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const requested = await session.requestCode(phone.trim())
      setSent(true)
      // Dev builds answer with the code, so the whole flow can be walked
      // without an SMS gateway. Shown rather than filled in: typing it is
      // part of what is being tested.
      setDevCode(requested.dev_code ?? null)
    } catch (problem) {
      setError(messageOf(problem))
    } finally {
      setBusy(false)
    }
  }

  const verify = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await session.signIn(phone.trim(), code.trim())
    } catch (problem) {
      setError(messageOf(problem))
    } finally {
      setBusy(false)
    }
  }

  const reason = session.status === "anonymous" ? session.reason : undefined

  return (
    <main className="flex min-h-full items-center justify-center px-5 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <span className="inline-flex size-11 items-center justify-center rounded-[var(--radius-panel)] bg-brand-soft text-brand-deep">
            <Building2 className="size-5" />
          </span>
          <h1 className="text-lg font-semibold text-ink">Mini Bozor</h1>
          <p className="text-[length:var(--text-small)] text-ink-soft">{t.app}</p>
        </div>

        {reason ? (
          <p
            role="alert"
            className="rounded-[var(--radius-control)] bg-warn-soft px-4 py-3 text-[length:var(--text-small)] text-warn-ink"
          >
            {reason}
          </p>
        ) : null}

        <form
          onSubmit={sent ? verify : request}
          className="space-y-4 rounded-[var(--radius-panel)] border border-line bg-surface p-5"
        >
          <h2 className="text-[length:var(--text-body)] font-semibold text-ink">
            {t.signInTitle}
          </h2>

          <Field id="phone" label={t.phone} error={sent ? undefined : error}>
            {(props) => (
              <Input
                {...props}
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                value={phone}
                disabled={sent}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+998900000001"
              />
            )}
          </Field>

          {sent ? (
            <Field
              id="code"
              label={t.code}
              error={error}
              hint={devCode ? `${t.devCode}: ${devCode}` : undefined}
            >
              {(props) => (
                <Input
                  {...props}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="123456"
                />
              )}
            </Field>
          ) : null}

          <Button type="submit" variant="primary" size="lg" block disabled={busy}>
            {sent ? t.signIn : t.sendCode}
          </Button>

          {sent ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              block
              onClick={() => {
                setSent(false)
                setCode("")
                setError(null)
                setDevCode(null)
              }}
            >
              {t.changePhone}
            </Button>
          ) : null}
        </form>
      </div>
    </main>
  )
}
