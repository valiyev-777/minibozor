package uz.minibozor.data.remote

import okhttp3.Interceptor
import okhttp3.Response
import uz.minibozor.core.util.AppLocale
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Tells the backend which language to answer in.
 *
 * Plenty of user-visible text arrives from the server — category names, order
 * statuses, the FAQ — so translating only the app would leave those in Uzbek.
 */
@Singleton
class LanguageInterceptor @Inject constructor() : Interceptor {

    override fun intercept(chain: Interceptor.Chain): Response = chain.proceed(
        chain.request().newBuilder()
            .header("Accept-Language", AppLocale.current())
            .build()
    )
}
