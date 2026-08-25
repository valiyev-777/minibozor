package uz.minibozor.core.util

import androidx.annotation.StringRes
import uz.minibozor.R

/**
 * Where the app delivers. Tashkent city and Karakalpakstan are not viloyats but
 * are separate administrative units, so all fourteen belong in one picker.
 *
 * [canonical] is what goes to the server and into saved addresses; it stays
 * Uzbek in every language so a city chosen in Russian still matches the
 * catalogue's delivery data. Only [labelRes] changes with the language.
 */
data class UzRegion(val canonical: String, @StringRes val labelRes: Int)

val UZ_REGIONS: List<UzRegion> = listOf(
    UzRegion("Toshkent", R.string.region_toshkent),
    UzRegion("Toshkent viloyati", R.string.region_toshkent_viloyati),
    UzRegion("Andijon", R.string.region_andijon),
    UzRegion("Buxoro", R.string.region_buxoro),
    UzRegion("Farg'ona", R.string.region_fargona),
    UzRegion("Jizzax", R.string.region_jizzax),
    UzRegion("Xorazm", R.string.region_xorazm),
    UzRegion("Namangan", R.string.region_namangan),
    UzRegion("Navoiy", R.string.region_navoiy),
    UzRegion("Qashqadaryo", R.string.region_qashqadaryo),
    UzRegion("Qoraqalpog'iston", R.string.region_qoraqalpogiston),
    UzRegion("Samarqand", R.string.region_samarqand),
    UzRegion("Sirdaryo", R.string.region_sirdaryo),
    UzRegion("Surxondaryo", R.string.region_surxondaryo),
)

/** The display name for a stored city, falling back to the stored text. */
fun regionLabel(canonical: String): String =
    UZ_REGIONS.firstOrNull { it.canonical == canonical }
        ?.let { AppStrings[it.labelRes] }
        ?: canonical
