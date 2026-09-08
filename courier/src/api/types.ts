import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than a screen quietly showing `undefined`.
 *
 * A courier reaches five endpoints and that is the whole list — `/courier/*`
 * plus the shared auth. Everything else in the document belongs to somebody
 * at a desk, and naming it here would invite a screen that calls one and puts
 * a 403 in front of somebody standing at a door.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]

/** One stop: either mine already, or on the board and anybody's to take. */
export type Stop = S["CourierOrderOut"]
export type DeliverIn = S["DeliverIn"]
export type FailedIn = S["FailedIn"]

/** What I have delivered and what it came to. */
export type Earnings = S["CourierEarningsOut"]

/** A collection run: approved returns to pick up from customers. */
export type Run = S["PickupRunOut"]
export type RunLine = S["PickupLineOut"]
export type CollectIn = S["PickupCollectIn"]
