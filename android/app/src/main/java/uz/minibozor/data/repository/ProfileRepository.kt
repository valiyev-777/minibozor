package uz.minibozor.data.repository

import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ProfileRepository @Inject constructor(private val api: MiniBozorApi) {

    suspend fun me(): Outcome<UserDto> = apiCall { api.me() }

    suspend fun updateMe(body: UserUpdateRequest): Outcome<UserDto> = apiCall { api.updateMe(body) }

    suspend fun overview(): Outcome<ProfileOverviewDto> = apiCall { api.overview() }

    suspend fun settings(): Outcome<SettingsDto> = apiCall { api.settings() }

    suspend fun updateSettings(body: SettingsRequest): Outcome<SettingsDto> =
        apiCall { api.updateSettings(body) }

    suspend fun notificationPrefs(): Outcome<NotificationPrefsDto> =
        apiCall { api.notificationPrefs() }

    suspend fun updateNotificationPrefs(
        body: NotificationPrefsRequest,
    ): Outcome<NotificationPrefsDto> = apiCall { api.updateNotificationPrefs(body) }

    suspend fun setBiometrics(enabled: Boolean): Outcome<UserDto> =
        apiCall { api.setBiometrics(enabled) }

    suspend fun notifications(): Outcome<List<NotificationGroupDto>> = apiCall { api.notifications() }

    suspend fun unreadCount(): Outcome<Int> =
        apiCall { api.unreadCount()["count"] ?: 0 }

    suspend fun markNotificationsRead(): Outcome<Unit> =
        apiCall { api.markNotificationsRead() }.let {
            if (it is Outcome.Failure) it else Outcome.Success(Unit)
        }

    suspend fun myReviews(page: Int = 1): Outcome<PageDto<ReviewDto>> = apiCall { api.myReviews(page) }

    suspend fun deleteReview(id: Int): Outcome<Unit> =
        apiCall { api.deleteReview(id) }.let {
            if (it is Outcome.Failure) it else Outcome.Success(Unit)
        }

    suspend fun pendingReviews(): Outcome<List<OrderItemDto>> = apiCall { api.pendingReviews() }
}
