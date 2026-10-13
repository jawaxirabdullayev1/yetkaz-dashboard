# YETKAZ — Filiallar boshqaruvi: texnik hujjat (IT bo'limi uchun)

Holat: 2026-10-13. Repozitoriy: `github.com/jawaxirabdullayev1/yetkaz-dashboard` (private).

## 1. Tizim nima qiladi

| Qism | Vazifasi |
|---|---|
| Telegram bot **@yetkazfilial_bot** | Yangi filial ochmoqchi bo'lganlardan anketa oladi (ism, lokatsiya, viloyat/tuman, telefon, savollar), keyingi bosqichlarda taklif yuboradi va hujjatlarni (pasport, rasmlar, bank) yig'adi |
| Avtomatik baholash | Har bir arizani mavjud aktiv filiallar bilan solishtiradi: eng yaqin filialgacha masofa + aholi zichligi → ✅ Ma'qul / ⚠️ Ko'rib chiqish / ❌ Ma'qul emas |
| Veb-dashboard (port 8800) | Filiallar tarmog'ini boshqarish (qo'shish/tahrirlash/yopish), xarita, arizalar (CRM: status, izoh, aloqa sanasi, bosqichlar), bo'sh hududlar, tahlil |

## 2. Arxitektura

- **Bitta Python jarayoni** (`bot.py`): aiogram 3 (Telegram long polling) + aiohttp veb-server (dashboard). Ikkalasi bitta asyncio loopda.
- **Ma'lumotlar bazasi:** SQLite — `leads.db`.
- **Front-end:** bitta statik sahifa `dashboard/index.html` (vanilla JS, Leaflet, Leaflet.markercluster, Chart.js — CDN orqali).
- Tashqi server/SQL server/Docker yo'q.

```
Telegram API  <──polling──  bot.py ──── leads.db (SQLite)
                              │  ├──── rasmlar/  (yuklangan rasmlar)
                              │  └──── data/     (filiallar, aholi xaritasi)
Brauzer  ──HTTP :8800──>  dashboard.py (aiohttp) ── analytics.py / branches.py / branch_store.py
```

### Fayllar

| Fayl | Mazmuni |
|---|---|
| `bot.py` | Bot: anketa (FSM), baholash, admin buyruqlari, 2–3-bosqichlar, Excel eksport, `main()` (dashboardni ham ishga tushiradi) |
| `dashboard.py` | aiohttp ilova, login (cookie), REST API |
| `dashboard/index.html` | Dashboard UI |
| `branches.py` | Filiallarni o'qish, masofa (haversine), aholi zichligi, ariza xulosasi (`evaluate`) |
| `analytics.py` | Qamrov, bo'sh hududlar (gaps), olti burchakli zonalar, hududlar kesimi, ma'lumot sifati |
| `branch_store.py` | Filiallarni CRUD (fayl qulfi, zaxira nusxa, o'zgarishlar tarixi) |
| `regions.py` | Viloyat → tumanlar ro'yxati (bot tugmalari uchun) |
| `config.py` | Barcha sozlamalar (maxfiy bo'lmaganlari) |
| `config_local.py` | **Maxfiy:** `BOT_TOKEN`, `ADMIN_IDS`, `DASHBOARD_PASSWORD` (gitda yo'q; namuna — `config_local.example.py`) |
| `offer.txt` | Tijoriy taklif matni (2-bosqich) |
| `run.bat` | Qo'lda ishga tushirish |

## 3. Hozirgi o'rnatilish (ishlab turgan kompyuter)

- Papka: `D:\Yetkaz dashboard\` (hamma narsa shu yerda).
- Python: ichki nusxa `D:\Yetkaz dashboard\python\` (3.12.10, kutubxonalar o'rnatilgan). Gitda yo'q.
- Avtomatik ishga tushirish: Windows Task Scheduler, vazifa **"YETKAZ lid bot va dashboard"**:
  - trigger: foydalanuvchi tizimga kirganda; action: `python\pythonw.exe bot.py`, working dir — loyiha papkasi;
  - xato bo'lsa har 1 daqiqada qayta ishga tushadi; vaqt cheklovi yo'q.
- Bitta nusxa himoyasi: 8800-port band bo'lsa ikkinchi jarayon darhol chiqib ketadi.
- Jurnal: `logs\bot.log` (2 MB × 3 aylanma).

Boshqarish (PowerShell):
```powershell
Stop-ScheduledTask  -TaskName "YETKAZ lid bot va dashboard"
Start-ScheduledTask -TaskName "YETKAZ lid bot va dashboard"
Get-Content "D:\Yetkaz dashboard\logs\bot.log" -Tail 50
```
Kod/sozlama o'zgarsa — vazifani to'xtatib qayta ishga tushirish kerak (`Stop-ScheduledTask` dan keyin jarayon qolsa, `pythonw.exe` ni tugating).

## 4. Yangi joyga o'rnatish

1. Python 3.12+ → `pip install -r requirements.txt` (aiogram, aiohttp, numpy, openpyxl, pillow, tifffile).
2. `config_local.example.py` → `config_local.py`, qiymatlarni kiriting (token BotFather'dan; admin ID — botga `/myid`).
3. `data/filiallar.json` ni joylashtiring (gitda yo'q). Mavjud arizalarni ko'chirish kerak bo'lsa — `leads.db` va `rasmlar/` ni ham.
4. `python bot.py`. Dashboard: `http://<host>:8800`.
5. Bot faqat **bitta joyda** ishlashi shart (Telegram polling: ikki nusxa bo'lsa `Conflict` xatosi).
6. Linux serverda: systemd service (`Restart=always`), oldiga HTTPS reverse proxy (nginx/Caddy) tavsiya etiladi.

Tarmoq: chiquvchi — `api.telegram.org:443`; kiruvchi — 8800 (faqat ichki tarmoq yoki proxy orqali).

## 5. Sozlamalar (`config.py`)

| Kalit | Ma'nosi | Hozir |
|---|---|---|
| `QUESTIONS` | 1-bosqich savollari (Google Form asosida), ballari | — |
| `FOLLOWUP_QUESTIONS` | 3-bosqich: pasport, qo'shimcha telefon, 2 ta rasm, bank | — |
| `HOT_SCORE` / `WARM_SCORE` | Issiq/Iliq/Sovuq chegarasi | 11 / 6 |
| `SHAHAR_RADIUS_KM` / `TUMAN_RADIUS_KM` | Ariza xulosasi: shu masofada filial bo'lsa — ❌ | 1 / 3 km |
| `GAVJUM_ZICHLIK` / `ORTA_ZICHLIK` | Aholi zichligi chegaralari, kishi/km² | 2600 / 1200 |
| `ZONA_SHAHAR_KM` / `ZONA_TUMAN_KM` | Xaritadagi zonalar (faqat ko'rinish) | 2 / 5 km |
| `ZONA_TAVSIYA_ZICHLIK` | "Tavsiya etilgan zona" chegarasi | 4000 |
| `MOS_EMAS_KM` | Lokatsiya tanlangan tumandan shuncha uzoq bo'lsa — ⚠️ | 40 km |
| `DASHBOARD_PORT` | Dashboard porti | 8800 |
| `APPROVED_TEXT` | Hujjatlar tasdiqlanganda odamga boradigan xabar | — |

## 6. Ma'lumotlar

### `leads.db` (SQLite)
- `leads` — bitta Telegram foydalanuvchi = bitta qator (`user_id` PK). Asosiy ustunlar: `name, phone, username, viloyat, tuman, lat, lon, maps, source, answers (JSON), score, level, holat (✅ To'liq / ⏳ Tugallanmagan), xulosa, sabab, eng_yaqin, masofa_km, tumanda_filial, zichlik, yaqinlar (JSON), bosqich, answers2 (JSON — 3-bosqich javoblari, bank ma'lumotlari shu yerda), photos (JSON — Telegram file_id), status, izoh, aloqa_sana, status_vaqt, filial_id, korildi, created, updated`.
  `region` — eski ustun, ishlatilmaydi.
- `settings` — kalit/qiymat (masalan, `group` — xabarlar yuboriladigan Telegram guruh ID).
- `fsm` — botdagi anketa holati (qayta ishga tushganda anketa davom etadi).

### Fayllar
| Yo'l | Mazmuni | Gitda |
|---|---|---|
| `rasmlar/<user_id>/<key>.jpg` | Pasport va joy rasmlari | yo'q |
| `data/filiallar.json` | Filiallar ro'yxati (365 ta) — dashboard yozadi | yo'q |
| `data/backups/` | Har bir filial o'zgarishidan oldingi nusxa (oxirgi 100 ta) | yo'q |
| `data/filial_tarix.jsonl` | Filiallar o'zgarishlari tarixi | yo'q |
| `data/aholi_zichligi.npy` + `.json` | Aholi zichligi rastri (kishi/km², ~1 km) | bor |
| `data/population.js` | Viloyatlar aholisi (stat.uz, 2026-01-01) | bor |
| `data/gap_names.json` | Bo'sh hudud nomlari keshi (Nominatim) | bor |

### Aholi ma'lumoti manbasi
Aralash rastr: Toshkent shahri (markazdan 16 km) — WorldPop R2025A 2026 (1 km, constrained, UN-adj.); qolgan hudud — Kontur Population 2023-11 (400 m H3; Toshkent janubidagi xato kataklar 4000 kishi/katak bilan cheklanib, qayta taqsimlangan). Jami stat.uz 2026-01-01 (38 236 704) ga moslangan. **Cheklov:** viloyat markazlari ~1,5–2 baravar kam ko'rinadi.

## 7. Bot jarayoni

1. **Ariza:** `/start` (`?start=<manba>` — e'lon havolasi) → anketa → baholash → adminlarga xabar ("📨 Davom ettirish" tugmasi bilan).
2. **Taklif:** admin tasdiqlaydi → `offer.txt` yuboriladi → odam "Roziman" / savol / rad.
3. **Hujjatlar:** 5 savol (rasm savollari majburiy, karta raqami va telefon tekshiriladi) → adminga xabar va rasmlar → "✅ Tasdiqlash" / "↩️ Qayta so'rash".
4. **Tasdiqlandi** → `APPROVED_TEXT` yuboriladi. Ariza dashboarddan filialga aylantirilishi mumkin.

Bosqichni dashboarddan ham o'tkazish mumkin (`POST /api/stage/{uid}`).

Admin buyruqlari (faqat `ADMIN_IDS`): `/help /maqul /export /rasmlar /stats /leads /link /recheck /filiallar /setgroup /unsetgroup`. Hammaga: `/start`, `/myid`.

## 8. Dashboard API (hammasi login cookie talab qiladi)

| Metod | Yo'l | Vazifasi |
|---|---|---|
| GET/POST | `/login` | Kirish (parol → `lid_auth` cookie, HMAC, 30 kun) |
| GET | `/api/leads` | Arizalar + statuslar, savollar ro'yxati |
| GET | `/api/network` | Filiallar, tahlil, bo'sh hududlar (filiallar.json o'zgarganda qayta hisoblanadi) |
| GET | `/api/zones?s&w&n&e` | Xaritadagi olti burchakli zonalar |
| POST | `/api/evaluate` | Nuqta / Google Maps havolasini baholash |
| POST/PUT/DELETE | `/api/branches[/{id}]` | Filial qo'shish / tahrirlash / o'chirish |
| GET | `/api/tarix[?id=]` | Filiallar o'zgarishlari tarixi |
| POST | `/api/lead/{uid}` | Status, izoh, aloqa sanasi, "ko'rildi" |
| POST | `/api/stage/{uid}` | Bosqich: offer / docs / remind / approve / reject |
| POST | `/api/offer/{uid}`, `/api/korildi_hammasi` | Taklif yuborish; hammasini ko'rildi deb belgilash |
| GET | `/photo/{uid}/{key}`, `/export.xlsx` | Rasm; Excel eksport |

## 9. Tashqi xizmatlar

| Xizmat | Nima uchun | Shaxsiy ma'lumot ketadimi |
|---|---|---|
| Telegram Bot API | Bot ishlashi, rasmlarni yuklab olish | Ha — Telegram'ning o'zi orqali |
| Esri World Street Map (zaxira: OSM) | Xarita fonida | Yo'q |
| unpkg / jsdelivr / Google Fonts | JS kutubxonalar, shriftlar | Yo'q |
| Nominatim (OSM) | Bo'sh hudud nomlari (bir marta, keshlanadi) | Yo'q (faqat hudud koordinatasi) |
| Google Maps | Qisqa havoladan koordinata olish | Faqat havolaning o'zi |

## 10. Xavfsizlik — e'tibor bering

- `leads.db` va `rasmlar/` da **shaxsiy ma'lumotlar** bor: pasport rasmlari, telefon, bank karta ma'lumotlari. Disk shifrlanishi, kirish huquqlari, zaxira nusxa siyosati kerak.
- Dashboard **HTTP** (TLS yo'q), bitta umumiy parol, foydalanuvchi akkauntlari va kirish jurnali yo'q. Tarmoqdan ochish uchun HTTPS proxy va alohida akkauntlar tavsiya etiladi.
- `config_local.py` dagi token oshkor bo'lsa — BotFather'da `/revoke` qilib yangisini oling.
- Arizalar bazasining avtomatik zaxirasi **yo'q** (faqat filiallar fayli zaxiralanadi). Kunlik zaxira sozlash tavsiya etiladi.
- Kompyuter o'chiq yoki foydalanuvchi tizimdan chiqqan bo'lsa bot ishlamaydi (Telegram xabarlarni 24 soatgacha saqlaydi). Doimiy ishlashi uchun server kerak.

## 11. Ma'lum cheklovlar va keyingi ishlar

- Avtomatik testlar yo'q; o'zgarishlar qo'lda tekshirilgan.
- Aholi ma'lumoti viloyat markazlarida past (6-bo'lim).
- Filiallarni tuman bo'yicha bog'lash nom o'xshashligiga asoslangan (`branches.branches_in_tuman`).
- Eski filiallar xaritasi (`web_map`, port 8790) o'z `filiallar.json` nusxasidan foydalanadi — bu tizim bilan sinxron emas.
- `filiallar.json` dagi `masul` maydoni xato qo'shilgan, dashboardda ishlatilmaydi.
