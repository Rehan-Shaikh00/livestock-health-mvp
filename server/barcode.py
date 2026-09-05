"""Cryptographically-signed Code-128 barcodes for laboratory chain of custody.

Barcode value:  MH-<LGD district>-<YYMMDD>-<6 hex>   e.g. MH-521-260905-A3F9C1
Signature:      first 8 hex chars of HMAC-SHA256(secret, barcode)
Printed label:  barcode value + signature suffix, rendered as Code-128B so any
                lab scanner reads it. The signature lets the receiving lab verify
                the sample was issued by this system and not forged/retyped.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone

SECRET = os.getenv("BARCODE_SECRET", os.getenv("SECRET_KEY", "dev-barcode-secret"))

# Code 128 pattern table (bar/space widths). Index = symbol value 0..106.
_PATTERNS = (
    "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 "
    "123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 "
    "232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 "
    "313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 "
    "111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 "
    "111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 "
    "114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112"
).split()
START_B, STOP = 104, 106


def generate(district_code: str) -> tuple[str, str]:
    """Return (barcode, signature)."""
    stamp = datetime.now(timezone.utc).strftime("%y%m%d")
    code = f"MH-{district_code or '000'}-{stamp}-{secrets.token_hex(3).upper()}"
    return code, sign(code)


def sign(code: str) -> str:
    return hmac.new(SECRET.encode(), code.encode(), hashlib.sha256).hexdigest()[:8].upper()


def verify(code: str, signature: str) -> bool:
    return hmac.compare_digest(sign(code), (signature or "").upper())


def code128_modules(text: str) -> list[tuple[int, bool]]:
    """Encode `text` as Code-128B. Returns [(width, is_bar), ...]."""
    values = [START_B] + [ord(ch) - 32 for ch in text]
    checksum = (values[0] + sum(i * v for i, v in enumerate(values[1:], start=1))) % 103
    values += [checksum, STOP]
    modules: list[tuple[int, bool]] = []
    for v in values:
        for i, w in enumerate(_PATTERNS[v]):
            modules.append((int(w), i % 2 == 0))
    return modules


def code128_svg(text: str, height: int = 64, module: int = 2, label: str | None = None) -> str:
    modules = code128_modules(text)
    quiet = 10 * module
    total = sum(w for w, _ in modules) * module + 2 * quiet
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{height + 22}" viewBox="0 0 {total} {height + 22}">',
             f'<rect width="{total}" height="{height + 22}" fill="#fff"/>']
    x = quiet
    for w, bar in modules:
        if bar:
            parts.append(f'<rect x="{x}" y="4" width="{w * module}" height="{height}" fill="#111"/>')
        x += w * module
    parts.append(f'<text x="{total / 2}" y="{height + 17}" font-family="ui-monospace,monospace" font-size="12" text-anchor="middle" fill="#111">{label or text}</text></svg>')
    return "".join(parts)
