# Viza konsalting - Telegram sotuv boti

Hech qanday tashqi CRM yoki Google Sheets kerak emas — hammasi shu bot va bitta
baza fayli (`vizabot.db`) ichida ishlaydi.

## Qanday ishlaydi

1. Mijoz botga yozadi → bot 3 ta savol so'raydi (davlat, maqsad, ism, telefon)
2. Lid avtomatik eng bo'sh sotuvchiga biriktiriladi (ish yukini tenglashtiradi)
3. Sotuvchiga shaxsiy xabar + sizning nazorat guruhingizga xabar boradi
4. Sotuvchi `/tolov` buyrug'i bilan Click to'lov havolasi yaratadi va mijozga yuboradi
5. Mijoz to'laganida bot avtomatik hammaga xabar beradi
6. 3 soat ichida bog'lanilmagan lidlar uchun avtomatik ogohlantirish keladi

## 1-qadam: Botni yaratish

1. Telegram'da **@BotFather** ga yozing
2. `/newbot` buyrug'ini yuboring, nom va username bering
3. Sizga token beradi (masalan: `123456:ABC-DEF1234ghIkl...`)
4. Shu tokenni `config.py` faylidagi `BOT_TOKEN` ga qo'ying (yoki muhit o'zgaruvchisi sifatida)

## 2-qadam: Nazorat guruhini sozlash

1. Telegram'da yangi guruh yarating (masalan "Viza — nazorat")
2. Botni shu guruhga qo'shing
3. Guruh ID sini bilish uchun: guruhga istalgan xabar yozing, so'ng
   `https://api.telegram.org/bot<TOKEN>/getUpdates` manzilini brauzerda oching —
   `"chat":{"id":-100xxxxxxxxxx}` qismidan guruh ID sini topasiz (manfiy son)
4. Shu ID ni `config.py` dagi `ADMIN_GROUP_ID` ga qo'ying

## 3-qadam: O'rnatish

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 4-qadam: Botni ishga tushirish

```bash
./venv/bin/python bot.py
```

## 5-qadam: Sotuvchilarni qo'shish

1. Har bir sotuvchi botga `/start` yozadi
2. Sotuvchi `/myid` buyrug'i bilan o'z Telegram ID sini biladi
3. Siz nazorat guruhida shunday yozasiz:
   ```
   /add_seller 123456789 Aziz
   ```
4. Shundan keyin Aziz'ga avtomatik lidlar tusha boshlaydi

## Sotuvchi buyruqlari (botga shaxsiy yozadi)

| Buyruq | Vazifasi |
|---|---|
| `/mine` | Menga biriktirilgan ochiq lidlar ro'yxati |
| `/contacted 5` | 5-lid bilan bog'landim deb belgilash |
| `/tolov 5 500000` | 5-lid uchun 500,000 so'mlik Click to'lov havolasi yaratish |
| `/yoqotildi 5` | 5-lidni yo'qotilgan deb belgilash |

## Click.uz to'lovlarini ulash

1. https://merchant.click.uz saytida biznesingizni ro'yxatdan o'tkazing va
   Merchant shartnoma tuzing (bank rekvizitlaringiz kerak bo'ladi)
2. Sizga `merchant_id`, `service_id`, `secret_key` beriladi — shularni
   `config.py` ga yozing
3. **Muhim**: to'lov "muvaffaqiyatli o'tdi" degan xabarni Click sizning serveringizga
   yuboradi (`webhook_server.py` shu uchun yozilgan) — bu server ishlashi uchun
   sizda **ochiq domen + SSL** bo'lgan VPS/hosting kerak (masalan DigitalOcean,
   Beget, yoki mahalliy hosting). O'z shaxsiy kompyuteringizda bu qism ishlamaydi.
4. Click panelida webhook manzilini `https://sizningdomen.uz/click/webhook`
   deb ko'rsatasiz
5. `webhook_server.py` ni alohida process sifatida ishga tushirasiz:
   ```bash
   ./venv/bin/python webhook_server.py
   ```
   (production'da buni gunicorn/nginx bilan ishga tushirish tavsiya etiladi)

## AI sotuvchini yoqish (Claude bilan avtomatik sotuv)

Bot endi mijoz bilan **avtomatik gaplashib, sotib beradigan** rejimga ega.
Yoqish uchun:

1. https://console.anthropic.com saytida hisob oching va API kalit yarating
   (Settings → API Keys → Create Key)
2. Railway'dagi "Variables" bo'limiga 2 ta o'zgaruvchi qo'shing:
   ```
   ANTHROPIC_API_KEY=sk-ant-...sizning-kalitingiz...
   AI_SELLER_ENABLED=true
   ```
3. Deploy tugagach, botga `/start` yozib tekshiring — endi savol-anketa o'rniga
   AI siz bilan tabiiy tarzda gaplasha boshlaydi.

**AI qanday ishlaydi:**
- `pricing.py` faylidagi narxlar jadvali va shartnoma shartlari asosida javob beradi
- Mijoz ism+telefon bergach, avtomatik lidni saqlab, sotuvchiga biriktiradi
- Mijoz to'lovga rozi bo'lsa, to'lov havolasini o'zi tayyorlaydi
- G'azablangan/murakkab holatlarda avtomatik ravishda nazorat guruhiga signal beradi

**Narxni yoki shartlarni o'zgartirish:** `pricing.py` (raqamlar) va `ai_seller.py`
ichidagi `SYSTEM_PROMPT` (qoidalar, ohang, jarayon tavsifi) fayllarini tahrirlang.

**AI'ni o'chirib, oddiy anketaga qaytish:** Railway'da `AI_SELLER_ENABLED=false`
qiling — bot avtomatik eski (davlat/maqsad/telefon so'raydigan) rejimga qaytadi.

## Keyingi bosqichlar (kengaytirish uchun g'oyalar)

- Target reklama linkini `https://t.me/BOTUSERNAME?start=fb_ads` ko'rinishida
  qilib, qaysi reklama kanalidan qancha lid kelayotganini kuzatish mumkin
- Har bir sotuvchi uchun oylik statistika (nechta lid, nechtasi to'lagan) —
  bazada barcha ma'lumot bor, faqat `/stat` buyrug'ini qo'shish kifoya
- Mijozga to'lovdan keyin avtomatik "hujjatlar ro'yxati" PDF yuborish
- 24 soat javobsiz mijozlarga avtomatik eslatma yuborish (hozir faqat sotuvchi-tomon eslatma bor)

## Fayllar tuzilishi

```
vizabot/
├── bot.py              # Asosiy bot (shu faylni ishga tushirasiz)
├── config.py            # Sozlamalar (token, guruh ID va h.k.)
├── database.py           # SQLite baza funksiyalari
├── click_pay.py           # Click to'lov havolasi yaratish
├── webhook_server.py       # Click'dan to'lov tasdiqni qabul qilish
├── requirements.txt
└── vizabot.db            # Avtomatik yaratiladigan baza fayli
```
