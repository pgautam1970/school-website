"""Readable Nepali (Bikram Sambat) date, produced only when reliably available."""
from __future__ import annotations

from datetime import date

NE_MONTHS = [
    "बैशाख", "जेठ", "असार", "साउन", "भदौ", "असोज",
    "कार्तिक", "मंसिर", "पुष", "माघ", "फागुन", "चैत",
]
NE_DIGITS = "०१२३४५६७८९"
WEEKDAYS_NE = ["सोमबार", "मंगलबार", "बुधबार", "बिहीबार", "शुक्रबार", "शनिबार", "आइतबार"]


def to_ne_digits(n: int | str) -> str:
    return "".join(NE_DIGITS[int(d)] if d.isdigit() else d for d in str(n))


def nepali_date_str(ad: date) -> str:
    """e.g. '२०८२ असोज २४ गते, शुक्रबार'. Falls back to ISO on conversion error."""
    try:
        import nepali_datetime
        nd = nepali_datetime.date.from_ad_date(ad)
        month = NE_MONTHS[nd.month - 1]
        weekday = WEEKDAYS_NE[ad.weekday()]
        return f"{to_ne_digits(nd.year)} {month} {to_ne_digits(nd.day)} गते, {weekday}"
    except Exception:
        return ""  # "when reliably available" — never fabricate a Nepali date
