import hashlib
from decimal import Decimal

def hash_sha256(value: str) -> str:
    """Hashes a normalized string using SHA-256 for Meta Conversions API."""
    if not value:
        return ''
    clean_val = value.strip().lower()
    return hashlib.sha256(clean_val.encode('utf-8')).hexdigest()

def normalize_phone_pk(phone: str) -> str:
    """
    Normalizes a Pakistani phone number to E.164 standard without plus: 923XXXXXXXXX.
    E.g. 03001234567 -> 923001234567, +92 300 1234567 -> 923001234567.
    """
    digits = ''.join(filter(str.isdigit, str(phone)))
    if digits.startswith('03') and len(digits) == 11:
        return '92' + digits[1:]
    elif digits.startswith('923') and len(digits) == 12:
        return digits
    elif digits.startswith('3') and len(digits) == 10:
        return '92' + digits
    return digits

def format_currency(amount, currency_symbol='Rs.'):
    """Formats decimal amount as readable currency string e.g. Rs. 2,499."""
    try:
        val = Decimal(amount)
        return f"{currency_symbol} {val:,.0f}" if val % 1 == 0 else f"{currency_symbol} {val:,.2f}"
    except Exception:
        return f"{currency_symbol} {amount}"
