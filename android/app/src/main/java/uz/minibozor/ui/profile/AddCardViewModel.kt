package uz.minibozor.ui.profile

import uz.minibozor.core.util.AppStrings
import uz.minibozor.R
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import uz.minibozor.core.util.CardBrand
import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.luhnValid
import uz.minibozor.data.remote.dto.CardRequest
import uz.minibozor.data.repository.OrderRepository
import java.time.YearMonth
import java.util.UUID
import javax.inject.Inject

data class CardFormState(
    /** Digits only; never leaves the device. */
    val number: String = "",
    /** Digits only, `MMYY`. */
    val expiry: String = "",
    val holder: String = "",
    val makeDefault: Boolean = false,
    val saving: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,
) {
    val brand: CardBrand get() = CardBrand.of(number)

    val numberComplete: Boolean get() = number.length == brand.length
    val numberValid: Boolean get() = numberComplete && luhnValid(number)

    val expiryMonth: Int? get() = expiry.take(2).toIntOrNull()?.takeIf { it in 1..12 }
    val expiryYear: Int? get() = expiry.drop(2).take(2).toIntOrNull()?.let { 2000 + it }

    val expiryValid: Boolean
        get() {
            val month = expiryMonth ?: return false
            val year = expiryYear ?: return false
            if (expiry.length != 4) return false
            return !YearMonth.of(year, month).isBefore(YearMonth.now())
        }

    val canSave: Boolean get() = numberValid && expiryValid && !saving
}

/**
 * Screen 32 — "Yangi karta qo'shish".
 *
 * The full card number stays in this state object and is never sent anywhere:
 * only the brand, the last four digits, the expiry and a token reach the API.
 * [PROCESSOR_TOKEN_PREFIX] marks the one line to replace with the payment
 * provider's SDK result before this goes live — the app must never be the thing
 * that holds a PAN.
 */
@HiltViewModel
class AddCardViewModel @Inject constructor(
    private val orders: OrderRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(CardFormState())
    val state = _state.asStateFlow()

    fun onNumberChange(raw: String) {
        val digits = raw.filter(Char::isDigit).take(19)
        _state.update { it.copy(number = digits, error = null) }
    }

    fun onExpiryChange(raw: String) {
        val digits = raw.filter(Char::isDigit).take(4)
        _state.update { it.copy(expiry = digits, error = null) }
    }

    fun onHolderChange(raw: String) {
        _state.update { it.copy(holder = raw.uppercase(), error = null) }
    }

    fun onDefaultChange(value: Boolean) {
        _state.update { it.copy(makeDefault = value) }
    }

    fun save() {
        val current = _state.value
        if (!current.canSave) {
            _state.update { it.copy(error = validationMessage(current)) }
            return
        }

        _state.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            val result = orders.addCard(
                CardRequest(
                    brand = current.brand.label,
                    last4 = current.number.takeLast(4),
                    holder = current.holder.trim(),
                    expiryMonth = current.expiryMonth ?: 1,
                    expiryYear = current.expiryYear ?: 2030,
                    // Stand-in for the token the processor's SDK returns.
                    processorToken = PROCESSOR_TOKEN_PREFIX + UUID.randomUUID(),
                    isDefault = current.makeDefault,
                )
            )
            _state.update {
                when (result) {
                    is Outcome.Success -> it.copy(saving = false, done = true, number = "")
                    is Outcome.Failure -> it.copy(saving = false, error = result.message)
                }
            }
        }
    }

    private fun validationMessage(state: CardFormState): String = when {
        !state.numberComplete -> AppStrings[R.string.karta_raqamini_toliq_kiriting]
        !state.numberValid -> AppStrings[R.string.karta_raqami_notogri]
        state.expiryMonth == null && state.expiry.length != 4 ->
            AppStrings[R.string.amal_qilish_muddatini_kiriting]
        state.expiryMonth == null -> AppStrings[R.string.oy_01_12_oraligida_bolishi_kerak]
        else -> AppStrings[R.string.kartaning_muddati_otgan]
    }

    companion object {
        const val PROCESSOR_TOKEN_PREFIX = "dev_tok_"
    }
}
