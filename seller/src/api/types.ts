import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than a screen quietly showing `undefined`.
 *
 * Only what a seller can actually reach. The document describes the whole
 * API — a hundred and thirty endpoints, most of them an operator's or an
 * admin's — and listing them here would invite a screen that calls one and
 * gets a 403 in front of somebody's face.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type UserRole = S["UserRole"]
export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]

// What I sell, and for how much.
export type Offer = S["StaffOfferOut"]
export type OfferVariant = S["StaffOfferVariantOut"]
export type OfferUpdateIn = S["OfferUpdateIn"]

// What is on the shelf: on hand, held for baskets, sellable.
export type Shelf = S["ShelfOut"]

// Batches I send in.
export type Supply = S["SupplyOut"]
export type SupplyLine = S["SupplyLineOut"]
export type SupplyStatus = S["SupplyStatus"]
export type SupplyCreateIn = S["SupplyCreateIn"]

// What handling and storage cost, by weight band. Readable because a fee
// somebody is charged and cannot look up is a fee they can only dispute.
export type Tariff = S["FulfilmentTariffOut"]
