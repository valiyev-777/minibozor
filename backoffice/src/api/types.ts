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

export type StaffOffer = S["StaffOfferOut"]

// ---------------------------------------------------------------- admin

export type AdminSeller = S["AdminSellerOut"]
export type SellerCreateIn = S["SellerCreateIn"]
export type SellerUpdateIn = S["SellerUpdateIn"]

export type StaffUser = S["StaffUserOut"]
export type StaffUserPage = S["Page_StaffUserOut_"]
export type RoleWriteIn = S["RoleWriteIn"]

export type AdminProduct = S["AdminProductOut"]
export type AdminProductPage = S["Page_AdminProductOut_"]
export type ProductStatus = S["ProductStatus"]
export type ProductStatusIn = S["ProductStatusIn"]
export type Category = S["CategoryOut"]
export type Brand = S["BrandOut"]

export type AdminBanner = S["AdminBannerOut"]
export type BannerWriteIn = S["BannerWriteIn"]
export type BannerUpdateIn = S["BannerUpdateIn"]
export type AdminSection = S["AdminSectionOut"]
export type SectionWriteIn = S["SectionWriteIn"]
export type SectionUpdateIn = S["SectionUpdateIn"]
export type AdminPromo = S["AdminPromoOut"]
export type PromoWriteIn = S["PromoWriteIn"]
export type PromoUpdateIn = S["PromoUpdateIn"]
export type ReorderIn = S["ReorderIn"]

// The editor's own shapes. The customer ones answer in the language asked for
// and carry only what a shopper needs; an editor needs the Uzbek that is on
// the row, the ids it deletes and reorders by, and what it is allowed to do.
export type AdminCategory = S["AdminCategoryOut"]
export type AdminBrand = S["AdminBrandOut"]
export type CatalogSummary = S["CatalogSummaryOut"]
export type AdminProductDetail = S["AdminProductDetailOut"]
export type AdminImage = S["AdminImageOut"]
export type AdminVariant = S["AdminVariantOut"]
export type AdminVariants = S["AdminVariantsOut"]
export type VariantKind = S["VariantKind"]
export type SpecOut = S["SpecOut"]
export type AdminSpec = S["AdminSpecOut"]
export type MediaOut = S["MediaOut"]

export type Supply = S["SupplyOut"]
export type SupplyStatus = S["SupplyStatus"]
export type SupplyLine = S["SupplyLineOut"]

export type StockCount = S["StockCountOut"]
export type StockCountStatus = S["StockCountStatus"]
export type StockCountLine = S["StockCountLineOut"]

export type Removal = S["RemovalOut"]
export type RemovalStatus = S["RemovalStatus"]
export type RemovalReason = S["RemovalReason"]

export type Shelf = S["ShelfOut"]
export type Movement = S["MovementOut"]
export type MovementKind = S["StockMovementKind"]
export type MovementPage = S["Page_MovementOut_"]

export type TokenPair = S["TokenPair"]
export type OtpRequested = S["OtpRequested"]
