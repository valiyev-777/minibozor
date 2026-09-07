import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than a screen quietly showing `undefined`.
 *
 * Only what a courier can actually reach. The document describes the whole
 * API — most of it a customer's or an operator's — and listing the rest here
 * would invite a screen that calls one and gets a 403 on a doorstep.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type UserRole = S["UserRole"]
export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]

/** One stop on a round: an address, a phone, and how much cash to ask for. */
export type CourierOrder = S["CourierOrderOut"]
export type OrderStatus = S["OrderStatus"]
export type PaymentMethod = S["PaymentMethod"]
export type DeliverIn = S["DeliverIn"]
export type FailedIn = S["FailedIn"]

/** A round and the money that came back from it. */
export type Shift = S["ShiftDetailOut"]
export type ShiftCloseIn = S["ShiftCloseIn"]
export type DeliveryAttempt = S["DeliveryAttemptOut"]

/** Returns to collect from customers, door by door. */
export type PickupRun = S["PickupRunOut"]
export type PickupLine = S["PickupLineOut"]
export type PickupCollectIn = S["PickupCollectIn"]
export type PickupLineIn = S["PickupLineIn"]

export type Media = S["MediaOut"]
