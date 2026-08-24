package uz.minibozor.data.repository

import uz.minibozor.core.util.Outcome
import uz.minibozor.core.util.apiCall
import uz.minibozor.data.remote.MiniBozorApi
import uz.minibozor.data.remote.dto.FaqDto
import uz.minibozor.data.remote.dto.LegalDocDto
import uz.minibozor.data.remote.dto.LegalDocFullDto
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ContentRepository @Inject constructor(private val api: MiniBozorApi) {

    suspend fun faq(): Outcome<List<FaqDto>> = apiCall { api.faq() }

    suspend fun support(): Outcome<Map<String, String>> = apiCall { api.support() }

    suspend fun legalDocs(): Outcome<List<LegalDocDto>> = apiCall { api.legalDocs() }

    suspend fun legalDoc(slug: String): Outcome<LegalDocFullDto> = apiCall { api.legalDoc(slug) }

    suspend fun languages(): Outcome<List<Map<String, String>>> = apiCall { api.languages() }
}
