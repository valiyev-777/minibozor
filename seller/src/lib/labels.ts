import type { SupplyStatus } from "@/api/types"

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
