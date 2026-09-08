# Panellarni noldan qurish

Uch panel o'chirilgan. Backend, `android/`, `ios/`, `shared/` va `design/` — tegilmagan.
Eski kod kerak bo'lsa: `git checkout before-reset -- backoffice seller courier`.

## Nima qurilishi kerak

| Papka | Port | Kim kiradi |
|---|---|---|
| `backoffice/` | 5173 | admin `+998900000001` · operator `+998900000002` · ombor `+998900000003` |
| `seller/` | 5174 | sotuvchi `+998900000005` |
| `courier/` | 5175 | kuryer `+998900000004` |

Kirish: telefon + SMS kod `123456`. Rol `GET /api/v1/staff/me`dan olinadi.
`./dev.sh` shu nomlar va portlarni kutadi — o'zgartirmang.

## Oqim — hamma ekran shundan chiqadi

```
Sotuvchi tovar + rang + o'lcham + miqdor kiritadi → "Omborga topshirish"
   ↓  tovar: Kutilmoqda
Ombor sanab qabul qiladi  →  tovar Sotuvda, ilovada ko'rinadi
   ↓
Xaridor telefondan oladi  →  buyurtma: Yangi
   ↓
Ombor yig'adi  →  Tayyor  →  bo'sh zakaslar ro'yxatiga tushadi
   ↓
Kuryer o'zi oladi ("Olaman")  →  Yo'lda  →  Yetkazildi
   ↓
Qaytarish → ombor tekshiradi → sotuvchi qaror qiladi (qayta sotuvga / olib ketaman)
```

Muhim qoidalar:
- **Ombor "Yo'lda" qila olmaydi.** Kuryer o'zi olishi = yo'lga chiqishi. Operator kuryer biriktirmaydi.
- **Admin sotuvchining tovariga tegmaydi.** Faqat ko'radi.
- **Har rangning o'z rasmi majburiy.** Rasmsiz rang API tomonidan rad etiladi.

## Har panelda qanday ekran bo'lishi kerak

**seller** — Tovarlarim (ro'yxat + qidiruv + holat filtri) · Yangi tovar · Tovar sahifasi
(tahrirlash, narx, rang/o'lcham qo'shish, qo'shimcha topshirish) · Buyurtmalar (faqat
ko'rish) · Qaytarishlar (qaror tugmalari) · Hisob.

**backoffice** — ombor: Qabul qilish · Yig'ish · Qaytgan tovarlar · Sotuvchiga qaytarish ·
Qoldiq. operator: Buyurtmalar · Qaytarishlar. admin: yuqoridagilar + Sotuvchilar ·
Xodimlar · Kategoriyalar/Brendlar · bosh ekranda 4 son.

**courier** — Bo'sh zakaslar (`[Olaman]`) · Mening ishim · Zakas (yetkazdim / yetkaza
olmadim) · Qaytarishni olish · Profil (nechta yetkazgan, qancha ishlagan, qo'lidagi naqd).

## Qat'iy talablar

1. **API'ni o'zingiz o'qing:** `http://localhost:8000/docs` va `/openapi.json`. 145 endpoint
   bor. Tiplar `openapi-typescript` bilan generatsiya qilinadi (`src/api/schema.d.ts`) —
   qo'lda yozilmaydi.
2. **Tugmalar `next_statuses`dan chiqadi.** Backend qaysi o'tish mumkinligini aytadi;
   clientda status mantiqi qayta yozilmaydi.
3. **Stack:** React 18 + TypeScript + Vite + react-router + @tanstack/react-query.
   Stil: `shared/theme.css` va `shared/ui/*`. Yangi UI kutubxona qo'shilmaydi.
4. **Menyu:** laptopda chapda rail, telefonda pastda bar. Tepada tab strip — yo'q.
   Matn kengligi cheklangan (`max-w-5xl`), aks holda jadval ekran bo'yi cho'ziladi.
5. **Jadval tartibi:** ish navbati (`Yangi`, `Tayyor`, kutayotgan qaytarish) — eskisi
   birinchi; qolgan hamma ro'yxat — yangisi yuqorida.
6. **Jadval qatorida odam ko'radigan narsa birinchi:** ombor uchun tovar nomi, keyin
   xaridor. Ichki kod (`SUP-000012`, `1 satr`) ikkinchi darajali.
7. **Rang tanlash — palitra, hex kod emas.** Sotuvchi `#FFFFFF` yozmaydi.
8. **Til:** faqat o'zbek (lotin). Matn `src/lib/labels.ts`da, komponent ichida qattiq
   yozilmaydi.
9. Har ekranda: loading, bo'sh holat, xato holati.
10. `npx tsc -b --noEmit` toza bo'lishi shart.

## Ish tartibi

Bitta paneldan boshlang, tugating, keyin keyingisiga o'ting. Tartib: `seller` →
`backoffice` → `courier`.

Har panel uchun: `src/api` + auth + shell + bo'sh route'lar → har ekranni alohida commit →
oxirida `./dev.sh` bilan ochib, yuqoridagi oqimni qo'lda boshdan-oxir yurib chiqing.

**Ekran qo'shmang.** Yuqoridagi ro'yxatdan boshqa ekran, dashboard grafigi, analitika,
sozlamalar sahifasi — yo'q. Kerak bo'lib qolsa to'xtab so'rang.
