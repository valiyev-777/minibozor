/**
 * The map the round is driven on — Leaflet over OpenStreetMap tiles.
 *
 * ------------------------------------------------------------- why Leaflet raw
 *
 * `leaflet` and not `react-leaflet`. The wrapper exists to turn a map into
 * declarative children, which is worth having when a page has many maps or
 * when markers come and go with the render tree. This app has one map with a
 * handful of pins on it, and the wrapper would add a second dependency, a
 * second release cadence and a second set of React-version constraints in
 * exchange for the twenty lines of `useEffect` below. The imperative API is
 * also the honest shape for what this does: the map is a long-lived object
 * that outlives renders, and pretending otherwise is how a map ends up being
 * torn down and rebuilt every time a stop is selected.
 *
 * -------------------------------------------------------------- when it fails
 *
 * **A courier in a basement still has to finish the round**, so the map is
 * treated as a convenience the whole time and never as the screen. Three
 * things go wrong and each is said out loud rather than shown as a grey box:
 *
 *   - **no network** — `navigator.onLine` is false, or tiles come back as
 *     errors. Watched rather than assumed: a phone that drops to no signal
 *     mid-round must degrade *while the screen is open*, not only on load.
 *   - **tiles never arrive** — online by the browser's reckoning but nothing
 *     renders, which is what a captive wifi portal looks like. A timer catches
 *     it, because "no error and no tile" fires no event at all.
 *   - **no pins** — every stop on the round predates the shop recording
 *     coordinates. There is nothing wrong with the network and nothing to draw;
 *     saying "no connection" here would send somebody to look for wifi.
 *
 * In all three the caller gets told, the map area prints the reason, and the
 * stop list — which is the thing that actually gets the parcels delivered —
 * takes the screen.
 *
 * **Tiles are never precached.** They are third-party raster from
 * `tile.openstreetmap.org`, fetched at runtime; the service worker precaches
 * this app's own build output and nothing else, and no runtime caching rule is
 * declared for that host in `vite.config.ts`. Putting a city's worth of tiles
 * into a warehouse phone's storage budget would evict the app itself.
 */

import L from "leaflet"
import { MapPinOff, WifiOff } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import "leaflet/dist/leaflet.css"

import { cn } from "@/lib/cn"

/** Tashkent, which is where every stop in this shop's round is. Used only as
 *  the opening view before the pins arrive — the map fits itself to them the
 *  moment there is more than one. */
const CITY: [number, number] = [41.2995, 69.2401]

const TILES = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
const CREDIT = '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>'

/** How long a map gets to put one tile on screen before it is declared down.
 *  Eight seconds is long enough for a bad 3G tile and short enough that a
 *  courier is not staring at nothing while deciding whether to scroll. */
const PATIENCE = 8000

export type Trouble = "offline" | "tiles" | "nopins"

export const TROUBLE_WORD: Record<Trouble, string> = {
  offline: "Internet yo'q — xarita yuklanmadi",
  tiles: "Xarita yuklanmadi",
  nopins: "Bekatlar xaritada belgilanmagan",
}

const TROUBLE_WHAT: Record<Trouble, string> = {
  offline: "Bekatlar ro'yxati quyida — yetkazishni davom ettiraverasiz.",
  tiles: "Aloqa zaif ko'rinadi. Bekatlar ro'yxati quyida ishlaydi.",
  nopins: "Bu buyurtmalarda koordinata yo'q. Manzillar ro'yxatda to'liq turibdi.",
}

/** One pin. A stop with no coordinates never becomes one of these — it stays
 *  in the list instead, which is the whole rule. */
export type Pin = {
  id: number
  /** The stop number the courier reads, 1-based. */
  n: number
  lat: number
  lng: number
  state: "past" | "now" | "next"
}

export function RouteMap({
  pins,
  activeId,
  onPick,
  onTrouble,
  className,
}: {
  pins: Pin[]
  activeId?: number
  onPick?: (id: number) => void
  /** Told on every change, so the screen around the map can give the list the
   *  room the map is not using. */
  onTrouble?: (trouble: Trouble | null) => void
  className?: string
}) {
  const host = useRef<HTMLDivElement | null>(null)
  const map = useRef<L.Map | null>(null)
  const layer = useRef<L.LayerGroup | null>(null)
  const drawn = useRef<Map<number, L.Marker>>(new Map())

  const [tilesUp, setTilesUp] = useState(false)
  const [tilesFailed, setTilesFailed] = useState(false)
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  )
  const [waited, setWaited] = useState(false)

  // Which of the three troubles, in the order a person would ask. No pins is
  // first because it is a fact about the data and no amount of signal fixes
  // it; saying "no connection" over a round with no coordinates sends the
  // courier to look for wifi that would change nothing.
  const trouble: Trouble | null = !pins.length
    ? "nopins"
    : !online
      ? "offline"
      : tilesFailed || (waited && !tilesUp)
        ? "tiles"
        : null

  useEffect(() => {
    onTrouble?.(trouble)
  }, [trouble, onTrouble])

  // A phone that walks into a basement has to degrade while the screen is
  // open, not only when it was opened.
  useEffect(() => {
    const up = () => {
      setOnline(true)
      // A fresh chance: the layer retries its own tiles on the next redraw.
      setTilesFailed(false)
      setWaited(false)
      map.current?.invalidateSize()
    }
    const down = () => setOnline(false)
    window.addEventListener("online", up)
    window.addEventListener("offline", down)
    return () => {
      window.removeEventListener("online", up)
      window.removeEventListener("offline", down)
    }
  }, [])

  // "No error and no tile" fires no event, which is exactly what a captive
  // wifi portal looks like. Only a clock catches it.
  useEffect(() => {
    if (tilesUp) return
    const timer = window.setTimeout(() => setWaited(true), PATIENCE)
    return () => window.clearTimeout(timer)
  }, [tilesUp])

  // The map object itself, made once and kept. Rebuilding it per render would
  // reset the pan and zoom every time a stop is tapped.
  useEffect(() => {
    if (!host.current || map.current) return

    const made = L.map(host.current, {
      center: CITY,
      zoom: 12,
      // A map inside a scrolling phone screen must not eat the scroll. Panning
      // is by drag; zoom is by the two controls Leaflet draws.
      scrollWheelZoom: false,
      attributionControl: true,
      zoomControl: false,
    })

    const tiles = L.tileLayer(TILES, {
      maxZoom: 19,
      attribution: CREDIT,
      // The class the dark theme's filter hangs off — see `.kuryer-tiles`.
      // On the tile pane alone, so the route and the pins drawn over it keep
      // their real colours.
      className: "kuryer-tiles",
    })
    tiles.on("tileload", () => setTilesUp(true))
    tiles.on("tileerror", () => setTilesFailed(true))
    tiles.addTo(made)

    layer.current = L.layerGroup().addTo(made)
    map.current = made

    return () => {
      made.remove()
      map.current = null
      layer.current = null
      drawn.current.clear()
    }
  }, [])

  // The pins and the line between them, redrawn whenever the round changes.
  useEffect(() => {
    const group = layer.current
    const made = map.current
    if (!group || !made) return

    group.clearLayers()
    drawn.current.clear()

    // The route, in the order the stops are driven, and only through the ones
    // that have a pin: a stop with no coordinates must not put a kink in the
    // line by being guessed at.
    if (pins.length > 1) {
      L.polyline(
        pins.map((pin) => [pin.lat, pin.lng] as [number, number]),
        { className: "kuryer-route", weight: 6, opacity: 1 },
      ).addTo(group)
    }

    for (const pin of pins) {
      const marker = L.marker([pin.lat, pin.lng], {
        icon: L.divIcon({
          className: "",
          html: `<span class="kuryer-pin kuryer-pin-${pin.state}">${pin.n}</span>`,
          iconSize: [34, 34],
          iconAnchor: [17, 17],
        }),
        keyboard: true,
        title: `${pin.n}-bekat`,
      })
      if (onPick) marker.on("click", () => onPick(pin.id))
      marker.addTo(group)
      drawn.current.set(pin.id, marker)
    }

    // Fit to the whole round rather than to the current stop: a courier reads
    // this to decide what order to drive in, and a map zoomed to one door
    // answers a question nobody asked.
    if (pins.length > 1) {
      made.fitBounds(
        L.latLngBounds(pins.map((pin) => [pin.lat, pin.lng] as [number, number])),
        { padding: [48, 48], maxZoom: 15 },
      )
    } else if (pins.length === 1) {
      made.setView([pins[0].lat, pins[0].lng], 15)
    }
  }, [pins, onPick])

  // The selected stop is brought into view without re-fitting everything.
  useEffect(() => {
    if (!map.current || activeId === undefined) return
    const marker = drawn.current.get(activeId)
    if (marker) map.current.panTo(marker.getLatLng(), { animate: true })
  }, [activeId])

  // The map is left mounted under the explanation rather than unmounted: it
  // costs nothing while it has no tiles, and keeping it means the moment the
  // signal comes back the tiles simply appear. Tearing it down and rebuilding
  // it would drop the pan and the zoom the courier had set.
  return (
    <div className={cn("kuryer-map relative isolate", className)}>
      <div ref={host} className="absolute inset-0 bg-kuryer-ground-deep" />
      {trouble ? (
        <div className="absolute inset-0 grid place-items-center bg-kuryer-ground-deep/95 px-6">
          <div className="flex max-w-80 flex-col items-center gap-2 text-center">
            {trouble === "nopins" ? (
              <MapPinOff className="size-8 text-kuryer-ink-faint" />
            ) : (
              <WifiOff className="size-8 text-kuryer-ink-faint" />
            )}
            <p className="text-body font-semibold text-kuryer-ink">
              {TROUBLE_WORD[trouble]}
            </p>
            <p className="text-small text-kuryer-ink-soft">{TROUBLE_WHAT[trouble]}</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}
