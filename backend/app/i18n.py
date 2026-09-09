"""Answering in the language the app asked for.

Two different kinds of text need translating and they are handled separately:

* **Labels written in code** — order statuses, delivery wording, sort options,
  error details. These live in [LABELS] below, next to the code that uses them.
* **Content in the database** — category names, banner copy, product
  descriptions, the FAQ. These live in the ``translation`` table, keyed by the
  row they belong to, so new content can be translated without a deploy.

The active language is a context variable set once per request by the
middleware in ``app.main``. That keeps it out of twenty function signatures in
``services.py``, which otherwise thread only a session around.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, timedelta

from sqlmodel import Session, select

DEFAULT = "uz"
SUPPORTED = (DEFAULT, "ru", "en")

_lang: ContextVar[str] = ContextVar("lang", default=DEFAULT)
_cache: ContextVar[dict | None] = ContextVar("translation_cache", default=None)


def parse_accept_language(header: str | None) -> str:
    """First supported language in an Accept-Language header, else Uzbek.

    Quality values are honoured so a browser sending ``ru;q=0.9, en;q=0.8``
    gets Russian, but the app sends a bare tag like ``ru``.
    """
    if not header:
        return DEFAULT
    entries: list[tuple[float, str]] = []
    for part in header.split(","):
        piece, _, params = part.strip().partition(";")
        tag = piece.strip().lower().split("-")[0]
        quality = 1.0
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                quality = 0.0
        if tag in SUPPORTED:
            entries.append((quality, tag))
    if not entries:
        return DEFAULT
    return max(entries, key=lambda e: e[0])[1]


def set_language(lang: str) -> None:
    _lang.set(lang if lang in SUPPORTED else DEFAULT)
    _cache.set(None)


def current() -> str:
    return _lang.get()


# ─────────────────────────────── labels in code ────────────────────────────

LABELS: dict[str, dict[str, str]] = {
    # order status and delivery
    "delivered": {"uz": "Yetkazildi", "ru": "Доставлен", "en": "Delivered"},
    "cancelled": {"uz": "Bekor qilindi", "ru": "Отменён", "en": "Cancelled"},
    "pickup": {"uz": "Punktdan olish", "ru": "Самовывоз", "en": "Pick-up point"},
    "eta_pending": {
        "uz": "Yetkazish sanasi aniqlanmoqda",
        "ru": "Дата доставки уточняется",
        "en": "Delivery date being confirmed",
    },
    "between": {"uz": "{label} {window} orasida", "ru": "{label} с {window}",
                "en": "{label} between {window}"},
    "delivered_on": {"uz": "{date} yetkaziladi", "ru": "Доставим {date}",
                     "en": "Arrives {date}"},
    "today": {"uz": "Bugun", "ru": "Сегодня", "en": "Today"},
    "tomorrow": {"uz": "Ertaga", "ru": "Завтра", "en": "Tomorrow"},
    "eta_next_day": {"uz": "Ertaga yetkaziladi", "ru": "Доставим завтра",
                     "en": "Arrives tomorrow"},
    "eta_few_days": {"uz": "2–3 kunda yetkaziladi", "ru": "Доставим за 2–3 дня",
                     "en": "Arrives in 2–3 days"},
    "eta_free_suffix": {"uz": " · bepul", "ru": " · бесплатно", "en": " · free"},
    "doc_not_found": {"uz": "Hujjat topilmadi", "ru": "Документ не найден",
                      "en": "Document not found"},
    "support_hours": {"uz": "Har kuni 08:00–22:00", "ru": "Ежедневно 08:00–22:00",
                      "en": "Every day 08:00–22:00"},
    # messages returned by the routers
    "auth_required": {
        "uz": "Avtorizatsiya talab qilinadi",
        "ru": "Требуется авторизация",
        "en": "You need to sign in",
    },
    "forbidden": {
        "uz": "Bu amal uchun ruxsatingiz yo'q",
        "ru": "Недостаточно прав для этого действия",
        "en": "You don't have permission for this",
    },
    "refresh_invalid": {
        "uz": "Refresh token yaroqsiz",
        "ru": "Refresh-токен недействителен",
        "en": "That refresh token isn't valid",
    },
    "refresh_revoked": {
        "uz": "Refresh token bekor qilingan",
        "ru": "Refresh-токен отозван",
        "en": "That refresh token has been revoked",
    },
    "pin_verified": {"uz": "Tasdiqlandi", "ru": "Подтверждено", "en": "Confirmed"},
    "notification_not_found": {
        "uz": "Bildirishnoma topilmadi",
        "ru": "Уведомление не найдено",
        "en": "Notification not found",
    },
    "address_required": {
        "uz": "Yetkazish manzilini tanlang",
        "ru": "Выберите адрес доставки",
        "en": "Choose a delivery address",
    },
    "otp_expired": {
        "uz": "Kod eskirgan — qaytadan so'rang",
        "ru": "Код устарел — запросите новый",
        "en": "That code has expired — request a new one",
    },
    "otp_too_many": {
        "uz": "Juda ko'p urinish — qaytadan so'rang",
        "ru": "Слишком много попыток — запросите новый код",
        "en": "Too many attempts — request a new code",
    },
    "otp_wrong": {"uz": "Kod noto'g'ri", "ru": "Неверный код", "en": "That code isn't right"},
    "user_not_found": {
        "uz": "Foydalanuvchi topilmadi",
        "ru": "Пользователь не найден",
        "en": "User not found",
    },
    "signed_out": {
        "uz": "Hisobdan chiqdingiz",
        "ru": "Вы вышли из аккаунта",
        "en": "You've been signed out",
    },
    "pin_current_wrong": {
        "uz": "Joriy kod noto'g'ri",
        "ru": "Неверный текущий код",
        "en": "That current code isn't right",
    },
    "pin_changed": {"uz": "PIN o'zgartirildi", "ru": "PIN изменён", "en": "PIN changed"},
    "pin_wrong": {"uz": "PIN noto'g'ri", "ru": "Неверный PIN", "en": "That PIN isn't right"},
    "pin_removed": {"uz": "PIN o'chirildi", "ru": "PIN удалён", "en": "PIN removed"},
    "product_not_found": {
        "uz": "Mahsulot topilmadi",
        "ru": "Товар не найден",
        "en": "Product not found",
    },
    "product_out_of_stock": {
        "uz": "Mahsulot mavjud emas",
        "ru": "Товара нет в наличии",
        "en": "That product is out of stock",
    },
    "variant_required": {
        "uz": "Qaysi rang va o'lchamligini ko'rsating",
        "ru": "Укажите, какой это цвет и размер",
        "en": "Say which colour and size this is",
    },
    "choose_a_size": {
        "uz": "O'lchamni tanlang",
        "ru": "Выберите размер",
        "en": "Choose a size",
    },
    "choose_a_colour": {
        "uz": "Rangni tanlang",
        "ru": "Выберите цвет",
        "en": "Choose a colour",
    },
    "variant_invalid": {
        "uz": "Variant noto'g'ri",
        "ru": "Неверный вариант",
        "en": "That option isn't valid",
    },
    "cart_item_not_found": {
        "uz": "Savatda topilmadi",
        "ru": "Не найдено в корзине",
        "en": "Not found in your cart",
    },
    "category_not_found": {
        "uz": "Turkum topilmadi",
        "ru": "Категория не найдена",
        "en": "Category not found",
    },
    "address_removed": {"uz": "Manzil o'chirildi", "ru": "Адрес удалён", "en": "Address removed"},
    "address_not_found": {
        "uz": "Manzil topilmadi",
        "ru": "Адрес не найден",
        "en": "Address not found",
    },
    "fav_added": {
        "uz": "Sevimlilarga qo'shildi",
        "ru": "Добавлено в избранное",
        "en": "Added to favourites",
    },
    "fav_removed": {
        "uz": "Sevimlilardan olib tashlandi",
        "ru": "Убрано из избранного",
        "en": "Removed from favourites",
    },
    "marked_read": {
        "uz": "O'qilgan deb belgilandi",
        "ru": "Отмечено как прочитанное",
        "en": "Marked as read",
    },
    "deleted": {"uz": "O'chirildi", "ru": "Удалено", "en": "Deleted"},
    "cart_empty": {"uz": "Savat bo'sh", "ru": "Корзина пуста", "en": "Your cart is empty"},
    "order_placed": {"uz": "Buyurtma qabul qilindi", "ru": "Заказ принят", "en": "Order placed"},
    "order_not_cancellable": {
        "uz": "Bu buyurtmani bekor qilib bo'lmaydi",
        "ru": "Этот заказ отменить нельзя",
        "en": "This order can't be cancelled",
    },
    "order_cancelled": {
        "uz": "Buyurtma bekor qilindi",
        "ru": "Заказ отменён",
        "en": "Order cancelled",
    },
    "return_delivered_only": {
        "uz": "Faqat yetkazilgan buyurtmani qaytarish mumkin",
        "ru": "Вернуть можно только доставленный заказ",
        "en": "Only a delivered order can be returned",
    },
    "order_not_found": {
        "uz": "Buyurtma topilmadi",
        "ru": "Заказ не найден",
        "en": "Order not found",
    },
    "account_deleted": {"uz": "Hisob o'chirildi", "ru": "Аккаунт удалён", "en": "Account deleted"},
    "order_placed_note": {
        "uz": "{code} qabul qilindi — tez orada yig'amiz",
        "ru": "{code} принят — скоро начнём сборку",
        "en": "{code} placed — we'll start picking shortly",
    },
    "order_cancelled_note": {
        "uz": "{code} bekor qilindi. To'lov 1–3 kunda qaytariladi.",
        "ru": "{code} отменён. Оплата вернётся за 1–3 дня.",
        "en": "{code} cancelled. The payment returns within 1–3 days.",
    },
    # what an operator is told when a move is not allowed
    "bad_transition": {
        "uz": "{from_} holatidan {to} holatiga o'tib bo'lmaydi",
        "ru": "Переход из «{from_}» в «{to}» невозможен",
        "en": "{from_} cannot become {to}",
    },
    "cancel_is_operators": {
        "uz": "Buyurtmani bekor qilish operator ishi — ombor faqat yig'adi "
              "va kuryerga topshiradi",
        "ru": "Отменяет заказ оператор — склад только собирает и передаёт "
              "курьеру",
        "en": "Cancelling is the operator's — the warehouse picks and hands "
              "over, and nothing else",
    },
    "nothing_new": {
        "uz": "Yangi rang yoki o'lcham yo'q va miqdor ham kiritilmagan",
        "ru": "Нет ни нового цвета или размера, ни количества",
        "en": "Nothing new here, and no quantity either",
    },
    "colour_needs_photo": {
        "uz": "Har rangning o'z rasmi bo'lishi kerak. Rasmsiz rang: {colours}",
        "ru": "У каждого цвета должно быть своё фото. Без фото: {colours}",
        "en": "Every colour needs its own photograph. Without one: {colours}",
    },
    # The three gates between a pile on the shelf and a card in the shop. Each
    # is named on its own so a queue can say what is missing without anybody
    # opening the card to find out.
    "needs_category": {
        "uz": "kategoriya",
        "ru": "категория",
        "en": "a category",
    },
    "needs_price": {
        "uz": "sotuv narxi",
        "ru": "цена продажи",
        "en": "a selling price",
    },
    "needs_photo": {
        "uz": "rasm",
        "ru": "фото",
        "en": "a photograph",
    },
    "tile_held_back": {
        "uz": "Javonda bor, do'konda yo'q",
        "ru": "На полке есть, в магазине нет",
        "en": "On the shelf, not in the shop",
    },
    "sack_sorted_note": {
        "uz": "Saralandi — tovarlari uyum bo'lib kirdi",
        "ru": "Разобрано — товар оформлен партиями",
        "en": "Sorted — the goods went in as piles",
    },
    # The soft list: what a card is missing to read like a shop. Not refused,
    # so the wording is a thing to do rather than a thing that is wrong.
    "needs_subtitle": {
        "uz": "qisqa izoh",
        "ru": "короткое описание",
        "en": "a short line",
    },
    "needs_description": {
        "uz": "tavsif",
        "ru": "описание",
        "en": "a description",
    },
    "needs_specs": {
        "uz": "xususiyatlar",
        "ru": "характеристики",
        "en": "a specification table",
    },
    "needs_more_photos": {
        "uz": "ko'proq rasm",
        "ru": "больше фото",
        "en": "more photographs",
    },
    "card_not_ready": {
        "uz": "Sotuvga chiqarish uchun yetishmaydi: {gaps}",
        "ru": "Для продажи не хватает: {gaps}",
        "en": "Not ready for sale — missing: {gaps}",
    },
    "move_nowhere": {
        "uz": "Bir katakdan o'sha katakka ko'chirib bo'lmaydi",
        "ru": "Нельзя переместить в ту же ячейку",
        "en": "That is the cell it is already in",
    },
    "card_deleted": {
        "uz": "Karta o'chirildi",
        "ru": "Карточка удалена",
        "en": "The card is gone",
    },
    "card_archived_not_deleted": {
        "uz": "Kartaning tarixi bor — o'chirilmadi, arxivga olindi",
        "ru": "У карточки есть история — не удалена, а в архиве",
        "en": "This card has history — archived rather than deleted",
    },
    "card_has_history": {
        "uz": "qoldiq harakati yoki buyurtmasi bor",
        "ru": "есть движение остатка или заказ",
        "en": "a stock movement or an order names it",
    },
    "no_such_cell": {
        "uz": "Bunday yacheyka yo'q: {code}",
        "ru": "Такой ячейки нет: {code}",
        "en": "No such cell: {code}",
    },
    "pile_needs_a_colour": {
        "uz": "Qaysi rang kelganini tanlang: {colours}",
        "ru": "Выберите, какой цвет пришёл: {colours}",
        "en": "Say which colour arrived: {colours}",
    },
    "pile_needs_a_name": {
        "uz": "Tavar nomi yoki turi kerak",
        "ru": "Нужно название или тип товара",
        "en": "The goods need a name or a kind",
    },
    "order_taken": {
        "uz": "Bu zakasni boshqa kuryer olib ketdi",
        "ru": "Этот заказ уже забрал другой курьер",
        "en": "Another courier has taken this one",
    },
    "order_not_ready": {
        "uz": "Zakas hali tayyor emas — ombor yig'ishini kutmoqda",
        "ru": "Заказ ещё не готов — склад его собирает",
        "en": "Not ready yet — the warehouse is still picking it",
    },
    "shipping_is_couriers": {
        "uz": "Zakasni yo'lga chiqarish kuryer ishi — u ombordan o'zi olib "
              "ketadi. Ombor faqat 'Tayyor' deb belgilaydi",
        "ru": "Заказ отправляет курьер — он сам забирает его со склада. "
              "Склад только помечает «Готов»",
        "en": "Shipping is the courier's — they take it off the shelf "
              "themselves. The warehouse only marks it ready",
    },
    "reason_required": {
        "uz": "Rad etish sababini yozing",
        "ru": "Укажите причину отказа",
        "en": "Give a reason for the refusal",
    },
    "return_not_found": {
        "uz": "Ariza topilmadi",
        "ru": "Заявка не найдена",
        "en": "Request not found",
    },
    "slot_not_found": {
        "uz": "Yetkazish oynasi topilmadi",
        "ru": "Интервал доставки не найден",
        "en": "Delivery window not found",
    },
    "slot_window_invalid": {
        "uz": "Oynaning tugash vaqti boshlanishidan keyin bo'lishi kerak",
        "ru": "Конец интервала должен быть позже начала",
        "en": "A window has to end after it starts",
    },
    "order_repeats": {
        "uz": "Tartibda takrorlangan qator bor",
        "ru": "В порядке есть повторяющаяся строка",
        "en": "That order names a row twice",
    },
    "order_incomplete": {
        "uz": "Tartibda hamma qator bo'lishi kerak",
        "ru": "Порядок должен содержать все строки",
        "en": "The order has to name every row",
    },
    "account_taken": {
        "uz": "Bu hisob boshqa sotuvchiga bog'langan",
        "ru": "Этот аккаунт привязан к другому продавцу",
        "en": "That account is linked to another seller",
    },
    "sku_exists": {
        "uz": "Bu SKU allaqachon ishlatilgan",
        "ru": "Такой SKU уже используется",
        "en": "That SKU is already in use",
    },
    "slug_exists": {
        "uz": "Bu slug allaqachon ishlatilgan",
        "ru": "Такой slug уже используется",
        "en": "That slug is already in use",
    },
    "brand_not_found": {
        "uz": "Brend topilmadi",
        "ru": "Бренд не найден",
        "en": "Brand not found",
    },
    "brand_in_use": {
        "uz": "Bu brendda mahsulotlar bor",
        "ru": "У этого бренда есть товары",
        "en": "That brand still has products",
    },
    "category_in_use": {
        "uz": "Bu turkumda mahsulot yoki ichki turkum bor",
        "ru": "В этой категории есть товары или подкатегории",
        "en": "That category still has products or children",
    },
    "category_own_parent": {
        "uz": "Turkum o'ziga ota bo'lolmaydi",
        "ru": "Категория не может быть родителем себе",
        "en": "A category cannot be its own parent",
    },
    "image_not_found": {
        "uz": "Rasm topilmadi",
        "ru": "Изображение не найдено",
        "en": "Image not found",
    },
    "size_needs_a_colour": {
        "uz": "O'lcham qaysi rangga tegishli ekanini ko'rsating",
        "ru": "Укажите, какому цвету принадлежит размер",
        "en": "Say which colour the size belongs to",
    },
    "variant_would_move_the_count": {
        "uz": "Javonda tovar bor — o'lcham qo'shish sanoq joyini o'zgartiradi. "
              "Avval qoldiqni chiqarib, keyin qo'shing.",
        "ru": "На складе есть остаток — добавление размера сдвинет уровень учёта. "
              "Сначала обнулите остаток.",
        "en": "There is stock on the shelf — adding a size would move where it is "
              "counted. Count it out first.",
    },
    "variant_has_history": {
        "uz": "Bu variant bo'yicha harakat yoki buyurtma bor — o'chirib bo'lmaydi. "
              "Uni javondan chiqaring.",
        "ru": "По этому варианту есть движения или заказы — удалить нельзя. "
              "Обнулите остаток.",
        "en": "That variant has movements or orders against it — it cannot be "
              "deleted. Take it out of stock instead.",
    },
    "variant_has_children": {
        "uz": "Bu rangning o'lchamlari bor",
        "ru": "У этого цвета есть размеры",
        "en": "That colour still has sizes",
    },
    "last_admin": {
        "uz": "Bu oxirgi admin — rolini tushirib bo'lmaydi, aks holda tizimga "
              "hech kim kira olmaydi. Avval boshqa admin tayinlang.",
        "ru": "Это последний администратор — понизить его нельзя, иначе в систему "
              "никто не войдёт. Сначала назначьте другого администратора.",
        "en": "That is the last admin — demoting them would leave nobody who can "
              "sign in. Appoint another admin first.",
    },
    "file_empty": {
        "uz": "Fayl bo'sh",
        "ru": "Файл пустой",
        "en": "That file is empty",
    },
    "file_too_large": {
        "uz": "Fayl juda katta — {limit} MB gacha ruxsat etiladi",
        "ru": "Файл слишком большой — не более {limit} МБ",
        "en": "That file is too large — the limit is {limit} MB",
    },
    "not_an_image": {
        "uz": "Bu fayl rasm emas — nomi rasmga o'xshasa ham",
        "ru": "Это не изображение — даже если имя файла говорит обратное",
        "en": "That file isn't an image — whatever its name says",
    },
    "idempotency_key_required": {
        "uz": "Idempotency-Key sarlavhasi kerak — takroriy so'rov ikki marta "
              "bajarilmasligi uchun",
        "ru": "Нужен заголовок Idempotency-Key — чтобы повторный запрос не "
              "выполнился дважды",
        "en": "An Idempotency-Key header is required, so a retry does not do "
              "the thing twice",
    },
    "idempotency_key_reused": {
        "uz": "Bu kalit boshqa so'rov uchun ishlatilgan — bir kalit bir "
              "so'rovga tegishli",
        "ru": "Этот ключ уже использован для другого запроса — один ключ на "
              "один запрос",
        "en": "That key was used for a different request — one key belongs to "
              "one request",
    },
    "not_your_delivery": {
        "uz": "Bu buyurtma sizga biriktirilmagan",
        "ru": "Этот заказ не назначен вам",
        "en": "That order is not on your round",
    },
    "not_out_for_delivery": {
        "uz": "Buyurtma yo'lda emas — urinish yozib bo'lmaydi",
        "ru": "Заказ не в пути — попытку записать нельзя",
        "en": "That order is not out for delivery, so an attempt cannot be "
              "recorded against it",
    },
    "cash_mismatch": {
        "uz": "Naqd summa to'g'ri kelmadi: {owed} so'm olinishi kerak, "
              "{given} ko'rsatilgan",
        "ru": "Сумма наличных не сходится: нужно {owed} сум, указано {given}",
        "en": "The cash does not match: {owed} so'm is owed and {given} was "
              "entered",
    },
    "courier_not_found": {
        "uz": "Kuryer topilmadi",
        "ru": "Курьер не найден",
        "en": "Courier not found",
    },
    "courier_inactive": {
        "uz": "Bu kuryerning hisobi o'chirilgan",
        "ru": "Аккаунт этого курьера отключён",
        "en": "That courier's account is switched off",
    },
    "order_finished": {
        "uz": "Buyurtma tugagan — kuryerni o'zgartirib bo'lmaydi",
        "ru": "Заказ завершён — курьера изменить нельзя",
        "en": "That order is finished — its courier cannot be changed",
    },
    "return_not_approved": {
        "uz": "Faqat tasdiqlangan ariza bo'yicha yig'uvga chiqiladi",
        "ru": "Забирать можно только по одобренной заявке",
        "en": "Only an approved request is worth sending a van for",
    },
    "return_already_on_a_run": {
        "uz": "Bu ariza allaqachon yig'uv reysida",
        "ru": "Эта заявка уже в маршруте забора",
        "en": "That request is already on a collection run",
    },
    "pickup_not_found": {
        "uz": "Yig'uv reysi topilmadi",
        "ru": "Маршрут забора не найден",
        "en": "Collection run not found",
    },
    "not_your_pickup": {
        "uz": "Bu sizning reysingiz emas",
        "ru": "Это не ваш маршрут",
        "en": "That is not your run",
    },
    "pickup_line_not_of_run": {
        "uz": "Bu ariza shu reysda yo'q",
        "ru": "Этой заявки нет в маршруте",
        "en": "That request is not on this run",
    },
    "pickup_reason_required": {
        "uz": "Olinmagan bo'lsa sababini yozing — operator shu jumla bilan "
              "qaror qiladi",
        "ru": "Если не забрали — напишите причину: оператор решает по ней",
        "en": "If it was not collected, say why — an operator decides from "
              "that sentence",
    },
    "images_required": {
        "uz": "Kamida bitta rasm kerak — rasmsiz mahsulotni hech kim bosmaydi",
        "ru": "Нужно хотя бы одно фото — товар без фото никто не откроет",
        "en": "At least one picture — a card with no photo is a card nobody taps",
    },
    "sizes_all_or_none": {
        "uz": "Yo hamma rangda razmer bo'lsin, yo hech qaysisida: qoldiq eng "
              "pastki bo'g'inda sanaladi va ikki darajani aralashtirib bo'lmaydi",
        "ru": "Либо размеры у всех цветов, либо ни у одного: остаток считается "
              "на нижнем уровне, и смешивать два уровня нельзя",
        "en": "Either every colour has sizes or none does — stock is counted on "
              "the leaves and the two levels cannot be mixed",
    },
    "sizes_repeat": {
        "uz": "Bitta rangda bir razmer ikki marta berilgan",
        "ru": "В одном цвете размер указан дважды",
        "en": "A size is repeated within one colour",
    },
    "colors_repeat": {
        "uz": "Bir rang ikki marta berilgan",
        "ru": "Цвет указан дважды",
        "en": "A colour is repeated",
    },
    "variants_required": {
        "uz": "Mahsulotning har bir variantini ko'rsatish shart: {missing}",
        "ru": "Нужно указать каждый вариант товара: {missing}",
        "en": "Every variant of the product has to be listed: {missing}",
    },
    "variant_not_of_product": {
        "uz": "Variant bu mahsulotga tegishli emas",
        "ru": "Вариант не принадлежит этому товару",
        "en": "That variant does not belong to this product",
    },
    # the warehouse
    "supply_nothing_sorted": {
        "uz": "Avval qopni saralang: birorta ham qator yo'q.",
        "ru": "Сначала разберите мешок: ни одной строки.",
        "en": "Sort the sack first: it has no lines.",
    },
    "tile_unsorted_sacks": {
        "uz": "Saralanmagan qoplar",
        "ru": "Неразобранные мешки",
        "en": "Sacks nobody has opened",
    },
    "tile_orders_today": {
        "uz": "Bugungi buyurtmalar",
        "ru": "Заказы за сегодня",
        "en": "Orders today",
    },
    "tile_awaiting_putaway": {
        "uz": "Qabulda turibdi",
        "ru": "Ждёт размещения",
        "en": "Standing in the receiving area",
    },
    "tile_cells_full": {
        "uz": "To'lgan kataklar",
        "ru": "Заполненные ячейки",
        "en": "Cells nearly full",
    },
    "tile_cells_empty": {
        "uz": "{count} ta bo'sh katak",
        "ru": "{count} пустых ячеек",
        "en": "{count} empty cells",
    },
    "tile_low_stock": {
        "uz": "Tugayotgan variantlar",
        "ru": "Заканчиваются",
        "en": "Running out",
    },
    "tile_low_stock_hint": {
        "uz": "{count} tadan kam qolgan",
        "ru": "Осталось {count} или меньше",
        "en": "{count} left or fewer",
    },
    "tile_no_photograph": {
        "uz": "Rasmsiz — sotuvga chiqmagan",
        "ru": "Без фото — не в продаже",
        "en": "Held back for want of a photograph",
    },
    "tile_no_photograph_hint": {
        "uz": "Rasm qo'yilsa, o'zi sotuvga chiqadi",
        "ru": "Появится в продаже, как только будет фото",
        "en": "One picture each and they are in the shop",
    },
    "tile_couriers_out": {
        "uz": "Yo'ldagi kuryerlar",
        "ru": "Курьеры в пути",
        "en": "Couriers out with parcels",
    },
    "age_hours_minutes": {
        "uz": "{hours} soat {minutes} daqiqa",
        "ru": "{hours} ч {minutes} мин",
        "en": "{hours} h {minutes} min",
    },
    "age_hours": {
        "uz": "{hours} soat",
        "ru": "{hours} ч",
        "en": "{hours} h",
    },
    "age_minutes": {
        "uz": "{minutes} daqiqa",
        "ru": "{minutes} мин",
        "en": "{minutes} min",
    },
    "location_not_found": {
        "uz": "Bunday joy yo'q: {code}",
        "ru": "Такого места нет: {code}",
        "en": "No such place: {code}",
    },
    "putaway_needs_a_cell": {
        "uz": "Faqat javon katagiga joylashtiriladi",
        "ru": "Разместить можно только в ячейку стеллажа",
        "en": "Goods go into a shelf cell, not into a staging area",
    },
    "count_already_open": {
        "uz": "Bu katak allaqachon sanalmoqda",
        "ru": "Эта ячейка уже пересчитывается",
        "en": "Somebody is already counting this cell",
    },
    "count_already_closed": {
        "uz": "Sanash yakunlangan",
        "ru": "Пересчёт уже закрыт",
        "en": "That count is closed",
    },
    "count_not_found": {
        "uz": "Sanash topilmadi",
        "ru": "Пересчёт не найден",
        "en": "Count not found",
    },
    "count_difference": {
        "uz": "Sanashdagi farq",
        "ru": "Расхождение при пересчёте",
        "en": "What the count found",
    },
    "labels_need_a_selection": {
        "uz": "Qaysi yorliqlar? Qabul yoki variantlarni tanlang",
        "ru": "Какие этикетки? Укажите поставку или варианты",
        "en": "Which labels? Name a market run or some variants",
    },
    "order_not_pickable": {
        "uz": "Bu buyurtma terishga tayyor emas",
        "ru": "Этот заказ ещё не для сборки",
        "en": "That order is not one to pick",
    },
    "pick_not_found": {
        "uz": "Terish vazifasi topilmadi",
        "ru": "Задание на сборку не найдено",
        "en": "Pick task not found",
    },
    "pick_line_not_found": {
        "uz": "Terish qatori topilmadi",
        "ru": "Строка сборки не найдена",
        "en": "That line is not on this task",
    },
    "pick_already_taken": {
        "uz": "Bu vazifani boshqa xodim oldi",
        "ru": "Задание уже взял другой сотрудник",
        "en": "Somebody has already taken this one",
    },
    "pick_not_yours": {
        "uz": "Bu vazifa sizniki emas",
        "ru": "Это не ваше задание",
        "en": "That trolley is somebody else's",
    },
    "pick_already_done": {
        "uz": "Bu vazifa yakunlangan",
        "ru": "Задание уже завершено",
        "en": "That task is finished",
    },
    "pick_line_done": {
        "uz": "Bu qator allaqachon terilgan",
        "ru": "Эта строка уже собрана",
        "en": "That line is already fetched",
    },
    "pick_not_finished": {
        "uz": "Hali hamma qator terilmagan",
        "ru": "Собрано не всё",
        "en": "Not everything has been fetched yet",
    },
    "supply_not_found": {
        "uz": "Partiya topilmadi",
        "ru": "Поставка не найдена",
        "en": "Supply not found",
    },
    # what the customer is told when somebody finally answers
    "order_packing_note": {
        "uz": "{code} omborda yig'ilmoqda",
        "ru": "{code} собирается на складе",
        "en": "{code} is being picked at the warehouse",
    },
    "order_shipped_note": {
        "uz": "{code} kuryerga topshirildi",
        "ru": "{code} передан курьеру",
        "en": "{code} has been handed to the courier",
    },
    "order_delivered_note": {
        "uz": "{code} yetkazildi — sharh qoldirasizmi?",
        "ru": "{code} доставлен — оставите отзыв?",
        "en": "{code} delivered — would you leave a review?",
    },
    "order_returned_note": {
        "uz": "{code} qaytarildi",
        "ru": "{code} возвращён",
        "en": "{code} has been returned",
    },
    "return_approved": {
        "uz": "Qaytarish tasdiqlandi",
        "ru": "Возврат одобрен",
        "en": "Return approved",
    },
    "return_approved_note": {
        "uz": "{code} bo'yicha arizangiz tasdiqlandi — pul tez orada qaytariladi",
        "ru": "Заявка по {code} одобрена — деньги вернутся в ближайшее время",
        "en": "Your request for {code} is approved — the money follows shortly",
    },
    "return_rejected": {
        "uz": "Qaytarish rad etildi",
        "ru": "Возврат отклонён",
        "en": "Return refused",
    },
    "return_rejected_note": {
        "uz": "{code} bo'yicha arizangiz rad etildi: {reason}",
        "ru": "Заявка по {code} отклонена: {reason}",
        "en": "Your request for {code} was refused: {reason}",
    },
    "return_refunded": {
        "uz": "Pul qaytarildi",
        "ru": "Деньги возвращены",
        "en": "Refunded",
    },
    "return_refunded_note": {
        "uz": "{code} bo'yicha {amount} so'm qaytarildi",
        "ru": "По {code} возвращено {amount} сум",
        "en": "{amount} UZS returned for {code}",
    },
    # ------------------------------------------- the goods after the refund
    #
    # Two people are told two different things about the same parcel: the
    # warehouse's verdict goes to the seller, because it is the seller who has
    # to answer it, and the answer has a deadline on it. The customer is not
    # in this conversation at all — their money is already back.
    "inspection_ok": {
        "uz": "Butun",
        "ru": "Целый",
        "en": "Whole",
    },
    "inspection_damaged": {
        "uz": "Buzilgan",
        "ru": "Повреждён",
        "en": "Damaged",
    },
    "return_already_inspected": {
        "uz": "Bu ariza allaqachon tekshirilgan",
        "ru": "Эта заявка уже осмотрена",
        "en": "That request has already been inspected",
    },
    "return_not_here_yet": {
        "uz": "Tovar hali omborga kelmagan — avval qaytarish tasdiqlanadi",
        "ru": "Товар ещё не на складе — сначала возврат одобряют",
        "en": "The goods are not here yet — a return is approved first",
    },
    # a batch the warehouse refused
    # order status pills and timeline
    "status_placed": {"uz": "QABUL QILINDI", "ru": "ПРИНЯТ", "en": "PLACED"},
    "status_packing": {"uz": "TAYYOR", "ru": "ГОТОВ", "en": "READY"},
    "status_shipped": {"uz": "YO'LDA", "ru": "В ПУТИ", "en": "ON THE WAY"},
    "status_delivered": {"uz": "YETKAZILDI", "ru": "ДОСТАВЛЕН", "en": "DELIVERED"},
    "status_cancelled": {"uz": "BEKOR QILINDI", "ru": "ОТМЕНЁН", "en": "CANCELLED"},
    "status_returned": {"uz": "QAYTARILDI", "ru": "ВОЗВРАЩЁН", "en": "RETURNED"},
    "event_placed": {"uz": "Buyurtma qabul qilindi", "ru": "Заказ принят",
                     "en": "Order placed"},
    "event_packing": {"uz": "Yig'ildi — kuryer kutilmoqda", "ru": "Собран — ждёт курьера",
                      "en": "Picked at the warehouse"},
    "event_shipped": {"uz": "Kuryerga topshirildi", "ru": "Передан курьеру",
                      "en": "Handed to the courier"},
    "event_delivered": {"uz": "Yetkazildi", "ru": "Доставлен", "en": "Delivered"},
    "event_cancelled": {"uz": "Bekor qilindi", "ru": "Заказ отменён",
                        "en": "Order cancelled"},
    "event_returned": {"uz": "Qaytarildi", "ru": "Возвращён", "en": "Returned"},
    # delivery slots
    "slot_express": {
        "uz": "2 soat ichida",
        "ru": "В течение 2 часов",
        "en": "Within 2 hours",
    },
    "slot_note_morning": {
        "uz": "Ertalabki yetkazish",
        "ru": "Утренняя доставка",
        "en": "Morning delivery",
    },
    "slot_note_popular": {
        "uz": "Eng ko'p tanlanadigan oraliq",
        "ru": "Самый популярный интервал",
        "en": "The most-chosen window",
    },
    "slot_note_evening": {
        "uz": "Ish kunidan keyin",
        "ru": "После рабочего дня",
        "en": "After work",
    },
    "slot_note_express": {
        "uz": "Tezkor yetkazish · Toshkent markazi",
        "ru": "Экспресс-доставка · центр Ташкента",
        "en": "Express delivery · central Tashkent",
    },
    # payment
    "cash_courier": {"uz": "Naqd pul · kuryerga", "ru": "Наличные · курьеру",
                     "en": "Cash · to the courier"},
    "card": {"uz": "Karta", "ru": "Карта", "en": "Card"},
    "paid": {"uz": "to'landi", "ru": "оплачено", "en": "paid"},
    "unpaid": {"uz": "to'lanmagan", "ru": "не оплачено", "en": "unpaid"},
    # filter flags and rating buckets
    "flag_next_day_delivery": {"uz": "Ertaga yetkaziladi", "ru": "Доставка завтра",
                               "en": "Arrives tomorrow"},
    "flag_next_day_delivery_sub": {"uz": "Toshkent bo'ylab", "ru": "По Ташкенту",
                                   "en": "Across Tashkent"},
    "flag_free_delivery": {"uz": "Bepul yetkazish", "ru": "Бесплатная доставка",
                           "en": "Free delivery"},
    "flag_free_delivery_sub": {"uz": "250 000 so'mdan yuqori", "ru": "от 250 000 сум",
                               "en": "Over 250,000 UZS"},
    "flag_discounted": {"uz": "Chegirmada", "ru": "Со скидкой", "en": "On sale"},
    "flag_discounted_sub": {"uz": "Faqat arzonlashgan tovarlar",
                            "ru": "Только уценённые товары",
                            "en": "Discounted items only"},
    "flag_is_original": {"uz": "Original kafolati", "ru": "Гарантия оригинала",
                         "en": "Authenticity guaranteed"},
    "flag_is_original_sub": {"uz": "Tekshirilgan sotuvchilar",
                             "ru": "Проверенные продавцы",
                             "en": "Vetted sellers"},
    "rating_45": {"uz": "4.5 ★ dan yuqori", "ru": "Выше 4.5 ★", "en": "Above 4.5 ★"},
    "rating_40": {"uz": "4.0 ★ dan yuqori", "ru": "Выше 4.0 ★", "en": "Above 4.0 ★"},
    "rating_many": {"uz": "Sharhi ko'p", "ru": "Много отзывов", "en": "Many reviews"},
    # sort options
    "sort_popular": {"uz": "Ommabop", "ru": "Популярные", "en": "Popular"},
    "sort_price_asc": {"uz": "Avval arzoni", "ru": "Сначала дешёвые",
                       "en": "Cheapest first"},
    "sort_price_desc": {"uz": "Avval qimmati", "ru": "Сначала дорогие",
                        "en": "Most expensive first"},
    "sort_rating": {"uz": "Reyting bo'yicha", "ru": "По рейтингу", "en": "By rating"},
    "sort_new": {"uz": "Yangilari", "ru": "Новинки", "en": "New arrivals"},
    "sort_discount": {"uz": "Chegirma bo'yicha", "ru": "По скидке", "en": "By discount"},
}

MONTHS: dict[str, list[str]] = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
}

WEEKDAYS: dict[str, list[str]] = {
    "uz": ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"],
    "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}

# Uzbek writes 22-avgust, Russian 22 августа, English 22 August.
DATE_FORMAT = {"uz": "{day}-{month}", "ru": "{day} {month}", "en": "{day} {month}"}


# The notes the seed writes on a slot, mapped to the labels above. Keyed on the
# Uzbek text because a slot's id changes every time the week is re-seeded, so a
# translation row keyed on the row would not survive.
SLOT_NOTES: dict[str, str] = {
    "Ertalabki yetkazish": "slot_note_morning",
    "Eng ko'p tanlanadigan oraliq": "slot_note_popular",
    "Ish kunidan keyin": "slot_note_evening",
    "Tezkor yetkazish · Toshkent markazi": "slot_note_express",
}


def slot_note(note: str) -> str:
    """A slot's note in the active language, or the note itself if unknown."""
    key = SLOT_NOTES.get(note)
    return label(key) if key else note


def label(key: str, **fmt: object) -> str:
    """A code-level label in the active language, falling back to Uzbek."""
    entry = LABELS.get(key)
    if entry is None:
        return key
    text = entry.get(current()) or entry[DEFAULT]
    return text.format(**fmt) if fmt else text


def month_name(month: int) -> str:
    return MONTHS.get(current(), MONTHS[DEFAULT])[month - 1]


def weekday_name(weekday: int) -> str:
    return WEEKDAYS.get(current(), WEEKDAYS[DEFAULT])[weekday]


def format_date(d: date) -> str:
    return DATE_FORMAT.get(current(), DATE_FORMAT[DEFAULT]).format(
        day=d.day, month=month_name(d.month)
    )


def day_label(d: date, today: date | None = None) -> str:
    today = today or date.today()
    if d == today:
        return label("today")
    if d == today + timedelta(days=1):
        return label("tomorrow")
    return weekday_name(d.weekday())


# ─────────────────────────────── content in the DB ─────────────────────────

def _load(session: Session) -> dict[tuple[str, int, str], str]:
    """Every translation for the active language, read once per request.

    One query for the whole table rather than a join per row: the catalogue is
    a few hundred rows per language, and the alternative is an extra lookup for
    every card in a listing.
    """
    from app.models import Translation

    cached = _cache.get()
    if cached is not None:
        return cached
    lang = current()
    if lang == DEFAULT:
        table: dict[tuple[str, int, str], str] = {}
    else:
        rows = session.exec(select(Translation).where(Translation.lang == lang)).all()
        table = {(r.entity, r.entity_id, r.field): r.value for r in rows}
    _cache.set(table)
    return table


def t(session: Session, entity: str, entity_id: int | None, field: str, default: str) -> str:
    """A translated field, falling back to the Uzbek text already on the row."""
    if entity_id is None or current() == DEFAULT:
        return default
    return _load(session).get((entity, entity_id, field)) or default


def invalidate() -> None:
    """Drop the per-request cache after writing to the table.

    ``_load`` reads the whole table once and holds it for the rest of the
    request. An endpoint that writes a translation and then renders the row it
    wrote would otherwise answer out of a snapshot taken before the write —
    the admin would save Russian and be shown Uzbek back.
    """
    _cache.set(None)


# Which fields of which row may be translated, and therefore what a write is
# allowed to name. The lists are the read path in reverse: every field here is
# one that ``services.py`` or a router passes through ``t()`` above, and
# nothing else, because a translation nobody reads is a row that quietly does
# nothing.
WRITABLE: dict[str, frozenset[str]] = {
    "product": frozenset({"title", "subtitle", "description", "badge", "warranty"}),
    "category": frozenset({"name", "subtitle"}),
    "brand": frozenset({"name"}),
    "variant": frozenset({"label"}),
    "spec": frozenset({"key", "value"}),
}


def stored(session: Session, entity: str, entity_id: int) -> dict[str, dict[str, str]]:
    """Every translation held for one row, as ``{lang: {field: text}}``.

    For the panel that edits them: the read path answers in one language and
    falls back silently, which is the right behaviour for a shopper and no use
    at all to somebody trying to see what is still missing.
    """
    from app.models import Translation

    rows = session.exec(
        select(Translation).where(
            Translation.entity == entity, Translation.entity_id == entity_id
        )
    ).all()
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        out.setdefault(row.lang, {})[row.field] = row.value
    return out


def write(
    session: Session,
    entity: str,
    entity_id: int,
    table: dict[str, dict[str, str | None]],
) -> None:
    """Store the Russian and English for a row, without committing.

    ``table`` is ``{lang: {field: text}}`` and names only what the caller
    meant to change: a field that is absent is left alone, and a field given
    as ``None`` or blank has its row deleted so the field falls back to the
    Uzbek on the record again. That is the difference between "I am not
    editing the description" and "there is no Russian description".

    The caller commits, along with the row being described.
    """
    from app.models import Translation

    allowed = WRITABLE.get(entity, frozenset())
    touched = False
    for lang, fields in table.items():
        if lang == DEFAULT or lang not in SUPPORTED:
            # Uzbek is on the record itself, not in this table.
            continue
        for field, value in fields.items():
            if field not in allowed:
                continue
            row = session.exec(
                select(Translation).where(
                    Translation.entity == entity,
                    Translation.entity_id == entity_id,
                    Translation.field == field,
                    Translation.lang == lang,
                )
            ).first()
            text = (value or "").strip()
            if not text:
                if row is not None:
                    session.delete(row)
                    touched = True
                continue
            if row is None:
                session.add(
                    Translation(
                        entity=entity,
                        entity_id=entity_id,
                        field=field,
                        lang=lang,
                        value=text,
                    )
                )
            else:
                row.value = text
                session.add(row)
            touched = True
    if touched:
        invalidate()


def forget(session: Session, entity: str, entity_id: int) -> None:
    """Drop every translation for a row that is going away.

    Not tidiness. SQLite hands out the id of a deleted row again, so a brand
    deleted at id 5 and a brand created afterwards at id 5 would be the same
    key — and the new one would arrive in Russian already, under the old one's
    name. Specs make this certain rather than likely: replacing a spec table
    deletes every row and writes fresh ones straight back.
    """
    from app.models import Translation

    rows = session.exec(
        select(Translation).where(
            Translation.entity == entity, Translation.entity_id == entity_id
        )
    ).all()
    for row in rows:
        session.delete(row)
    if rows:
        invalidate()
