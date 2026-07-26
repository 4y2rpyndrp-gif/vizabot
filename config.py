"""
Bot sozlamalari.
Bu yerdagi qiymatlarni o'zingiznikiga almashtiring.
"""

import os

# BotFather'dan olingan token (@BotFather -> /newbot)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8632423216:AAHz5Qr_LPiHD3LClzQMFBvPi8NACr8LqO8")

# Nazorat guruhingizning Telegram ID raqami (manfiy son bo'ladi, masalan -1001234567890)
# Qanday topish mumkinligi README.md faylida yozilgan
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-5484716510"))

# Lid sotuvchiga biriktirilgandan keyin necha soatdan keyin
# "hali bog'lanilmadi" degan eslatma yuborilsin
FOLLOWUP_HOURS = 3

# Click.uz Merchant sozlamalari (Click bilan shartnoma tuzgach to'ldirasiz)
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "")

# AI sotuvchi uchun Anthropic API sozlamalari (console.anthropic.com dan olinadi)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
# AI sotuvchi yoqilgan/o'chirilganligi - "true" bo'lsa mijoz bilan AI gaplashadi,
# aks holda oddiy anketa (davlat/maqsad/telefon) ishlaydi
AI_SELLER_ENABLED = os.getenv("AI_SELLER_ENABLED", "false").lower() == "true"

# Ma'lumotlar bazasi fayli (hech narsa o'zgartirish shart emas)
DB_PATH = os.path.join(os.path.dirname(__file__), "vizabot.db")
