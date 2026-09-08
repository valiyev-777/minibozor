# Oqim testi — 15 qadam, hammasi o'tdi

Sana: 2026-09-08. `backend/tools/walk_flow.py`.

## Nima qilindi

Sizning oqimni **HTTP orqali, har rol o'z akkaunti bilan** boshdan-oxir yuruvchi
skript yozildi. Hech narsa mock qilinmagan, hech narsa to'g'ridan-to'g'ri
ma'lumotlar bazasiga yozilmagan — har qadam panel ishlatadigan eshikdan
o'tadi. Ya'ni bu yerda o'tgan qadam — odam qo'lda qila oladigan qadam.

```
cd backend && .venv/bin/python -m tools.walk_flow
```

Backend ishlab turishi kerak (`./dev.sh`). Boshqa portda bo'lsa:
`--api http://localhost:8010/api/v1`.

## Natija

| # | Qadam | Natija |
|---|---|---|
| 1 | Sotuvchi tovar yaratadi va omborga topshiradi | ✅ 30 dona, bitta partiya |
| 2 | Sotuvchi "Kutilmoqda" holatida ko'radi, qoldiq yo'q | ✅ topshirildi 30 · omborda 0 |
| 3 | Xaridor hali topa olmaydi | ✅ 404, qidiruvda ham yo'q |
| 4 | Ombor sanab qabul qiladi (L bittasi kam) | ✅ 29 dona |
| 5 | Tovar sotuvga chiqdi — **hech kim boshqa tasdiqlamadi** | ✅ on_sale · 29 |
| 6 | Xaridor topadi, ochadi, o'lchamlarni ko'radi | ✅ 3 o'lcham · 89 000 |
| 7 | Xaridor bittasini oladi | ✅ buyurtma yaratildi |
| 8 | Sotuvchi buyurtmani ko'radi, qoldiq kamaydi | ✅ sotuvga tayyor 28 |
| 9 | Ombor yig'adi, operator kuryerga biriktiradi | ✅ kuryerda |
| 10 | Kuryer yetkazadi | ✅ **ikki marta bosilsa bir marta yoziladi** |
| 11 | Xaridor qaytaradi → ombor tekshiradi: buzilmagan | ✅ omborda |
| 12 | Sotuvchi qayta sotuvga chiqaradi | ✅ omborda 29 · sotuvga tayyor 29 |
| 13 | Ombor rad etadi — sabab sotuvchiga, do'konda paydo bo'lmaydi | ✅ rejected + sabab |
| 14 | Buzilgan qaytarish — sotuvchi qayta sotuvga chiqara olmaydi | ✅ 409, qoldiq o'zgarmadi |
| 15 | Kuryer yetkaza olmadi — urinish yoziladi, buyurtma yo'lda qoladi | ✅ bekor qilinganda qoldiq qaytdi |

Mavjud test to'plami: **181 o'tdi**. Ikki xato faqat mening nusxamdagi kamchilikdan
(`media/` papkasi ko'chirilmagan, `.env`da bitta origin yo'q) — kodda emas.

## Test topgan haqiqiy kamchilik — tuzatildi

**Kuryer yetkaza olmaganini operator ko'rmayotgan edi.**

Kodning o'z izohi (`app/transitions.py`) shunday deydi: kuryer taslim bo'lish
qarorini qabul qilmaydi — u bitta eshik oldida bitta rad javobi bilan turadi;
uchtasini ko'rib, xaridorga qo'ng'iroq qiladigan odam boshqa. O'sha odam —
operator. Lekin operatorning buyurtma ekranida urinishlar **yo'q edi**:
`GET /staff/orders/{id}` xaridorning shaklini qaytaradi, unda faqat holat
hodisalari bor. Kuryer urinishni yozadi (`DeliveryAttempt` qatori), o'z
ekranida sonini ko'radi — operator esa hech narsa ko'rmaydi va qarorni nimaga
asoslanib qabul qilishini bilmaydi.

Tuzatish:

| Fayl | O'zgarish |
|---|---|
| `app/schemas.py` | `DeliveryAttemptOut` — **ikki marta e'lon qilingan ekan**, biri ishlatilmagan; bittaga birlashtirildi va `courier_name` qo'shildi. `OrderOut.attempts` maydoni qo'shildi |
| `app/services.py` | `order_out(..., with_attempts=False)` — xaridor uchun o'chirilgan (bu shtatning ishi), staff uchun yoqiladi. `_attempts_out()` yordamchisi |
| `app/routers/operations.py` | `GET /staff/orders/{id}` endi `with_attempts=True` bilan chaqiradi |
| `backoffice/src/pages/OrderPage.tsx` | Yangi "Yetkazish urinishlari" bloki — har urinishda: kuryer ismi, sabab, vaqt. Urinish bo'lmasa blok umuman ko'rinmaydi |

`courier_name`, `courier_id` emas — operator xaridorga qo'ng'iroq qilib "kim
bordi" deb so'raganda raqamni emas, ismni aytadi.

Uch panelda ham TypeScript toza, tiplar yangi API'dan qayta generatsiya qilingan.

## Test aniqlagan, lekin to'g'ri bo'lgan qoidalar

Bular skript avvaliga "xato" deb ko'rsatgan, lekin tekshirganda backend haq edi:

- **Rasmsiz tovar qabul qilinmaydi** — `400: "Kamida bitta rasm kerak"`.
- **Kuryer amallariga `Idempotency-Key` header majburiy.** Ixtiyoriy emas,
  majburiy — bu to'g'ri tomoni: headerni yubormagan klientga aytiladi, jimgina
  ikki marta yozilib qolmaydi.
- **Yetkazilmagan buyurtmani qaytarib bo'lmaydi** — `409`.
- **Tekshirilmagan qaytarish uchun sotuvchi qaror qabul qila olmaydi** —
  `409: "Tovar hali tekshirilmagan"`.
- **Yetkazib bo'lmagani buyurtmani bekor qilmaydi** — u yo'lda qoladi;
  bekor qilishni faqat operator qiladi, va shundagina qoldiq qaytadi.

## Qolgani — brauzerda

Skript API'ni tekshiradi, tugmalarni bosmaydi. Qolgan qismi:

1. `./dev.sh`
2. Sotuvchi (`+998900000005`) → yangi tovar → Submit
3. Ombor (`+998900000003`) → Qabul qilish → sanash → Qabul qilaman
4. Mijoz ilovasi (`+998901234567`) → tovarni topish → sotib olish
5. Operator (`+998900000002`) → kuryer biriktirish
6. Kuryer (`+998900000004`) → **Yetkaza olmadim** → keyin operatorda
   "Yetkazish urinishlari" blokini ko'rish (yangi)
7. Qaytarish → ombor tekshiruvi → sotuvchi qarori

`docs/walkthrough.md` shu yo'lni qadam-baqadam, kutilgan natijalari bilan yozib
beradi.
