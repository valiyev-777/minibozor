# Mini Bozor — oqim va qayta qurish rejasi

Sana: 2026-09-08. Repo: `minibozor`.

> Bu hujjat **sizning oqimingiz** tilida yozilgan. Kodda boshqa nomlar bor (Offer, Supply,
> Listing, Removal, Statement) — ular §7'da tarjima qilingan va **hech qaysi ekranda
> ko'rinmaydi**. Foydalanuvchi faqat 4 ta narsani biladi: **Tovar, Topshiruv, Buyurtma,
> Qaytarish.**

---

## 1. Oqim — sizning so'zlaringiz bilan

```
SOTUVCHI                     OMBOR                    XARIDOR              KURYER
────────────────────────────────────────────────────────────────────────────────────
Tovar yaratadi
"Oq futbolka"
S=10, M=15, L=5
narx 89 000
      │
      │ SUBMIT
      ▼
 [Kutilmoqda] ──────────► Tovar keldi, sanaydi
                          S=10 ✓ M=15 ✓ L=4 (bittasi kam)
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
              [Rad etildi]                 [Sotuvda]
              sabab: "rasmga             ilovada paydo
               to'g'ri kelmadi"           bo'ladi, qoldiq 29
                    │                           │
              sotuvchi tuzatadi                 │ xaridor M oladi
              yoki olib ketadi                  ▼
                                          qoldiq 28 ─────────► yig'adi ──► oladi
                                                                              │
                                                                              ▼
                                                                         yetkazadi
                                                                              │
                                            ┌─────────────────────────────────┤
                                            ▼                                 ▼
                                      yoqmadi: qaytarish              yoqdi: tamom
                                            │
                          kuryer olib ketadi YOKI punktga tashlaydi
                                            │
                                            ▼
                                   Ombor tekshiradi
                                            │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                        Buzilmagan                    Buzilgan
                              │                           │
                    sotuvchiga xabar boradi               │
                              │                           │
                  ┌───────────┴───────────┐               │
                  ▼                       ▼               ▼
          [Qayta sotuvga]          [Olib ketaman]   sotuvchiga xabar,
          qoldiq +1, ilovada        ombor sotuvchiga  hisobdan chiqadi
          yana ko'rinadi            beradi
```

**Tovar holatlari — jami 4 ta:** `Kutilmoqda` · `Sotuvda` · `Rad etildi` · `Tugagan`
**Buyurtma holatlari — jami 5 ta:** `Yangi` · `Yig'ilgan` · `Yo'lda` · `Yetkazildi` · `Bekor qilindi`
**Qaytarish holatlari — jami 4 ta:** `So'raldi` · `Omborda` · `Tekshirildi` · `Yopildi`

Boshqa holat yo'q. Kodda ko'proq bo'lsa — o'chiriladi.

---

## 2. Nega birinchi reja chalkash bo'ldi

Kod **Ozon/Wildberries modeli** bo'yicha yozilgan, sizning modelingiz boshqa:

| | Ozon modeli (koddagi) | Sizning modelingiz |
|---|---|---|
| Kartochka | Umumiy. "Samsung A54" bitta, 20 sotuvchi shunga narx qo'yadi | Bitta tovar = bitta sotuvchi. Umumiy kartochka yo'q |
| Narx/qoldiq | Alohida qatlam (`Offer`) | Tovarning o'zida |
| Kim publish qiladi | Admin kartochkani ko'rib chiqadi | **Ombor qabul qilgani = publish.** Admin moderatsiya qadami yo'q |
| Tovar topshirish | Alohida qadam (`Supply`) | Submit'ning ichida |
| Sotuvchi qoldiqni | O'zi o'zgartiradi | O'zgartirmaydi. Faqat ombor sanaydi |

Ya'ni koddagi oqim **8 qadam**, sizdagi **5 qadam**. Farq: admin publish qadami va alohida narx qadami — ikkisi ham ketadi.

---

## 3. Sotuvchi kabineti — 4 ta ekran, boshqa hech narsa

### 3.1 Tovarlarim (bosh ekran)

```
┌──────────────────────────────────────────────────────┐
│  Tovarlarim                        [+ Yangi tovar]   │
├──────────────────────────────────────────────────────┤
│  ┌────┐  Oq futbolka                                 │
│  │IMG │  89 000 so'm · S 10, M 15, L 4               │
│  └────┘  🟢 Sotuvda · omborda 29 dona                │
├──────────────────────────────────────────────────────┤
│  ┌────┐  Ko'k krossovka                              │
│  │IMG │  340 000 so'm · 40, 41, 42                   │
│  └────┘  🟡 Kutilmoqda · omborga topshirilmagan      │
├──────────────────────────────────────────────────────┤
│  ┌────┐  Qora shim                                   │
│  │IMG │  150 000 so'm                                │
│  └────┘  🔴 Rad etildi · "rasm tovarga mos emas"     │
│          [Tuzatib qayta yuborish]  [Olib ketaman]    │
└──────────────────────────────────────────────────────┘
```

Har qatorda: rasm, nomi, narx, variantlar, holat, omborda qancha borligi. Rad etilgan bo'lsa — sabab shu yerda, tugmalar bilan.

### 3.2 Yangi tovar (bitta forma, bitta Submit)

```
┌──────────────────────────────────────────────────────┐
│  Yangi tovar                                         │
├──────────────────────────────────────────────────────┤
│  Nomi        [Oq futbolka                        ]   │
│  Kategoriya  [Erkaklar kiyimi › Futbolka       ▾ ]   │
│  Tavsif      [                                   ]   │
│  Rasmlar     [+] [IMG] [IMG] [IMG]                   │
│  Narx        [89 000] so'm                           │
├──────────────────────────────────────────────────────┤
│  O'lchamlar va soni                                  │
│     ☑ S   [10] dona                                  │
│     ☑ M   [15] dona                                  │
│     ☑ L   [ 5] dona                                  │
│     ☐ XL                                             │
│     ☐ XXL                                            │
│                                                      │
│  Rang (ixtiyoriy)  [Oq ▾]                            │
├──────────────────────────────────────────────────────┤
│  Jami omborga topshiriladi: 30 dona                  │
│                                                      │
│         [Bekor]        [Omborga topshirish]          │
└──────────────────────────────────────────────────────┘
```

**Bitta tugma.** Bosilganda: tovar yaratiladi + narx qo'yiladi + topshiruv hujjati ochiladi — hammasi bir vaqtda. Sotuvchi bir dona forma to'ldiradi, tamom.

O'lcham ro'yxati kategoriyadan keladi (kiyimda S–XXL, poyabzalda 36–45, texnikada o'lcham yo'q — faqat rang yoki hech narsa).

### 3.3 Buyurtmalar (faqat ko'rish)

```
┌──────────────────────────────────────────────────────┐
│  Buyurtmalar                    Hammasi ▾            │
├──────────────────────────────────────────────────────┤
│  #1042 · Oq futbolka, M, 1 dona · 89 000 so'm        │
│  8-sentabr 14:20 · 🚚 Yo'lda                         │
├──────────────────────────────────────────────────────┤
│  #1038 · Ko'k krossovka, 41 · 340 000 so'm           │
│  7-sentabr · ✅ Yetkazildi                            │
└──────────────────────────────────────────────────────┘
```

Sotuvchi hech narsa bosmaydi — buyurtmani biz boshqaramiz. Xaridor ismi/telefoni **ko'rinmaydi**.

### 3.4 Qaytarishlar (qaror kutayotganlar yuqorida)

```
┌──────────────────────────────────────────────────────┐
│  Qaytarishlar                                        │
├──────────────────────────────────────────────────────┤
│  ⚠️  QARORINGIZ KUTILMOQDA                            │
│                                                      │
│  Oq futbolka, M · #1042                              │
│  Sabab: "o'lcham kichik keldi"                       │
│  Ombor tekshirdi: ✅ Buzilmagan, sotuvga yaroqli      │
│  [Foto]                                              │
│                                                      │
│  5 kun ichida javob bermasangiz — avtomatik          │
│  qayta sotuvga chiqadi.                              │
│                                                      │
│      [Qayta sotuvga chiqar]   [Olib ketaman]         │
├──────────────────────────────────────────────────────┤
│  Qora shim, 48 · #1015 · 3-sentabr                   │
│  Ombor tekshirdi: ❌ Buzilgan                         │
│  Hisobdan chiqarildi                                 │
└──────────────────────────────────────────────────────┘
```

### Va shell'da

Yuqorida: do'kon nomi, 🔔 bildirishnoma. Pastda yoki yon menyuda: shu 4 ta bo'lim + **Hisob** — bitta oddiy ekran, uch son: `Sotildi: 2 340 000` · `Qaytdi: 89 000` · `Sizga to'lanadi: 2 025 000`, ostida qatorlar ro'yxati. Grafik yo'q, davr tanlash yo'q.

**Sotuvchi kabinetida BO'LMAYDIGAN narsalar:** "Offer", "Supply", "Listing" so'zlari · qoldiqni qo'lda o'zgartirish · umumiy katalogdan kartochka tanlash · alohida "narx qo'yish" qadami · javon/katak · reklama, promokod, banner · sharh moderatsiyasi · analitika/grafik.

---

## 4. Ombor paneli — 3 ta ekran

### 4.1 Qabul qilish (bosh ekran)

```
┌──────────────────────────────────────────────────────┐
│  Qabul qilish                            3 ta kutadi │
├──────────────────────────────────────────────────────┤
│  Chorsu Bozori · Oq futbolka · 30 dona · bugun 10:15 │
│  Chorsu Bozori · Ko'k krossovka · 12 dona · kecha    │
└──────────────────────────────────────────────────────┘

Bittasini bossa:
┌──────────────────────────────────────────────────────┐
│  Oq futbolka · Chorsu Bozori                         │
│  [IMG] [IMG] [IMG]         89 000 so'm               │
├──────────────────────────────────────────────────────┤
│  Sanang:                                             │
│     S    aytilgan 10   keldi [10]                    │
│     M    aytilgan 15   keldi [15]                    │
│     L    aytilgan  5   keldi [ 4]  ⚠️ 1 kam          │
│                                                      │
│  Izoh (ixtiyoriy) [                              ]   │
├──────────────────────────────────────────────────────┤
│   [Qabul qilaman — sotuvga chiqadi]                  │
│   [Rad etaman]  ← sabab yozish majburiy              │
└──────────────────────────────────────────────────────┘
```

"Qabul qilaman" bosilishi = **tovar ilovada paydo bo'ladi**, qoldiq = kelgan son. Boshqa hech kim tasdiqlamaydi.

### 4.2 Yig'ish

```
┌──────────────────────────────────────────────────────┐
│  Yig'ish                                  5 ta yangi │
├──────────────────────────────────────────────────────┤
│  #1042  Oq futbolka, M, 1 dona                       │
│         Chorsu Bozori          [Yig'ildi]            │
├──────────────────────────────────────────────────────┤
│  #1041  Ko'k krossovka, 41, 1 dona                   │
│         🟢 Yig'ilgan           [Kuryerga berdim]     │
└──────────────────────────────────────────────────────┘
```

### 4.3 Qaytganlarni qabul qilish

```
┌──────────────────────────────────────────────────────┐
│  Qaytgan tovarlar                                    │
├──────────────────────────────────────────────────────┤
│  Oq futbolka, M · #1042 · kuryer Jasur keltirdi      │
│  Sabab: "o'lcham kichik" · [Foto]                    │
│                                                      │
│  Tekshirdingizmi?                                    │
│  [✅ Buzilmagan]      [❌ Buzilgan]                   │
├──────────────────────────────────────────────────────┤
│  Sotuvchiga qaytarib berish                          │
│  Qora shim × 3 · Chorsu Bozori   [Berdim]            │
└──────────────────────────────────────────────────────┘
```

**Omborda BO'LMAYDIGAN:** inventarizatsiya (stock-count), javon/katak/zona, tovar ko'chirish operatsiyalari.

---

## 5. Operator va admin

**Operator** — 2 ekran: `Buyurtmalar` (hammasi, filtr, kuryer biriktirish, bekor qilish) · `Qaytarishlar` (pulni qaytarishni tasdiqlash).

**Admin** — operator + ombor ekranlari, ustiga: `Sotuvchilar` (yangi sotuvchini tasdiqlash) · `Xodimlar` (rol berish) · `Kategoriyalar` (va har kategoriyaning o'lcham ro'yxati — bu muhim, sotuvchi formasi shundan oziqlanadi) · `Tovarni tahrirlash` (sotuvchi xato yozgan bo'lsa tuzatish) · bosh ekranda **4 ta son**: yangi buyurtma, qabul kutayotgan tovar, yig'ilmagan buyurtma, qaror kutayotgan qaytarish.

**Adminda BO'LMAYDIGAN:** banner/bosh sahifa bo'limlari · promokod · sharh moderatsiyasi · kuryer smenasi va kassa · to'lov davrlari va tariflar (2-bosqichda) · grafik/analitika.

---

## 6. Kuryer (PWA, telefon)

```
┌────────────────────────────┐
│  Bugun · 4 vazifa          │
├────────────────────────────┤
│  🚚 #1042 Yunusobod 12-45  │
│     1 dona · 89 000 naqd   │
├────────────────────────────┤
│  ↩️  #1015 Chilonzor 8-12   │
│     Qaytarishni olish      │
└────────────────────────────┘

Bittasini bossa:
┌────────────────────────────┐
│  #1042                     │
│  Yunusobod 12-45, 3-qavat  │
│  📞 +998 90 123 45 67      │
│  Oq futbolka, M, 1 dona    │
│  Olinadi: 89 000 so'm      │
│                            │
│  [Yetkazdim]               │
│  [Yetkaza olmadim]         │
└────────────────────────────┘
```

**Kuryerda BO'LMAYDIGAN:** smena ochish/yopish, kassa hisobi, offline outbox (1-versiyada online).

---

## 7. Kod nomlari ↔ bizning nomlar

Agent uchun tarjima. **Chap ustun UI'da hech qachon ko'rinmaydi.**

| Koddagi nom | Bu nima | UI'da |
|---|---|---|
| `Product` | tovar kartochkasi | **Tovar** |
| `ProductVariant` | o'lcham/rang | **O'lcham**, **Rang** |
| `Offer` | narx + qoldiq qatlami | ko'rinmaydi — tovarning o'zida ko'rsatiladi |
| `Listing` | sotuvchining kartochka taklifi | ko'rinmaydi — "Yangi tovar" formasi |
| `Supply` / `SupplyLine` | omborga topshirish hujjati | **Topshiruv** (yoki umuman ko'rsatilmaydi) |
| `RemovalOrder` | sotuvchiga qaytarib berish | **Olib ketaman** |
| `ReturnRequest` | xaridor qaytarishi | **Qaytarish** |
| `PickupRun` | qaytarilganni yig'ib kelish | ko'rinmaydi — kuryer vazifasi |
| `StockMovement` | qoldiq tarixi | **Harakatlar** (faqat omborda) |
| `SellerStatement` | sotuvchi hisobi | **Hisob** |

### Backendda 3 ta o'zgarish kerak

| # | Nima | Qayerda |
|---|---|---|
| **B1** | `POST /staff/catalog/listings` bitta so'rovda tovar + variantlar + narx + topshiruvni yaratsin. Sotuvchi uchun bu "Omborga topshirish" tugmasi. Tovar `MODERATING`da qoladi, lekin **admin navbatiga tushmaydi** — ombor navbatiga tushadi. | `routers/listings.py`, `services.py` |
| **B2** | Ombor qabul qilganda (`POST /staff/supplies/{id}/receive`) tovar avtomatik `PUBLISHED` bo'lsin, qoldiq = kelgan son. Rad etilsa (`cancel` + majburiy sabab) tovar `REJECTED` bo'lsin va sabab sotuvchiga bildirishnoma bilan borsin. | `routers/warehouse.py`, `transitions.py` |
| **B3** | Qaytarishga tekshiruv va sotuvchi qarori qo'shilsin: `ReturnRequest`ga `inspection` (`ok`/`damaged`), `seller_decision` (`relist`/`take_back`), `decision_due_at`. Yangi: `POST /staff/returns/{id}/inspect` (ombor), `POST /staff/returns/{id}/decide` (sotuvchi). `relist` → qoldiq +1. N kun o'tsa va `ok` bo'lsa avtomatik `relist` (N — sozlama, default 7). | `models.py`, `routers/operations.py`, alembic |

### O'chiriladi

**Endpointlar (~55):** `showcase.py` butunlay (banner, bosh sahifa bo'limlari, promokod — 14) · `reviews.py` butunlay + `GET /products/{id}/reviews*` (9) · stock-counts (4) · kuryer va operator smenalari (6) · `GET /staff/catalog/browse*` (2) · `GET /staff/offers/{id}/shelf` (1) · `POST /staff/catalog/products` va `POST …/{id}/status` (2) · `PUT /staff/offers/{id}/stock` (1) · `POST /cart/promo` (1).

**Jadvallar (9):** `Banner`, `HomeSection`, `PromoCode`, `Review`, `ReviewLike`, `ReviewTag`, `StockCount`, `StockCountLine`, `CourierShift`.

**Tegilmaydi (mobil ilova ishlatadi):** `catalog`, `search`, `home`, `favorites`, `cart`, `orders`, `delivery`, `profile`, `content`, `cards`. To'lov davrlari va tariflar (`payouts.py`) — qoladi, lekin panelda ekrani yo'q.

---

## 8. Agentga beriladigan prompt

Har panel uchun alohida sessiya. Quyidagini o'zgartirmasdan bering:

---

Sen `minibozor` monorepo'sida ishlaysan. `backend/` — FastAPI, ishlab turadi (`http://localhost:8000/docs`). Uch web panel o'chirilgan va noldan yoziladi.

**`docs/rebuild-plan.md`ni to'liq o'qi. U yagona manba.** §1 — oqim, §3–6 — har panelning ekranlari va ulardagi haqiqiy matn, §7 — kod nomlari va bizning nomlar o'rtasidagi tarjima.

Qat'iy qoidalar:

1. **§3–6 dagi ekranlardan boshqa ekran yaratma.** Dashboard grafik, sozlamalar sahifasi, analitika, "tez orada" — yo'q. Ekran kerak bo'lib qolsa, to'xta va so'ra.
2. **§7 chap ustundagi so'zlar (Offer, Supply, Listing, Removal, Statement) UI'da hech qanday ko'rinishda chiqmasin** — na sarlavhada, na tugmada, na URL'da, na xato xabarida. O'ng ustundagi nomlar ishlatiladi.
3. Holatlar §1 oxiridagi ro'yxatdan: tovar 4, buyurtma 5, qaytarish 4. Backend boshqa holat qaytarsa — bizning holatga map qil, yangi holat UI'ga chiqmasin.
4. Tugmalar backenddan keladigan ruxsat etilgan o'tishlardan chiqadi (`app/transitions.py`), clientda status mantiqi qayta yozilmaydi.
5. Stack: React 18 + TypeScript + Vite, `react-router`, `@tanstack/react-query`. Tiplar `openapi-typescript` bilan `/openapi.json`dan generatsiya (`src/api/schema.d.ts` — qo'lda yozilmaydi). Stil: `shared/theme.css` va `shared/ui/*`; yangi UI kutubxona qo'shilmaydi.
6. Portlar: `backoffice` 5173, `seller` 5174, `courier` 5175 — `dev.sh` shuni kutadi.
7. Kirish: telefon + OTP `123456`. Seed: admin `+998900000001`, operator `+998900000002`, ombor `+998900000003`, kuryer `+998900000004`, sotuvchi `+998900000005`. Rol `GET /staff/me`dan olinadi, menyu rolga qarab filtrlanadi.
8. Til: faqat o'zbek (lotin). Matn `src/lib/labels.ts`da, komponent ichida qattiq yozilmaydi. §3–6 dagi matnlarni **so'zma-so'z** ishlat.
9. Har ekranda: loading, bo'sh holat, xato holati (`shared/ui/states.tsx`).
10. Tartib: `src/api` + auth + shell + bo'sh route'lar → har ekranni alohida commit → oxirida `./dev.sh` bilan ochib, §1 oqimini qo'lda yurib chiq.

---

## 9. Ish tartibi

| # | Ish | Kim | Tekshiruv |
|---|---|---|---|
| 1 | §7 B1–B3 backend o'zgarishlari | agent, alohida sessiya | `backend/tests` yashil |
| 2 | §7 "O'chiriladi" ro'yxatini backenddan olib tashlash | agent, alohida sessiya va alohida commit | `/docs` ochiladi, testlar yashil |
| 3 | `seller/` panelini qurish | agent, §8 prompt | sotuvchi tovar qo'shib Submit qila oladi |
| 4 | `backoffice/` panelini qurish | agent, §8 prompt | ombor qabul qiladi, tovar ilovada chiqadi |
| 5 | `courier/` panelini qurish | agent, §8 prompt | oqim boshdan-oxir yuradi |
| 6 | Mobil ilova (`android/`, `ios/`) | keyingi bosqich | — |

**Qaytarish nuqtasi:** `git checkout pre-cleanup -- backoffice seller courier` — o'chirilgan uch panelning eski kodi shu tegda turadi.
