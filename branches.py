"""Yangi lid manzilini mavjud filiallar bilan solishtirib, xulosa chiqaradi."""
import difflib
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

import config

MAQUL = "✅ Ma'qul"
KORIB = "⚠️ Ko'rib chiqish"
MAQUL_EMAS = "❌ Ma'qul emas"

# Filiallar faylidagi "hudud" -> bot viloyati
HUDUD_MAP = {"Qo'qon": "Farg'ona", "Qoraqalpog'iston Respublikasi": "Qoraqalpog'iston"}

_cache = {"mtime": None, "items": []}


def _norm(text):
    text = text.lower()
    for ch in "'‘’ʻʼ`":
        text = text.replace(ch, "")
    text = re.sub(r"\bsh\.?\s*rashidov", "sharof rashidov", text)
    return text.replace("shaxar", "shahar")


def _key(name):
    """'Kattaqo'rg'on tumani 2' -> 'kattaqorgon'"""
    t = re.sub(r"\d+", " ", _norm(name))
    t = re.sub(r"\b(shahar|sh|tumani|tuman)\b\.?", " ", t)
    return re.sub(r"[^a-z]", "", t)


def _kind(name):
    t = _norm(name)
    if re.search(r"\bsh\.|\bshahar\b", t):
        return "shahar"
    if re.search(r"\btuman", t):
        return "tuman"
    return None


def load_branches():
    """Filiallar faylini o'qiydi (fayl o'zgarsa avtomatik qayta o'qiladi)."""
    path = Path(config.FILIALLAR_JSON)
    mtime = path.stat().st_mtime
    if _cache["mtime"] != mtime:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for b in data:
            b["viloyat"] = HUDUD_MAP.get(b["hudud"], b["hudud"])
            if not isinstance(b.get("address"), str):  # bo'sh katak ba'zan [[]] bo'lib keladi
                b["address"] = ""
            b["_key"], b["_kind"] = _key(b["nomi"]), _kind(b["nomi"])
        _cache.update(mtime=mtime, items=data)
    return _cache["items"]


def active_branches():
    return [b for b in load_branches() if b.get("status") == "Aktiv" and b.get("lat")]


def haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def branches_in_tuman(viloyat, tuman):
    tk, tkind = _key(tuman), _kind(tuman)
    out = []
    for b in active_branches():
        if tkind and b["_kind"] and tkind != b["_kind"]:
            continue
        if abs(len(tk) - len(b["_key"])) > 2:  # Chirchiq ≠ O'rtachirchiq
            continue
        ratio = difflib.SequenceMatcher(None, tk, b["_key"]).ratio()
        # Bazada ba'zi filiallar boshqa viloyatga yozilgan (masalan, Ellikqal'a — Xorazm),
        # shuning uchun nomi deyarli bir xil bo'lsa viloyatga qaramaymiz.
        if (b["viloyat"] == viloyat and ratio >= 0.82) or ratio >= 0.95:
            out.append(b)
    return out

# ===================== GOOGLE MAPS HAVOLASIDAN KOORDINATA =====================

_COORD_PATTERNS = [
    r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
    r"@(-?\d+\.\d+),(-?\d+\.\d+)",
    r"[?&](?:q|ll|query|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)",
    r"/place/(-?\d+\.\d+),\s*(-?\d+\.\d+)",
    r"/search/(-?\d+\.\d+),\+?\s*(-?\d+\.\d+)",
]


def coords_from_text(text):
    text = urllib.parse.unquote(text)
    for p in _COORD_PATTERNS:
        m = re.search(p, text)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if 37 <= lat <= 46 and 55 <= lon <= 74:  # O'zbekiston atrofi
                return lat, lon
    return None


def resolve_maps_link(url):
    """Qisqa havolani (maps.app.goo.gl) ochib, koordinatani topadi. Topilmasa None."""
    found = coords_from_text(url)
    if found:
        return found
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            final = r.geturl()
            found = coords_from_text(final)
            if found:
                return found
            body = r.read(400_000).decode("utf-8", "ignore")
        return coords_from_text(body)
    except Exception:
        return None

# ===================== AHOLI ZICHLIGI (WorldPop 2020, 1 km) =====================

_DATA = Path(__file__).parent / "data"
_raster = {}


def _load_raster():
    if not _raster:
        import numpy as np
        a = np.load(_DATA / "aholi_zichligi.npy")
        a[a < 0] = 0
        _raster.update(a=a, **json.loads((_DATA / "aholi_zichligi.json").read_text()))
    return _raster


def density(lat, lon):
    """Nuqta va atrofidagi ~3x3 km dagi eng yuqori aholi zichligi (kishi/km²). Topilmasa None."""
    r = _load_raster()
    a = r["a"]
    row = int((r["lat0"] - lat) / r["dy"])
    col = int((lon - r["lon0"]) / r["dx"])
    if not (0 <= row < a.shape[0] and 0 <= col < a.shape[1]):
        return None
    v = float(a[max(row - 1, 0):row + 2, max(col - 1, 0):col + 2].max())
    return round(v) if v > 0 else None


def density_level(d):
    if d is None:
        return "aniqlanmadi"
    if d >= config.GAVJUM_ZICHLIK:
        return "gavjum"
    if d >= config.ORTA_ZICHLIK:
        return "o'rtacha"
    return "kam"


# ===================== XULOSA =====================

def evaluate(lead):
    """lead: viloyat, tuman, lat/lon yoki maps. Natija — dict (bazaga yoziladi)."""
    res = {"xulosa": KORIB, "sabab": "", "eng_yaqin": "", "masofa_km": None,
           "tumanda_filial": None, "zichlik": "", "lat": lead.get("lat"), "lon": lead.get("lon")}
    viloyat, tuman = lead.get("viloyat"), lead.get("tuman") or ""
    in_tuman = branches_in_tuman(viloyat, tuman)
    res["tumanda_filial"] = len(in_tuman)

    lat, lon = lead.get("lat"), lead.get("lon")
    if not lat and lead.get("maps"):
        found = resolve_maps_link(lead["maps"])
        if found:
            lat, lon = found
            res["lat"], res["lon"] = str(lat), str(lon)
    if not lat:
        res["sabab"] = "Lokatsiya aniqlanmadi — qo'lda tekshiring"
        return res
    lat, lon = float(lat), float(lon)

    near = sorted(((haversine(lat, lon, b["lat"], b["lng"]), b) for b in active_branches()),
                  key=lambda x: x[0])[:3]
    if near:
        km, b = near[0]
        res["masofa_km"] = round(km, 2)
        res["eng_yaqin"] = f"{b['nomi']} — {b.get('address') or ''}".strip(" —")
        res["yaqinlar"] = [f"{b['nomi']} ({k:.1f} km)" for k, b in near]

    is_city = tuman.endswith("sh.") or viloyat == "Toshkent shahri"
    limit = config.SHAHAR_RADIUS_KM if is_city else config.TUMAN_RADIUS_KM
    d = density(lat, lon)
    lvl = density_level(d)
    res["zichlik"] = lvl + (f" (~{d} kishi/km²)" if d else "")

    tuman_km = min((haversine(lat, lon, b["lat"], b["lng"]) for b in in_tuman), default=None)
    if tuman_km is not None and tuman_km > config.MOS_EMAS_KM:
        res["sabab"] = (f"Lokatsiya tanlangan tumanga mos emas: {tuman} filiallaridan {tuman_km:.0f} km uzoqda. "
                        f"Odam lokatsiyani boshqa joydan yuborgan bo'lishi mumkin — qo'lda tekshiring")
    elif near and near[0][0] < limit:
        res["xulosa"] = MAQUL_EMAS
        res["sabab"] = f"{limit:g} km ichida filial bor: {near[0][1]['nomi']} ({near[0][0]:.2f} km)"
    elif config.QATIY_TUMAN and in_tuman:
        res["sabab"] = (f"{limit:g} km ichida filial yo'q, lekin tumanda {len(in_tuman)} ta filial bor: "
                        + ", ".join(b["nomi"] for b in in_tuman[:5]))
    elif lvl == "gavjum":
        res["xulosa"] = MAQUL
        res["sabab"] = (f"{limit:g} km ichida filial yo'q, aholi gavjum"
                        + ("; tumanda filial yo'q" if not in_tuman else f"; tumanda {len(in_tuman)} ta filial bor"))
    elif lvl == "kam":
        res["xulosa"] = MAQUL_EMAS
        res["sabab"] = f"Aholi kam: ~{d} kishi/km² (gavjum hisoblanishi uchun {config.GAVJUM_ZICHLIK}+ kerak)"
    else:
        res["sabab"] = f"Yaqinida filial yo'q, aholi zichligi {lvl} — qo'lda tekshiring"
    return res
