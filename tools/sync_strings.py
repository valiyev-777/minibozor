#!/usr/bin/env python3
"""Regenerate the iOS string resources from the Android ones.

The two apps show the same text, and the Android resources are where it is
written and translated. Keeping a second hand-maintained copy of 300-odd
strings is how the two drift apart, so this converts instead:

    python3 tools/sync_strings.py

What changes between the platforms is the container and the format specifiers.
Android's %1$s is an object placeholder on the iOS side (%1$@); its <plurals>
become a .stringsdict, where the count picks the case and a second argument
carries the number as the caller formatted it — which is what keeps "2 140
tovar" grouped. Android's <string-array> has no iOS equivalent, so its items
land as name.0, name.1 and so on.

A key missing from a translation falls back to the Uzbek, exactly as it does
on Android.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android/app/src/main/res"
IOS = ROOT / "ios/MiniBozor"
LANGS = {"uz": "values", "ru": "values-ru", "en": "values-en"}

DICT_HEAD = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
'''


def strings_value(text: str) -> str:
    if len(text) > 1 and text.startswith('"') and text.endswith('"'):
        text = text[1:-1]          # Android quotes to protect edge spaces
    text = text.replace("\\'", "'")
    text = re.sub(r"%(\d+)\$s", r"%\1$@", text)
    return text.replace('"', '\\"')


def plural_value(text: str) -> str:
    text = text.replace("\\'", "'")
    text = re.sub(r"%\d+\$s", "%2$@", text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def read(bucket: str):
    root = ET.parse(ANDROID / bucket / "strings.xml").getroot()
    strings, plurals, arrays = {}, {}, {}
    for e in root:
        if e.tag == "string":
            strings[e.get("name")] = "".join(e.itertext())
        elif e.tag == "plurals":
            plurals[e.get("name")] = {
                i.get("quantity"): "".join(i.itertext()) for i in e
            }
        elif e.tag == "string-array":
            arrays[e.get("name")] = ["".join(i.itertext()) for i in e]
    return strings, plurals, arrays


def main() -> None:
    base = read("values")

    for lang, bucket in LANGS.items():
        strings, plurals, arrays = read(bucket)
        merged = {**base[0], **strings}
        merged_plurals = {**base[1], **plurals}
        merged_arrays = {**base[2], **arrays}

        out = IOS / f"{lang}.lproj"
        out.mkdir(parents=True, exist_ok=True)

        lines = [
            f"/* Generated from android/app/src/main/res/{bucket}/strings.xml by",
            "   tools/sync_strings.py. Edit the Android resources, then re-run it. */",
            "",
        ]
        lines += [f'"{k}" = "{strings_value(v)}";' for k, v in sorted(merged.items())]
        for name, items in sorted(merged_arrays.items()):
            lines += [
                f'"{name}.{i}" = "{strings_value(item)}";'
                for i, item in enumerate(items)
            ]
        (out / "Localizable.strings").write_text("\n".join(lines) + "\n", encoding="utf-8")

        body = []
        for name, cases in sorted(merged_plurals.items()):
            body += [
                f"\t<key>{name}</key>",
                "\t<dict>",
                "\t\t<key>NSStringLocalizedFormatKey</key>",
                "\t\t<string>%1$#@count@</string>",
                "\t\t<key>count</key>",
                "\t\t<dict>",
                "\t\t\t<key>NSStringFormatSpecTypeKey</key>",
                "\t\t\t<string>NSStringPluralRuleType</string>",
                "\t\t\t<key>NSStringFormatValueTypeKey</key>",
                "\t\t\t<string>d</string>",
            ]
            for quantity, text in cases.items():
                body += [f"\t\t\t<key>{quantity}</key>",
                         f"\t\t\t<string>{plural_value(text)}</string>"]
            body += ["\t\t</dict>", "\t</dict>"]
        (out / "Localizable.stringsdict").write_text(
            DICT_HEAD + "\n".join(body) + "\n</dict>\n</plist>\n", encoding="utf-8"
        )

        print(f"{lang}: {len(merged)} strings, {len(merged_plurals)} plurals, "
              f"{len(merged_arrays)} arrays")


if __name__ == "__main__":
    main()
