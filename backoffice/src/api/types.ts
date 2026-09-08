import type { components } from "./schema"

/**
 * Names for the generated shapes.
 *
 * Nothing here is hand-written: `schema.d.ts` comes out of the backend's own
 * OpenAPI document (`npm run gen`), so when a field moves the build says so
 * rather than a screen quietly showing `undefined`.
 *
 * Only what the three staff roles can reach — `docs/rebuild-plan.md` §3 in
 * TypeScript. The document describes the whole API, most of it the mobile
 * apps', and listing all of it here would invite a screen that calls
 * something no role behind this login can open.
 */
type S = components["schemas"]

export type StaffMe = S["StaffMeOut"]
export type Role = S["UserRole"]
export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]

// ------------------------------------------------------- the warehouse's day
//
// Goods arrive as a declared batch and reach the shelf only when somebody
// counts them; refusing a batch takes the product down with it, with a reason
// the seller reads. Nothing here sets a figure — every write is a difference
// through the movement ledger.

export type Supply = S["SupplyOut"]
export type SupplyLine = S["SupplyLineOut"]
export type SupplyStatus = S["SupplyStatus"]
export type SupplyReceiveIn = S["SupplyReceiveIn"]
export type SupplyCancelIn = S["SupplyCancelIn"]

export type Removal = S["RemovalOut"]
export type RemovalLine = S["RemovalLineOut"]
export type RemovalPrepareIn = S["RemovalPrepareIn"]

export type Movement = S["MovementOut"]
export type MovementPage = S["Page_MovementOut_"]
export type MovementKind = S["StockMovementKind"]
export type WriteOffIn = S["WriteOffIn"]
export type Shelf = S["ShelfOut"]

// ---------------------------------------------------------------- the queue
//
// One list, four jobs: the operator runs it, the warehouse picks from it, the
// admin does either, a seller watches their own. The buttons come from
// `next_statuses`, which is `app.transitions` answering rather than a copy of
// the rules written again here.

export type Order = S["StaffOrderOut"]
export type OrderPage = S["Page_StaffOrderOut_"]
export type OrderDetail = S["OrderOut"]
export type DeliveryAttempt = S["DeliveryAttemptOut"]
export type OrderStatus = S["OrderStatus"]
export type OrderStatusIn = S["OrderStatusIn"]
export type Courier = S["StaffUserOut"]
export type AssignCourierIn = S["CourierAssignIn"]

// ------------------------------------------------------------ goods that came back
//
// Four answers in order, by four different people: the operator decides the
// money, a courier collects the parcel, the warehouse says what arrived, and
// the seller says what to do about it.

export type Return = S["StaffReturnOut"]
export type ReturnStatus = S["ReturnStatus"]
export type ReturnInspection = S["ReturnInspection"]
export type ReturnInspectIn = S["ReturnInspectIn"]
export type DecisionIn = S["DecisionIn"]
export type RefundIn = S["RefundIn"]

export type PickupRun = S["PickupRunOut"]
export type PickupCreateIn = S["PickupCreateIn"]

// ---------------------------------------------------------------- the admin's
//
// Sellers, staff roles, the catalogue's vocabulary, and fixing a card a seller
// wrote. Editing one is not approving it: nothing here publishes anything —
// that is the warehouse counting a box in.

export type Seller = S["SellerOut"]
export type SellerAdmin = S["AdminSellerOut"]
export type SellerCreateIn = S["SellerCreateIn"]
export type SellerPatchIn = S["SellerUpdateIn"]

export type StaffUser = S["StaffUserOut"]
export type StaffUserPage = S["Page_StaffUserOut_"]
export type RoleChangeIn = S["RoleWriteIn"]

export type Category = S["AdminCategoryOut"]
export type CategoryWriteIn = S["CategoryWriteIn"]
export type Brand = S["AdminBrandOut"]
export type BrandWriteIn = S["BrandWriteIn"]

export type Product = S["AdminProductOut"]
export type ProductDetail = S["AdminProductDetailOut"]
export type ProductPage = S["Page_AdminProductOut_"]
export type ProductUpdateIn = S["ProductUpdateIn"]
export type ProductImage = S["AdminImageOut"]
export type ProductVariant = S["AdminVariantOut"]
export type ProductSpec = S["AdminSpecOut"]
export type PickupLine = S["PickupLineOut"]

export type CatalogSummary = S["CatalogSummaryOut"]

// ----------------------------------------------------------- the bell in the shell

export type NotificationGroup = S["NotificationGroupOut"]
export type UnreadCount = { unread: number }
