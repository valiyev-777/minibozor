package uz.minibozor.ui.catalog

/**
 * Everything the listing and the filter sheet agree on. Kept immutable so the
 * sheet can edit a draft copy and only commit on "Qo'llash".
 */
data class ProductQuery(
    val text: String? = null,
    val category: String? = null,
    val brands: Set<String> = emptySet(),
    val sizes: Set<String> = emptySet(),
    val minPrice: Int? = null,
    val maxPrice: Int? = null,
    val minRating: Double? = null,
    val flags: Map<String, Boolean> = emptyMap(),
    /**
     * Whether to list what cannot be bought.
     *
     * Off by default — a shelf shows what is for sale, and a sold-out product
     * behind its veil was taking a slot in every grid from something that could
     * actually be bought. Its own field rather than one of [flags], because it
     * is a choice about what the listing shows rather than a property of the
     * products in it.
     */
    val showSoldOut: Boolean = false,
    val sort: String = "popular",
) {
    /** Drives the "N ta filtr" badge on the listing toolbar. */
    val activeFilterCount: Int
        get() = brands.size + sizes.size + flags.count { it.value } +
            listOfNotNull(minPrice, maxPrice).size.coerceAtMost(1) +
            (if (minRating != null) 1 else 0) +
            (if (showSoldOut) 1 else 0)

    fun toggleBrand(slug: String) = copy(
        brands = if (slug in brands) brands - slug else brands + slug
    )

    fun toggleSize(label: String) = copy(
        sizes = if (label in sizes) sizes - label else sizes + label
    )

    fun toggleFlag(key: String) = copy(
        flags = flags + (key to !(flags[key] ?: false))
    )

    fun cleared() = ProductQuery(text = text, category = category, sort = sort)
}
