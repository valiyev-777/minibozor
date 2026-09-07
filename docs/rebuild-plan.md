# Mini Bozor — tozalash va qayta qurish rejasi

Sana: 2026-09-07. Repo: `minibozor`.

## 1. Nima qilindi

- Tag `pre-cleanup` (commit `91a228f`) — o'chirishdan oldingi to'liq holat, backoffice'dagi 20 ta commit qilinmagan o'zgarish ham ichida. Qaytarish: `git checkout pre-cleanup -- backoffice seller courier`.
- `backoffice/`, `seller/`, `courier/` papkalari **butunlay o'chirildi** (commit `3c9675d`, `011e94c`).
- `dev.sh` — panel papkasi yo'q bo'lsa o'sha panelni o'tkazib yuboradi, backend yolg'iz ishga tushadi. Papkalar qayta yaratilganda hech narsa o'zgartirmasdan ishlaydi (nomlar va portlar bir xil bo'lsa: backoffice 5173, seller 5174, courier 5175).
- Tegilmadi: `backend/`, `android/`, `ios/`, `shared/` (theme.css + ui), `design/`, `docs/`, `README.md`.

> Agar `./dev.sh` hali ishlab turgan bo'lsa — `./dev.sh down` qiling, aks holda eski vite serverlar `.vite/` papkalarini qaytadan yaratadi.

## 2. Backend — hozirgi model va oqimdan farqi

Backend yaxshi tuzilgan (state machine `app/transitions.py`da, 190 endpoint, 53 jadval), lekin **Ozon/WB modeli** bo'yicha yozilgan: bitta umumiy tovar kartochkasi (`Product`) + har sotuvchining o'z narxi/qoldig'i (`Offer`). Hozirgi oqim 8 qadam:

`sotuvchi kartochka taklif qiladi (Listing) → admin publish → sotuvchi Offer (narx) yaratadi → sotuvchi Supply e'lon qiladi → ombor qabul qiladi → xaridor oladi → operator ship → kuryer yetkazadi → payout`

Bizning oqim 5 qadam — **admin publish va alohida Offer qadami yo'q**, ombor qabul qilgani = tovar chiqdi:

`sotuvchi tovar + variantlar + narx + miqdor kiritadi → Submit → ombor qabul qiladi (son/sifat) → ilovada ko'rinadi → xaridor oladi → ombor yig'adi → kuryer → yetkazildi → (qaytarish → ombor tekshiradi → sotuvchi qarori)`

Jadvallarni buzmasdan, backendda **3 ta o'zgarish** kifoya:

| # | O'zgarish | Qayerda |
|---|---|---|
| B1 | `POST /staff/catalog/listings` bitta so'rovda **Product + variantlar + Offer (narx) + Supply (miqdor)** yaratsin. Sotuvchi uchun bu "Submit". Product `MODERATING`da qoladi, lekin admin ko'rmaydi. | `routers/listings.py`, `services.py` |
| B2 | `POST /staff/supplies/{id}/receive` qabul qilganda Product avtomatik `PUBLISHED` bo'lsin; rad etilsa (`cancel` + sabab) Product `REJECTED` bo'lsin, sabab sotuvchiga notification. Qisman qabul — kelgan son bilan publish. | `routers/warehouse.py`, `transitions.py` |
| B3 | Qaytarishga **tekshiruv natijasi + sotuvchi qarori** qo'shilsin: `ReturnRequest`ga `inspection: ok/damaged`, `seller_decision: relist/take_back/null`, `decision_due_at`. Endpointlar: `POST /staff/returns/{id}/inspect` (ombor), `POST /staff/returns/{id}/decide` (sotuvchi). `relist` → offer stock +1. N kun o'tsa va `ok` bo'lsa avtomatik relist (N config, default 7). | `models.py`, `routers/operations.py`, alembic |

## 3. Backend API — saqlash / o'chirish jadvali

Belgi: **KEEP** oqimga xizmat qiladi · **CHANGE** yuqoridagi B1–B3 · **LATER** oqimga kirmaydi, lekin mobil ilova (android/ios) ishlatadi — mobil ilovaga qo'l tekkizmagunimizcha o'chirmaymiz · **DELETE** hozir o'chiriladi (router + model + migratsiya + seed + test).

### Sotuvchi kabineti ishlatadi

| Endpoint | Qaror | Izoh |
|---|---|---|
| `POST /auth/otp/request`, `/otp/verify`, `/refresh`, `/logout` | KEEP | Hamma panel |
| `GET /staff/me`, `GET /staff/sellers/me` | KEEP | |
| `POST /staff/catalog/listings`, `GET …/listings`, `GET …/listings/{id}` | CHANGE (B1) | Tovar yaratish = submit |
| `GET /staff/catalog/categories`, `/brands` | KEEP | Faqat o'qish sotuvchi uchun |
| `POST /staff/media` | KEEP | Rasm yuklash |
| `GET /staff/offers`, `PATCH /staff/offers/{id}` | KEEP | Narxni o'zgartirish; `POST /staff/offers` sotuvchi UI'dan yo'qoladi (B1 ichida) |
| `PUT /staff/offers/{id}/stock` | DELETE | Sotuvchi qoldiqni o'zi o'zgartirmaydi — faqat ombor orqali |
| `POST /staff/supplies`, `GET /staff/supplies`, `GET …/{id}` | KEEP | Qo'shimcha miqdor topshirish (A5) |
| `POST /staff/removals`, `GET /staff/removals`, `GET …/{id}` | KEEP | Tovarni ombordan olib ketish (A6) |
| `GET /staff/orders` (o'z tovarlari filtri) | KEEP | Faqat ko'rish |
| `GET /staff/returns`, `POST /staff/returns/{id}/decide` | CHANGE (B3) | Qaror tugmalari |
| `GET /staff/payouts/current`, `GET …/statements`, `GET …/statements/{id}` | KEEP | Sodda hisob: sotildi / qaytdi / to'lanadigan |
| `GET /notifications`, `/unread-count`, `DELETE …/{id}` | KEEP | |
| `GET /staff/catalog/browse`, `/browse/{id}` | DELETE | Umumiy katalogdan kartochka tanlash — Ozon modeli, bizda yo'q |

### Backoffice — ombor

| Endpoint | Qaror | Izoh |
|---|---|---|
| `GET /staff/supplies`, `GET …/{id}`, `POST …/{id}/receive`, `POST …/{id}/cancel` | CHANGE (B2) | Qabul = publish, cancel = reject + sabab |
| `GET /staff/orders`, `GET …/{id}`, `POST …/{id}/status` | KEEP | `placed→packing→shipped` |
| `GET /staff/pickups`, `POST /staff/pickups`, `POST …/{id}/receive` | KEEP | Qaytarilgan tovar omborga keldi |
| `POST /staff/returns/{id}/inspect` | CHANGE (B3) | Yangi |
| `GET /staff/removals`, `POST …/{id}/prepare`, `POST …/{id}/collect` | KEEP | Sotuvchiga qaytarib berish |
| `GET /staff/stock/movements` | KEEP | Qoldiqlar tarixi (bitta jadval, grafiksiz) |
| `POST /staff/offers/{id}/write-off` | KEEP | Buzilgan tovarni hisobdan chiqarish |
| `GET /staff/offers/{id}/shelf` | DELETE | Javon logikasi |
| `POST/GET /staff/stock-counts`, `…/{id}`, `…/{id}/close` | DELETE | Inventarizatsiya — oqimda yo'q. Jadvallar `StockCount`, `StockCountLine` ketadi |

### Backoffice — operator

| Endpoint | Qaror | Izoh |
|---|---|---|
| `GET /staff/orders`, `GET …/{id}`, `POST …/{id}/status` (cancel) | KEEP | |
| `GET /staff/couriers`, `POST /staff/orders/{id}/courier` | KEEP | Kuryer biriktirish |
| `GET /staff/returns`, `…/{id}`, `POST …/approve`, `…/reject`, `…/refund` | KEEP | Pul qismi; B3 tekshiruv+qaror shu yoniga qo'shiladi |
| `GET /staff/shifts`, `…/{id}`, `POST …/{id}/count` | DELETE | Kuryer smenasi va kassa hisobi — oqimda yo'q. `CourierShift` jadvali ketadi |
| `GET/POST/PATCH /staff/delivery/slots` | LATER | Mobil checkout slot tanlaydi; kuryer oqimida hozircha kerak emas |
| `GET /staff/reviews`, `POST …/publish`, `…/reject` | DELETE | Sharh moderatsiyasi — keyin alohida qo'shamiz |

### Backoffice — admin

| Endpoint | Qaror | Izoh |
|---|---|---|
| `GET/POST/GET/PATCH /staff/sellers…` | KEEP | Sotuvchini tasdiqlash |
| `GET /staff/users`, `PATCH …/{id}/role` | KEEP | |
| `GET/POST/PATCH/DELETE /staff/catalog/categories`, `/brands` | KEEP | |
| `GET /staff/catalog/products`, `…/{id}`, `PATCH …/{id}`, `…/images…`, `…/variants…`, `…/specs`, `…/translations` | KEEP | Admin sotuvchi kiritgan kartochkani **tuzatishi** mumkin (moderatsiya emas, tahrir) |
| `POST /staff/catalog/products`, `POST …/{id}/status` | DELETE | Admin o'zi kartochka yaratmaydi va publish qilmaydi — bu omborning qabul qadami (B2) |
| `GET /staff/catalog/summary` | KEEP | Bosh ekran sonlari |
| `GET/POST/PATCH/DELETE /staff/payouts/tariffs`, `…/periods…`, `…/statements/{id}/adjust`, `…/pay` | LATER | Komissiya va to'lov davri — sotuvchi hisobi uchun kerak, lekin 2-bosqich. Hozir tegilmaydi, backoffice'da ekran yo'q |
| `GET/POST/PATCH/DELETE /staff/showcase/banners…`, `/sections…`, `/promos…` | DELETE | Banner, bosh sahifa bo'limlari, promokod. Jadvallar `Banner`, `HomeSection`, `PromoCode` ketadi; `POST /cart/promo` ham |

### Kuryer PWA

| Endpoint | Qaror | Izoh |
|---|---|---|
| `GET /courier/orders`, `POST …/{id}/deliver`, `POST …/{id}/failed` | KEEP | |
| `GET /courier/pickups`, `POST …/{run_id}/collect` | KEEP | Qaytarishni olib ketish |
| `GET /courier/shifts/current`, `POST /courier/shifts`, `…/{id}/close` | DELETE | Smena — oqimda yo'q |

### Mijoz ilovasi (android/ios — hozir tegilmaydi)

`catalog`, `search`, `home`, `favorites`, `cart`, `orders` (`create`, `list`, `get`, `cancel`, `return`, `reasons`), `delivery` (addresses, pickup-points, slots), `profile`, `content`, `cards` — **LATER**. Faqat `reviews.py` (6 endpoint) va `GET /products/{id}/reviews*` — DELETE bilan birga ketadi, chunki sharh tizimi butunlay o'chiriladi; ilovadagi sharh ekrani 404 oladi, bu qabul qilinadi.

### Natija

O'chiriladi: ~55 endpoint (showcase 14, reviews 6+3, stock-counts 4, shifts 3+3, browse 2, shelf 1, product create/status 2, offer stock 1, cart promo 1, product reviews 2), 9 jadval (`Banner`, `HomeSection`, `PromoCode`, `Review`, `ReviewLike`, `ReviewTag`, `StockCount`, `StockCountLine`, `CourierShift`). Qoladi ~135, shundan panellar ~55 tasini ishlatadi, qolgani mobil.

## 4. Panellarni qayta qurish — agentga prompt

Quyidagini AI agentga bering (har panel uchun alohida sessiya, ketma-ket: backend o'zgarishlari → seller → backoffice → courier).

---

Sen `minibozor` monorepo'sida ishlaysan. `backend/` — FastAPI, ishlab turadi, `http://localhost:8000/openapi.json` va `/docs`. Uch web panel (`backoffice/`, `seller/`, `courier/`) **o'chirilgan** va noldan qayta yoziladi. `docs/rebuild-plan.md` — yagona manba: §2 oqim, §3 qaysi endpoint ishlatiladi, §5 har rol ekranlari.

**Qoidalar**
1. Stack: React 18 + TypeScript + Vite, `react-router`, `@tanstack/react-query`, `openapi-typescript` bilan `/openapi.json`dan tiplar (`src/api/schema.d.ts` generatsiya, qo'lda yozilmaydi). Stil: `shared/theme.css` va `shared/ui/*` ishlatiladi, yangi UI kit qo'shilmaydi. Portlar: backoffice 5173, seller 5174, courier 5175 (`dev.sh` shuni kutadi).
2. **Faqat §3'da KEEP/CHANGE deb belgilangan endpointlar chaqiriladi.** Boshqa endpoint kerak bo'lib qolsa — to'xta va so'ra.
3. **Faqat §5'dagi ekranlar.** Dashboard grafik, analitika, sozlamalar sahifasi, "tez orada" placeholder — yo'q.
4. Tugmalar backenddan keladigan `next_states`dan chiqadi (`transitions.py` qoidasi), clientda status mantiqi takrorlanmaydi.
5. Kirish: telefon + OTP `123456`, seed akkauntlar: admin `+998900000001`, operator `+998900000002`, ombor `+998900000003`, kuryer `+998900000004`, sotuvchi `+998900000005`. Rol `GET /staff/me`dan olinadi, backoffice menyusi rolga qarab filtrlanadi.
6. Har ekran uchun: loading, empty, error holati (`shared/ui/states.tsx`). i18n — hozircha faqat o'zbek (lotin), kalitlar `src/lib/labels.ts`da.
7. Kuryer PWA: offline outbox **qo'shilmaydi** (1-versiyada online). PWA manifest + install — ha.
8. Ish tartibi: avval `src/api` + auth + shell + bo'sh route'lar → har ekranni alohida commit → oxirida `./dev.sh` bilan uch panel ochilishi va §2 oqimi qo'lda yurib chiqilishi (`docs/walkthrough.md` yangilanadi).

---

## 5. Har rol ekranlari (panel = faqat shular)

**seller** (`:5174`): `/login` · `/products` — tovarlar (holat: kutilmoqda / sotuvda / rad etilgan / tugagan, qoldiq) · `/products/new` — nomi, kategoriya, tavsif, rasmlar, narx, variantlar (o'lcham×rang, har birida miqdor) → **Submit** · `/products/:id` — detali, rad sababi, "qo'shimcha topshirish", "olib ketaman" · `/supplies` — topshiruvlar va holati · `/orders` — o'z tovarlari bo'yicha, faqat ko'rish · `/returns` — tekshiruv natijasi + [Qayta sotuvga] [Olib ketaman] · `/account` — sotildi / qaytdi / to'lanadigan (bitta ekran, 3 son + ro'yxat) · bildirishnoma qo'ng'irog'i shell'da.

**backoffice** (`:5173`):
- ombor: `/supplies` — kutilayotgan topshiruvlar → `/supplies/:id` qabul ekrani (variant bo'yicha kelgan son, sifat, [Qabul] [Rad + sabab]) · `/orders?status=placed|packing` — yig'ish, [Yig'ildi] [Kuryerga berildi] · `/pickups` — qaytgan tovarni qabul qilish → `/returns/:id` tekshiruv [Buzilmagan] [Buzilgan] · `/removals` — sotuvchiga qaytarib berish · `/stock` — movements jadvali.
- operator: `/orders` — hammasi, filtr, `/orders/:id` — kuryer biriktirish, bekor qilish · `/returns` — approve/reject/refund.
- admin: yuqoridagilar + `/sellers` (tasdiqlash) · `/users` (rollar) · `/categories`, `/brands` · `/products/:id/edit` (sotuvchi kartochkasini tuzatish) · `/` — 4 ta son: yangi buyurtma, kutilayotgan topshiruv, kutilayotgan qaytarish, yig'ilmagan buyurtma.

**courier** (`:5175`, PWA): `/` — bugungi vazifalar (yetkazish + olib ketish, bitta ro'yxat) · `/orders/:id` — manzil, telefon (tel: link), tovarlar, [Yetkazdim] [Yetkaza olmadim + sabab] · `/pickups/:id` — [Oldim].

## 6. Keyingi qadam

1. Backend B1–B3 (bir agent sessiyasi, `backend/tests` yashil bo'lishi shart).
2. §3 DELETE ro'yxatini backenddan o'chirish (alohida sessiya, alohida commit — qaytarish oson bo'lsin).
3. seller → backoffice → courier qayta qurish (§4 prompt).
4. Mobil ilova (android/ios) — alohida bosqich, hozir tegilmaydi.
