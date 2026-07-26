"""
Davlatlar bo'yicha xizmat narxlari.
Yangi davlat qo'shish yoki narxni o'zgartirish uchun shu faylni tahrirlang.
"""

PRICING = {
    "Bolgariya": {"total": 13_500_000, "prepay": 4_500_000, "remainder": 9_000_000, "refusal_fee": 4_500_000},
    "Chexiya": {"total": 13_500_000, "prepay": 4_500_000, "remainder": 9_000_000, "refusal_fee": 4_500_000},
    "Estoniya": {"total": 13_500_000, "prepay": 4_500_000, "remainder": 9_000_000, "refusal_fee": 4_500_000},
    "Germaniya": {"total": 21_000_000, "prepay": 4_500_000, "remainder": 16_500_000, "refusal_fee": 4_500_000},
    "Kanada": {"total": 27_000_000, "prepay": 4_500_000, "remainder": 22_500_000, "refusal_fee": 4_500_000},
    "Polsha": {"total": 13_500_000, "prepay": 4_500_000, "remainder": 9_000_000, "refusal_fee": 4_500_000},
    "Sloveniya": {"total": 13_500_000, "prepay": 4_500_000, "remainder": 9_000_000, "refusal_fee": 4_500_000},
}


def format_pricing_table() -> str:
    """AI uchun tizim promptiga qo'yiladigan matn ko'rinishidagi jadval."""
    lines = ["Davlat | Umumiy narx | Boshlang'ich to'lov | Qolgan qism | Rad etilsa ushlab qolinadigan summa"]
    for country, p in PRICING.items():
        lines.append(
            f"{country} | {p['total']:,} so'm | {p['prepay']:,} so'm | "
            f"{p['remainder']:,} so'm | {p['refusal_fee']:,} so'm"
        )
    return "\n".join(lines)


def get_country_pricing(country: str):
    """Mos kelmasa None qaytaradi - AI so'zma-so'z mos nomni ishlatishi kerak."""
    return PRICING.get(country)
