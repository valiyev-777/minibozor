package uz.minibozor.core.util

import retrofit2.HttpException
import java.io.IOException

/** What every repository call returns: a value, or a message the UI can show. */
sealed interface Outcome<out T> {
    data class Success<T>(val data: T) : Outcome<T>
    data class Failure(val message: String, val code: Int? = null) : Outcome<Nothing>
}

val <T> Outcome<T>.dataOrNull: T? get() = (this as? Outcome.Success)?.data

inline fun <T, R> Outcome<T>.map(transform: (T) -> R): Outcome<R> = when (this) {
    is Outcome.Success -> Outcome.Success(transform(data))
    is Outcome.Failure -> this
}

/**
 * Turns an API call into an [Outcome]. Server-side messages are surfaced as-is —
 * the backend already speaks Uzbek, so there is nothing to translate.
 */
suspend fun <T> apiCall(block: suspend () -> T): Outcome<T> = try {
    Outcome.Success(block())
} catch (e: HttpException) {
    Outcome.Failure(e.detailMessage(), e.code())
} catch (e: IOException) {
    Outcome.Failure("Internetga ulanib bo'lmadi. Aloqani tekshiring.")
} catch (e: Exception) {
    Outcome.Failure(e.message ?: "Kutilmagan xatolik yuz berdi")
}

private fun HttpException.detailMessage(): String {
    val raw = runCatching { response()?.errorBody()?.string() }.getOrNull().orEmpty()
    val detail = Regex("\"detail\"\\s*:\\s*\"(.*?)\"").find(raw)?.groupValues?.getOrNull(1)
    return detail ?: when (code()) {
        401 -> "Sessiya tugadi. Qaytadan kiring."
        404 -> "Topilmadi"
        409 -> "Bu amalni bajarib bo'lmaydi"
        in 500..599 -> "Server javob bermayapti. Birozdan so'ng urinib ko'ring."
        else -> "Xatolik yuz berdi"
    }
}
