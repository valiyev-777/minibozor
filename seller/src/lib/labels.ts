import type {
  SettlementStatus,
  StatementLineKind,
  SupplyStatus,
} from "@/api/types"

/**
 * Uzbek words for the enum values the API sends.
 *
 * Presentation only. What a supply may do next is never decided here — the
 * backend answers with the status and refuses an illegal move with a 409 and
 * an explanation, which is what the seller sees.
 */
export const SUPPLY_STATUS: Record<SupplyStatus, string> = {
  declared: "Kutilmoqda",
  received: "Qabul qilingan",
  cancelled: "Bekor qilingan",
}

export const SUPPLY_TONE: Record<SupplyStatus, "neutral" | "brand" | "good" | "warn" | "danger"> = {
  declared: "warn",
  received: "good",
  cancelled: "neutral",
}

/** Why a count moved. Keyed loosely so an added kind shows its raw name
 *  rather than blanking the cell. */
export const MOVEMENT_KIND: Record<string, string> = {
  opening: "Boshlang'ich",
  intake: "Kirim",
  sale: "Sotuv",
  cancel_return: "Bekor qilindi",
  customer_return: "Mijoz qaytardi",
  write_off: "Yaroqsizga chiqarildi",
  count_adjustment: "Sanoq tuzatishi",
  seller_return: "Sizga qaytarildi",
}

// ------------------------------------------------------------------ payouts

export const SETTLEMENT_STATUS: Record<SettlementStatus, string> = {
  open: "Ochiq",
  closed: "Tasdiqlangan",
  paid: "To'langan",
}

export const SETTLEMENT_TONE: Record<
  SettlementStatus,
  "neutral" | "brand" | "good" | "warn" | "danger"
> = {
  open: "warn",
  closed: "brand",
  paid: "good",
}

/**
 * What one row of a statement is.
 *
 * Worded from the seller's side, not the platform's: the backoffice calls a
 * refunded commission "Komissiya qaytdi" because it is money the platform
 * gave back, and here it reads as money returned *to you* — the same row,
 * described by whose account it lands in.
 */
export const LINE_KIND: Record<StatementLineKind, string> = {
  sale: "Sotildi",
  commission: "Komissiya",
  fulfilment: "Yig'ish-yetkazish",
  refund: "Qaytarildi",
  refund_commission: "Komissiya qaytarildi",
  storage: "Saqlash",
  adjustment: "Tuzatish",
}

/** Which side of the ledger a kind falls on, for the eye rather than the sum. */
export const LINE_CREDIT: Record<StatementLineKind, boolean> = {
  sale: true,
  commission: false,
  fulfilment: false,
  refund: false,
  refund_commission: true,
  storage: false,
  adjustment: true,
}
