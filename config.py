# ===================== SOZLAMALAR =====================
# Maxfiy qiymatlar (bot tokeni, adminlar, dashboard paroli) — config_local.py da (GitHub'ga yuklanmaydi).
# Yangi o'rnatishda: config_local.example.py -> config_local.py nusxalab to'ldiring.
try:
    from config_local import BOT_TOKEN, ADMIN_IDS, DASHBOARD_PASSWORD
except ImportError:
    BOT_TOKEN, ADMIN_IDS, DASHBOARD_PASSWORD = "", [], ""

# Botga kirganda chiqadigan salomlashuv
GREETING = ("Assalomu alaykum! 👋\n"
            "Siz ham o'z hududingizdan <b>iPost</b> filial ochmoqchimisiz? "
            "Unda quyidagi savollarga javob bering.")

# Anketa tugaganda chiqadigan xabar
FINISH_TEXT = ("Rahmat! 🎉 Arizangiz qabul qilindi. "
               "Mutaxassislarimiz tez orada siz bilan bog'lanishadi.")

# Viloyat va tumanlar ro'yxati: regions.py

# ===================== SO'ROVNOMA SAVOLLARI =====================
# Ism, lokatsiya, viloyat, tuman va telefon bot o'zi so'raydi. Qolganlari shu yerda.
# type "text"   — erkin javob. points: javob "yo'q" bo'lmasa beriladigan ball.
# type "choice" — tugmalar. options: [(javob, ball), ...]
QUESTIONS = [
    {"key": "manzil", "type": "text", "points": 0,
     "text": "Filial ochiladigan manzilni to'liq kiriting\n"
             "<i>(MFY, ko'cha va mo'ljalni to'liq yozing)</i>"},
    {"key": "tg_guruh", "type": "text", "points": 2,
     "text": "Telegram savdo kanalingiz yoki guruhingiz bormi? Bo'lsa linkini yuboring"},
    {"key": "faoliyat", "type": "choice",
     "text": "Hozirgi kundagi asosiy ish faoliyatingiz nima?",
     "options": [("Uy bekasi", 2), ("Davlat ishida ishlayman", 1), ("O'z biznesim bor", 3),
                 ("Ishsiz", 0)]},
    {"key": "afzallik", "type": "choice",
     "text": "Biz bilan ishlashingizdagi eng muhim afzallik qaysi?",
     "options": [("Barqaror daromad", 1),
                 ("Ishonchli brend bilan uzoq muddatli hamkorlik", 2),
                 ("Uyimizgacha yetkazib berilishi", 1),
                 ("Boshqa kargoga qaraganda arzon va tezligi", 1)]},
    {"key": "joy", "type": "choice",
     "text": "O'z uyingizdan ishlamoqchimisiz yoki noturar joymi?",
     "options": [("O'z uyimda", 1), ("Ijaraga", 3), ("Aniq emas", 0)]},
    {"key": "xitoy", "type": "choice",
     "text": "Xitoy onlayn savdo platformalari bilan ishlash tajribangiz bormi va qaysi platformalarda?",
     "options": [("Pinduoduo", 3), ("Taobao", 3), ("1688", 3), ("WeChat", 3), ("Alipay", 3),
                 ("Tajribam yo'q", 0)]},
    {"key": "strategiya", "type": "text", "points": 2,
     "text": "Filial ochilgandan so'ng rivojlantirish strategiyangiz bormi?"},
]

# Ball chegaralari (maksimal 15)
HOT_SCORE = 11   # >= bo'lsa Issiq
WARM_SCORE = 6   # >= bo'lsa Iliq, aks holda Sovuq

DB_PATH = "leads.db"

# ===================== DASHBOARD =====================
# Bot ishlayotganda brauzerda: http://localhost:8800  (login: admin, parol: pastda)
# Bir xil Wi-Fi'dagi boshqa kompyuterdan: http://<shu kompyuter IP manzili>:8800
DASHBOARD_PORT = 8800
# DASHBOARD_PASSWORD — config_local.py da

# ===================== IKKINCHI BOSQICH (admin "Davom ettirish" bosgandan keyin) =====================
# Taklif matni: offer.txt (oddiy matn, istalgancha o'zgartiring)
OFFER_FILE = "offer.txt"

# "Roziman" deganlardan so'raladigan qo'shimcha savollar.
# type: "text" — yozma javob, "choice" — tugmalar, "photo" — rasm (yuborilmaguncha keyingisiga o'tilmaydi)
# require: "phone" — telefon raqam bo'lishi shart, "card" — 16 xonali karta raqami bo'lishi shart
FOLLOWUP_QUESTIONS = [
    {"key": "pasport", "type": "photo", "name": "Pasport",
     "text": "Pasportingiz rasmini yuboring 📷\n<i>Rasm tiniq bo'lishi, barcha yozuvlar o'qiladigan bo'lishi kerak.</i>"},
    {"key": "qoshimcha_tel", "type": "text", "require": "phone",
     "text": "Qo'shimcha telefon raqam yuboring (oila a'zosi yoki ikkinchi raqamingiz):\n"
             "<i>Masalan: +998 90 123 45 67</i>"},
    {"key": "rasm_kocha", "type": "photo", "name": "Uy - kocha tomondan",
     "text": "Uyning (filial joyining) ko'cha tomondan rasmini yuboring 📷"},
    {"key": "rasm_xona", "type": "photo", "name": "Yuk saqlash xonasi",
     "text": "Yuk saqlash uchun xonaning rasmini yuboring 📷"},
    {"key": "bank", "type": "text", "require": "card",
     "text": "Bank ma'lumotlaringizni quyidagi shablon bo'yicha yozib yuboring 👇\n\n"
             "<code>Bank nomi: ...\n"
             "Karta raqam: 8600 XXXX XXXX XXXX\n"
             "Karta egasi: Familiya Ism\n"
             "MFO: .....\n"
             "INN: .........\n"
             "Tranzit x/r: ....................</code>"},
]

FOLLOWUP_FINISH_TEXT = ("Rahmat! 🤝 Ma'lumotlaringiz qabul qilindi. "
                        "Rasmiylashtirish bo'yicha mutaxassisimiz siz bilan bog'lanadi.")

# Admin hujjatlarni tasdiqlaganda odamga boradigan xabar
APPROVED_TEXT = ("Tabriklaymiz! 🎉 Hujjatlaringiz tasdiqlandi.\n"
                 "Tez orada mutaxassisimiz shartnoma imzolash va filialni ochish bo'yicha siz bilan bog'lanadi.")

# ===================== MAVJUD FILIALLAR BILAN SOLISHTIRISH =====================
# Filiallar ro'yxati — dastur papkasining o'zida (data\filiallar.json). Dashboarddan boshqariladi,
# har bir o'zgarishdan oldin nusxasi data\backups\ ga tushadi.
import os as _os
FILIALLAR_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "filiallar.json")

# Eng yaqin aktiv filial shu masofadan yaqin bo'lsa — "Ma'qul emas"
SHAHAR_RADIUS_KM = 1   # shaharlar (tuman nomi "sh." bilan tugasa) va Toshkent shahri
TUMAN_RADIUS_KM = 3    # tumanlar

# Xaritadagi zonalar (olti burchakli kataklar) uchun alohida qoida — botdagi baholashga ta'sir qilmaydi
ZONA_SHAHAR_KM = 2     # aholi gavjum joyda: filialdan shu masofagacha — "ochib bo'lmaydi"
ZONA_TUMAN_KM = 5      # aholi siyrakroq joyda
ZONA_KATAK_KM = 1.0    # katak radiusi, km
ZONA_TAVSIYA_ZICHLIK = 4000   # "Tavsiya etilgan zona" uchun aholi, kishi/km² (aktiv filiallarning o'rtachasi ~3570)
ZONA_ORTA_KORSATISH = False   # aholi o'rtacha (1200–2600 kishi/km²) joylarni ham ko'rsatish

# Lokatsiya tanlangan tumandagi filiallardan shuncha km uzoq bo'lsa — "mos emas" deb ko'rib chiqishga
MOS_EMAS_KM = 40

# True bo'lsa: tumanda bitta bo'lsa ham aktiv filial bor bo'lsa "Ma'qul" berilmaydi
QATIY_TUMAN = False

# Aholi zichligi, kishi/km² (data/aholi_zichligi.npy — Kontur 2023, stat.uz 2026-01-01 jami bo'yicha moslangan).
# 2600 — aktiv filiallarning 75% shundan zichroq joyda; 1200 dan kam — filiallarning 95% idan ham siyrak.
GAVJUM_ZICHLIK = 2600
ORTA_ZICHLIK = 1200
