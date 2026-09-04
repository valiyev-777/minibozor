import type { OrderStatus, ReturnStatus, ReviewStatus, UserRole } from "@/api/types"

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

/** The verb for a move, so a button reads as an action rather than a state. */
export const ORDER_ACTION: Record<OrderStatus, string> = {
  placed: "Qabul qilindi deb belgilash",
  packing: "Yig'ishga berish",
  shipped: "Kuryerga topshirish",
  delivered: "Yetkazildi deb belgilash",
  cancelled: "Bekor qilish",
  returned: "Qaytarildi deb belgilash",
}
