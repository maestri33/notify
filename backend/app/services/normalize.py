"""Normalization helpers for phone / WhatsApp inputs.

Rules (from spec):
- phone_sms: DDD + 9 + number, WITHOUT country code 55. Ex: "43996648750"
- whatsapp_jid: "554396648750@s.whatsapp.net" (with country code, no 9 for mobile per WA convention)

Inputs can be messy (spaces, dashes, parens, +55). We strip everything non-digit
then apply channel-specific rules.
"""

import re

_NON_DIGITS = re.compile(r"\D+")


def _digits(value: str) -> str:
    return _NON_DIGITS.sub("", value or "")


def normalize_phone_sms(raw: str | None) -> str | None:
    """Return phone in format expected by SMS Gateway: DDD + 9 + number, no '55'.

    Accepts inputs like:
      "+55 (43) 99664-8750" -> "43996648750"
      "5543996648750"       -> "43996648750"
      "43996648750"         -> "43996648750"
      "4396648750"          -> "43996648750"  (legacy mobile, injects the 9)
    """
    if raw is None:
        return None
    d = _digits(raw)
    if not d:
        return None
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    # Brazilian mobile: DDD (2) + 9 + 8 digits = 11. If 10, inject the 9.
    if len(d) == 10:
        d = d[:2] + "9" + d[2:]
    if len(d) != 11:
        raise ValueError(f"invalid brazilian phone: {raw!r} -> {d!r}")
    return d


def normalize_whatsapp_jid(raw: str | None) -> str | None:
    """Return WhatsApp JID: '<countrycode><ddd><number>@s.whatsapp.net'.

    WhatsApp in Brazil uses the 10-digit mobile format (no extra 9) for most
    numbers, but Baileys' onWhatsApp() is the source of truth. Here we just
    build a candidate JID with country code 55 prepended.

    Accepts:
      "+55 (43) 99664-8750"            -> "5543996648750@s.whatsapp.net"
      "554396648750"                    -> "554396648750@s.whatsapp.net"
      "554396648750@s.whatsapp.net"     -> "554396648750@s.whatsapp.net"
    """
    if raw is None:
        return None
    if "@" in raw:
        return raw.strip()
    d = _digits(raw)
    if not d:
        return None
    if not d.startswith("55"):
        d = "55" + d
    if len(d) < 12 or len(d) > 13:
        raise ValueError(f"invalid whatsapp number: {raw!r} -> {d!r}")
    return f"{d}@s.whatsapp.net"
