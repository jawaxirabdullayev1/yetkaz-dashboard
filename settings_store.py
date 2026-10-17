"""Bot sozlamalari (savollar, matnlar, baholash qoidalari) — dashboarddan tahrirlanadi.

Asl qiymatlar config.py da. Dashboarddan saqlanganlari data/bot_sozlamalari.json ga yoziladi va
ishlab turgan botga darhol qo'llanadi (config modulidagi qiymatlar almashtiriladi).
"""
import copy
import json
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

import config

BASE = Path(__file__).parent
FILE = BASE / "data" / "bot_sozlamalari.json"
HISTORY = BASE / "data" / "bot_sozlamalari_tarix.jsonl"
_lock = threading.Lock()

# Telegram'ga HTML bilan yuboriladigan matnlar va oddiy matn sifatida yuboriladiganlar
HTML_TEXTS = ["GREETING", "FINISH_TEXT", "FOLLOWUP_FINISH_TEXT"]
PLAIN_TEXTS = ["APPROVED_TEXT", "OFFER"]
NUMBERS = {   # kalit: (min, max, butun sonmi)
    "HOT_SCORE": (0, 200, True), "WARM_SCORE": (0, 200, True),
    "SHAHAR_RADIUS_KM": (0.1, 50, False), "TUMAN_RADIUS_KM": (0.1, 100, False),
    "GAVJUM_ZICHLIK": (0, 200000, True), "ORTA_ZICHLIK": (0, 200000, True),
}


def _offer_path():
    return BASE / config.OFFER_FILE


def current():
    """Hozir amalda bo'lgan sozlamalar (JSON ko'rinishida)."""
    d = {k: getattr(config, k) for k in HTML_TEXTS + ["APPROVED_TEXT"]}
    d["OFFER"] = _offer_path().read_text(encoding="utf-8").strip() if _offer_path().exists() else ""
    d["QUESTIONS"] = [dict(q, options=[list(o) for o in q.get("options", [])]) if q.get("type") == "choice" else dict(q)
                      for q in config.QUESTIONS]
    d["FOLLOWUP_QUESTIONS"] = copy.deepcopy(config.FOLLOWUP_QUESTIONS)
    for k in NUMBERS:
        d[k] = getattr(config, k)
    return d


DEFAULTS = current()   # config.py dagi asl qiymatlar (saqlanganlari qo'llanishidan oldin olinadi)

_ALLOWED_TAG = re.compile(r"</?(b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler)>|<a href=\"[^\"<>]*\">|</a>", re.I)
_ENTITY = re.compile(r"&(amp|lt|gt|quot|#\d+|#x[0-9a-f]+);", re.I)


def _html_ok(text, label):
    """Telegram HTML: faqat ruxsat etilgan teglar; yolg'iz & avtomatik &amp; ga aylantiriladi."""
    text = re.sub(r"&(?!(amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);)", "&amp;", text)
    rest = _ALLOWED_TAG.sub("", text)
    if "<" in rest or ">" in rest:
        raise ValueError(f"{label}: '<' yoki '>' belgisi ishlatib bo'lmaydi. Faqat <b>qalin</b>, <i>qiya</i>, "
                         f"<u>tagiga chizilgan</u> teglari mumkin.")
    return text


def _slug(text, used):
    base = re.sub(r"[^a-z0-9]+", "_", text.lower().replace("'", "").replace("ʻ", "").replace("‘", ""))
    base = (base.strip("_") or "savol")[:24].rstrip("_")
    k, n = base, 2
    while k in used:
        k, n = f"{base}_{n}", n + 1
    used.add(k)
    return k


def _text(v, label, mx=3500, html=False):
    v = str(v or "").replace("\r\n", "\n").strip()
    if not v:
        raise ValueError(f"{label} bo'sh bo'lishi mumkin emas")
    if len(v) > mx:
        raise ValueError(f"{label} juda uzun ({len(v)} belgi, ko'pi bilan {mx})")
    return _html_ok(v, label) if html else v


def _int(v, label, lo, hi):
    try:
        v = int(round(float(v)))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: son kiriting")
    if not lo <= v <= hi:
        raise ValueError(f"{label}: {lo}..{hi} oralig'ida bo'lsin")
    return v


def _options(opts, label, with_points):
    if not isinstance(opts, list) or not 2 <= len(opts) <= 12:
        raise ValueError(f"{label}: javob variantlari 2 tadan 12 tagacha bo'lsin")
    out, seen = [], set()
    for i, o in enumerate(opts, 1):
        t = o[0] if isinstance(o, (list, tuple)) else (o.get("t") if isinstance(o, dict) else o)
        t = _text(t, f"{label}, {i}-variant", 60)
        if t.lower() in seen:
            raise ValueError(f"{label}: «{t}» varianti takrorlangan")
        seen.add(t.lower())
        if with_points:
            p = o[1] if isinstance(o, (list, tuple)) and len(o) > 1 else (o.get("p", 0) if isinstance(o, dict) else 0)
            out.append([t, _int(p, f"{label}, «{t}» bali", -50, 100)])
        else:
            out.append(t)
    return out


def validate(d):
    out = {}
    names = {"GREETING": "Salomlashuv", "FINISH_TEXT": "Anketa tugagandagi xabar",
             "FOLLOWUP_FINISH_TEXT": "Hujjatlar qabul qilingandagi xabar", "APPROVED_TEXT": "Tasdiqlangandagi xabar",
             "OFFER": "Tijoriy taklif"}
    for k in HTML_TEXTS:
        out[k] = _text(d.get(k), names[k], html=True)
    out["APPROVED_TEXT"] = _text(d.get("APPROVED_TEXT"), names["APPROVED_TEXT"])
    out["OFFER"] = _text(d.get("OFFER"), names["OFFER"], 4000)

    used = set()
    qs = d.get("QUESTIONS") or []
    if len(qs) > 30:
        raise ValueError("1-bosqichda ko'pi bilan 30 ta savol bo'lishi mumkin")
    keys_in = [q.get("key") for q in qs if re.fullmatch(r"[a-z0-9_]{1,40}", str(q.get("key") or ""))]
    used.update(k for k in keys_in if keys_in.count(k) == 1)
    out["QUESTIONS"] = []
    for i, q in enumerate(qs, 1):
        label = f"1-bosqich, {i}-savol"
        typ = q.get("type")
        if typ not in ("text", "choice"):
            raise ValueError(f"{label}: turi noto'g'ri")
        k = q.get("key") if q.get("key") in used else None
        if k is None or any(x["key"] == k for x in out["QUESTIONS"]):
            k = _slug(str(q.get("text") or "savol"), used)
        item = {"key": k, "type": typ, "text": _text(q.get("text"), label, 1000, html=True)}
        if typ == "choice":
            item["options"] = _options(q.get("options"), label, True)
        else:
            item["points"] = _int(q.get("points", 0), f"{label} bali", 0, 100)
        out["QUESTIONS"].append(item)

    used2 = set()
    fq = d.get("FOLLOWUP_QUESTIONS") or []
    if not 1 <= len(fq) <= 20:
        raise ValueError("3-bosqichda 1 tadan 20 tagacha savol bo'lishi kerak")
    k_in = [q.get("key") for q in fq if re.fullmatch(r"[a-z0-9_]{1,40}", str(q.get("key") or ""))]
    used2.update(k for k in k_in if k_in.count(k) == 1)
    out["FOLLOWUP_QUESTIONS"] = []
    for i, q in enumerate(fq, 1):
        label = f"3-bosqich, {i}-savol"
        typ = q.get("type")
        if typ not in ("text", "choice", "photo"):
            raise ValueError(f"{label}: turi noto'g'ri")
        k = q.get("key") if q.get("key") in used2 else None
        if k is None or any(x["key"] == k for x in out["FOLLOWUP_QUESTIONS"]):
            k = _slug(str(q.get("name") or q.get("text") or "savol"), used2)
        item = {"key": k, "type": typ, "text": _text(q.get("text"), label, 1000, html=True)}
        nm = str(q.get("name") or "").strip()[:40]
        if nm:
            item["name"] = nm
        if typ == "choice":
            item["options"] = _options(q.get("options"), label, False)
        if typ == "text" and q.get("require") in ("phone", "card"):
            item["require"] = q["require"]
        out["FOLLOWUP_QUESTIONS"].append(item)

    for k, (lo, hi, is_int) in NUMBERS.items():
        v = d.get(k, getattr(config, k))
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k}: son kiriting")
        if not lo <= v <= hi:
            raise ValueError(f"{k}: {lo}..{hi} oralig'ida bo'lsin")
        out[k] = int(round(v)) if is_int else round(v, 2)
    if out["HOT_SCORE"] <= out["WARM_SCORE"]:
        raise ValueError("«Issiq» chegarasi «Iliq» chegarasidan katta bo'lishi kerak")
    if out["GAVJUM_ZICHLIK"] <= out["ORTA_ZICHLIK"]:
        raise ValueError("«Gavjum» zichlik «aholi kam» chegarasidan katta bo'lishi kerak")
    return out


def apply(d):
    """Ishlab turgan botga qo'llash: config qiymatlarini almashtiradi, taklif faylini yozadi."""
    for k in HTML_TEXTS + ["APPROVED_TEXT", "QUESTIONS", "FOLLOWUP_QUESTIONS"] + list(NUMBERS):
        setattr(config, k, d[k])
    _offer_path().write_text(d["OFFER"] + ("\n" if not d["OFFER"].endswith("\n") else ""), encoding="utf-8")


def load_and_apply():
    """Bot ishga tushganda: saqlangan sozlamalar bo'lsa, qo'llaydi."""
    if FILE.exists():
        try:
            apply(validate(json.loads(FILE.read_text(encoding="utf-8"))))
            return True
        except Exception:
            import logging
            logging.exception("bot_sozlamalari.json o'qilmadi — config.py qiymatlari ishlatiladi")
    return False


def save(d, who="dashboard"):
    clean = validate(d)
    with _lock:
        old = current()
        if FILE.exists():
            bdir = BASE / "data" / "backups"
            bdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(FILE, bdir / f"bot_sozlamalari_{datetime.now():%Y%m%d_%H%M%S_%f}.json")
            for f in sorted(bdir.glob("bot_sozlamalari_*.json"))[:-50]:
                f.unlink(missing_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(FILE)
        apply(clean)
        changed = [k for k in clean if clean[k] != old.get(k)]
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"), "kim": who,
                                "ozgargan": changed}, ensure_ascii=False) + "\n")
    return clean, changed


def history(limit=30):
    if not HISTORY.exists():
        return []
    rows = [json.loads(x) for x in HISTORY.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows[::-1][:limit]
