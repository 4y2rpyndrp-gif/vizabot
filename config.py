"""
Bot sozlamalari.
Bu yerdagi qiymatlarni o'zingiznikiga almashtiring.
"""

import os

# BotFather'dan olingan token (@BotFather -> /newbot)
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")

# Nazorat guruhingizning Telegram ID raqami (manfiy son bo'ladi, masalan -1001234567890)
# Qanday topish mumkinligi README.md faylida yozilgan
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))

# Lid sotuvchiga biriktirilgandan keyin necha soatdan keyin
# "hali bog'lanilmadi" degan eslatma yuborilsin
FOLLOWUP_HOURS = 3

# Click.uz Merchant sozlamalari (Click bilan shartnoma tuzgach to'ldirasiz)
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
CLICK_MERCHANT_USER_ID = os.getenv("CLICK_MERCHANT_USER_ID", "")

# Ma'lumotlar bazasi fayli (hech narsa o'zgartirish shart emas)
DB_PATH = os.path.join(os.path.dirname(__file__), "vizabot.db")
