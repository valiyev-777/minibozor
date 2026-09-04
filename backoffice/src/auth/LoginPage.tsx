import * as React from "react"
import { ApiError } from "@/api/client"
import { useSession } from "@/auth/session"
import { Button } from "@/components/ui/button"
import { FieldError, Hint, Input, Label } from "@/components/ui/field"

const PHONE = /^\+998\d{9}$/

export function LoginPage({ reason }: { reason?: string }) {
  const { requestCode, signIn } = useSession()
  const [phone, setPhone] = React.useState("+998")
  const [code, setCode] = React.useState("")
  const [devCode, setDevCode] = React.useState<string | null>(null)
  const [step, setStep] = React.useState<"phone" | "code">("phone")
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  async function run(work: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await work()
    } catch (e) {
      // The backend explains itself — a wrong code, an expired one, a role
      // this panel is not for. Showing our own sentence instead would replace
      // an answer with a shrug.
      setError(e instanceof ApiError ? e.message : "So'rov bajarilmadi.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-xs">
        <div className="mb-5">
          <p className="text-[15px] font-semibold text-ink">Mini Bozor</p>
          <p className="text-[12px] text-ink-soft">Operator paneli</p>
        </div>

        {reason ? (
          <p className="mb-4 rounded border border-danger/20 bg-danger-soft px-2.5 py-2 text-[12px] font-medium text-danger">
            {reason}
          </p>
        ) : null}

        <form
          className="space-y-3 rounded-lg border border-line bg-surface p-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (step === "phone") {
              void run(async () => {
                const requested = await requestCode(phone)
                setDevCode(requested.dev_code ?? null)
                setStep("code")
              })
            } else {
              void run(() => signIn(phone, code))
            }
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="phone">Telefon raqami</Label>
            <Input
              id="phone"
              inputMode="tel"
              autoComplete="username"
              value={phone}
              disabled={step === "code"}
              onChange={(event) => setPhone(event.target.value.trim())}
              placeholder="+998901234567"
            />
          </div>

          {step === "code" ? (
            <div className="space-y-1">
              <Label htmlFor="code">SMS kod</Label>
              <Input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                maxLength={6}
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                placeholder="123456"
              />
              {devCode ? <Hint>Dev muhitida kod: {devCode}</Hint> : null}
            </div>
          ) : null}

          <FieldError>{error}</FieldError>

          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={busy || (step === "phone" ? !PHONE.test(phone) : code.length < 4)}
          >
            {busy ? "…" : step === "phone" ? "Kod olish" : "Kirish"}
          </Button>

          {step === "code" ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => {
                setStep("phone")
                setCode("")
                setError(null)
              }}
            >
              Raqamni o'zgartirish
            </Button>
          ) : null}
        </form>
      </div>
    </div>
  )
}
