import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import { api } from "@/api/client"
import type { StaffSlot } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FieldError, Hint, Input, Label } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { day, money } from "@/lib/utils"

const KEY = ["staff", "slots"]

function iso(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function addDays(from: string, count: number): string {
  const date = new Date(`${from}T00:00:00`)
  date.setDate(date.getDate() + count)
  return iso(date)
}

type WindowDraft = {
  start_time: string
  end_time: string
  capacity: string
  price: string
  note: string
}

const BLANK: WindowDraft = {
  start_time: "09:00",
  end_time: "13:00",
  capacity: "20",
  price: "0",
  note: "",
}

export function SlotsPage() {
  const today = iso(new Date())
  const [from, setFrom] = React.useState(today)
  const [to, setTo] = React.useState(addDays(today, 14))
  const [opening, setOpening] = React.useState(false)
  const [editing, setEditing] = React.useState<StaffSlot | null>(null)

  const query = useQuery({
    queryKey: [...KEY, from, to],
    queryFn: () =>
      api<StaffSlot[]>("/staff/delivery/slots", { query: { from_day: from, to_day: to } }),
  })

  const columns: Column<StaffSlot>[] = [
    {
      key: "day",
      header: "Kun",
      sortValue: (row) => row.day,
      cell: (row) => <span className="tabular text-ink">{day(row.day)}</span>,
    },
    {
      key: "window",
      header: "Oyna",
      sortValue: (row) => `${row.day}${row.start_time}`,
      cell: (row) => (
        <span className="tabular font-medium text-ink">
          {row.start_time}–{row.end_time}
        </span>
      ),
    },
    {
      key: "note",
      header: "Izoh",
      cell: (row) => (
        <span className="text-ink-soft">
          {row.note || "—"}
          {row.express ? (
            <Badge tone="warn" className="ml-1.5">
              Tezkor
            </Badge>
          ) : null}
        </span>
      ),
    },
    {
      key: "price",
      header: "Ustama",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.price,
      cell: (row) => (row.price ? money(row.price) : "bepul"),
    },
    {
      key: "capacity",
      header: "Sig'im",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.capacity_left,
      cell: (row) =>
        row.capacity_left > 0 ? (
          row.capacity_left
        ) : (
          <span className="font-medium text-danger">0</span>
        ),
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <Button size="sm" onClick={() => setEditing(row)}>
          Sig'imni o'zgartirish
        </Button>
      ),
    },
  ]

  return (
    <Page
      title="Yetkazish oynalari"
      hint="Sig'im buyurtma berilganda kamayadi. Tugagan oyna mijozga ko'rinmaydi."
      actions={
        <Button variant="primary" onClick={() => setOpening(true)}>
          <Plus />
          Oyna ochish
        </Button>
      }
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Bu oraliqda oyna yo'q"
        emptyHint="«Oyna ochish» bilan bir necha kunga birdan ochish mumkin."
        clientPageSize={40}
        toolbar={
          <>
            <div className="flex items-center gap-1.5">
              <Label htmlFor="from">Dan</Label>
              <Input
                id="from"
                type="date"
                className="w-36"
                value={from}
                onChange={(event) => setFrom(event.target.value)}
              />
            </div>
            <div className="flex items-center gap-1.5">
              <Label htmlFor="to">Gacha</Label>
              <Input
                id="to"
                type="date"
                className="w-36"
                value={to}
                onChange={(event) => setTo(event.target.value)}
              />
            </div>
            <Hint>{query.data?.length ?? 0} ta oyna</Hint>
          </>
        }
      />

      {opening ? <OpenWindows from={from} onClose={() => setOpening(false)} /> : null}
      {editing ? <EditCapacity slot={editing} onClose={() => setEditing(null)} /> : null}
    </Page>
  )
}

function OpenWindows({ from, onClose }: { from: string; onClose: () => void }) {
  const [start, setStart] = React.useState(from)
  const [days, setDays] = React.useState("14")
  const [windows, setWindows] = React.useState<WindowDraft[]>([BLANK])

  const count = Math.max(1, Math.min(60, Number(days) || 1))
  const dates = Array.from({ length: count }, (_, index) => addDays(start, index))

  const broken = windows.some((w) => w.end_time <= w.start_time)

  const open = useAction<void, StaffSlot[]>({
    run: () =>
      api<StaffSlot[]>("/staff/delivery/slots", {
        method: "POST",
        json: {
          days: dates,
          windows: windows.map((w) => ({
            start_time: w.start_time,
            end_time: w.end_time,
            capacity: Number(w.capacity) || 0,
            price: Number(w.price) || 0,
            note: w.note,
          })),
        },
      }),
    invalidate: [KEY],
    success: (made) =>
      made.length
        ? `${made.length} ta oyna ochildi`
        : "Yangi oyna qo'shilmadi — bu oynalar allaqachon bor",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Oyna ochish"
      description={`${count} kun × ${windows.length} oyna = ${count * windows.length} ta yozuv`}
      confirmLabel="Ochish"
      disabled={broken || windows.length === 0}
      pending={open.isPending}
      onConfirm={() => open.mutate()}
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="start">Boshlanish kuni</Label>
            <Input
              id="start"
              type="date"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </div>
          <div className="w-24 space-y-1">
            <Label htmlFor="days">Necha kun</Label>
            <Input
              id="days"
              type="number"
              min={1}
              max={60}
              value={days}
              onChange={(event) => setDays(event.target.value)}
            />
          </div>
        </div>

        <Hint>
          Bir kunga bittadan ochish haftaga 28 chaqiruv bo'ladi — shuning uchun bir
          so'rovda butun oraliq ochiladi. Allaqachon bor oynalar o'tkazib yuboriladi.
        </Hint>

        <div className="space-y-2">
          {windows.map((window, index) => (
            <div key={index} className="rounded border border-line p-2">
              <div className="flex items-end gap-1.5">
                <div className="w-24 space-y-1">
                  <Label>Dan</Label>
                  <Input
                    type="time"
                    value={window.start_time}
                    onChange={(event) =>
                      setWindows((list) =>
                        list.map((w, i) =>
                          i === index ? { ...w, start_time: event.target.value } : w,
                        ),
                      )
                    }
                  />
                </div>
                <div className="w-24 space-y-1">
                  <Label>Gacha</Label>
                  <Input
                    type="time"
                    value={window.end_time}
                    onChange={(event) =>
                      setWindows((list) =>
                        list.map((w, i) =>
                          i === index ? { ...w, end_time: event.target.value } : w,
                        ),
                      )
                    }
                  />
                </div>
                <div className="w-20 space-y-1">
                  <Label>Sig'im</Label>
                  <Input
                    type="number"
                    min={0}
                    value={window.capacity}
                    onChange={(event) =>
                      setWindows((list) =>
                        list.map((w, i) =>
                          i === index ? { ...w, capacity: event.target.value } : w,
                        ),
                      )
                    }
                  />
                </div>
                <div className="w-24 space-y-1">
                  <Label>Ustama</Label>
                  <Input
                    type="number"
                    min={0}
                    step={1000}
                    value={window.price}
                    onChange={(event) =>
                      setWindows((list) =>
                        list.map((w, i) =>
                          i === index ? { ...w, price: event.target.value } : w,
                        ),
                      )
                    }
                  />
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  disabled={windows.length === 1}
                  aria-label="Oynani olib tashlash"
                  onClick={() => setWindows((list) => list.filter((_, i) => i !== index))}
                >
                  <Trash2 />
                </Button>
              </div>
              <div className="mt-1.5 space-y-1">
                <Label>Izoh</Label>
                <Input
                  value={window.note}
                  placeholder="Ertalabki yetkazish"
                  onChange={(event) =>
                    setWindows((list) =>
                      list.map((w, i) => (i === index ? { ...w, note: event.target.value } : w)),
                    )
                  }
                />
              </div>
              {window.end_time <= window.start_time ? (
                <FieldError>Tugash vaqti boshlanishidan keyin bo'lishi kerak.</FieldError>
              ) : null}
            </div>
          ))}
        </div>

        <Button size="sm" onClick={() => setWindows((list) => [...list, BLANK])}>
          <Plus />
          Yana oyna
        </Button>
      </div>
    </ConfirmDialog>
  )
}

function EditCapacity({ slot, onClose }: { slot: StaffSlot; onClose: () => void }) {
  const [capacity, setCapacity] = React.useState(String(slot.capacity_left))
  const [price, setPrice] = React.useState(String(slot.price))

  const save = useAction<void, StaffSlot>({
    run: () =>
      api<StaffSlot>(`/staff/delivery/slots/${slot.id}`, {
        method: "PATCH",
        json: { capacity_left: Number(capacity) || 0, price: Number(price) || 0 },
      }),
    invalidate: [KEY],
    success: "Oyna o'zgartirildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Sig'im va ustama"
      description={`${day(slot.day)} · ${slot.start_time}–${slot.end_time}`}
      confirmLabel="Saqlash"
      pending={save.isPending}
      onConfirm={() => save.mutate()}
    >
      <div className="flex gap-2">
        <div className="flex-1 space-y-1">
          <Label htmlFor="capacity">Sig'im</Label>
          <Input
            id="capacity"
            type="number"
            min={0}
            autoFocus
            value={capacity}
            onChange={(event) => setCapacity(event.target.value)}
          />
          <Hint>Hozir: {slot.capacity_left}</Hint>
        </div>
        <div className="flex-1 space-y-1">
          <Label htmlFor="slot-price">Ustama (so'm)</Label>
          <Input
            id="slot-price"
            type="number"
            min={0}
            step={1000}
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
          <Hint>Har bir o'zgarish audit jurnaliga tushadi.</Hint>
        </div>
      </div>
    </ConfirmDialog>
  )
}
