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

// My own products. A seller owns the product they sell: they open it,
// photograph it, price it and say what colours and sizes they have. What the
// warehouse confirms is that the goods arrived — not that the listing was
// allowed.
export type Listing = S["SellerListingOut"]
export type ListingCreateIn = S["ListingCreateIn"]
export type ListingColorIn = S["ListingColorIn"]
export type ListingSizeIn = S["ListingSizeIn"]
export type ListingStock = S["ListingStockOut"]
/** Where a product has got to: awaiting_warehouse … on_sale … rejected. */
export type ListingStage = Listing["stage"]

// Batches I send in.
export type Supply = S["SupplyOut"]
export type SupplyLine = S["SupplyLineOut"]
export type SupplyStatus = S["SupplyStatus"]
export type SupplyCreateIn = S["SupplyCreateIn"]

// What handling and storage cost, by weight band. Readable because a fee
// somebody is charged and cannot look up is a fee they can only dispute.
export type Tariff = S["FulfilmentTariffOut"]

// Which shop am I. `/staff/me` answers with the user — a phone and a role —
// and says nothing about the `sellers` row behind it.
export type Shop = S["SellerMeOut"]

// The catalogue as somebody looking for something to stock reads it.
export type CatalogCard = S["SellerCatalogOut"]
export type CatalogCardPage = S["Page_SellerCatalogOut_"]
export type CatalogCardDetail = S["SellerCatalogDetailOut"]
export type CatalogVariant = S["SellerVariantOut"]
export type PublicOffer = S["OfferOut"]
export type OfferCreateIn = S["OfferCreateIn"]

// My own account for a settlement period, and what adds up to it.
export type Statement = S["SellerStatementOut"]
export type StatementDetail = S["SellerStatementDetailOut"]
export type StatementLine = S["StatementLineOut"]
export type StatementLineKind = S["StatementLineKind"]
export type SettlementStatus = S["SettlementStatus"]

// Suggesting a card for the platform's catalogue. A seller does not write to
// it directly — the catalogue belongs to the platform.
export type ProposeIn = S["ProductProposeIn"]
export type Proposal = S["AdminProductOut"]
export type Category = S["CategoryOut"]
export type Brand = S["BrandOut"]
