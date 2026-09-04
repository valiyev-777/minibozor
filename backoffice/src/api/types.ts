import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than the screen quietly showing `undefined`. This file only gives the
 * ones we use a shorter name.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type UserRole = S["UserRole"]

export type StaffReturn = S["StaffReturnOut"]
export type ReturnStatus = S["ReturnStatus"]
export type DecisionIn = S["DecisionIn"]
export type RefundIn = S["RefundIn"]

export type StaffReview = S["StaffReviewOut"]
export type ReviewStatus = S["ReviewStatus"]

export type StaffOrder = S["StaffOrderOut"]
export type OrderStatus = S["OrderStatus"]
export type OrderDetail = S["OrderOut"]
export type OrderStatusIn = S["OrderStatusIn"]
export type OrderPage = S["Page_StaffOrderOut_"]

export type StaffSlot = S["StaffSlotOut"]
export type SlotCreateIn = S["SlotCreateIn"]
export type SlotUpdateIn = S["SlotUpdateIn"]
export type SlotWindowIn = S["SlotWindowIn"]

export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]
