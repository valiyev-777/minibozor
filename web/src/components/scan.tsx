/**
 * The scan target — one component, one behaviour, every warehouse screen.
 *
 * A scanner gun and a phone camera both end at the same place: a string. The
 * gun is a keyboard that types very fast and presses Enter, so the wedge here
 * buffers keystrokes that arrive faster than a human types and acts on the
 * Enter — no focused input required, and **a real field always wins**: while
 * an input, textarea or contenteditable has focus, the person is typing and
 * the buffer stays out of it.
 *
 * The camera is the browser's own `BarcodeDetector`, which Android Chrome
 * has and the desk does not need. Where it is missing the component says so
 * in plain words and leaves manual entry to the screen — a 300 KB decoding
 * library to cover a browser this shop does not use is not worth its weight.
 * The camera closes itself the moment it reads one code.
 *
 * Either way the string goes through `GET /warehouse/scan` and the **typed
 * answer** is handed to the screen. The screen decides what a variant, a
 * cell or a miss means where it is standing — this component only knows how
 * to read.
 */

import { Camera, Loader2, ScanLine, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"

import { Panel } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { useScan } from "@/lib/queries"
import type { ScanAnswer } from "@/lib/types"

export type { ScanAnswer } from "@/lib/types"

// A gun "types" its code in a burst — tens of milliseconds between keys — and
// a person does not. Keys further apart than this start the buffer over, so
// somebody idly pressing letters never accidentally builds a code.
const GUN_GAP_MS = 60

// Shorter than any code we print. An Enter over less than this is a person
// pressing Enter, not a gun finishing a code.
const MIN_CODE = 3

/** The person is typing into a real control, so the field wins. */
function fieldHasFocus(): boolean {
  const focused = document.activeElement
  if (focused instanceof HTMLInputElement || focused instanceof HTMLTextAreaElement) {
    return true
  }
  return focused instanceof HTMLElement && focused.isContentEditable
}

export function ScanTarget({
  onAnswer,
  paused = false,
}: {
  onAnswer: (answer: ScanAnswer) => void
  /** Silences the wedge and the camera — for a screen whose moment is over. */
  paused?: boolean
}) {
  const scan = useScan()
  const [camera, setCamera] = useState(false)
  const [said, setSaid] = useState("")

  // Refs, not state: the buffer changes per keystroke and a gun is thirteen
  // keystrokes in a third of a second — that is not thirteen renders.
  const buffer = useRef("")
  const lastKey = useRef(0)

  // The latest callback, so the document listener never acts on a stale
  // closure after the screen re-renders around it.
  const answer = useRef(onAnswer)
  answer.current = onAnswer

  const mutate = scan.mutate
  const submit = useRef<(code: string) => void>(() => {})
  submit.current = (code: string) => {
    const trimmed = code.trim()
    if (!trimmed) return
    mutate(trimmed, { onSuccess: (got) => answer.current(got) })
  }

  useEffect(() => {
    if (paused) return
    const listen = (event: KeyboardEvent) => {
      if (fieldHasFocus()) {
        buffer.current = ""
        return
      }
      if (event.key === "Enter") {
        const code = buffer.current
        buffer.current = ""
        if (code.length >= MIN_CODE) {
          event.preventDefault()
          submit.current(code)
        }
        return
      }
      // Single printable characters only — arrows, F-keys and chords are the
      // person driving the screen, not a code arriving.
      if (event.key.length !== 1 || event.ctrlKey || event.metaKey || event.altKey) return
      const now = performance.now()
      buffer.current =
        now - lastKey.current <= GUN_GAP_MS ? buffer.current + event.key : event.key
      lastKey.current = now
    }
    document.addEventListener("keydown", listen)
    return () => document.removeEventListener("keydown", listen)
  }, [paused])

  // A phone that cannot detect barcodes is told so once, quietly, and the
  // manual field on the screen stays the way in.
  function openCamera() {
    setSaid("")
    if (!hasDetector()) {
      setSaid("Bu brauzerda kamera skaneri yo'q — kodni qo'lda yozing.")
      return
    }
    setCamera(true)
  }

  return (
    <div className="no-print flex flex-wrap items-center gap-2">
      <span
        className={cn(
          "flex h-control items-center gap-1.5 rounded-control bg-line-soft px-2.5 text-micro font-medium",
          paused ? "text-ink-faint" : "text-ink-soft",
        )}
        title="Skaner qurol shu ekranda ishlaydi — kodni o'qiting"
      >
        {scan.isPending ? (
          <Loader2 className="size-4 animate-spin text-brand" />
        ) : (
          <ScanLine className={cn("size-4", !paused && "text-brand")} />
        )}
        Skaner
      </span>
      <Button
        type="button"
        variant="secondary"
        size="icon"
        aria-label="Kamera bilan skanerlash"
        disabled={paused}
        onClick={openCamera}
      >
        <Camera />
      </Button>
      {said ? <span className="text-micro text-danger">{said}</span> : null}
      {camera && !paused ? (
        <CameraEye
          onRead={(code) => {
            setCamera(false)
            submit.current(code)
          }}
          onClose={() => setCamera(false)}
        />
      ) : null}
    </div>
  )
}

/**
 * The scan target wearing the strip every warehouse screen puts it in: the
 * reader, one line saying what a scan will do here, and — under a hairline —
 * whatever the last scan said back.
 *
 * It exists because `/qabul` already drew this strip by hand and three more
 * screens were about to copy it. A miss must look the same in every room or
 * somebody learns to ignore it in one of them.
 */
export function ScanBar({
  hint,
  said,
  tone = "danger",
  onAnswer,
  paused = false,
}: {
  /** What a scan does on this screen, in one line. */
  hint: string
  /** What the last scan said back — the loud part. */
  said?: string
  /** `danger` refuses, `good` confirms. A miss is never quiet. */
  tone?: "danger" | "good"
  onAnswer: (answer: ScanAnswer) => void
  paused?: boolean
}) {
  return (
    <Panel bare className="no-print">
      <div className="flex flex-wrap items-center gap-3 p-3">
        <ScanTarget onAnswer={onAnswer} paused={paused} />
        <p className="min-w-0 flex-1 text-micro text-ink-faint">{hint}</p>
      </div>
      {said ? (
        <p
          role="status"
          className={cn(
            "border-t border-line px-3 py-2 text-small font-semibold",
            tone === "good" ? "text-good" : "text-danger",
          )}
        >
          {said}
        </p>
      ) : null}
    </Panel>
  )
}

/** The words for a code the server could not place. Said the same way in
 *  every room, and always naming the code — "topilmadi" without the string
 *  is a person wondering whether the gun even fired. */
export function missWords(code: string): string {
  return `«${code}» hech narsaga to'g'ri kelmadi — yorliqni qayta o'qiting yoki qo'lda qidiring.`
}

// ---------------------------------------------------------------- the camera

// `BarcodeDetector` is not in TypeScript's DOM library yet, so its shape is
// written down here — only what this file calls.
type Detected = { rawValue: string }
type Detector = { detect(source: HTMLVideoElement): Promise<Detected[]> }
type DetectorMaker = new () => Detector

function hasDetector(): boolean {
  return Boolean((window as unknown as { BarcodeDetector?: DetectorMaker }).BarcodeDetector)
}

/**
 * The phone's eye. Opens the back camera, looks a few times a second, and
 * hands over the first code it reads — then the whole thing closes itself,
 * because one scan is one act and a camera left running is a battery gone by
 * lunch.
 */
function CameraEye({
  onRead,
  onClose,
}: {
  onRead: (code: string) => void
  onClose: () => void
}) {
  const video = useRef<HTMLVideoElement>(null)
  const [failed, setFailed] = useState("")

  // The latest handler, for the interval below.
  const read = useRef(onRead)
  read.current = onRead

  useEffect(() => {
    const Maker = (window as unknown as { BarcodeDetector?: DetectorMaker })
      .BarcodeDetector
    if (!Maker) return

    let stream: MediaStream | null = null
    let alive = true
    let timer = 0

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" } })
      .then((got) => {
        if (!alive) {
          got.getTracks().forEach((track) => track.stop())
          return
        }
        stream = got
        if (video.current) {
          video.current.srcObject = got
          void video.current.play()
        }
        const detector = new Maker()
        timer = window.setInterval(() => {
          const eye = video.current
          if (!eye || eye.readyState < 2) return
          detector
            .detect(eye)
            .then((found) => {
              if (!alive || !found.length) return
              alive = false
              read.current(found[0].rawValue)
            })
            .catch(() => {
              // A frame that would not decode is the next frame's job.
            })
        }, 200)
      })
      .catch(() => {
        setFailed("Kamera ochilmadi — ruxsat berilmagan bo'lishi mumkin. Kodni qo'lda yozing.")
      })

    return () => {
      alive = false
      window.clearInterval(timer)
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  // Escape is the way out of any mode.
  useEffect(() => {
    const listen = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", listen)
    return () => window.removeEventListener("keydown", listen)
  }, [onClose])

  // A portal, so a header that clips or transforms its children cannot pin
  // the viewfinder inside itself.
  return createPortal(
    <div className="no-print fixed inset-0 z-50 grid place-items-center bg-scrim/70 p-4">
      <div className="w-full max-w-sm space-y-2 rounded-panel border border-line bg-surface p-3 shadow-raised">
        <div className="flex items-center justify-between gap-2">
          <span className="text-small font-semibold">Kamera bilan skanerlash</span>
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Yopish">
            <X />
          </Button>
        </div>
        {failed ? (
          <p className="rounded-control bg-danger-soft p-3 text-small text-danger">{failed}</p>
        ) : (
          <>
            {/* Muted and inline: iOS Safari will not start an unmuted stream,
                and a fullscreen takeover is not what a viewfinder is. */}
            <video
              ref={video}
              muted
              playsInline
              className="aspect-[4/3] w-full rounded-control bg-scrim object-cover"
            />
            <p className="text-micro text-ink-soft">
              Kodni ramkaga tuting — o'qilgan zahoti oyna o'zi yopiladi.
            </p>
          </>
        )}
      </div>
    </div>,
    document.body,
  )
}
