# YETKAZ — Filiallar boshqaruvi

Telegram bot (@yetkazfilial_bot) va dashboard: yangi filial ochish arizalarini qabul qiladi,
mavjud filiallar bilan solishtiradi (masofa, aholi zichligi), filiallar tarmog'ini boshqaradi.

## Tarkibi
- `bot.py` — Telegram bot (aiogram 3) va dashboardni ishga tushiradi
- `dashboard.py`, `dashboard/index.html` — veb-dashboard (http://localhost:8800)
- `branches.py` — arizani filiallar bilan solishtirish
- `analytics.py` — tarmoq tahlili, bo'sh hududlar, zonalar
- `branch_store.py` — filiallarni qo'shish/tahrirlash (zaxira nusxa + tarix)
- `config.py` — sozlamalar; maxfiy qiymatlar `config_local.py` da
- `offer.txt` — tijoriy taklif matni
- `data/aholi_zichligi.npy` — aholi zichligi (Kontur 2023 + WorldPop 2026, stat.uz 2026 jami bo'yicha)
- `data/population.js` — viloyatlar aholisi (stat.uz, 2026-01-01)

## O'rnatish
1. Python 3.12 va kutubxonalar: `pip install -r requirements.txt`
2. `config_local.example.py` ni `config_local.py` nomi bilan nusxalab, token, adminlar va parolni yozing
3. `data/filiallar.json` faylini joylashtiring (GitHub'da yo'q — shaxsiy ma'lumot)
4. `python bot.py`

GitHub'ga yuklanmaydi: arizalar bazasi (`leads.db`), pasport rasmlari (`rasmlar/`), filiallar ro'yxati,
jurnallar va maxfiy sozlamalar — qarang `.gitignore`.
