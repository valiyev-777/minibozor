package uz.minibozor.core.util

import retrofit2.HttpException
import uz.minibozor.R
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
 * Turns an API call into an [Outcome].
 *
 * A message from the server is surfaced as-is: the request carried an
 * Accept-Language header, so it already arrives in the user's language. Only
 * the fallbacks below — the cases where no response reached us — come from
 * local resources.
 */
suspend fun <T> apiCall(block: suspend () -> T): Outcome<T> = try {
    Outcome.Success(block())
} catch (e: HttpException) {
    Outcome.Failure(e.detailMessage(), e.code())
} catch (e: IOException) {
    Outcome.Failure(AppStrings[R.string.error_no_internet])
} catch (e: Exception) {
    Outcome.Failure(e.message ?: AppStrings[R.string.error_unexpected])
}

private fun HttpException.detailMessage(): String {
    val raw = runCatching { response()?.errorBody()?.string() }.getOrNull().orEmpty()
    val detail = Regex("\"detail\"\\s*:\\s*\"(.*?)\"").find(raw)?.groupValues?.getOrNull(1)
    return detail ?: when (code()) {
        401 -> AppStrings[R.string.error_session_expired]
        404 -> AppStrings[R.string.error_not_found]
        409 -> AppStrings[R.string.error_conflict]
        in 500..599 -> AppStrings[R.string.error_server]
        else -> AppStrings[R.string.error_generic]
    }
}
