package uz.minibozor.data.repository

import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.*
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OrderRepository @Inject constructor(private val api: MiniBozorApi) {

    suspend fun addresses(): Outcome<List<AddressDto>> = apiCall { api.addresses() }

    suspend fun createAddress(body: AddressRequest): Outcome<AddressDto> =
        apiCall { api.createAddress(body) }

    suspend fun updateAddress(id: Int, body: AddressRequest): Outcome<AddressDto> =
        apiCall { api.updateAddress(id, body) }

    suspend fun deleteAddress(id: Int): Outcome<Unit> =
        apiCall { api.deleteAddress(id) }.let { if (it is Outcome.Failure) it else Outcome.Success(Unit) }

    suspend fun slots(days: Int = 3): Outcome<List<SlotDayDto>> = apiCall { api.slots(days) }

    suspend fun pickupPoints(): Outcome<List<PickupPointDto>> = apiCall { api.pickupPoints() }

    suspend fun cards(): Outcome<List<CardDto>> = apiCall { api.cards() }

    suspend fun addCard(body: CardRequest): Outcome<CardDto> = apiCall { api.addCard(body) }

    suspend fun makeCardDefault(id: Int): Outcome<CardDto> = apiCall { api.makeCardDefault(id) }

    suspend fun deleteCard(id: Int): Outcome<Unit> =
        apiCall { api.deleteCard(id) }.let { if (it is Outcome.Failure) it else Outcome.Success(Unit) }

    suspend fun preview(body: CheckoutRequest): Outcome<CheckoutPreviewDto> =
        apiCall { api.checkoutPreview(body) }

    suspend fun place(body: CheckoutRequest): Outcome<OrderDto> = apiCall { api.createOrder(body) }

    suspend fun orders(active: Boolean?, page: Int = 1): Outcome<PageDto<OrderSummaryDto>> =
        apiCall { api.orders(active, page) }

    suspend fun order(id: Int): Outcome<OrderDto> = apiCall { api.order(id) }

    suspend fun cancel(id: Int, body: CancelRequest): Outcome<OrderDto> =
        apiCall { api.cancelOrder(id, body) }

    suspend fun requestReturn(id: Int, body: ReturnRequestBody): Outcome<ReturnDto> =
        apiCall { api.requestReturn(id, body) }

    suspend fun returns(): Outcome<List<ReturnDto>> = apiCall { api.returns() }

    suspend fun cancelReasons(): Outcome<List<ReasonDto>> = apiCall { api.cancelReasons() }

    suspend fun returnReasons(): Outcome<List<ReasonDto>> = apiCall { api.returnReasons() }
}
