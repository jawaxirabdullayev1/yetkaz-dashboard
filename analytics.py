"""Filiallar tarmog'i tahlili: qamrov, bo'sh hududlar (yangi filial uchun tavsiya joylar), viloyatlar kesimi."""
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import branches
import config

DATA = Path(__file__).parent / "data"
_cache = {"key": None, "result": None}

COVER_KM = 3      # aholi "qamrab olingan" hisoblanadigan masofa
GAP_MIN_KM = 5    # bo'sh hudud — eng yaqin aktiv filialdan kamida shuncha uzoq
GAP_SPACING_KM = 8
GAP_COUNT = 40
TASHKENT_CENTER, TASHKENT_RADIUS_KM = (41.305, 69.27), 14


def _population_table():
    """Viloyatlar aholisi (ming) — data\\population.js."""
    p = Path(config.FILIALLAR_JSON).parent / "population.js"
    try:
        txt = p.read_text(encoding="utf-8")
        return {k: int(v) for k, v in re.findall(r'"([^"]+)"\s*:\s*(\d+)', txt)}
    except Exception:
        return {}


def _raster():
    r = branches._load_raster()
    return r["a"], r


def _cell(r, lat, lon):
    return int((r["lat0"] - lat) / r["dy"]), int((lon - r["lon0"]) / r["dx"])


def _cell_center(r, row, col):
    return r["lat0"] - (row + 0.5) * r["dy"], r["lon0"] + (col + 0.5) * r["dx"]


def _box_sum(arr, ry, rx):
    """Har bir katak atrofidagi (2ry+1)x(2rx+1) oyna yig'indisi."""
    c = np.pad(arr, ((ry + 1, ry), (rx + 1, rx))).cumsum(0).cumsum(1)
    h, w = arr.shape
    return (c[2 * ry + 1:2 * ry + 1 + h, 2 * rx + 1:2 * rx + 1 + w] - c[:h, 2 * rx + 1:2 * rx + 1 + w]
            - c[2 * ry + 1:2 * ry + 1 + h, :w] + c[:h, :w])


def _disk_mask(shape, cells, rad_km, r):
    """Berilgan nuqtalardan rad_km ichidagi kataklar maskasi."""
    mask = np.zeros(shape, bool)
    km_y = r["dy"] * 111.32
    for (row, col, lat) in cells:
        km_x = r["dx"] * 111.32 * math.cos(math.radians(lat))
        ny, nx = int(rad_km / km_y) + 1, int(rad_km / km_x) + 1
        y0, y1 = max(row - ny, 0), min(row + ny + 1, shape[0])
        x0, x1 = max(col - nx, 0), min(col + nx + 1, shape[1])
        if y0 >= y1 or x0 >= x1:
            continue
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask[y0:y1, x0:x1] |= ((yy - row) * km_y) ** 2 + ((xx - col) * km_x) ** 2 <= rad_km ** 2
    return mask


# ===================== ZONALAR (olti burchakli kataklar) =====================
# Har bir katak: "band" — yaqinida aktiv filial bor (ochib bo'lmaydi), "tavsiya" — filial yo'q va aholi gavjum,
# "orta" — filial yo'q, aholi o'rtacha. Aholi kam kataklar qaytarilmaydi.
HEX_R = config.ZONA_KATAK_KM                  # katak radiusi, km
KX = 111.32 * math.cos(math.radians(41.0))    # 1° uzunlik ≈ km (O'zbekiston uchun)
KY = 110.57                                   # 1° kenglik ≈ km
MAX_ZONE_AREA_KM2 = 9000                      # bundan katta oynada hisoblanmaydi (xaritani yaqinlashtirish kerak)


def zones(s, w, n, e):
    if (e - w) * KX * (n - s) * KY > MAX_ZONE_AREA_KM2:
        return {"too_big": True}
    a, r = _raster()
    R, sq3 = HEX_R, math.sqrt(3)
    x0, x1, y0, y1 = w * KX, e * KX, s * KY, n * KY
    cx, cy = [], []
    for row in range(math.floor(y0 / (1.5 * R)) - 1, math.ceil(y1 / (1.5 * R)) + 2):
        q0 = math.floor(x0 / (R * sq3) - row / 2) - 1
        q1 = math.ceil(x1 / (R * sq3) - row / 2) + 1
        q = np.arange(q0, q1 + 1)
        cx.append(R * sq3 * (q + row / 2))
        cy.append(np.full(q.shape, 1.5 * R * row))
    if not cx:
        return {"hex": []}
    cx, cy = np.concatenate(cx), np.concatenate(cy)
    lat, lon = cy / KY, cx / KX
    rows = ((r["lat0"] - lat) / r["dy"]).astype(int)
    cols = ((lon - r["lon0"]) / r["dx"]).astype(int)
    ok = (rows >= 0) & (rows < a.shape[0]) & (cols >= 0) & (cols < a.shape[1])
    dens = np.zeros(lat.shape)
    dens[ok] = a[rows[ok], cols[ok]]
    keep = dens >= config.ORTA_ZICHLIK
    cx, cy, lat, lon, dens = cx[keep], cy[keep], lat[keep], lon[keep], dens[keep]
    act = [b for b in branches.active_branches()]
    if len(cx) and act:
        bx = np.array([b["lng"] * KX for b in act]); by = np.array([b["lat"] * KY for b in act])
        near = np.empty(len(cx))
        for i in range(0, len(cx), 4000):   # bo'laklab — xotira tejaladi
            dx = cx[i:i + 4000, None] - bx[None, :]
            dy = cy[i:i + 4000, None] - by[None, :]
            near[i:i + 4000] = np.sqrt(dx * dx + dy * dy).min(axis=1)
    else:
        near = np.full(len(cx), 999.0)
    urban = dens >= config.GAVJUM_ZICHLIK
    limit = np.where(urban, config.ZONA_SHAHAR_KM, config.ZONA_TUMAN_KM)
    cls = np.where(near < limit, "band", np.where(dens >= config.ZONA_TAVSIYA_ZICHLIK, "tavsiya", "orta"))
    if not config.ZONA_ORTA_KORSATISH:
        show = cls != "orta"
        cls, lat, lon, dens, near, limit = cls[show], lat[show], lon[show], dens[show], near[show], limit[show]
    out = [[round(float(la), 5), round(float(lo), 5), c, int(d), round(float(k), 2), float(li)]
           for la, lo, c, d, k, li in zip(lat, lon, cls, dens, near, limit)]
    return {"r": R, "kx": KX, "ky": KY, "hex": out}


NAMES_FILE = DATA / "gap_names.json"
_names_thread = {"t": None}


def _load_names():
    try:
        return json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _reverse(lat, lon):
    """OpenStreetMap (Nominatim) orqali nuqtaning hudud va joy nomi."""
    import urllib.request
    url = (f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
           f"&zoom=14&accept-language=uz")
    req = urllib.request.Request(url, headers={"User-Agent": "yetkaz-filial-dashboard/1.0 (local)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        a = json.load(r).get("address", {})
    city, state = a.get("city") or "", a.get("state") or ""
    if city == "Toshkent":
        hudud = "Toshkent shahri"
    elif state:
        hudud = state if state in ("Toshkent viloyati",) or "Respublika" in state else re.sub(r"\s+viloyati$", "", state)
    else:
        hudud = ""
    county = re.sub(r"\s+Tumani$", " tumani", a.get("county") or a.get("district") or "")   # shaharda tuman "district" da
    place = (a.get("suburb") or a.get("city_district") or a.get("quarter") or a.get("residential") or a.get("village")
             or a.get("town") or a.get("neighbourhood") or a.get("hamlet") or a.get("road") or "")
    main = county or (city if city and city != "Toshkent" else "")
    joy = ", ".join(dict.fromkeys(x for x in (main, place) if x))
    return {"hudud": hudud, "joy": joy}


def _fill_names(points):
    """Fonda: yetishmagan bo'sh hudud nomlarini olib, faylga yozadi (Nominatim: 1 so'rov/soniya)."""
    names = _load_names()
    for lat, lon in points:
        k = f"{lat:.4f},{lon:.4f}"
        if k in names and (names[k].get("joy") or "").strip():
            continue
        try:
            names[k] = _reverse(lat, lon)
        except Exception:
            continue
        DATA.mkdir(exist_ok=True)
        NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(1.1)
    _cache["key"] = None   # keyingi so'rovda nomlar bilan qayta hisoblanadi


def _norm_hudud(h):
    """'Farg'ona Viloyati' -> 'Farg'ona', 'Toshkent Viloyati' -> 'Toshkent viloyati' (filiallar bazasidagidek)."""
    h = (h or "").strip()
    if re.match(r"(?i)toshkent\s+viloyati$", h):
        return "Toshkent viloyati"
    if re.search(r"(?i)respublika", h):
        return "Qoraqalpog'iston Respublikasi"
    return re.sub(r"(?i)\s+viloyati$", "", h)


def _apply_names(gaps):
    names = _load_names()
    missing = []
    for g in gaps:
        n = names.get(f"{g['lat']:.4f},{g['lon']:.4f}")
        if n and (n.get("joy") or "").strip():
            if n.get("hudud"):
                g["hudud"] = _norm_hudud(n["hudud"])
            # kirillcha qismlarni tashlab yuboramiz (o'zbekcha nom bo'lmasa OSM ruscha beradi)
            g["joy"] = ", ".join(p for p in (n.get("joy") or "").split(", ") if p and not re.search("[А-Яа-яЁё]", p))
        else:
            g["joy"] = ""
            missing.append((g["lat"], g["lon"]))
    t = _names_thread["t"]
    if missing and not (t and t.is_alive()):
        import threading
        _names_thread["t"] = threading.Thread(target=_fill_names, args=(missing,), daemon=True)
        _names_thread["t"].start()


def compute():
    path = Path(config.FILIALLAR_JSON)
    key = path.stat().st_mtime
    if _cache["key"] == key:
        return _cache["result"]

    allb = branches.load_branches()
    act = [b for b in allb if b.get("status") == "Aktiv" and b.get("lat")]
    a, r = _raster()
    lat_c = 41.0
    cell_km2 = (r["dy"] * 111.32) * (r["dx"] * 111.32 * math.cos(math.radians(lat_c)))
    people = a * cell_km2                                # har bir katakdagi odamlar soni
    total_pop = float(people.sum())

    act_cells = []
    for b in act:
        row, col = _cell(r, b["lat"], b["lng"])
        if 0 <= row < a.shape[0] and 0 <= col < a.shape[1]:
            act_cells.append((row, col, b["lat"]))

    covered = _disk_mask(a.shape, act_cells, COVER_KM, r)
    covered_pop = float(people[covered].sum())
    near5 = _disk_mask(a.shape, act_cells, GAP_MIN_KM, r)

    # Bo'sh hududlar: ~3 km atrofida eng ko'p aholi bo'lgan, lekin 5 km ichida aktiv filial yo'q joylar
    ry = int(COVER_KM / (r["dy"] * 111.32))
    rx = int(COVER_KM / (r["dx"] * 111.32 * math.cos(math.radians(lat_c))))
    pop3 = _box_sum(people, ry, rx)
    pop3[near5] = 0
    flat = np.argsort(pop3, axis=None)[::-1]
    gaps = []
    for idx in flat[:20000]:
        row, col = divmod(int(idx), a.shape[1])
        p = float(pop3[row, col])
        if p < 5000 or len(gaps) >= GAP_COUNT:
            break
        lat, lon = _cell_center(r, row, col)
        if any(branches.haversine(lat, lon, g["lat"], g["lon"]) < GAP_SPACING_KM for g in gaps):
            continue
        near = min(((branches.haversine(lat, lon, b["lat"], b["lng"]), b) for b in act), key=lambda x: x[0])
        if near[0] < GAP_MIN_KM:   # katak chegarasida turib qolganlar — aniq masofa bo'yicha tekshiramiz
            continue
        anyb = min(((branches.haversine(lat, lon, b["lat"], b["lng"]), b) for b in allb if b.get("lat")),
                   key=lambda x: x[0])
        # Toshkent shahrida filial deyarli yo'q — eng yaqin filial bo'yicha hudud noto'g'ri chiqadi
        in_tashkent = branches.haversine(lat, lon, *TASHKENT_CENTER) <= TASHKENT_RADIUS_KM
        gaps.append({"lat": round(lat, 5), "lon": round(lon, 5), "aholi_3km": int(round(p, -2)),
                     "zichlik": int(a[row, col]), "eng_yaqin": near[1]["nomi"], "masofa_km": round(near[0], 1),
                     "hudud": "Toshkent shahri" if in_tashkent else anyb[1]["hudud"],
                     "yopilgan_yaqin": anyb[1]["nomi"] if anyb[1].get("status") != "Aktiv" and anyb[0] < 3 else ""})

    _apply_names(gaps)   # aniq hudud va joy nomi (Toshkent shahri — Chilonzor tumani ...)

    # Har bir filial uchun ko'rsatkichlar
    enriched = []
    for b in allb:
        e = {k: b.get(k) for k in ("num", "id", "nomi", "mrk", "hudud", "manager", "phone1", "phone2", "landmark",
                                    "locationUrl", "izoh", "status", "ochilgan", "ijara", "banner", "yopilgan_sana")}
        e["address"] = b.get("address") or ""
        e["lat"], e["lng"] = b.get("lat"), b.get("lng")
        if b.get("lat"):
            d = branches.density(b["lat"], b["lng"])
            e["zichlik"] = d
            row, col = _cell(r, b["lat"], b["lng"])
            inside = 0 <= row < a.shape[0] and 0 <= col < a.shape[1]
            e["aholi_3km"] = int(round(float(people[max(row - ry, 0):row + ry + 1,
                                                    max(col - rx, 0):col + rx + 1].sum()), -2)) if inside else None
            others = [(branches.haversine(b["lat"], b["lng"], o["lat"], o["lng"]), o) for o in act if o is not b]
            if others:
                km, o = min(others, key=lambda x: x[0])
                e["qoshni"], e["qoshni_km"] = o["nomi"], round(km, 2)
        enriched.append(e)

    # Viloyatlar kesimi
    pop_tbl = _population_table()
    vil = defaultdict(lambda: {"aktiv": 0, "yopilgan": 0, "ijara": 0, "banner": 0})
    for b in allb:
        v = vil[b["hudud"]]
        v["aktiv" if b.get("status") == "Aktiv" else "yopilgan"] += 1
        if b.get("status") == "Aktiv":
            v["ijara"] += b.get("ijara") == "Bor"
            v["banner"] += b.get("banner") == "Bor"
    vil_rows = []
    for h, v in vil.items():
        pop = pop_tbl.get(h)
        vil_rows.append({"hudud": h, **v, "jami": v["aktiv"] + v["yopilgan"],
                         "yopilish_foiz": round(100 * v["yopilgan"] / max(1, v["aktiv"] + v["yopilgan"])),
                         "aholi_ming": pop,
                         "aholi_per_filial": round(pop / v["aktiv"]) if pop and v["aktiv"] else None,
                         "oq_doglar": sum(g["hudud"] == h for g in gaps)})
    vil_rows.sort(key=lambda x: -(x["aholi_per_filial"] or 10 ** 9))

    # Bir-biriga juda yaqin aktiv filiallar (bir-birining mijozini bo'lishi mumkin)
    close_pairs = []
    for i, b1 in enumerate(act):
        for b2 in act[i + 1:]:
            km = branches.haversine(b1["lat"], b1["lng"], b2["lat"], b2["lng"])
            if km < 1.0:
                close_pairs.append({"a": b1["nomi"], "b": b2["nomi"], "km": round(km, 2), "hudud": b1["hudud"]})
    close_pairs.sort(key=lambda x: x["km"])

    # Ma'lumot sifati muammolari
    sifat = []
    for b in allb:
        if not b.get("lat"):
            sifat.append({"nomi": b["nomi"], "hudud": b["hudud"], "muammo": "Koordinata yo'q — xaritada ko'rinmaydi"})
        if not (b.get("address") or "").strip():
            sifat.append({"nomi": b["nomi"], "hudud": b["hudud"], "muammo": "Manzil bo'sh"})
    for p in close_pairs:
        if p["km"] < 0.05:
            sifat.append({"nomi": f"{p['a']} / {p['b']}", "hudud": p["hudud"],
                          "muammo": f"Ikki filial bir nuqtada ({p['km'] * 1000:.0f} m) — koordinata xato bo'lishi mumkin"})

    months = Counter((b.get("ochilgan") or "")[:7] for b in allb if b.get("ochilgan"))
    act_dens = [e["zichlik"] for e in enriched if e["status"] == "Aktiv" and e.get("zichlik")]
    closed_dens = [e["zichlik"] for e in enriched if e["status"] != "Aktiv" and e.get("zichlik")]

    result = {
        "branches": enriched,
        "gaps": gaps,
        "viloyatlar": vil_rows,
        "close_pairs": close_pairs,
        "sifat": sifat,
        "ochilish_oylar": sorted(months.items()),
        "summary": {
            "jami": len(allb), "aktiv": len(act), "yopilgan": len(allb) - len([b for b in allb if b.get("status") == "Aktiv"]),
            "koordinatasiz": sum(1 for b in allb if not b.get("lat")),
            "ijara": sum(1 for b in allb if b.get("status") == "Aktiv" and b.get("ijara") == "Bor"),
            "banner": sum(1 for b in allb if b.get("status") == "Aktiv" and b.get("banner") == "Bor"),
            "izohli": sum(1 for b in allb if b.get("izoh")),
            "aholi_jami_mln": round(total_pop / 1e6, 1),
            "qamrov_foiz": round(100 * covered_pop / total_pop, 1),
            "qamrov_mln": round(covered_pop / 1e6, 1),
            "cover_km": COVER_KM, "gap_km": GAP_MIN_KM,
            "kam_aholili_aktiv": sum(1 for d in act_dens if d < config.ORTA_ZICHLIK),
            "median_zichlik_aktiv": int(np.median(act_dens)) if act_dens else None,
            "median_zichlik_yopilgan": int(np.median(closed_dens)) if closed_dens else None,
        },
    }
    _cache.update(key=key, result=result)
    return result
