
def mask_phone_number(phone_number: str) -> str:
    """+998901234567 -> '+998 90 *** ** 67'. The full number must never
    appear in the API response — only masked through this function."""
    digits = phone_number.lstrip('+')
    country, op, g3 = digits[:3], digits[3:5], digits[10:12]
    return f"+{country} {op} *** ** {g3}"