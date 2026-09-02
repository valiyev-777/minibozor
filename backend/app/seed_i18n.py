"""Russian and English for the seeded catalogue.

Written as data rather than as extra columns on every model: see
``app.models.Translation`` for why. A phrase that repeats across rows — a badge,
a colour, a spec key — is written once in [PHRASES] and applied wherever it
appears, so "Original" is translated in one place rather than seventeen.

Anything missing here simply stays Uzbek; nothing breaks.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    Banner,
    CancelReason,
    Category,
    FaqItem,
    HomeSection,
    LegalDoc,
    Product,
    ProductSpec,
    ProductVariant,
    ReturnReason,
    Translation,
)

LANGS = ("ru", "en")

# ─────────── vocabulary that repeats: badges, warranties, colours, specs ────

PHRASES: dict[str, tuple[str, str]] = {
    # badges and warranties
    "Original": ("Оригинал", "Genuine"),
    "Bestseller": ("Хит продаж", "Bestseller"),
    "Yangi": ("Новинка", "New"),
    "Kafolat 1 yil": ("Гарантия 1 год", "1-year warranty"),
    "Original kafolati": ("Гарантия оригинала", "Authenticity guaranteed"),
    "Rasmiy kafolat 1 yil": ("Официальная гарантия 1 год", "Official 1-year warranty"),
    "ASOSIY": ("ОСНОВНОЙ", "DEFAULT"),
    "OFIS": ("ОФИС", "OFFICE"),
    # colours
    "Ko'k": ("Синий", "Blue"),
    "Qora": ("Чёрный", "Black"),
    "Oq": ("Белый", "White"),
    "Qizil": ("Красный", "Red"),
    "Pushti": ("Розовый", "Pink"),
    "Kulrang": ("Серый", "Grey"),
    "Bordo": ("Бордовый", "Burgundy"),
    "To'q ko'k": ("Тёмно-синий", "Navy"),
    "Oq-pushti": ("Бело-розовый", "White and pink"),
    "Oltin-qora": ("Золотой с чёрным", "Gold and black"),
    "Yashil": ("Зелёный", "Green"),
    # subtitle tokens
    "zamsh": ("замша", "suede"),
    "charm": ("кожа", "leather"),
    "yengil": ("лёгкие", "lightweight"),
    "trening": ("тренировки", "training"),
    "kundalik": ("на каждый день", "everyday"),
    "yozgi": ("летнее", "summer"),
    "over-ear": ("накладные", "over-ear"),
    "mavjud": ("в наличии", "in stock"),
    "tez quvvat": ("быстрая зарядка", "fast charging"),
    "silikon": ("силикон", "silicone"),
    "3 rejim": ("3 режима", "3 modes"),
    "3 rang": ("3 цвета", "3 colours"),
    "Yugurish": ("Бег", "Running"),
    "Sovg'a qutisi": ("Подарочная коробка", "Gift box"),
    "6 dona qoldi": ("осталось 6 шт.", "6 left"),
    "S–XXL": ("S–XXL", "S–XXL"),
    "L": ("L", "L"),
    "3 o'lcham": ("3 размера", "3 sizes"),
    # subtitle tokens for the new arrivals
    "pushti swoosh": ("розовый swoosh", "pink swoosh"),
    "tekstura": ("текстура", "textured"),
    "paxta": ("хлопок", "cotton"),
    "pike": ("пике", "pique"),
    "chiziqli": ("в полоску", "striped"),
    "Jubilee": ("Jubilee", "Jubilee"),
    "Oyster": ("Oyster", "Oyster"),
    "po'lat": ("сталь", "steel"),
    "avtomatik": ("автоматический", "automatic"),
    "Gradient linza": ("Градиентные линзы", "Gradient lenses"),
    "titan": ("титан", "titanium"),
    "Ramkasiz": ("Без оправы", "Rimless"),
    "oltin": ("золотой", "gold"),
    "Aviator": ("Авиатор", "Aviator"),
    "qora": ("чёрный", "black"),
    "Past": ("Низкий", "Low"),
    # spec keys
    "Material": ("Материал", "Material"),
    "Materiali": ("Материал", "Material"),
    "Taglik": ("Подошва", "Sole"),
    "Mavsum": ("Сезон", "Season"),
    "Ishlab chiqarilgan": ("Произведено", "Made in"),
    "Vazn": ("Вес", "Weight"),
    "Turi": ("Тип", "Type"),
    "Ulanish": ("Подключение", "Connectivity"),
    "Ishlash vaqti": ("Время работы", "Battery life"),
    "Sig'im": ("Ёмкость", "Capacity"),
    "Chiqish": ("Выход", "Output"),
    "Kabellar": ("Кабели", "Cables"),
    "Quvvat": ("Мощность", "Power"),
    "Rejimlar": ("Режимы", "Modes"),
    "Ranglar": ("Цвета", "Colours"),
    "Bichim": ("Крой", "Fit"),
    "Zichlik": ("Плотность", "Density"),
    "Yopilishi": ("Застёжка", "Fastening"),
    "O'lchamlar": ("Размеры", "Sizes"),
    "Predmetlar": ("Предметы", "Items"),
    "Qadoq": ("Упаковка", "Packaging"),
    "ANC": ("ANC", "ANC"),
    "Korpus": ("Корпус", "Case"),
    "Braslet": ("Браслет", "Bracelet"),
    "Mexanizm": ("Механизм", "Movement"),
    "Suvga chidamlilik": ("Водозащита", "Water resistance"),
    "Ramka": ("Оправа", "Frame"),
    "Linza": ("Линзы", "Lenses"),
    "UV himoya": ("УФ-защита", "UV protection"),
    "Yoqasi": ("Воротник", "Collar"),
    # spec values
    "Tabiiy zamsh": ("Натуральная замша", "Genuine suede"),
    "Tabiiy charm": ("Натуральная кожа", "Genuine leather"),
    "Sun'iy charm": ("Искусственная кожа", "Synthetic leather"),
    "Rezina": ("Резина", "Rubber"),
    "Rezina, Air": ("Резина, Air", "Rubber, Air"),
    "Bahor-kuz": ("Весна-осень", "Spring–autumn"),
    "Butun yil": ("Круглый год", "All year"),
    "Yoz": ("Лето", "Summer"),
    "Vetnam": ("Вьетнам", "Vietnam"),
    "Bor": ("Есть", "Yes"),
    "Over-ear": ("Накладные", "Over-ear"),
    "Oversize": ("Оверсайз", "Oversize"),
    "Ilma": ("Петля", "Loop"),
    "Silikon": ("Силикон", "Silicone"),
    "Viskoza": ("Вискоза", "Viscose"),
    "Trening": ("Тренировки", "Training"),
    "100% paxta": ("100% хлопок", "100% cotton"),
    "95% paxta, 5% elastan": ("95% хлопок, 5% эластан", "95% cotton, 5% elastane"),
    "40 soat": ("40 часов", "40 hours"),
    "6 soat + 30 soat": ("6 часов + 30 часов", "6 hours + 30 hours"),
    "7 ta": ("7 шт.", "7 pieces"),
    "218 g": ("218 г", "218 g"),
    "220 g/m²": ("220 г/м²", "220 g/m²"),
    "180 g/m²": ("180 г/м²", "180 g/m²"),
    "Klassik": ("Классический", "Classic"),
    "100% paxta pike": ("100% хлопок пике", "100% cotton pique"),
    "Paxta aralashma": ("Смесь хлопка", "Cotton blend"),
    "Po'lat 41 mm": ("Сталь 41 мм", "Steel 41 mm"),
    "Po'lat 40 mm": ("Сталь 40 мм", "Steel 40 mm"),
    "Avtomatik": ("Автоматический", "Automatic"),
    "100 m": ("100 м", "100 m"),
    "50 m": ("50 м", "50 m"),
    "Titan": ("Титан", "Titanium"),
    "Gradient": ("Градиент", "Gradient"),
    "UV400": ("UV400", "UV400"),
    "Bir tekis": ("Однотонные", "Solid"),
}


def phrase(text: str, index: int) -> str | None:
    """Translate a value, splitting the ``a · b`` subtitles the design uses."""
    if text in PHRASES:
        return PHRASES[text][index]
    if " · " in text:
        parts = [PHRASES.get(p.strip(), (None, None))[index] or p.strip()
                 for p in text.split(" · ")]
        joined = " · ".join(parts)
        return joined if joined != text else None
    return None


# ─────────── content written once, per row ────────────────────────────────

CATEGORIES: dict[str, tuple[tuple[str, str], tuple[str, str] | None]] = {
    # slug: ((ru name, en name), (ru subtitle, en subtitle) | None)
    "elektronika": (("Электроника", "Electronics"),
                    ("Смартфоны, ноутбуки, аксессуары", "Phones, laptops, accessories")),
    "kiyim-poyabzal": (("Одежда и обувь", "Clothing and shoes"),
                       ("Женщинам, мужчинам, детям", "Women, men, children")),
    "maishiy-texnika": (("Бытовая техника", "Home appliances"),
                        ("Стиральные машины, холодильники", "Washers, fridges")),
    "uy-bog": (("Дом и сад", "Home and garden"),
               ("Мебель, декор, инструменты", "Furniture, decor, tools")),
    "oyinchoqlar": (("Игрушки", "Toys"), ("Всё для детей", "Everything for kids")),
    "gozallik": (("Красота", "Beauty"), ("Парфюмерия, косметика", "Perfume, cosmetics")),
    "oziq-ovqat": (("Продукты", "Groceries"), ("Товары на каждый день", "Everyday essentials")),
    "avto": (("Автотовары", "Car goods"), ("Запчасти, аксессуары", "Parts, accessories")),
    "sport": (("Спорт", "Sport"), ("Тренажёры, одежда, инвентарь", "Machines, clothing, gear")),
    "maktab-bozori": (("Школьный базар", "Back to school"),
                      ("Рюкзаки, тетради, форма", "Backpacks, notebooks, uniforms")),
    "taom-yetkazish": (("Доставка еды", "Food delivery"),
                       ("Из ресторанов и кафе", "From restaurants and cafés")),
    "chet-eldan": (("Из-за рубежа", "From abroad"),
                   ("Международная доставка", "International delivery")),
    "kundalik": (("Повседневное", "Daily goods"),
                 ("Гигиена, бытовая химия", "Hygiene, household chemicals")),
    # subcategories
    "futbolka-toplar": (("Футболки и топы", "T-shirts and tops"), None),
    "krossovkalar": (("Кроссовки", "Trainers"), None),
    "koylak-libos": (("Платья и одежда", "Dresses and clothing"), None),
    "kundalik-poyabzal": (("Повседневная обувь", "Everyday shoes"), None),
    "sport-kiyim": (("Спортивная одежда", "Sportswear"), None),
    "bolalar-poyabzali": (("Детская обувь", "Kids' shoes"), None),
    "quloqchinlar": (("Наушники", "Headphones"), None),
    "quvvat-aksessuar": (("Зарядки и аксессуары", "Chargers and accessories"), None),
    "yoruglik": (("Освещение", "Lighting"), None),
    "aksessuar": (("Аксессуары", "Accessories"),
                  ("Часы, очки, украшения", "Watches, eyewear, jewellery")),
    "polo": (("Поло", "Polo shirts"), None),
    "soatlar": (("Наручные часы", "Wristwatches"), None),
    "kozoynaklar": (("Солнцезащитные очки", "Sunglasses"), None),
}

SECTIONS: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "deals": (("Выбор дня", "Today's picks"), ("Обновляется каждый день", "Updated daily")),
    "for-you": (("Для вас", "For you"),
                ("на основе просмотров", "based on what you viewed")),
    "shoes": (("Обувь", "Shoes"), ("оригинальные бренды", "genuine brands")),
    "electronics": (("Электроника", "Electronics"), ("с гарантией", "with warranty")),
}

BANNERS: dict[str, dict[str, tuple[str, str]]] = {
    # matched on the Uzbek title
    "Ish stolingiz uchun": {
        "kicker": ("MINI BOZOR / ДОМ И СВЕТ", "MINI BOZOR / HOME AND LIGHT"),
        "title": ("Для вашего рабочего стола", "For your desk"),
        "subtitle": ("До 40% на лампы и аксессуары", "Up to 40% off lamps and accessories"),
        "cta": ("Смотреть", "Browse"),
    },
    "Original kafolat bilan": {
        "kicker": ("MINI BOZOR / ЭЛЕКТРОНИКА", "MINI BOZOR / ELECTRONICS"),
        "title": ("С гарантией оригинала", "With an authenticity guarantee"),
        "subtitle": ("Наушники и зарядные аксессуары", "Headphones and charging accessories"),
        "cta": ("Смотреть", "Browse"),
    },
    "Bahorgi yangilanish": {
        "kicker": ("MINI BOZOR / ОБУВЬ", "MINI BOZOR / SHOES"),
        "title": ("Весеннее обновление", "Spring refresh"),
        "subtitle": ("Скидки на оригинальные бренды", "Discounts on genuine brands"),
        "cta": ("Смотреть", "Browse"),
    },
}

TITLES: dict[str, tuple[str, str]] = {
    # Brand names stay; only the descriptive tail is translated.
    "MB-1001": ("adidas Gazelle, синяя замша", "adidas Gazelle, blue suede"),
    "MB-1002": ("Nike Air Force 1 Low, белые", "Nike Air Force 1 Low, white"),
    "MB-1003": ("Nike ZoomX, для бега", "Nike ZoomX, for running"),
    "MB-1004": ("Nike Air Zoom, розовые", "Nike Air Zoom, pink"),
    "MB-1005": ("adidas Grand Court, чёрные", "adidas Grand Court, black"),
    "MB-2001": ("AirPods Pro 2, USB-C", "AirPods Pro 2, USB-C"),
    "MB-2002": ("Беспроводные наушники ANC, 40 часов",
                "Wireless ANC headphones, 40 hours"),
    "MB-2003": ("Повербанк 30000 мА·ч, 4 кабеля", "Power bank 30,000 mAh, 4 cables"),
    "MB-2004": ("Повербанк 20000 мА·ч, 22.5 Вт", "Power bank 20,000 mAh, 22.5 W"),
    "MB-2005": ("Адаптер 20 Вт USB-C", "20 W USB-C adapter"),
    "MB-2006": ("Амбушюры для AirPods", "Ear tips for AirPods"),
    "MB-3001": ("Настольная LED-лампа, сенсорная", "LED desk lamp, touch control"),
    "MB-3002": ("Детская настольная лампа, астронавт", "Kids' desk lamp, astronaut"),
    "MB-4001": ("Оверсайз футболка, 100% хлопок", "Oversize T-shirt, 100% cotton"),
    "MB-4002": ("Классическая футболка, зелёная", "Classic T-shirt, green"),
    "MB-5001": ("Парфюмерный набор, 7 предметов", "Perfume set, 7 pieces"),
    "MB-1006": ("Nike Air Force 1 '07, бело-розовые",
                "Nike Air Force 1 '07, white and pink"),
    "MB-1007": ("Air Jordan 1 Low, полностью белые", "Air Jordan 1 Low, all white"),
    "MB-1008": ("Nike Air Force 1, полностью чёрные", "Nike Air Force 1, all black"),
    "MB-4004": ("Классическая футболка, белая", "Classic T-shirt, white"),
    "MB-4005": ("Классическая футболка, тёмно-синяя", "Classic T-shirt, navy"),
    "MB-4006": ("Поло, бордовое", "Polo shirt, burgundy"),
    "MB-4007": ("Поло в сине-белую полоску", "Polo shirt, blue and white stripes"),
    "MB-6001": ("Rolex Datejust 41, синий циферблат", "Rolex Datejust 41, blue dial"),
    "MB-6002": ("Rolex Datejust 41, зелёный циферблат", "Rolex Datejust 41, green dial"),
    "MB-6003": ("Rolex Datejust 41, чёрный циферблат", "Rolex Datejust 41, black dial"),
    "MB-6004": ("Rolex Datejust 41, браслет Oyster", "Rolex Datejust 41, Oyster bracelet"),
    "MB-6005": ("Gucci G-Timeless, зелёный циферблат", "Gucci G-Timeless, green dial"),
    "MB-7001": ("Солнцезащитные очки DITA, золото и чёрный",
                "DITA sunglasses, gold and black"),
    "MB-7002": ("Очки без оправы, синие линзы", "Rimless sunglasses, blue lenses"),
    "MB-7003": ("DITA авиаторы, чёрные", "DITA aviators, black"),
}

DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "MB-1001": (
        "Классические adidas Gazelle из натуральной замши, для повседневной носки. "
        "Мягкая внутренняя отделка, прочная подошва. Оригинал, от официального "
        "дистрибьютора.\n"
        "\n"
        "## Материал и пошив\n"
        "Верх — цельный кусок натуральной замши, швы прошиты в две нити. "
        "Внутренняя подкладка тканая: нога не потеет даже за целый день.\n"
        "\n"
        "![Вид сбоку](products/gazelle.png)\n"
        "\n"
        "## Чем хороши\n"
        "- Натуральная замша, не искусственная\n"
        "- Резиновая подошва — не скользит ни на асфальте, ни в зале\n"
        "- Мягкий внутренний кант, не натирает пятку\n"
        "- Поставляется в оригинальной коробке с биркой\n"
        "\n"
        "## Как выбрать размер\n"
        "Модель соответствует размеру. При широкой стопе советуем взять на размер "
        "больше — возврат в течение 14 дней бесплатный.\n"
        "\n"
        "![Чёрный вариант](products/af1-black.png)\n"
        "\n"
        "На фото второй вариант цвета. Оба цвета приходят в одной и той же "
        "коробке и с одной гарантией.",
        "The classic adidas Gazelle in genuine suede, made for everyday wear. "
        "Soft lining, hard-wearing sole. Genuine, from the official "
        "distributor.\n"
        "\n"
        "## Material and stitching\n"
        "The upper is a single piece of genuine suede, double-stitched at the "
        "seams. The woven lining keeps the foot dry through a full day.\n"
        "\n"
        "![Side view](products/gazelle.png)\n"
        "\n"
        "## What is good about them\n"
        "- Genuine suede, not synthetic\n"
        "- Rubber sole — grips on tarmac and in the gym alike\n"
        "- Soft inner collar that does not rub the heel\n"
        "- Ships in the original box, with its tag\n"
        "\n"
        "## Picking a size\n"
        "The model runs true to size. For a wider foot we suggest going one size "
        "up — returns are free within 14 days.\n"
        "\n"
        "![The black one](products/af1-black.png)\n"
        "\n"
        "The second colourway, pictured. Both colours arrive in the same box, "
        "with the same warranty.",
    ),
    "MB-1002": (
        "Белые AF1, которые подходят ко всему. Кожаный верх, амортизация Air.",
        "White AF1s that go with everything. Leather upper, Air cushioning.",
    ),
    "MB-1003": (
        "Пеноматериал ZoomX в подошве — лёгкие и отзывчивые для длинных дистанций.",
        "A ZoomX foam sole — light and responsive over long distances.",
    ),
    "MB-1004": ("Универсальная модель для зала и лёгкого бега.",
                "A versatile model for the gym and easy runs."),
    "MB-1005": ("Удобная детская модель, легко надевается.",
                "Comfortable for children and easy to put on."),
    "MB-2001": (
        "Активное шумоподавление, прозрачный режим и зарядка USB-C. "
        "С официальной гарантией, серийный номер проверяется.",
        "Active noise cancellation, transparency mode and USB-C charging. "
        "Officially warranted, with the serial number verified.",
    ),
    "MB-2002": ("До 40 часов работы, активное шумоподавление и быстрая зарядка.",
                "Up to 40 hours of playback, active noise cancellation and fast charging."),
    "MB-2003": (
        "Четыре встроенных кабеля — заряжает телефон, планшет и наушники разом.",
        "Four built-in cables — charges a phone, a tablet and headphones at once.",
    ),
    "MB-2004": ("Тонкий корпус, быстрая зарядка и цифровой индикатор.",
                "A slim body, fast charging and a digital readout."),
    "MB-2005": ("Заряжает телефон до 50% за 30 минут.",
                "Charges a phone to 50% in 30 minutes."),
    "MB-2006": ("Набор сменных силиконовых амбушюр размеров S/M/L.",
                "A set of replacement silicone tips in S/M/L."),
    "MB-3001": ("Сенсорное управление, три температуры света и регулировка яркости.",
                "Touch control, three light temperatures and adjustable brightness."),
    "MB-3002": ("Лампа с мягким светом для детской комнаты.",
                "A soft-light lamp for a child's room."),
    "MB-4001": ("Плотный хлопок, оверсайз крой. Не теряет цвет после стирки.",
                "Heavy cotton in an oversize fit. Keeps its colour after washing."),
    "MB-4002": ("Футболка классического кроя на каждый день.",
                "A classic-fit T-shirt for everyday wear."),
    "MB-5001": ("Подарочный набор из семи предметов в коробке.",
                "A seven-piece gift set in a presentation box."),
    "MB-1006": (
        "Женская модель в классическом силуэте AF1 — розовый swoosh и фиолетовая "
        "подошва. Кожаный верх, амортизация Air.",
        "A women's take on the classic AF1 silhouette — pink swoosh, purple sole. "
        "Leather upper, Air cushioning.",
    ),
    "MB-1007": ("Однотонные белые Jordan 1 Low — подходят к чему угодно.",
                "All-white Jordan 1 Lows — they go with anything."),
    "MB-1008": ("Полностью чёрные AF1 с треугольной текстурой верха, на каждый день.",
                "All-black AF1s with a triangle-textured upper, for everyday wear."),
    "MB-4004": ("Мягкий хлопковый трикотаж, круглый вырез. Основа гардероба.",
                "Soft cotton jersey with a ribbed neck. A wardrobe staple."),
    "MB-4005": ("Тёмно-синий вариант белой модели — та же ткань, тот же крой.",
                "The navy version of the white one — same fabric, same fit."),
    "MB-4006": ("Бордовое поло с белой отделкой воротника и рукавов. Ткань пике дышит.",
                "A burgundy polo tipped in white at collar and cuff. Pique breathes."),
    "MB-4007": ("Поло с однотонным верхом и широкой полоской по низу.",
                "A polo with a solid top and broad stripes across the body."),
    "MB-6001": (
        "Корпус Oystersteel, браслет Jubilee и рифлёный безель. "
        "Окошко даты, автоматический механизм.",
        "An Oystersteel case, a Jubilee bracelet and a fluted bezel. "
        "Date window, automatic movement.",
    ),
    "MB-6002": ("Datejust с мятно-зелёным циферблатом — редкий цвет.",
                "A Datejust with a mint-green dial — an unusual colour."),
    "MB-6003": ("Чёрный циферблат, браслет Jubilee — самый ходовой Datejust.",
                "Black dial, Jubilee bracelet — the Datejust that sells most."),
    "MB-6004": ("Гладкий безель и трёхзвенный браслет Oyster — вид построже.",
                "A smooth bezel and a three-link Oyster bracelet — a plainer look."),
    "MB-6005": ("Зелёный циферблат, малая секундная стрелка и рифлёный безель. "
                "Швейцарская сборка.",
                "A green dial, a small seconds hand and a fluted bezel. Swiss made."),
    "MB-7001": ("Полуободковая прямоугольная модель, серые градиентные линзы, "
                "титановые заушники.",
                "A half-rim rectangular frame, grey gradient lenses, titanium temples."),
    "MB-7002": ("Прямоугольные линзы без оправы, тонкие заушники золотого цвета.",
                "Rimless rectangular lenses on slim gold-toned temples."),
    "MB-7003": ("Авиаторы с двойным мостом, полностью чёрная оправа и градиентные линзы.",
                "Double-bridge aviators with an all-black frame and gradient lenses."),
}

LEGAL: dict[str, dict[str, tuple[str, str]]] = {
    # matched on slug
    "ommaviy-oferta": {
        "title": ("Публичная оферта", "Public offer"),
        "meta": ("Обновлено 12.08.2026", "Updated 12.08.2026"),
    },
    "tolov-shartlari": {
        "title": ("Условия оплаты", "Payment terms"),
        "meta": ("Картой и наличными", "Card and cash"),
    },
    "qaytarish-siyosati": {
        "title": ("Политика возврата", "Return policy"),
        "meta": ("В течение 14 дней", "Within 14 days"),
    },
    "maxfiylik": {
        "title": ("Политика конфиденциальности", "Privacy policy"),
        "meta": ("Защита данных", "Data protection"),
    },
}

CANCEL_REASONS: dict[str, tuple[str, str]] = {
    "Fikrimdan qaytdim": ("Передумал(а)", "I changed my mind"),
    "Boshqa joydan arzon topdim": ("Нашёл(ла) дешевле в другом месте",
                                   "I found it cheaper elsewhere"),
    "Yetkazish vaqti to'g'ri kelmadi": ("Не подошло время доставки",
                                        "The delivery time didn't suit me"),
    "Xato tovar tanlagan edim": ("Выбрал(а) не тот товар", "I picked the wrong item"),
    "Boshqa sabab": ("Другая причина", "Another reason"),
}

RETURN_REASONS: dict[str, tuple[str, str]] = {
    "O'lcham to'g'ri kelmadi": ("Не подошёл размер", "The size didn't fit"),
    "Sifati kutganimdek emas": ("Качество не такое, как ожидал(а)",
                                "The quality wasn't what I expected"),
    "Rasmga mos kelmadi": ("Не соответствует фото", "It doesn't match the photo"),
    "Nuqsonli yoki shikastlangan": ("Бракованный или повреждённый",
                                    "Faulty or damaged"),
    "Boshqa tovar keldi": ("Пришёл другой товар", "The wrong item arrived"),
}

FAQ: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "Buyurtmani qanday bekor qilaman?": (
        ("Как отменить заказ?", "How do I cancel an order?"),
        ("Пока заказ не собран, его можно отменить в разделе «Мои заказы». "
         "Оплата вернётся на карту в течение 1–3 рабочих дней.",
         "While an order is not yet picked you can cancel it under “My orders”. "
         "The payment returns to your card within 1–3 business days."),
    ),
    "Yetkazish qancha vaqt oladi?": (
        ("Сколько идёт доставка?", "How long does delivery take?"),
        ("По Ташкенту — за день, в области — 2–3 дня. Экспресс-доставка за 2 часа.",
         "Next-day across Tashkent, 2–3 days to the regions. Express delivery within 2 hours."),
    ),
    "Tovarni qaytarish shartlari qanday?": (
        ("Какие условия возврата?", "What are the return terms?"),
        ("В течение 14 дней после доставки, если товар не использован и упаковка цела.",
         "Within 14 days of delivery, if the item is unused and the packaging is intact."),
    ),
    "To'lov o'tmadi, pul qaytadimi?": (
        ("Платёж не прошёл, деньги вернутся?", "The payment failed — do I get the money back?"),
        ("Да. Заблокированная сумма возвращается банком автоматически за 1–3 рабочих дня.",
         "Yes. The held amount is released by the bank automatically within 1–3 business days."),
    ),
    "Punktdan olish qanday ishlaydi?": (
        ("Как работает самовывоз?", "How does pick-up work?"),
        ("Пункт выбирается при оформлении заказа. Когда товар придёт, вы получите SMS — "
         "заберите его с паспортом.",
         "You choose a point at checkout. When the item arrives you get an SMS — "
         "collect it with your passport."),
    ),
}


# ─────────── writing them in ───────────────────────────────────────────────

def _add(rows: list[Translation], entity: str, entity_id: int | None,
         field: str, values: tuple[str, str] | None) -> None:
    if entity_id is None or values is None:
        return
    for lang, value in zip(LANGS, values, strict=True):
        if value:
            rows.append(Translation(entity=entity, entity_id=entity_id,
                                    field=field, lang=lang, value=value))


def seed_translations(session: Session) -> int:
    """Replaces every translation row. Safe to re-run."""
    for existing in session.exec(select(Translation)).all():
        session.delete(existing)
    session.commit()

    rows: list[Translation] = []

    for category in session.exec(select(Category)).all():
        entry = CATEGORIES.get(category.slug)
        if entry:
            _add(rows, "category", category.id, "name", entry[0])
            _add(rows, "category", category.id, "subtitle", entry[1])

    for section in session.exec(select(HomeSection)).all():
        entry = SECTIONS.get(section.key)
        if entry:
            _add(rows, "section", section.id, "title", entry[0])
            _add(rows, "section", section.id, "subtitle", entry[1])

    for banner in session.exec(select(Banner)).all():
        entry = BANNERS.get(banner.title)
        if entry:
            for field, values in entry.items():
                _add(rows, "banner", banner.id, field, values)

    for product in session.exec(select(Product)).all():
        _add(rows, "product", product.id, "title", TITLES.get(product.sku))
        _add(rows, "product", product.id, "description", DESCRIPTIONS.get(product.sku))
        for field in ("subtitle", "badge", "warranty"):
            value = getattr(product, field, None)
            if value:
                pair = (phrase(value, 0), phrase(value, 1))
                if pair[0] or pair[1]:
                    _add(rows, "product", product.id, field,
                         (pair[0] or value, pair[1] or value))

    for variant in session.exec(select(ProductVariant)).all():
        pair = (phrase(variant.label, 0), phrase(variant.label, 1))
        if pair[0] or pair[1]:
            _add(rows, "variant", variant.id, "label",
                 (pair[0] or variant.label, pair[1] or variant.label))

    for spec in session.exec(select(ProductSpec)).all():
        for field in ("key", "value"):
            text = getattr(spec, field)
            pair = (phrase(text, 0), phrase(text, 1))
            if pair[0] or pair[1]:
                _add(rows, "spec", spec.id, field, (pair[0] or text, pair[1] or text))

    for doc in session.exec(select(LegalDoc)).all():
        entry = LEGAL.get(doc.slug)
        if entry:
            for field, values in entry.items():
                _add(rows, "legal", doc.id, field, values)

    for reason in session.exec(select(CancelReason)).all():
        _add(rows, "cancel_reason", reason.id, "label", CANCEL_REASONS.get(reason.label))

    for reason in session.exec(select(ReturnReason)).all():
        _add(rows, "return_reason", reason.id, "label", RETURN_REASONS.get(reason.label))

    for faq in session.exec(select(FaqItem)).all():
        entry = FAQ.get(faq.question)
        if entry:
            _add(rows, "faq", faq.id, "question", entry[0])
            _add(rows, "faq", faq.id, "answer", entry[1])

    session.add_all(rows)
    session.commit()
    return len(rows)
