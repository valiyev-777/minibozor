"""Seed the database with the exact content of the design.

Running this makes every one of the 47 screens show real data, so the apps can
be developed and demoed without any other backing service.

    python -m app.seed          # fill an empty database
    python -m app.seed --reset  # drop everything first
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from sqlmodel import Session, SQLModel, delete, select

from app.core.security import hash_secret
from app.db import engine, init_db
from app.models import (
    Address,
    Banner,
    Brand,
    CancelReason,
    CardStatus,
    CartItem,
    Category,
    DeliverySlot,
    FaqItem,
    Favorite,
    HomeSection,
    LegalDoc,
    Notification,
    NotificationKind,
    Order,
    OrderEvent,
    OrderItem,
    OrderStatus,
    PaymentCard,
    PaymentMethod,
    PickupPoint,
    PopularQuery,
    Product,
    ProductImage,
    ProductSpec,
    ProductVariant,
    PromoCode,
    ReturnReason,
    Review,
    ReviewStatus,
    ReviewTag,
    User,
    VariantKind,
)
from app.seed_i18n import seed_translations

DEMO_PHONE = "+998901234567"
DEMO_PIN = "1234"


def _at(day_offset: int, hh: int, mm: int) -> datetime:
    base = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=day_offset)
    return base.replace(hour=hh, minute=mm, second=0, microsecond=0)


# --------------------------------------------------------------------------- catalogue

# Pictures the shop supplied for the tiles. A category without one keeps its
# line glyph, which is what the rest of the list still uses.
CATEGORY_IMAGES = {
    "elektronika": "categories/elektronika.png",
    "kiyim-poyabzal": "categories/kiyim-poyabzal.png",
    "maishiy-texnika": "categories/maishiy-texnika.png",
    "uy-bog": "categories/uy-bog.png",
    "oyinchoqlar": "categories/oyinchoqlar.png",
    "avto": "categories/avto.png",
    "maktab-bozori": "categories/maktab-bozori.png",
    "sport": "categories/sport.png",
    "gozallik": "categories/gozallik.png",
    "taom-yetkazish": "categories/taom-yetkazish.png",
    "chet-eldan": "categories/chet-eldan.png",
    "kundalik": "categories/kundalik.png",
    "aksessuar": "categories/aksessuar.png",
    "oziq-ovqat": "categories/oziq-ovqat.png",
}

ROOT_CATEGORIES = [
    # slug, name, subtitle, icon, quick_link, product_count (counted at read time)
    ("elektronika", "Elektronika", "Smartfon, noutbuk, aksessuar", "phone", True, 0),
    ("kiyim-poyabzal", "Kiyim va poyabzal", "Ayollar, erkaklar, bolalar", "shirt", True, 0),
    ("maishiy-texnika", "Maishiy texnika", "Kir mashina, muzlatgich", "washer", True, 0),
    ("uy-bog", "Uy va bog'", "Mebel, dekor, asboblar", "sofa", True, 0),
    ("oyinchoqlar", "O'yinchoqlar", "Bolalar uchun hammasi", "gift", True, 0),
    ("gozallik", "Go'zallik", "Parfyumeriya, kosmetika", "lipstick", False, 0),
    ("oziq-ovqat", "Oziq-ovqat", "Kundalik mahsulotlar", "basket", False, 0),
    ("avto", "Avto tovarlar", "Ehtiyot qism, aksessuar", "car", True, 0),
    ("sport", "Sport", "Trenajyor, kiyim, jihoz", "ball", False, 0),
    ("maktab-bozori", "Maktab bozori", "Sumka, daftar, forma", "backpack", True, 0),
    ("taom-yetkazish", "Taom yetkazish", "Restoran va kafelardan", "food", True, 0),
    ("chet-eldan", "Chet eldan", "Xalqaro yetkazish", "globe", True, 0),
    ("kundalik", "Kundalik", "Gigiyena, uy kimyosi", "bottle", True, 0),
    # Not a quick link: the home grid is exactly 5x2, so an eleventh tile
    # would break the row. Reachable from the catalogue tab.
    ("aksessuar", "Aksessuar", "Soat, ko'zoynak, taqinchoq", "star", False, 0),
]

SUBCATEGORIES = [
    # parent, slug, name, image, product_count (counted at read time)
    ("kiyim-poyabzal", "futbolka-toplar", "Futbolka va toplar",
     "products/tshirt-white.png", 2_140),
    ("kiyim-poyabzal", "krossovkalar", "Krossovkalar", "products/gazelle.png", 0),
    ("kiyim-poyabzal", "koylak-libos", "Ko'ylak va libos", "products/polo-striped.png", 0),
    ("kiyim-poyabzal", "kundalik-poyabzal", "Kundalik poyabzal",
     "products/af1-black.png", 1_240),
    ("kiyim-poyabzal", "sport-kiyim", "Sport kiyim", "products/tshirt-green.png", 0),
    ("kiyim-poyabzal", "bolalar-poyabzali", "Bolalar poyabzali",
     "products/jordan1-low-white.png", 0),
    ("elektronika", "quloqchinlar", "Quloqchinlar", "products/airpods.png", 0),
    ("elektronika", "quvvat-aksessuar", "Quvvat va aksessuar", "products/powerbank.png", 0),
    ("uy-bog", "yoruglik", "Yoritish", "products/lamp.png", 0),
    ("kiyim-poyabzal", "polo", "Polo ko'ylaklar", "products/polo-burgundy.png", 0),
    ("aksessuar", "soatlar", "Qo'l soatlari", "products/rolex-datejust-blue.png", 0),
    ("aksessuar", "kozoynaklar", "Quyosh ko'zoynaklari",
     "products/sunglasses-aviator-black.png", 0),
]

BRANDS = [
    ("nike", "Nike"), ("adidas", "adidas"), ("apple", "Apple"), ("ugreen", "UGREEN"),
    ("anker", "Anker"), ("zara", "Zara"), ("hm", "H&M"), ("puma", "Puma"),
    ("new-balance", "New Balance"), ("reebok", "Reebok"), ("mango", "Mango"),
    ("jordan", "Jordan"), ("rolex", "Rolex"), ("gucci", "Gucci"), ("dita", "DITA"),
    ("uniqlo", "UNIQLO"),
]

SHOE_SIZES = ["39", "40", "41", "42", "43", "44", "45", "46"]
TEE_SIZES = ["S", "M", "L", "XL", "XXL"]
WATCH_SIZES = ["36 mm", "41 mm"]

PRODUCTS = [
    dict(
        sku="MB-1001", title="adidas Gazelle, ko'k zamsh", subtitle="Ko'k · zamsh",
        category="krossovkalar", brand="adidas", price=1_090_000, old_price=1_540_000,
        rating=4.8, reviews_count=136, sold_count=1_240, badge="Original",
        images=["products/gazelle.png", "products/af1-black.png"],
        sizes=SHOE_SIZES,
        colors=[
            ("Ko'k", "#2F4B8F", "products/gazelle.png"),
            ("Qora", "#0E0F12", "products/af1-black.png"),
        ],
        warranty="Original kafolati",
        # A full description, with the shop's own photographs inside it: the
        # product page renders "## " as a heading, "- " as a bullet and
        # "![alt](path)" as a picture, so a seller can write a page rather than
        # a paragraph. Everything else is plain text.
        description=(
            "Klassik adidas Gazelle — tabiiy zamshdan tikilgan, kundalik kiyish "
            "uchun. Ichki qismi yumshoq, taglik mustahkam. Original, rasmiy "
            "distribyutordan.\n"
            "\n"
            "## Materiali va tikuvi\n"
            "Yuza qismi butun bo'lak tabiiy zamshdan, choklar ikki qatlam ip "
            "bilan tikilgan. Ichki astar to'qima mato — oyoq terlamaydi va "
            "kun bo'yi kiyganda ham hidi qolmaydi.\n"
            "\n"
            "![Yon ko'rinish](products/gazelle.png)\n"
            "\n"
            "## Nimasi bilan yaxshi\n"
            "- Tabiiy zamsh yuza, sun'iy emas\n"
            "- Rezina taglik — asfaltda ham, zalda ham siljimaydi\n"
            "- Ichki yumshoq ustki qism, tovonni ishqalamaydi\n"
            "- Original quti va yorliq bilan yetkaziladi\n"
            "\n"
            "## O'lcham tanlash\n"
            "Model o'lchamiga aynan mos keladi. Oyoq kengligi o'rtachadan "
            "kattaroq bo'lsa, bir o'lcham kattasini olishni maslahat beramiz — "
            "qaytarish 14 kun ichida bepul.\n"
            "\n"
            "![Qora varianti](products/af1-black.png)\n"
            "\n"
            "Rasmda ikkinchi rang varianti. Ikkala rang ham bir xil qutida, "
            "bir xil kafolat bilan keladi."
        ),
        specs=[("Material", "Tabiiy zamsh"), ("Taglik", "Rezina"), ("Mavsum", "Bahor-kuz"),
               ("Ishlab chiqarilgan", "Vetnam")],
    ),
    dict(
        sku="MB-1002", title="Nike Air Force 1 Low, oq", subtitle="Oq · charm",
        category="kundalik-poyabzal", brand="nike", price=1_249_000, old_price=1_665_000,
        rating=4.9, reviews_count=204, sold_count=2_010, badge="Bestseller",
        images=["products/jordan1-low-white.png"], sizes=SHOE_SIZES, colors=[("Oq", "#FFFFFF")],
        warranty="Original kafolati",
        description="Har narsaga mos keladigan oq AF1. Charm yuza, Air amortizatsiyasi.",
        specs=[("Material", "Tabiiy charm"), ("Taglik", "Rezina, Air"), ("Mavsum", "Butun yil")],
    ),
    dict(
        sku="MB-1003", title="Nike ZoomX, yugurish uchun", subtitle="Yugurish · yengil",
        category="krossovkalar", brand="nike", price=1_480_000, old_price=1_805_000,
        rating=4.7, reviews_count=88, sold_count=640,
        images=["products/nike-pink.png"], sizes=SHOE_SIZES,
        description="ZoomX ko'pikli taglik — uzoq masofaga yugurish uchun yengil va qaytaruvchan.",
        specs=[("Vazn", "218 g"), ("Taglik", "ZoomX"), ("Turi", "Yugurish")],
    ),
    dict(
        sku="MB-1004", title="Nike Air Zoom, pushti", subtitle="Pushti · trening",
        category="krossovkalar", brand="nike", price=1_320_000, old_price=1_692_000,
        rating=4.6, reviews_count=51, sold_count=380,
        images=["products/nike-pink.png"], sizes=SHOE_SIZES,
        description="Zal va yengil yugurish uchun universal model.",
        specs=[("Taglik", "Air Zoom"), ("Turi", "Trening")],
    ),
    dict(
        sku="MB-1005", title="adidas Grand Court, qora", subtitle="Qora · kundalik",
        category="bolalar-poyabzali", brand="adidas", price=890_000, old_price=1_290_000,
        rating=4.5, reviews_count=42, sold_count=520,
        images=["products/af1-black.png"], sizes=["32", "33", "34", "35", "36"],
        description="Bolalar uchun qulay, oson kiyiladigan model.",
        specs=[("Material", "Sun'iy charm"), ("Yopilishi", "Ilma")],
    ),
    dict(
        sku="MB-2001", title="AirPods Pro 2, USB-C", subtitle="Original · kafolat 1 yil",
        category="quloqchinlar", brand="apple", price=2_190_000, old_price=2_890_000,
        rating=4.9, reviews_count=318, sold_count=1_890, badge="Original",
        images=["products/airpods.png", "products/airpods-dark.png"],
        colors=[
            ("Oq", "#FFFFFF", "products/airpods.png"),
            ("Qora", "#0E0F12", "products/airpods-dark.png"),
        ],
        warranty="Rasmiy kafolat 1 yil",
        description=(
            "Faol shovqin bostirish, shaffof rejim va USB-C quvvatlash. "
            "Rasmiy kafolat bilan, seriya raqami tekshiriladi."
        ),
        specs=[("Ulanish", "Bluetooth 5.3"), ("ANC", "Bor"), ("Quvvat", "USB-C"),
               ("Ishlash vaqti", "6 soat + 30 soat")],
    ),
    dict(
        sku="MB-2002", title="Simsiz quloqchin ANC, 40 soat", subtitle="Qora · over-ear",
        category="quloqchinlar", brand="anker", price=612_000, old_price=890_000,
        rating=4.9, reviews_count=212, sold_count=1_460, badge="Bestseller",
        images=["products/headphones.png"], colors=[("Qora", "#0E0F12")],
        warranty="Kafolat 1 yil",
        description="40 soatgacha ishlaydi, aktiv shovqin bostirish va tez quvvatlash.",
        specs=[("Turi", "Over-ear"), ("ANC", "Bor"), ("Ishlash vaqti", "40 soat")],
    ),
    dict(
        sku="MB-2003", title="Powerbank 30000 mAh, 4 kabel", subtitle="Qora · mavjud",
        category="quvvat-aksessuar", brand="ugreen", price=429_000, old_price=572_000,
        rating=4.6, reviews_count=97, sold_count=880,
        images=["products/powerbank.png"], colors=[("Qora", "#0E0F12")],
        description=(
            "To'rtta o'rnatilgan kabel — telefon, planshet va quloqchinni birga quvvatlaydi."
        ),
        specs=[("Sig'im", "30000 mAh"), ("Quvvat", "22.5W"),
               ("Kabellar", "USB-C, Lightning, Micro")],
    ),
    dict(
        sku="MB-2004", title="Powerbank 20000 mAh, 22.5W", subtitle="Kulrang · tez quvvat",
        category="quvvat-aksessuar", brand="ugreen", price=389_000, old_price=620_000,
        rating=4.7, reviews_count=64, sold_count=740,
        images=["products/powerbank-ugreen.png"],
        description="Yupqa korpus, tez quvvatlash va raqamli indikator.",
        specs=[("Sig'im", "20000 mAh"), ("Quvvat", "22.5W")],
    ),
    dict(
        sku="MB-2005", title="Adapter 20W USB-C", subtitle="Oq · tez quvvat",
        category="quvvat-aksessuar", brand="apple", price=189_000, old_price=222_000,
        rating=4.8, reviews_count=126, sold_count=1_320,
        images=["products/charger.png"],
        description="Telefonni 30 daqiqada 50% gacha quvvatlaydi.",
        specs=[("Quvvat", "20W"), ("Chiqish", "USB-C")],
    ),
    dict(
        sku="MB-2006", title="AirPods uchun quloqchalar", subtitle="3 o'lcham · silikon",
        category="quloqchinlar", brand="apple", price=39_000, old_price=65_000,
        rating=4.4, reviews_count=38, sold_count=460,
        images=["products/airpods-tips.png"],
        description="S/M/L o'lchamli almashtiriladigan silikon quloqchalar to'plami.",
        specs=[("Materiali", "Silikon"), ("O'lchamlar", "S, M, L")],
    ),
    dict(
        sku="MB-3001", title="Stol chirog'i LED, sensorli", subtitle="Oq · 3 rejim",
        category="yoruglik", price=189_000, old_price=320_000,
        rating=4.7, reviews_count=92, sold_count=780, badge="Kafolat 1 yil",
        images=["products/lamp.png"],
        colors=[("Oq", "#FFFFFF", "products/lamp.png"), ("Qora", "#0E0F12")],
        warranty="Kafolat 1 yil",
        description="Sensorli boshqaruv, uchta yorug'lik harorati va yorqinlikni sozlash.",
        specs=[("Quvvat", "9W"), ("Rejimlar", "3"), ("Ulanish", "USB-C")],
    ),
    dict(
        sku="MB-3002", title="Bolalar stol chirog'i, astronavt", subtitle="3 rang · 6 dona qoldi",
        category="yoruglik", price=129_000, old_price=190_000,
        rating=4.8, reviews_count=44, sold_count=310, stock_left=6,
        images=["products/lamp.png"],
        description="Bolalar xonasi uchun yumshoq yorug'lik beruvchi chiroq.",
        specs=[("Quvvat", "6W"), ("Ranglar", "3")],
    ),
    dict(
        sku="MB-4001", title="Oversize futbolka, 100% paxta", subtitle="Qora · L",
        category="futbolka-toplar", brand="zara", price=149_000, old_price=249_000,
        rating=5.0, reviews_count=38, sold_count=920, badge="Yangi",
        images=["products/tshirt-navy.png"], sizes=TEE_SIZES,
        colors=[
            ("Qora", "#0E0F12", "products/tshirt-navy.png"),
            ("Oq", "#FFFFFF", "products/tshirt-white.png"),
        ],
        description="Qalin paxta mato, oversize bichim. Yuvishdan keyin rangi o'zgarmaydi.",
        specs=[("Material", "100% paxta"), ("Bichim", "Oversize"), ("Zichlik", "220 g/m²")],
    ),
    dict(
        sku="MB-4002", title="Klassik futbolka, yashil", subtitle="S–XXL · mavjud",
        category="futbolka-toplar", brand="hm", price=139_000, old_price=158_000,
        rating=4.6, reviews_count=27, sold_count=430,
        images=["products/tshirt-green.png"], sizes=TEE_SIZES,
        description="Kundalik kiyish uchun klassik bichimdagi futbolka.",
        specs=[("Material", "95% paxta, 5% elastan")],
    ),
    dict(
        sku="MB-5001", title="Parfyumeriya to'plami, 7 predmet", subtitle="Sovg'a qutisi",
        category="gozallik", price=749_000, old_price=913_000,
        rating=4.7, reviews_count=58, sold_count=340,
        images=["products/cosmetics.png"],
        description="Yetti predmetli sovg'abop to'plam, hediya qutisi bilan.",
        specs=[("Predmetlar", "7 ta"), ("Qadoq", "Sovg'a qutisi")],
    ),
    # ---- added from photographs supplied by the shop ----
    dict(
        sku="MB-1006", title="Nike Air Force 1 '07, oq-pushti", subtitle="Oq · pushti swoosh",
        category="kundalik-poyabzal", brand="nike", price=1_690_000, old_price=2_100_000,
        rating=4.9, reviews_count=112, sold_count=780, badge="Yangi",
        images=["products/af1-pink.png"], sizes=SHOE_SIZES,
        colors=[("Oq-pushti", "#F3D4DC")],
        warranty="Original kafolati",
        description=(
            "Klassik AF1 siluetidagi ayollar modeli — pushti swoosh va binafsha taglik. "
            "Charm yuza, Air amortizatsiyasi."
        ),
        specs=[("Material", "Tabiiy charm"), ("Taglik", "Rezina, Air"),
               ("Mavsum", "Butun yil"), ("Bichim", "Past")],
    ),
    dict(
        sku="MB-1007", title="Air Jordan 1 Low, butunlay oq", subtitle="Oq · charm",
        category="kundalik-poyabzal", brand="jordan", price=2_290_000, old_price=2_690_000,
        rating=4.9, reviews_count=176, sold_count=1_430, badge="Bestseller",
        images=["products/jordan1-low-white.png"], sizes=SHOE_SIZES,
        colors=[("Oq", "#FFFFFF")],
        warranty="Original kafolati",
        description="Bir rangli oq Jordan 1 Low — har qanday kiyimga mos keladigan model.",
        specs=[("Material", "Tabiiy charm"), ("Taglik", "Rezina"), ("Mavsum", "Butun yil")],
    ),
    dict(
        sku="MB-1008", title="Nike Air Force 1, butunlay qora", subtitle="Qora · tekstura",
        category="kundalik-poyabzal", brand="nike", price=1_590_000, old_price=1_990_000,
        rating=4.7, reviews_count=94, sold_count=610,
        images=["products/af1-black.png"], sizes=SHOE_SIZES,
        colors=[("Qora", "#0E0F12")],
        warranty="Original kafolati",
        description="Butunlay qora AF1 — uch burchakli teksturali yuza, kunlik kiyish uchun.",
        specs=[("Material", "Sun'iy charm"), ("Taglik", "Rezina, Air"), ("Mavsum", "Butun yil")],
    ),
    dict(
        sku="MB-4004", title="Klassik futbolka, oq", subtitle="Oq · paxta",
        category="futbolka-toplar", brand="uniqlo", price=189_000, old_price=239_000,
        rating=4.7, reviews_count=64, sold_count=1_180,
        images=["products/tshirt-white.png"], sizes=TEE_SIZES,
        colors=[("Oq", "#FFFFFF")],
        description="Yumshoq paxta trikotaj, tik yoqa. Kundalik kiyish uchun asos.",
        specs=[("Material", "100% paxta"), ("Bichim", "Klassik"), ("Zichlik", "180 g/m²")],
    ),
    dict(
        sku="MB-4005", title="Klassik futbolka, to'q ko'k", subtitle="To'q ko'k · paxta",
        category="futbolka-toplar", brand="uniqlo", price=199_000, old_price=249_000,
        rating=4.8, reviews_count=51, sold_count=870,
        images=["products/tshirt-navy.png"], sizes=TEE_SIZES,
        colors=[("To'q ko'k", "#141A2E")],
        description="Oq modelning to'q ko'k varianti — bir xil mato, bir xil bichim.",
        specs=[("Material", "100% paxta"), ("Bichim", "Klassik"), ("Zichlik", "180 g/m²")],
    ),
    dict(
        sku="MB-4006", title="Polo ko'ylak, bordo", subtitle="Bordo · pike",
        category="polo", brand="zara", price=449_000, old_price=599_000,
        rating=4.8, reviews_count=42, sold_count=380, badge="Yangi",
        images=["products/polo-burgundy.png"], sizes=TEE_SIZES,
        colors=[("Bordo", "#6E1F35")],
        description="Yoqasi va yengi oq chiziqli bordo polo. Pike to'qimasi nafas oladi.",
        specs=[("Material", "100% paxta pike"), ("Yoqasi", "Chiziqli"), ("Bichim", "Klassik")],
    ),
    dict(
        sku="MB-4007", title="Polo ko'ylak, ko'k-oq chiziqli", subtitle="Ko'k · chiziqli",
        category="polo", brand="puma", price=289_000, old_price=379_000,
        rating=4.5, reviews_count=29, sold_count=240,
        images=["products/polo-striped.png"], sizes=TEE_SIZES,
        colors=[("Ko'k", "#1B4FD8")],
        description="Yuqori qismi bir rang, pastki qismi keng chiziqli polo.",
        specs=[("Material", "Paxta aralashma"), ("Bichim", "Klassik")],
    ),
    dict(
        sku="MB-6001", title="Rolex Datejust 41, ko'k siferblat", subtitle="Jubilee · po'lat",
        category="soatlar", brand="rolex", price=168_000_000, old_price=185_000_000,
        rating=5.0, reviews_count=8, sold_count=12, badge="Original",
        images=["products/rolex-datejust-blue.png"], sizes=WATCH_SIZES,
        colors=[("Ko'k", "#1C4E9C")],
        warranty="Rasmiy kafolat 1 yil",
        description=(
            "Oysterste'l korpus, Jubilee brasleti va rifli bezel. "
            "Sana oynasi, avtomatik mexanizm."
        ),
        specs=[("Korpus", "Po'lat 41 mm"), ("Braslet", "Jubilee"),
               ("Mexanizm", "Avtomatik"), ("Suvga chidamlilik", "100 m")],
    ),
    dict(
        sku="MB-6002", title="Rolex Datejust 41, yashil siferblat", subtitle="Jubilee · po'lat",
        category="soatlar", brand="rolex", price=182_000_000,
        rating=5.0, reviews_count=5, sold_count=6, badge="Original",
        images=["products/rolex-datejust-green.png"], sizes=WATCH_SIZES,
        colors=[("Yashil", "#1F5C3A")],
        warranty="Rasmiy kafolat 1 yil",
        description="Mint-yashil siferblatli Datejust — kamdan-kam uchraydigan rang.",
        specs=[("Korpus", "Po'lat 41 mm"), ("Braslet", "Jubilee"),
               ("Mexanizm", "Avtomatik"), ("Suvga chidamlilik", "100 m")],
    ),
    dict(
        sku="MB-6003", title="Rolex Datejust 41, qora siferblat", subtitle="Jubilee · po'lat",
        category="soatlar", brand="rolex", price=159_000_000, old_price=172_000_000,
        rating=4.9, reviews_count=11, sold_count=15, badge="Original",
        images=["products/rolex-datejust-black.png"], sizes=WATCH_SIZES,
        colors=[("Qora", "#0E0F12")],
        warranty="Rasmiy kafolat 1 yil",
        description="Qora siferblat, Jubilee braslet — Datejust oilasining eng ko'p sotilgani.",
        specs=[("Korpus", "Po'lat 41 mm"), ("Braslet", "Jubilee"),
               ("Mexanizm", "Avtomatik"), ("Suvga chidamlilik", "100 m")],
    ),
    dict(
        sku="MB-6004", title="Rolex Datejust 41, Oyster braslet", subtitle="Oyster · po'lat",
        category="soatlar", brand="rolex", price=154_000_000,
        rating=4.9, reviews_count=7, sold_count=9, badge="Original",
        images=["products/rolex-datejust-oyster.png"], sizes=WATCH_SIZES,
        colors=[("Qora", "#0E0F12")],
        warranty="Rasmiy kafolat 1 yil",
        description="Tekis bezel va uch bo'g'inli Oyster braslet — soddaroq ko'rinish.",
        specs=[("Korpus", "Po'lat 41 mm"), ("Braslet", "Oyster"),
               ("Mexanizm", "Avtomatik"), ("Suvga chidamlilik", "100 m")],
    ),
    dict(
        sku="MB-6005", title="Gucci G-Timeless, yashil siferblat", subtitle="Po'lat · avtomatik",
        category="soatlar", brand="gucci", price=21_500_000, old_price=25_900_000,
        rating=4.8, reviews_count=14, sold_count=22,
        images=["products/gucci-g-timeless.png"], sizes=["40 mm"],
        colors=[("Yashil", "#1F5C3A")],
        warranty="Rasmiy kafolat 1 yil",
        description="Yashil siferblat, kichik soniya mili va rifli bezel. Shveysariya yig'uvi.",
        specs=[("Korpus", "Po'lat 40 mm"), ("Mexanizm", "Avtomatik"),
               ("Suvga chidamlilik", "50 m")],
    ),
    dict(
        sku="MB-7001", title="DITA quyosh ko'zoynagi, oltin-qora",
        subtitle="Gradient linza · titan",
        category="kozoynaklar", brand="dita", price=6_900_000, old_price=8_200_000,
        rating=4.9, reviews_count=16, sold_count=31, badge="Original",
        images=["products/sunglasses-gold-gradient.png"],
        colors=[("Oltin-qora", "#3A2E1C")],
        warranty="Original kafolati",
        description="Yarim ramkali to'rtburchak model, kulrang gradient linza, titan dastalar.",
        specs=[("Ramka", "Titan"), ("Linza", "Gradient"), ("UV himoya", "UV400")],
    ),
    dict(
        sku="MB-7002", title="Ramkasiz ko'zoynak, ko'k linza", subtitle="Ramkasiz · oltin",
        category="kozoynaklar", brand="dita", price=5_400_000, old_price=6_400_000,
        rating=4.7, reviews_count=9, sold_count=18,
        images=["products/sunglasses-rimless-blue.png"],
        colors=[("Ko'k", "#2C4A6E")],
        warranty="Original kafolati",
        description="Ramkasiz to'rtburchak linza, oltin rangli ingichka dastalar.",
        specs=[("Ramka", "Ramkasiz"), ("Linza", "Bir tekis"), ("UV himoya", "UV400")],
    ),
    dict(
        sku="MB-7003", title="DITA aviator, qora", subtitle="Aviator · qora",
        category="kozoynaklar", brand="dita", price=7_200_000,
        rating=4.9, reviews_count=21, sold_count=44, badge="Original",
        images=["products/sunglasses-aviator-black.png"],
        colors=[("Qora", "#0E0F12")],
        warranty="Original kafolati",
        description="Ikki ko'prikli aviator, butunlay qora ramka va gradient linza.",
        specs=[("Ramka", "Titan"), ("Linza", "Gradient"), ("UV himoya", "UV400")],
    ),
]

BANNERS = [
    dict(
        kicker="MINI BOZOR / UY VA YORUG'LIK",
        title="Ish stolingiz uchun",
        subtitle="Chiroq va aksessuarlarga 40% gacha",
        image_url="products/lamp.png",
        gradient_from="#14162A", gradient_to="#0E7BF5",
        target_type="category", target_value="yoruglik", sort=0,
    ),
    dict(
        kicker="MINI BOZOR / ELEKTRONIKA",
        title="Original kafolat bilan",
        subtitle="Quloqchin va quvvat aksessuarlari",
        image_url="products/airpods.png",
        gradient_from="#14162A", gradient_to="#0E7C66",
        target_type="category", target_value="elektronika", sort=1,
    ),
    dict(
        kicker="MINI BOZOR / POYABZAL",
        title="Bahorgi yangilanish",
        subtitle="Original brendlarga chegirma",
        image_url="products/gazelle.png",
        gradient_from="#14162A", gradient_to="#5A4BE3",
        target_type="category", target_value="krossovkalar", sort=2,
    ),
]

HOME_SECTIONS = [
    ("deals", "Bugungi tanlov", "Har kuni yangilanadi", None, "deals", 0),
    ("for-you", "Siz uchun", "ko'rganlaringiz asosida", None, "grid", 1),
    ("shoes", "Poyabzal", "original brendlar", "kiyim-poyabzal", "rail", 2),
    ("electronics", "Elektronika", "kafolat bilan", "elektronika", "rail", 3),
]

FAQ = [
    ("Buyurtmani qanday bekor qilaman?",
     "Buyurtma yig'ilmagan bo'lsa, «Buyurtmalarim» bo'limidan bekor qilishingiz mumkin. "
     "To'lov 1–3 ish kunida kartangizga qaytadi."),
    ("Yetkazish qancha vaqt oladi?",
     "Toshkent bo'ylab bir kunda, viloyatlarga 2–3 kunda. Tezkor yetkazish 2 soat ichida."),
    ("Tovarni qaytarish shartlari qanday?",
     "Yetkazilgandan keyin 14 kun ichida, tovar ishlatilmagan va qadog'i butun bo'lsa."),
    ("To'lov o'tmadi, pul qaytadimi?",
     "Ha. Bloklangan summa bank tomonidan 1–3 ish kunida avtomatik qaytariladi."),
    ("Punktdan olish qanday ishlaydi?",
     "Buyurtma berishda punktni tanlaysiz. Tovar yetib kelganda SMS keladi, "
     "pasport bilan borib olasiz."),
]

LEGAL = [
    ("ommaviy-oferta", "globe", "Ommaviy oferta", "Yangilangan 12.08.2026"),
    ("tolov-shartlari", "card", "To'lov shartlari", "Karta va naqd to'lov"),
    ("qaytarish-siyosati", "ret", "Qaytarish siyosati", "14 kun ichida"),
    ("maxfiylik", "gear", "Maxfiylik siyosati", "Ma'lumotlar himoyasi"),
]

CANCEL_REASONS = [
    ("Fikrimdan qaytdim", False),
    ("Boshqa joydan arzon topdim", False),
    ("Yetkazish vaqti to'g'ri kelmadi", False),
    ("Xato tovar tanlagan edim", False),
    ("Boshqa sabab", True),
]

RETURN_REASONS = [
    ("O'lcham to'g'ri kelmadi", False),
    ("Sifati kutganimdek emas", False),
    ("Rasmga mos kelmadi", False),
    ("Nuqsonli yoki shikastlangan", True),
    ("Boshqa tovar keldi", True),
]

REVIEW_TAGS = [
    "O'lcham mos", "Sifatli", "Tez yetkazildi", "Rasmga mos", "Narxi arzon", "Qadoq yaxshi",
]

POPULAR_QUERIES = [
    "iPhone 15", "robot changyutgich", "yozgi ko'ylak", "airfryer", "maktab sumkasi", "smart soat",
]

RECENT_QUERIES = [
    "krossovka nike", "mikroto'lqinli pech", "bolalar velosipedi", "kir yuvish mashinasi",
]

PICKUP_POINTS = [
    ("Mini Bozor punkti · Chilonzor 4", "Chilonzor tumani, Bunyodkor 12",
     "Har kuni 09:00–21:00", 1.2),
    ("Mini Bozor punkti · Yunusobod 19", "Yunusobod tumani, Amir Temur 108",
     "Har kuni 10:00–20:00", 3.4),
    ("Mini Bozor punkti · Sergeli", "Sergeli tumani, Yangi Sergeli 3",
     "Har kuni 09:00–20:00", 7.8),
]

# The windows a courier round covers, every day.
TIME_SLOTS = [
    ("09:00", "13:00", "Ertalabki yetkazish", 0),
    ("14:00", "18:00", "Eng ko'p tanlanadigan oraliq", 0),
    ("18:00", "22:00", "Ish kunidan keyin", 9_000),
]

# Express is not a window in the day, it is "two hours from now" — so it only
# exists today, and only while two hours still fit before the last round.
EXPRESS_NOTE = "Tezkor yetkazish · Toshkent markazi"
EXPRESS_PRICE = 19_000
DAY_OPENS = time.fromisoformat("09:00")
DAY_CLOSES = time.fromisoformat("22:00")


# --------------------------------------------------------------------------- runner


def reset(session: Session) -> None:
    for table in reversed(SQLModel.metadata.sorted_tables):
        session.exec(delete(table))
    session.commit()


def seed(session: Session) -> None:
    if session.exec(select(Product)).first():
        print("Database already seeded — nothing to do. Use --reset to start over.")
        return

    categories = _seed_categories(session)
    brands = _seed_brands(session)
    products = _seed_products(session, categories, brands)
    _seed_home(session)
    _seed_content(session)
    _seed_delivery(session)
    users = _seed_users(session)
    _seed_reviews(session, products, users)
    _seed_user_data(session, users["demo"], products)
    session.commit()
    translated = seed_translations(session)

    print(f"Seeded {len(products)} products, {len(categories)} categories.")
    print(f"Seeded {translated} translation rows (ru, en).")
    print(f"Demo login: {DEMO_PHONE} · SMS code 123456 (dev) · PIN {DEMO_PIN}")


def _seed_categories(session: Session) -> dict[str, Category]:
    out: dict[str, Category] = {}
    for sort, (slug, name, subtitle, icon, quick, count) in enumerate(ROOT_CATEGORIES):
        image = CATEGORY_IMAGES.get(slug)
        row = Category(
            slug=slug, name=name, subtitle=subtitle, icon=icon,
            image_url=image if image is None or _image_exists(image) else None,
            is_quick_link=quick, product_count=count, sort=sort,
        )
        session.add(row)
        out[slug] = row
    session.commit()

    for sort, (parent, slug, name, image, count) in enumerate(SUBCATEGORIES):
        row = Category(
            slug=slug, name=name, icon=out[parent].icon,
            # Same guard as the roots: a thumbnail whose file is not there
            # would render as an empty tile in the subcategory list.
            image_url=image if _image_exists(image) else None,
            parent_id=out[parent].id, product_count=count, sort=sort,
        )
        session.add(row)
        out[slug] = row
    session.commit()
    return out


def _seed_brands(session: Session) -> dict[str, Brand]:
    out = {}
    for slug, name in BRANDS:
        row = Brand(slug=slug, name=name)
        session.add(row)
        out[slug] = row
    session.commit()
    return out


MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"


def _split_stock(total: int, parts: int) -> list[int]:
    """
    The shelf, divided between the colours standing on it.

    A product is stocked as a whole and photographed one colour at a time, so
    the catalogue knows the total and the page has to answer for a colour. The
    split is by descending weight rather than evenly: the first colour is the
    one photographed first and the one that sells, and four blue against two
    black reads like a shelf while twelve of each reads like arithmetic.

    Deterministic, and the parts always sum back to the total — the page shows
    a share of a number the rest of the app still agrees with.
    """
    if parts <= 0:
        return []
    weights = list(range(parts, 0, -1))
    scale = sum(weights)
    out = [total * w // scale for w in weights]
    # Whatever the flooring dropped goes back to the first colours, in order.
    for i in range(total - sum(out)):
        out[i % parts] += 1
    return out


def _image_exists(path: str) -> bool:
    """Whether the export actually shipped this file.

    Several photos referenced by the design were never exported. Seeding a row
    for a missing file leaves the app rendering a broken tile; skipping it lets
    the tile show its "no photo" state instead, and a re-seed picks the photo
    up the moment the real PNG lands in media/.
    """
    return (MEDIA_DIR / path).is_file()


def _seed_products(
    session: Session, categories: dict[str, Category], brands: dict[str, Brand]
) -> dict[str, Product]:
    out: dict[str, Product] = {}
    for spec in PRODUCTS:
        product = Product(
            sku=spec["sku"],
            title=spec["title"],
            subtitle=spec.get("subtitle", ""),
            description=spec.get("description", ""),
            category_id=categories[spec["category"]].id,
            brand_id=brands[spec["brand"]].id if spec.get("brand") else None,
            price=spec["price"],
            old_price=spec.get("old_price"),
            rating=spec.get("rating", 0.0),
            reviews_count=spec.get("reviews_count", 0),
            sold_count=spec.get("sold_count", 0),
            badge=spec.get("badge"),
            warranty=spec.get("warranty"),
            stock_left=spec.get("stock_left", 25),
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        out[spec["sku"]] = product

        shipped = [u for u in spec.get("images", []) if _image_exists(u)]
        for i, url in enumerate(shipped):
            session.add(ProductImage(product_id=product.id, url=url, sort=i))
        for url in spec.get("images", []):
            if url not in shipped:
                print(f"  eksport qilinmagan rasm o'tkazib yuborildi: {url}")
        for i, label in enumerate(spec.get("sizes", [])):
            session.add(
                ProductVariant(
                    product_id=product.id, kind=VariantKind.SIZE,
                    label=label, value=label, sort=i,
                )
            )
        colors = spec.get("colors", [])
        color_stock = _split_stock(product.stock_left, len(colors))
        for i, color in enumerate(colors):
            # ("Qora", "#0E0F12") or ("Qora", "#0E0F12", "products/af1-black.png").
            label, value, *rest = color
            image = rest[0] if rest else None
            # A product photographed in one colour only *is* that colour's
            # photograph — no point repeating the path in the row above.
            if image is None and len(colors) == 1:
                image = next(iter(spec.get("images", [])), None)
            if image and not _image_exists(image):
                image = None
            left = color_stock[i]
            session.add(
                ProductVariant(
                    product_id=product.id, kind=VariantKind.COLOR,
                    label=label, value=value, image_url=image, sort=i,
                    stock_left=left, in_stock=left > 0,
                )
            )
        for i, (key, value) in enumerate(spec.get("specs", [])):
            session.add(ProductSpec(product_id=product.id, key=key, value=value, sort=i))
    session.commit()
    return out


def _seed_home(session: Session) -> None:
    for spec in BANNERS:
        session.add(Banner(**spec))
    for key, title, subtitle, category, layout, sort in HOME_SECTIONS:
        session.add(
            HomeSection(
                key=key, title=title, subtitle=subtitle,
                category_slug=category, layout=layout, sort=sort,
            )
        )
    session.add(PromoCode(code="MINI10", percent_off=10, min_total=200_000))
    session.add(PromoCode(code="YETKAZISH", amount_off=19_000, min_total=100_000))
    session.commit()


def _seed_content(session: Session) -> None:
    for sort, (question, answer) in enumerate(FAQ):
        session.add(FaqItem(question=question, answer=answer, sort=sort))
    for sort, (slug, icon, title, meta) in enumerate(LEGAL):
        session.add(
            LegalDoc(
                slug=slug, icon=icon, title=title, meta=meta, sort=sort,
                body=f"{title}\n\nHujjatning to'liq matni backend admin panelidan boshqariladi.",
            )
        )
    for sort, (label, needs_comment) in enumerate(CANCEL_REASONS):
        session.add(CancelReason(label=label, sort=sort, requires_comment=needs_comment))
    for sort, (label, needs_comment) in enumerate(RETURN_REASONS):
        session.add(ReturnReason(label=label, sort=sort, requires_comment=needs_comment))
    for sort, label in enumerate(REVIEW_TAGS):
        session.add(ReviewTag(label=label, sort=sort))
    for sort, query in enumerate(POPULAR_QUERIES):
        session.add(PopularQuery(query=query, hits=500 - sort * 40, sort=sort))
    session.commit()


def _seed_delivery(session: Session) -> None:
    for name, address, hours, distance in PICKUP_POINTS:
        session.add(
            PickupPoint(name=name, address=address, hours=hours, distance_km=distance)
        )
    today = date.today()
    for offset in range(7):
        day = today + timedelta(days=offset)
        for start, end, note, price in TIME_SLOTS:
            # A window that has already begun cannot be chosen.
            if offset == 0 and datetime.now().time() > time.fromisoformat(start):
                continue
            session.add(
                DeliverySlot(
                    day=day, start_time=start, end_time=end,
                    note=note, price=price, express=False,
                )
            )

    # Today only, and only if two hours fit before the last round: an express
    # slot on a future day would be offering "within two hours" tomorrow, which
    # is what it used to do.
    now = datetime.now()
    start = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)
    start = start.replace(minute=start.minute - start.minute % 15)
    end = start + timedelta(hours=2)
    if start.time() >= DAY_OPENS and end.time() <= DAY_CLOSES and end.date() == today:
        session.add(
            DeliverySlot(
                day=today,
                start_time=start.strftime("%H:%M"),
                end_time=end.strftime("%H:%M"),
                note=EXPRESS_NOTE,
                price=EXPRESS_PRICE,
                express=True,
            )
        )
    session.commit()


def _seed_users(session: Session) -> dict[str, User]:
    demo = User(
        phone=DEMO_PHONE,
        full_name="Aziz Toshmatov",
        email="aziz@example.uz",
        birth_date=date(1994, 5, 12),
        gender="erkak",
        pin_hash=hash_secret(DEMO_PIN),
    )
    madina = User(phone="+998901112233", full_name="Madina Karimova")
    bekzod = User(phone="+998934445566", full_name="Bekzod Tursunov")
    for user in (demo, madina, bekzod):
        session.add(user)
    session.commit()
    for user in (demo, madina, bekzod):
        session.refresh(user)
    return {"demo": demo, "madina": madina, "bekzod": bekzod}


def _seed_reviews(
    session: Session, products: dict[str, Product], users: dict[str, User]
) -> None:
    entries = [
        ("MB-1002", "madina", 5, "Oq · 38",
         "Juda yengil va qulay. O'lcham aynan mos keldi, qadoq butun holda yetib keldi. "
         "Rasmdagidek — rangi ham xuddi shunday.",
         ["O'lcham mos", "Qadoq yaxshi"], ["products/af1.png"], 12, -6),
        ("MB-1001", "bekzod", 4, "Qora · 43",
         "Sifati yaxshi, lekin yetkazish bir kun kechikdi. Taglik mustahkam, "
         "kun bo'yi yurdim — oyoq charchamadi.",
         ["Sifatli"], ["products/gazelle.png", "products/af1-black.png"], 5, -10),
        ("MB-1001", "demo", 5, "Ko'k · 42",
         "O'lcham aynan mos keldi, zamsh sifatli. Kuniga 8 soat kiyaman — oyoq charchamaydi.",
         ["O'lcham mos", "Sifatli"], ["products/gazelle.png"], 14, -12),
        ("MB-2001", "demo", 4, "Oq",
         "Original, shovqin bostirish zo'r. Faqat quti chizilib kelgan edi.",
         ["Tez yetkazildi"], [], 6, -20),
    ]
    for sku, who, rating, variant, text, tags, photos, likes, day_offset in entries:
        session.add(
            Review(
                user_id=users[who].id,
                product_id=products[sku].id,
                rating=rating,
                variant_label=variant,
                text=text,
                tags=tags,
                photos=photos,
                likes=likes,
                status=ReviewStatus.PUBLISHED,
                created_at=_at(day_offset, 12, 0),
            )
        )
    session.commit()


def _seed_user_data(session: Session, user: User, products: dict[str, Product]) -> None:
    home = Address(
        user_id=user.id, title="Uy", icon="pin", badge="ASOSIY",
        line="Toshkent, Amir Temur shoh ko'chasi 108",
        floor="12", apartment="45", entrance_code="1245K",
        latitude=41.3308, longitude=69.2846, is_default=True,
    )
    work = Address(
        user_id=user.id, title="Ish", icon="box", badge="OFIS",
        line="Toshkent, Mustaqillik ko'chasi 12A",
        floor="3", comment="Qabulxona · ish kunlari 9:00–18:00",
        latitude=41.3110, longitude=69.2797,
    )
    session.add(home)
    session.add(work)

    humo = PaymentCard(
        user_id=user.id, brand="Humo", last4="4417", holder="AZIZ TOSHMATOV",
        expiry_month=9, expiry_year=2029, is_default=True, processor_token="tok_demo_4417",
    )
    uzcard = PaymentCard(
        user_id=user.id, brand="UzCard", last4="3390", holder="AZIZ TOSHMATOV",
        expiry_month=3, expiry_year=2025, status=CardStatus.EXPIRED,
        processor_token="tok_demo_3390",
    )
    session.add(humo)
    session.add(uzcard)
    session.commit()
    session.refresh(home)
    session.refresh(humo)

    for sku in ("MB-5001", "MB-3002", "MB-2003", "MB-4002"):
        product = products[sku]
        session.add(
            Favorite(user_id=user.id, product_id=product.id, price_when_added=product.old_price)
        )

    for sku, qty in (("MB-4001", 2), ("MB-3001", 1), ("MB-2001", 1)):
        session.add(CartItem(user_id=user.id, product_id=products[sku].id, quantity=qty))

    _seed_orders(session, user, products, home, humo)
    _seed_notifications(session, user)
    session.commit()


def _seed_orders(
    session: Session,
    user: User,
    products: dict[str, Product],
    address: Address,
    card: PaymentCard,
) -> None:
    specs = [
        # code, status, items, day offset for created_at, delivery day offset
        ("#A-104729", OrderStatus.SHIPPED,
         [("MB-4001", 2, "Qora · L"), ("MB-3001", 1, "Oq · 3 rejim")], -2, 0),
        ("#A-104688", OrderStatus.PACKING,
         [("MB-1001", 1, "Ko'k · 42"), ("MB-2005", 2, "Oq")], -1, 2),
        ("#A-104512", OrderStatus.DELIVERED,
         [("MB-2002", 1, "Qora"), ("MB-4002", 1, "Yashil · M")], -18, -14),
    ]

    for code, status, lines, created_offset, delivery_offset in specs:
        created = _at(created_offset, 19, 40)
        delivery_day = date.today() + timedelta(days=delivery_offset)
        subtotal = sum(products[sku].price * qty for sku, qty, _ in lines)
        delivery_fee = 0 if subtotal >= 250_000 else 19_000

        order = Order(
            code=code, user_id=user.id, status=status,
            address_line=address.line, address_meta=address.meta,
            delivery_day=delivery_day, delivery_start="14:00", delivery_end="18:00",
            payment_method=PaymentMethod.CARD, payment_card_id=card.id, paid=True,
            recipient_name=user.full_name, recipient_phone=user.phone,
            subtotal=subtotal, delivery_fee=delivery_fee, discount=0,
            total=subtotal + delivery_fee,
            created_at=created, updated_at=created,
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        for sku, qty, variant in lines:
            product = products[sku]
            image = session.exec(
                select(ProductImage).where(ProductImage.product_id == product.id)
            ).first()
            session.add(
                OrderItem(
                    order_id=order.id, product_id=product.id, title=product.title,
                    image_url=image.url if image else "", variant_label=variant,
                    unit_price=product.price, quantity=qty,
                )
            )

        flow = [
            OrderStatus.PLACED, OrderStatus.PACKING, OrderStatus.SHIPPED, OrderStatus.DELIVERED,
        ]
        titles = [
            "Buyurtma qabul qilindi", "Omborda yig'ildi", "Kuryerga topshirildi", "Yetkazildi",
        ]
        reached = flow.index(status) if status in flow else len(flow)
        for i, (step, title) in enumerate(zip(flow, titles, strict=True)):
            session.add(
                OrderEvent(
                    order_id=order.id, status=step, title=title, sort=i,
                    happened_at=created + timedelta(hours=12 * i) if i <= reached else None,
                )
            )
    session.commit()


def _seed_notifications(session: Session, user: User) -> None:
    entries = [
        (NotificationKind.ORDER, "box", "Buyurtma yo'lda",
         "#A-104729 kuryerga topshirildi, 14:00–18:00 orasida yetadi", 0, 12, 5),
        (NotificationKind.PRICE_DROP, "heart", "Sevimlidagi narx tushdi",
         "adidas Gazelle — 1 540 000 → 1 090 000 so'm", 0, 9, 40),
        (NotificationKind.ORDER, "box", "Buyurtma yig'ildi",
         "#A-104688 omborda yig'ildi — ertaga jo'natiladi", 0, 8, 12),
        (NotificationKind.REVIEW, "star", "Sharh qoldirasizmi?",
         "Stol chirog'i LED — tajribangizni bo'lishing", -4, 15, 20),
        (NotificationKind.PAYMENT, "card", "To'lov muvaffaqiyatli",
         "444 100 so'm · Karta ···· 4417", -5, 11, 5),
    ]
    for kind, icon, title, text, day, hh, mm in entries:
        session.add(
            Notification(
                user_id=user.id, kind=kind, icon=icon, title=title, text=text,
                created_at=_at(day, hh, mm),
            )
        )
    session.commit()


def main() -> None:
    init_db()
    with Session(engine) as session:
        if "--reset" in sys.argv:
            reset(session)
            print("Database cleared.")
        if "--translations" in sys.argv:
            # Re-runnable on its own: translations change far more often than
            # the catalogue they describe.
            print(f"Seeded {seed_translations(session)} translation rows (ru, en).")
            return
        seed(session)


if __name__ == "__main__":
    main()
