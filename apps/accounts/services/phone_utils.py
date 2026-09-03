"""Utilities for displaying a phone number without ever exposing it in
full through an API response."""


def mask_phone_number(phone_number: str) -> str:
    """
    "+998901234567" -> "+998 90 *** ** 67"

    Assumes the Uzbek mobile format stored everywhere in this project:
    "+998" followed by 9 digits. Only the operator code and the last 2
    digits are shown. The caller must never send the raw phone_number to
    the client in this flow — only the output of this function.
    """
    digits = phone_number.lstrip('+')
    if len(digits) != 12:
        return "*** ** **"  # defensive fallback, should not happen
    country, op, last_two = digits[:3], digits[3:5], digits[10:12]
    return f"+{country} {op} *** ** {last_two}"