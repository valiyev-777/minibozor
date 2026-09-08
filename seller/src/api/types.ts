import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than a screen quietly showing `undefined`.
 *
 * Only what a seller can actually reach. The document describes the whole
 * API — a hundred and fifty endpoints, most of them an operator's or an
 * admin's — and listing them all here would invite a screen that calls one
 * and gets a 403 in front of somebody's face. `docs/rebuild-plan.md` §3 is
 * the list; this file is that list in TypeScript.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]

/** Which shop am I. `/staff/me` answers with the user, not the shop. */
export type Shop = S["SellerMeOut"]

// ------------------------------------------------------------- my own products
//
// A seller owns the product they sell: they open it, photograph it, price it
// and say what colours and sizes they have. What the warehouse confirms is
// that the goods arrived — not that the listing was allowed.

export type Listing = S["SellerListingOut"]
export type ListingCreateIn = S["ListingCreateIn"]
export type ListingColorIn = S["ListingColorIn"]
export type ListingSizeIn = S["ListingSizeIn"]
export type ListingStock = S["ListingStockOut"]
/** Where a product has got to: awaiting_warehouse … on_sale … rejected. */
export type ListingStage = Listing["stage"]

/**
 * The editorial category list, not the customer's translated tree.
 *
 * `GET /staff/catalog/categories` answers `AdminCategoryOut` — the Uzbek on
 * the row, flat, with `parent_slug` — which is what a form writing to the
 * catalogue needs. `CategoryOut` is the shopper's shape and translates as it
 * goes, which is right for the app and wrong for a field that is choosing
 * which row is meant.
 */
export type Category = S["AdminCategoryOut"]

// ------------------------------------------------------------------- the price
//
// The only figure on a product that stays the seller's after it is submitted.
// The count is the warehouse's; see the plan's §2.

export type Offer = S["StaffOfferOut"]
export type OfferUpdateIn = S["OfferUpdateIn"]

// ------------------------------------------------------ goods in and goods out

export type Supply = S["SupplyOut"]
export type SupplyLine = S["SupplyLineOut"]
export type SupplyStatus = S["SupplyStatus"]
export type SupplyCreateIn = S["SupplyCreateIn"]

export type Removal = S["RemovalOut"]
export type RemovalCreateIn = S["RemovalCreateIn"]
export type RemovalReason = S["RemovalReason"]

// ------------------------------------------------------------- what has sold

export type Order = S["StaffOrderOut"]
export type OrderPage = S["Page_StaffOrderOut_"]

// --------------------------------------------- goods that came back, and mine
//
// Two answers hang off a return and only the second is the seller's: the
// warehouse says what arrived in the parcel, and the seller says what to do
// about it. `seller_decisions` is which of those answers is still open — the
// rule that damaged goods do not go back on sale lives on the server, and the
// buttons come from this field rather than from a copy of the rule here.

export type Return = S["StaffReturnOut"]
export type ReturnInspection = S["ReturnInspection"]
export type SellerDecision = S["SellerReturnDecision"]
export type SellerDecisionIn = S["SellerDecisionIn"]

// ------------------------------------------------------------------ the money

export type RunningTotal = S["RunningTotalOut"]
export type Statement = S["SellerStatementOut"]
export type StatementDetail = S["SellerStatementDetailOut"]
export type StatementLine = S["StatementLineOut"]

// ------------------------------------------------------------ the bell in the shell

export type NotificationGroup = S["NotificationGroupOut"]
export type Notification = S["NotificationOut"]

/**
 * `GET /notifications/unread-count`, which has no named shape.
 *
 * It answers a bare `{"unread": 3}` and FastAPI describes that as
 * `dict[str, int]`, so there is nothing in `components` to point at. Named
 * here rather than inlined at the call site, and narrowed to the one key we
 * read: a `Record<string, number>` in a component's props would put the
 * guessing at the other end.
 */
export type UnreadCount = { unread: number }
