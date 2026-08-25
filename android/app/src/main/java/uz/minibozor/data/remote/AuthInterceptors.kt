package uz.minibozor.data.remote

import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import uz.minibozor.data.local.TokenStore
import uz.minibozor.di.ApiBaseUrl
import uz.minibozor.data.remote.dto.RefreshRequest
import uz.minibozor.data.remote.dto.TokenPairDto
import javax.inject.Inject
import javax.inject.Singleton

/** Attaches the access token to everything except the auth endpoints. */
@Singleton
class AuthInterceptor @Inject constructor(
    private val tokens: TokenStore,
) : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.url.encodedPath.contains("/auth/otp") ||
            request.url.encodedPath.endsWith("/auth/refresh")
        ) {
            return chain.proceed(request)
        }
        val token = tokens.accessToken ?: return chain.proceed(request)
        return chain.proceed(
            request.newBuilder().header("Authorization", "Bearer $token").build()
        )
    }
}

/**
 * Refreshes once on a 401 and replays the request.
 *
 * The refresh call goes out on a bare client rather than through Retrofit: using
 * the same client would re-enter this authenticator and deadlock.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val tokens: TokenStore,
    @ApiBaseUrl private val baseUrl: String,
    private val json: Json,
) : Authenticator {

    private val bareClient = OkHttpClient()

    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.header("Authorization") == null) return null
        if (responseCount(response) >= 2) return null

        val refresh = tokens.refreshToken ?: return null

        val refreshed = synchronized(this) {
            // Another thread may have refreshed while we waited on the lock.
            val current = tokens.accessToken
            val stale = response.request.header("Authorization")?.removePrefix("Bearer ")
            if (current != null && current != stale) current else runRefresh(refresh)
        } ?: run {
            tokens.clear()
            return null
        }

        return response.request.newBuilder()
            .header("Authorization", "Bearer $refreshed")
            .build()
    }

    private fun runRefresh(refreshToken: String): String? {
        val body = json.encodeToString(RefreshRequest.serializer(), RefreshRequest(refreshToken))
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url(baseUrl + "auth/refresh")
            .post(body)
            .build()

        return runCatching {
            bareClient.newCall(request).execute().use { res ->
                if (!res.isSuccessful) return@use null
                val pair = json.decodeFromString(
                    TokenPairDto.serializer(),
                    res.body?.string().orEmpty(),
                )
                tokens.save(pair.accessToken, pair.refreshToken)
                pair.accessToken
            }
        }.getOrNull()
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
