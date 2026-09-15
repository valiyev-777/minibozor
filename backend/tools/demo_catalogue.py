"""A small shop's worth of goods, through the doors a person would use.

    .venv/bin/python -m tools.demo_catalogue            # against localhost:8000
    .venv/bin/python -m tools.demo_catalogue --clear    # empty the room first

Six models, every one of them finished: colours with a photograph each, a size
run in the order it is worn, a category, a price, a description and a
specification table. Enough for the phone to look like a shop rather than a
test fixture, and few enough that a person can recognise all of it.

**Through the API, not the database.** Every pile is booked in by the warehouse
account and every card is filled in and published by the admin, so what comes
out is a catalogue the ledger can explain: the placements equal the movements,
the cards went active through the same gate a real one does, and nothing here
knows a column name. A fixture written straight into the tables would prove
nothing about the flow it is standing in for.

The pictures are drawn, not photographed — flat silhouettes on white, one per
colour. They are obviously placeholders and that is the point: nobody should
mistake them for the shop's own photographs, and a colour still has to have
*something* or the card cannot be published, which is the rule being
demonstrated.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

WAREHOUSE = "+998900000002"
ADMIN = "+998900000001"

COLOURS: dict[str, tuple[int, int, int]] = {
    "Qora": (28, 32, 44),
    "Oq": (238, 240, 244),
    "Ko'k": (30, 78, 168),
    "Qizil": (196, 42, 58),
    "Kulrang": (120, 128, 140),
    "Bej": (214, 196, 168),
}

CLOTHES = ["S", "M", "L", "XL", "XXL"]


def _tee(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.polygon(
        [(320, 260), (580, 260), (690, 360), (620, 430), (600, 370),
         (600, 700), (300, 700), (300, 370), (280, 430), (210, 360)],
        fill=c,
    )
    d.ellipse([(400, 240), (500, 290)], fill="white")


def _shirt(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.polygon(
        [(300, 250), (600, 250), (700, 350), (640, 410), (620, 350),
         (620, 730), (280, 730), (280, 350), (260, 410), (200, 350)],
        fill=c,
    )


def _jeans(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.polygon(
        [(340, 240), (560, 240), (575, 760), (485, 760), (450, 470),
         (415, 760), (325, 760)],
        fill=c,
    )
    d.rectangle([(340, 240), (560, 300)], fill=c)


def _shoe(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.polygon(
        [(220, 560), (330, 430), (450, 430), (520, 500), (680, 530),
         (700, 600), (680, 630), (240, 630)],
        fill=c,
    )
    d.rectangle([(230, 600), (700, 640)], fill=(32, 36, 44))


def _bag(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.rounded_rectangle([(300, 380), (620, 700)], 26, fill=c)
    d.arc([(360, 250), (560, 460)], 180, 360, fill=c, width=22)


def _cap(d: ImageDraw.ImageDraw, c: tuple[int, int, int]) -> None:
    d.pieslice([(300, 340), (620, 620)], 180, 360, fill=c)
    d.rounded_rectangle([(300, 470), (700, 512)], 20, fill=c)


SHAPES = {"tee": _tee, "shirt": _shirt, "jeans": _jeans, "shoe": _shoe,
          "bag": _bag, "cap": _cap}

# Every model: what it is, where it goes, and what a customer reads.
CATALOGUE: list[dict] = [
    {
        "shape": "tee", "kind": "Futbolka", "brand": "", "cell": "A-01-01",
        "category": ("kiyim", "Kiyim"),
        "title": "Erkaklar futbolkasi Sof",
        "subtitle": "100% paxta, kunlik",
        "description": (
            "Qalin paxta trikotaj, yuvishdan keyin shaklini yo'qotmaydi. "
            "Yelka choklari kuchaytirilgan. Kunlik kiyim uchun."
        ),
        "specs": [("Mato", "100% paxta"), ("Zichlik", "180 g/m²"),
                  ("Ishlab chiqarilgan", "O'zbekiston"), ("Parvarish", "30°C da mashinada")],
        "price": 79_000, "old_price": 99_000, "cost": 42_000,
        "colours": {"Qora": [3, 6, 8, 5, 2], "Oq": [4, 7, 9, 6, 3], "Ko'k": [2, 5, 6, 4, 2]},
        "sizes": CLOTHES,
    },
    {
        "shape": "shirt", "kind": "Ko'ylak", "brand": "", "cell": "A-01-02",
        "category": ("kiyim", "Kiyim"),
        "title": "Erkaklar ko'ylagi Bahor",
        "subtitle": "Uzun yeng, klassik",
        "description": (
            "Yengil paxta-lavsan, dazmol talab qilmaydi. Klassik yoqa, "
            "sadaflar mahkam tikilgan. Ish va bayram uchun."
        ),
        "specs": [("Mato", "65% paxta, 35% lavsan"), ("Yoqa", "Klassik"),
                  ("Yeng", "Uzun"), ("Parvarish", "40°C da mashinada")],
        "price": 149_000, "old_price": None, "cost": 82_000,
        "colours": {"Oq": [2, 5, 6, 4], "Ko'k": [2, 4, 5, 3], "Bej": [1, 3, 4, 2]},
        "sizes": ["S", "M", "L", "XL"],
    },
    {
        "shape": "jeans", "kind": "Shim", "brand": "", "cell": "A-02-01",
        "category": ("kiyim", "Kiyim"),
        "title": "Jinsi shim To'g'ri",
        "subtitle": "To'g'ri kesim, ko'k",
        "description": (
            "Qalin jinsi, cho'zilmaydigan. To'g'ri kesim — poyabzalning "
            "ustiga tushadi. Besh kissa, mis tugma."
        ),
        "specs": [("Mato", "100% paxta denim"), ("Kesim", "To'g'ri"),
                  ("Kissalar", "5"), ("Ishlab chiqarilgan", "Turkiya")],
        "price": 219_000, "old_price": 269_000, "cost": 120_000,
        "colours": {"Ko'k": [2, 4, 5, 4, 2], "Qora": [1, 3, 4, 3, 1]},
        "sizes": ["28", "30", "32", "34", "36"],
    },
    {
        "shape": "shoe", "kind": "Krossovka", "brand": "", "cell": "A-03-01",
        "category": ("oyoq-kiyim", "Oyoq kiyim"),
        "title": "Yugurish krossovkasi Yengil",
        "subtitle": "Nafas oladigan, kunlik",
        "description": (
            "Nafas oladigan to'r ustki qism, yengil ko'pikli taglik. "
            "Kunlik yurish va yengil yugurish uchun."
        ),
        "specs": [("Ustki qism", "To'r"), ("Taglik", "Ko'pik va rezina"),
                  ("Vazni", "280 g (42-o'lcham)"), ("Ishlab chiqarilgan", "Xitoy")],
        "price": 389_000, "old_price": 459_000, "cost": 215_000,
        "colours": {"Qora": [2, 3, 4, 4, 3, 1], "Oq": [1, 2, 3, 3, 2, 1]},
        "sizes": ["39", "40", "41", "42", "43", "44"],
    },
    {
        "shape": "bag", "kind": "Sumka", "brand": "", "cell": "B-01-01",
        "category": ("sumka", "Sumka"),
        "title": "Yelka sumkasi Kun",
        "subtitle": "Noutbuk sig'adi",
        "description": (
            "Suv o'tkazmaydigan mato, 15 dyuymli noutbuk uchun yumshoq "
            "bo'lma. Old kissasi va yon shisha kissasi bor."
        ),
        "specs": [("Mato", "Polyester 600D"), ("Hajmi", "22 litr"),
                  ("Noutbuk", "15 dyuymgacha"), ("Kafolat", "6 oy")],
        "price": 259_000, "old_price": None, "cost": 140_000,
        "colours": {"Qora": [6], "Qizil": [3]},
        "sizes": [""],
    },
    {
        "shape": "cap", "kind": "Kepka", "brand": "", "cell": "B-01-02",
        "category": ("aksessuar", "Aksessuar"),
        "title": "Kepka Yoz",
        "subtitle": "Sozlanadigan",
        "description": "Paxta kepka, orqasi sozlanadi. Yoz uchun yengil.",
        "specs": [("Mato", "100% paxta"), ("Sozlash", "Orqa tasma"),
                  ("Ishlab chiqarilgan", "O'zbekiston")],
        "price": 69_000, "old_price": None, "cost": 32_000,
        "colours": {"Qora": [8], "Kulrang": [5]},
        "sizes": [""],
    },
]


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api/v1"

    def call(self, path, body=None, tok=None, key=None, method=None, ok_also=()):
        headers = {"content-type": "application/json"}
        if tok:
            headers["authorization"] = f"Bearer {tok}"
        if key:
            headers["Idempotency-Key"] = key
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method or ("POST" if body is not None else "GET"),
        )
        try:
            with urllib.request.urlopen(req) as r:
                return json.loads(r.read() or "null")
        except urllib.error.HTTPError as error:
            # A category that is already there is not a failure: this runs
            # twice as often as it runs once, and six models share four
            # categories between them.
            if error.code in ok_also:
                return None
            sys.exit(f"{method or 'POST'} {path} → {error.code}: {error.read().decode()[:300]}")

    def signin(self, phone: str) -> str:
        self.call("/auth/otp/request", {"phone": phone})
        return self.call("/auth/otp/verify", {"phone": phone, "code": "123456"})["access_token"]

    def upload(self, tok: str, path: Path) -> str:
        out = subprocess.run(
            ["curl", "-sS", "-X", "POST", f"{self.base}/media?square=true",
             "-H", f"authorization: Bearer {tok}", "-F", f"file=@{path}"],
            capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(out)["media_url"]


def draw(shape: str, colour: str, into: Path) -> Path:
    """One flat silhouette on white, obviously a placeholder."""
    into.mkdir(parents=True, exist_ok=True)
    path = into / f"{shape}-{colour}.png"
    image = Image.new("RGB", (900, 900), "white")
    SHAPES[shape](ImageDraw.Draw(image), COLOURS[colour])
    image.save(path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument(
        "--clear", action="store_true",
        help="write off whatever is on the shelves first, so counts do not stack",
    )
    args = parser.parse_args()

    api = Api(args.base)
    warehouse = api.signin(WAREHOUSE)
    admin = api.signin(ADMIN)

    if args.clear:
        out = api.call("/warehouse/stock/empty",
                       {"reason": "demo katalog qayta yozildi"}, tok=admin)
        print(f"cleared: {out['cells']} cells, {out['units']} units written off")

    shots = Path("/tmp/minibozor-demo")
    for model in CATALOGUE:
        slug, name = model["category"]
        api.call("/admin/categories", {"slug": slug, "name": name},
                 tok=admin, ok_also=(409,))

        card_id = None
        for colour, counts in model["colours"].items():
            sizes = [
                {"size": size, "quantity": qty}
                for size, qty in zip(model["sizes"], counts, strict=True)
                if qty
            ]
            body = {
                "colour": colour, "sizes": sizes, "unit_cost": model["cost"],
                "place": "Chorsu",
            }
            if card_id is None:
                body |= {"kind": model["kind"], "brand": model["brand"]}
            else:
                body |= {"product_id": card_id}
            # Receiving is two doors now: the goods land in QABUL, and the cell
            # is answered at the shelf. The demo walks both so the shelf map
            # has something in it.
            receipt = api.call("/warehouse/receipts", body, tok=warehouse,
                               key=f"demo-{model['shape']}-{colour}")
            card_id = receipt["product"]["id"]
            api.call(f"/warehouse/receipts/{receipt['run_id']}/shelve",
                     {"location_code": model["cell"]}, tok=warehouse,
                     key=f"demo-shelve-{model['shape']}-{colour}")

            url = api.upload(admin, draw(model["shape"], colour, shots))
            api.call(f"/admin/products/{card_id}/images",
                     {"url": url, "colour": colour}, tok=admin)

        api.call(f"/admin/products/{card_id}", {
            "title": model["title"], "subtitle": model["subtitle"],
            "description": model["description"], "category_slug": slug,
        }, tok=admin, method="PATCH")
        api.call(f"/admin/products/{card_id}/specs", {
            "specs": [{"key": k, "value": v} for k, v in model["specs"]],
        }, tok=admin, method="PUT")
        api.call(f"/admin/products/{card_id}/price", {
            "price": model["price"], "old_price": model["old_price"],
        }, tok=admin)
        # A card already on sale is the state this wants, so the refusal for
        # active → active is a success here.
        live = api.call(f"/admin/products/{card_id}/status", {"status": "active"},
                        tok=admin, ok_also=(409,)) or {"status": "active"}

        units = sum(sum(counts) for counts in model["colours"].values())
        print(f"  {model['title']:34} {live['status']:8} "
              f"{len(model['colours'])} rang · {units} dona · {model['cell']}")

    print("\nDone. The shop has something in it.")


if __name__ == "__main__":
    main()
