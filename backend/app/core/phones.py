"""Egyptian phone normalization (CONTRACTS section 5, P2-2). Every phone in the DB is E.164 (+201012345678).

normalize_eg_phone("010 1234 5678")  → "+201012345678"
normalize_eg_phone("٠١٠١٢٣٤٥٦٧٨")    → "+201012345678"   (Arabic-Indic digits)
normalize_eg_phone("0020 10 1234 5678") / ("201012345678") / ("+20 10 1234 5678") → "+201012345678"
normalize_eg_phone("02 2345 6789")    → "+20223456789"    (Cairo landline)
normalize_eg_phone("call us")         → None

Mobile = +20 followed by 10/11/12/15 and 8 more digits (Vodafone, Etisalat/e&, Orange, WE).
"""

import re

import phonenumbers

_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_MOBILE_RE = re.compile(r"^\+20(10|11|12|15)\d{8}$")
_SEPARATORS_RE = re.compile(r"[/,;|،]| or | او | أو ")
_KEEP_RE = re.compile(r"[^\d+]")


def _clean(raw: str) -> str:
    text = raw.translate(_DIGIT_MAP).strip()
    text = _KEEP_RE.sub("", text)
    if text.startswith("00"):
        text = "+" + text[2:]
    # "201012345678": international form without the plus (national numbers start with 0).
    if not text.startswith("+") and text.startswith("20") and len(text) >= 11:
        text = "+" + text
    # "+2001012345678": the national leading 0 kept after the country code.
    if text.startswith("+200") and len(text) >= 13:
        text = "+20" + text[4:]
    # "1012345678": a mobile without its leading 0.
    if re.fullmatch(r"1[0125]\d{8}", text):
        text = "0" + text
    return text


def _normalize_one(raw: str) -> str | None:
    text = _clean(raw)
    if sum(ch.isdigit() for ch in text) < 8:
        return None
    candidate = text
    if _MOBILE_RE.match(candidate):
        return candidate
    try:
        number = phonenumbers.parse(candidate, "EG")
    except phonenumbers.NumberParseException:
        return None
    if number.country_code != 20:
        return None  # an Egyptian lead list; foreign numbers are not usable for this product
    e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    if _MOBILE_RE.match(e164) or phonenumbers.is_valid_number(number):
        return e164
    return None


def normalize_eg_phone(raw: str | None) -> str | None:
    """E.164 for an Egyptian mobile or landline in any common spelling; None for anything else.

    A field holding several numbers ("010… / 011…") yields the first valid one.
    """
    if not raw or not raw.strip():
        return None
    for part in _SEPARATORS_RE.split(raw.translate(_DIGIT_MAP)):
        result = _normalize_one(part)
        if result:
            return result
    return None


def is_eg_mobile(e164: str | None) -> bool:
    """True for +20 10/11/12/15 + 8 digits (the numbers that can have WhatsApp)."""
    return bool(e164) and bool(_MOBILE_RE.match(e164 or ""))
