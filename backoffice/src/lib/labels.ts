import type {
  OrderStatus,
  ProductStatus,
  ReturnStatus,
  ReviewStatus,
  SettlementStatus,
  StatementLineKind,
  UserRole,
} from "@/api/types"

/**
 * Uzbek words for the enum values the API sends.
 *
 * Presentation only. Which transitions are *possible* is never decided here —
 * that comes from `next_statuses` on the response, which the backend builds
 * from `app/transitions.py`. A second copy of those rules in the browser would
 * be a second copy to keep in step, and it would be the one that was wrong.
 */
export const ORDER_STATUS: Record<OrderStatus, string> = {
  placed: "Qabul qilindi",
  packing: "Yig'ilmoqda",
  shipped: "Yo'lda",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilindi",
  returned: "Qaytarildi",
}

export const RETURN_STATUS: Record<ReturnStatus, string> = {
  submitted: "Yuborilgan",
  approved: "Tasdiqlangan",
  rejected: "Rad etilgan",
  refunded: "Puli qaytarilgan",
}

export const REVIEW_STATUS: Record<ReviewStatus, string> = {
  moderating: "Tekshirilmoqda",
  published: "E'lon qilingan",
  rejected: "Rad etilgan",
}

export const ROLE: Record<UserRole, string> = {
  customer: "Mijoz",
  admin: "Administrator",
  operator: "Operator",
  warehouse: "Ombor",
  courier: "Kuryer",
  seller: "Sotuvchi",
}

type Tone = "neutral" | "accent" | "good" | "warn" | "danger"

export const ORDER_TONE: Record<OrderStatus, Tone> = {
  placed: "accent",
  packing: "warn",
  shipped: "warn",
  delivered: "good",
  cancelled: "danger",
  returned: "neutral",
}

export const RETURN_TONE: Record<ReturnStatus, Tone> = {
  submitted: "accent",
  approved: "warn",
  rejected: "danger",
  refunded: "good",
}

export const REVIEW_TONE: Record<ReviewStatus, Tone> = {
  moderating: "accent",
  published: "good",
  rejected: "danger",
}

export const MOVEMENT_KIND: Record<
  | "opening" | "intake" | "sale" | "cancel_return"
  | "customer_return" | "write_off" | "count_adjustment" | "seller_return",
  string
> = {
  opening: "Boshlang'ich qoldiq",
  intake: "Kirim",
  sale: "Sotuv",
  cancel_return: "Bekor qilindi",
  customer_return: "Mijoz qaytardi",
  write_off: "Yaroqsizga chiqarildi",
  count_adjustment: "Sanoq tuzatishi",
  seller_return: "Sotuvchiga qaytarildi",
}

export const SUPPLY_STATUS: Record<"declared" | "received" | "cancelled", string> = {
  declared: "Kutilmoqda",
  received: "Qabul qilingan",
  cancelled: "Bekor qilingan",
}

export const SUPPLY_TONE: Record<"declared" | "received" | "cancelled", Tone> = {
  declared: "accent",
  received: "good",
  cancelled: "neutral",
}

export const COUNT_STATUS: Record<"open" | "closed" | "cancelled", string> = {
  open: "Ochiq",
  closed: "Yopilgan",
  cancelled: "Bekor qilingan",
}

export const COUNT_TONE: Record<"open" | "closed" | "cancelled", Tone> = {
  open: "warn",
  closed: "good",
  cancelled: "neutral",
}

export const REMOVAL_STATUS: Record<
  "requested" | "ready" | "collected" | "cancelled",
  string
> = {
  requested: "So'ralgan",
  ready: "Tayyorlangan",
  collected: "Olib ketilgan",
  cancelled: "Bekor qilingan",
}

export const REMOVAL_TONE: Record<
  "requested" | "ready" | "collected" | "cancelled",
  Tone
> = {
  requested: "accent",
  ready: "warn",
  collected: "good",
  cancelled: "neutral",
}

export const REMOVAL_REASON: Record<"unsellable" | "unsold", string> = {
  unsellable: "Yaroqsiz",
  unsold: "Sotilmadi",
}

/** The verb for a move, so a button reads as an action rather than a state. */
export const ORDER_ACTION: Record<OrderStatus, string> = {
  placed: "Qabul qilindi deb belgilash",
  packing: "Yig'ishga berish",
  shipped: "Kuryerga topshirish",
  delivered: "Yetkazildi deb belgilash",
  cancelled: "Bekor qilish",
  returned: "Qaytarildi deb belgilash",
}

/**
 * A card's place in the catalogue.
 *
 * `moderating` is the queue an admin works; the rest are states a card rests
 * in. Which move is legal from where is never decided here — it comes from
 * `next_statuses` on the response, built from `app/transitions.py`.
 */
export const PRODUCT_STATUS: Record<ProductStatus, string> = {
  draft: "Qoralama",
  moderating: "Moderatsiyada",
  published: "E'lon qilingan",
  rejected: "Rad etilgan",
  archived: "Arxivlangan",
}

export const PRODUCT_TONE: Record<ProductStatus, Tone> = {
  draft: "neutral",
  moderating: "accent",
  published: "good",
  rejected: "danger",
  archived: "neutral",
}

/** The verb for a moderation decision, so a button reads as an action. */
export const PRODUCT_ACTION: Record<ProductStatus, string> = {
  draft: "Qoralamaga qaytarish",
  moderating: "Moderatsiyaga yuborish",
  published: "E'lon qilish",
  rejected: "Rad etish",
  archived: "Arxivlash",
}

// ------------------------------------------------------------------ payouts

export const SETTLEMENT_STATUS: Record<SettlementStatus, string> = {
  open: "Ochiq",
  closed: "Yopilgan",
  paid: "To'langan",
}

export const SETTLEMENT_TONE: Record<SettlementStatus, Tone> = {
  open: "accent",
  closed: "warn",
  paid: "good",
}

/**
 * What each row of a statement is.
 *
 * Read beside the sign, not instead of it: "Qaytarish" is a deduction and
 * "Komissiya qaytdi" is a credit, and the two belong to the same refund.
 */
export const LINE_KIND: Record<StatementLineKind, string> = {
  sale: "Sotuv",
  commission: "Komissiya",
  fulfilment: "Yig'ish-yetkazish",
  refund: "Qaytarish",
  refund_commission: "Komissiya qaytdi",
  storage: "Saqlash",
  adjustment: "Tuzatish",
}

/** What the row was computed from, for the column that names the source. */
export const LINE_SOURCE: Record<StatementLineKind, string> = {
  sale: "Buyurtma satri",
  commission: "Buyurtma satri",
  fulfilment: "Buyurtma satri",
  refund: "Qaytarish",
  refund_commission: "Qaytarish",
  storage: "Taklif",
  adjustment: "Qo'lda",
}
