"""Filiallarni boshqarish: filiallar.json ga xavfsiz yozish (zaxira + o'zgarishlar tarixi).

Fayl filiallar xaritasi loyihasi (web_map, 8790-port) bilan umumiy — u ham shu faylni o'qiydi.
"""
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import config

FIELDS = ["num", "id", "hudud", "nomi", "mrk", "manager", "phone1", "phone2", "address", "landmark",
          "locationUrl", "lat", "lng", "izoh", "status", "ochilgan", "ijara", "banner", "yopilgan_sana"]
EDITABLE = [f for f in FIELDS if f not in ("num", "id")]
STATUSES = ("Aktiv", "Yopilgan")

_lock = threading.Lock()
DATA = Path(__file__).parent / "data"
HISTORY = DATA / "filial_tarix.jsonl"


def _path():
    return Path(config.FILIALLAR_JSON)


def read_all():
    return json.loads(_path().read_text(encoding="utf-8-sig"))


def _write_all(items):
    p = _path()
    backups = p.parent / "backups"
    backups.mkdir(exist_ok=True)
    shutil.copy2(p, backups / f"filiallar_{datetime.now():%Y%m%d_%H%M%S_%f}.json")
    for old in sorted(backups.glob("filiallar_*.json"))[:-100]:   # oxirgi 100 ta zaxira saqlanadi
        old.unlink(missing_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=4), encoding="utf-8")
    os.replace(tmp, p)


def _log(action, branch, changes=None, who="dashboard"):
    DATA.mkdir(exist_ok=True)
    rec = {"vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"), "amal": action, "id": str(branch.get("id")),
           "nomi": branch.get("nomi"), "kim": who, "ozgarish": changes or {}}
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def history(branch_id=None, limit=200):
    if not HISTORY.exists():
        return []
    rows = [json.loads(line) for line in HISTORY.read_text(encoding="utf-8").splitlines() if line.strip()]
    if branch_id is not None:
        rows = [r for r in rows if r["id"] == str(branch_id)]
    return rows[::-1][:limit]


def _clean(body, partial):
    """Kiruvchi maydonlarni tekshiradi va tozalaydi. Xato bo'lsa ValueError."""
    out = {}
    for k in EDITABLE:
        if k not in body:
            continue
        v = body[k]
        if k in ("lat", "lng"):
            if v in (None, ""):
                v = None
            else:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"{k} noto'g'ri")
                if k == "lat" and not 37 <= v <= 46 or k == "lng" and not 55 <= v <= 74:
                    raise ValueError("Koordinata O'zbekistondan tashqarida")
        elif k == "status":
            if v not in STATUSES:
                raise ValueError("Holat Aktiv yoki Yopilgan bo'lishi kerak")
        elif k in ("ochilgan", "yopilgan_sana"):
            v = (str(v or "").strip() or None)
            if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                raise ValueError(f"{k}: sana YYYY-MM-DD ko'rinishida bo'lsin")
        elif k in ("ijara", "banner"):
            v = "Bor" if v in (True, "Bor", "bor", "1", 1) else "Yo'q"
        else:
            v = (str(v).strip() or None) if v is not None else None
            if v and len(v) > 500:
                v = v[:500]
        out[k] = v
    if not partial and not out.get("nomi"):
        raise ValueError("Filial nomi majburiy")
    if "nomi" in out and not out["nomi"]:
        raise ValueError("Filial nomi bo'sh bo'lishi mumkin emas")
    return out


def create(body, who="dashboard"):
    data = _clean(body, partial=False)
    with _lock:
        items = read_all()
        nums = [int(b["num"]) for b in items if str(b.get("num", "")).isdigit()]
        new = {f: None for f in FIELDS}
        new.update(num=str(max(nums, default=0) + 1), id=f"Y{int(time.time() * 1000)}",
                   status="Aktiv", ijara="Yo'q", banner="Yo'q")
        new.update(data)
        if new["status"] == "Aktiv" and not new.get("ochilgan"):
            new["ochilgan"] = datetime.now().strftime("%Y-%m-%d")
        items.append(new)
        _write_all(items)
    _log("qo'shildi", new, who=who)
    return new


def update(branch_id, body, who="dashboard"):
    data = _clean(body, partial=True)
    with _lock:
        items = read_all()
        b = next((x for x in items if str(x.get("id")) == str(branch_id)), None)
        if not b:
            raise KeyError(branch_id)
        if data.get("status") == "Yopilgan" and b.get("status") != "Yopilgan" and not data.get("yopilgan_sana"):
            data["yopilgan_sana"] = datetime.now().strftime("%Y-%m-%d")
        if data.get("status") == "Aktiv" and b.get("status") == "Yopilgan":
            data.setdefault("yopilgan_sana", None)
        changes = {k: [b.get(k), v] for k, v in data.items() if b.get(k) != v}
        if not changes:
            return b
        b.update(data)
        _write_all(items)
    action = ("yopildi" if changes.get("status", [None, None])[1] == "Yopilgan"
              else "qayta ochildi" if changes.get("status", [None, None])[1] == "Aktiv" else "tahrirlandi")
    _log(action, b, changes, who=who)
    return b


def delete(branch_id, who="dashboard"):
    with _lock:
        items = read_all()
        b = next((x for x in items if str(x.get("id")) == str(branch_id)), None)
        if not b:
            raise KeyError(branch_id)
        items = [x for x in items if x is not b]
        _write_all(items)
    _log("o'chirildi", b, {k: [v, None] for k, v in b.items() if v not in (None, "")}, who=who)
    return b
