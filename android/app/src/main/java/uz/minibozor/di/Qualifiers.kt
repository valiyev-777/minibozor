package uz.minibozor.di

import javax.inject.Qualifier

/**
 * Distinguishes the API base URL from any other `String` binding.
 *
 * Dagger rejects `@Provides` methods that return framework types such as
 * `Provider<T>`, so the URL is bound as a plain qualified `String`.
 */
@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class ApiBaseUrl
