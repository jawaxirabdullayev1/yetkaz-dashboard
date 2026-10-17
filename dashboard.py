"""Lidlar dashboardi — bot bilan bir jarayonda ishlaydigan kichik veb-server (aiohttp)."""
import hashlib
import json
import hmac
import html
import logging
from pathlib import Path

from aiohttp import web

import branches
import config

STATIC = Path(__file__).parent / "dashboard"

# Lid bilan ishlash statuslari (dashboardda qo'lda o'zgartiriladi)
STATUSES = [
    {"k": "Yangi", "c": "gray"}, {"k": "Bog'lanildi", "c": "blue"}, {"k": "Ko'tarmadi", "c": "orange"},
    {"k": "Qiziqdi", "c": "purple"}, {"k": "Uchrashuv", "c": "cyan"}, {"k": "Shartnoma", "c": "green"},
    {"k": "Mos emas", "c": "red"}, {"k": "Dubl", "c": "gray"},
]
STATUS_KEYS = {s["k"] for s in STATUSES}


def _phone_key(p):
    d = "".join(ch for ch in (p or "") if ch.isdigit())
    return d[-9:] if len(d) >= 9 else ""


def _unesc(v):
    return html.unescape(v) if isinstance(v, str) else v


def _token():
    return hmac.new(config.DASHBOARD_PASSWORD.encode(), b"ipost-dashboard", hashlib.sha256).hexdigest()


LOGIN_HTML = """<!doctype html><html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Kirish — YETKAZ</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;900&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#efebe1;font:15px Archivo,system-ui,sans-serif;color:#131b29}
form{background:#f8f5ee;border:1px solid #ddd5c5;border-radius:16px;padding:30px;width:min(360px,92vw);display:grid;gap:14px}
.brand{display:flex;align-items:center;gap:12px}.w{font-weight:900;font-size:24px;line-height:1}
.m{font:500 10.5px 'JetBrains Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:#6e7380;margin-top:4px}
input{font:inherit;padding:11px 12px;border:1px solid #ddd5c5;border-radius:9px;background:#fff}
button{font:inherit;font-weight:700;padding:11px;border:0;border-radius:9px;background:#131b29;color:#efebe1;cursor:pointer}
.e{color:#c2493f;font-size:13px}</style></head>
<body><form method="post" action="/login"><div class="brand">
<svg width="44" height="44" viewBox="0 0 48 48"><rect width="48" height="48" rx="12" fill="#131b29"/><path d="M15 30a9.5 9.5 0 0 1 18 0" fill="none" stroke="#efebe1" stroke-width="3.4" stroke-linecap="round"/><circle cx="15" cy="30" r="3.6" fill="#efebe1"/><circle cx="15" cy="30" r="1.4" fill="#131b29"/><circle cx="33" cy="30" r="4.2" fill="#4a7f99"/><circle cx="33" cy="30" r="1.6" fill="#131b29"/></svg>
<div><div class="w">YETKAZ</div><div class="m">Filiallar boshqaruvi</div></div></div>
<input type="password" name="p" placeholder="Parol" autofocus required>%ERR%<button>Kirish</button></form></body></html>"""


@web.middleware
async def auth(request, handler):
    if request.path == "/login" or hmac.compare_digest(request.cookies.get("lid_auth", ""), _token()):
        return await handler(request)
    if request.path.startswith("/api/"):
        return web.json_response({"ok": False, "error": "login"}, status=401)
    raise web.HTTPFound("/login")


def create_app(tg_bot, api):
    """api — bot moduli (all_leads, build_excel, send_offer, photo_path, ...)."""
    app = web.Application(middlewares=[auth])

    async def login_page(request):
        return web.Response(text=LOGIN_HTML.replace("%ERR%", ""), content_type="text/html")

    async def login(request):
        form = await request.post()
        if config.DASHBOARD_PASSWORD and hmac.compare_digest(str(form.get("p", "")), config.DASHBOARD_PASSWORD):
            resp = web.HTTPFound("/")
            resp.set_cookie("lid_auth", _token(), max_age=30 * 24 * 3600, httponly=True, samesite="Strict")
            raise resp
        return web.Response(text=LOGIN_HTML.replace("%ERR%", '<div class="e">Parol noto\'g\'ri</div>'),
                            content_type="text/html", status=401)

    async def index(_):
        return web.FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    async def leads(_):
        out = []
        all_ = api.all_leads()
        # Dubl: shu telefon raqami bilan undan oldin boshqa ariza bo'lsa
        first_by_phone = {}
        for l in sorted(all_, key=lambda x: x["created"] or ""):
            k = _phone_key(l["phone"])
            if k and k not in first_by_phone:
                first_by_phone[k] = l["user_id"]
        for l in all_:
            pk = _phone_key(l["phone"])
            out.append({
                "dubl": bool(pk) and first_by_phone.get(pk) != l["user_id"],
                "status": l["status"], "izoh": l["izoh"], "aloqa_sana": l["aloqa_sana"],
                "status_vaqt": l["status_vaqt"] or "", "filial_id": l.get("filial_id") or "", "korildi": l.get("korildi") or "",
                "id": l["user_id"], "name": _unesc(l["name"]), "username": l["username"],
                "phone": l["phone"], "viloyat": l["viloyat"], "tuman": l["tuman"],
                "lat": float(l["lat"]) if l["lat"] else None, "lon": float(l["lon"]) if l["lon"] else None,
                "map": api.map_link(l), "source": l["source"],
                "score": l["score"], "level": l["level"], "holat": l["holat"],
                "xulosa": l["xulosa"], "sabab": l["sabab"] or "", "eng_yaqin": l["eng_yaqin"] or "",
                "masofa_km": float(l["masofa_km"]) if l["masofa_km"] else None,
                "tumanda_filial": int(l["tumanda_filial"]) if l["tumanda_filial"] is not None else None,
                "zichlik": l["zichlik"] or "", "yaqinlar": l["yaqinlar"],
                "bosqich": l["bosqich"],
                "answers": {k: _unesc(v) for k, v in l["answers"].items()},
                "answers2": {k: _unesc(v) for k, v in l["answers2"].items()},
                "photos": list(l["photos"]),
                "created": l["created"], "updated": l["updated"],
            })
        try:
            br = [{"nomi": b["nomi"], "lat": b["lat"], "lng": b["lng"], "address": b.get("address") or ""}
                  for b in branches.active_branches()]
        except Exception as e:
            logging.warning("Filiallar o'qilmadi: %s", e)
            br = []
        return web.json_response({
            "leads": out, "branches": br,
            "questions": [{"key": q["key"], "label": api.qlabel(q), "type": q.get("type", "text")} for q in config.QUESTIONS],
            "followup": [{"key": q["key"], "label": q.get("name") or api.qlabel(q), "type": q["type"]}
                         for q in config.FOLLOWUP_QUESTIONS],
            "radius": {"shahar": config.SHAHAR_RADIUS_KM, "tuman": config.TUMAN_RADIUS_KM},
            "statuses": STATUSES,
            "admin_url": getattr(config, "FILIALLAR_ADMIN_URL", ""),
        })

    async def mark_all_seen(_):
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        n = 0
        for l in api.all_leads():
            if not l.get("korildi"):
                api.set_fields(l["user_id"], korildi=now); n += 1
        return web.json_response({"ok": True, "n": n})

    async def stage(request):
        """Bosqichni dashboarddan o'tkazish: offer | docs | remind | approve | reject."""
        uid = int(request.match_info["uid"])
        lead = api.get_lead(uid)
        if not lead:
            return web.json_response({"ok": False, "error": "Ariza topilmadi"}, status=404)
        body = await request.json()
        act, b = body.get("action"), lead["bosqich"]
        rules = {
            "offer":   (("", api.OFFER_SENT, api.ASKED, api.REFUSED), api.send_offer, "📨 Taklif yuborildi"),
            "docs":    ((api.OFFER_SENT, api.ASKED, api.REFUSED), api.stage_to_docs, "➡️ 3-bosqichga (hujjatlar) o'tkazildi"),
            "remind":  ((api.OFFER_SENT, api.ASKED, api.REFUSED, api.AGREED), api.stage_remind, "🔔 Eslatma yuborildi"),
            "approve": ((api.COMPLETE,), api.stage_approve, "✅ Hujjatlar tasdiqlandi"),
            "reject":  ((api.COMPLETE, api.APPROVED), None, "↩️ Hujjatlar qayta so'raldi"),
        }
        if act not in rules:
            return web.json_response({"ok": False, "error": "Noma'lum amal"}, status=400)
        allowed, fn, msg = rules[act]
        if lead["holat"] != api.DONE:
            return web.json_response({"ok": False, "error": "Anketa hali to'liq emas"}, status=409)
        if b not in allowed:
            return web.json_response({"ok": False, "error": f"Bu amal hozirgi bosqichda mumkin emas ({b or 'taklif yuborilmagan'})"}, status=409)
        ok = await (api.stage_reject(tg_bot, lead, body.get("reason", "")) if act == "reject" else fn(tg_bot, lead))
        if ok:
            await api.send_admins(tg_bot, f"{msg} (dashboard): {api.lead_title(lead)}"
                                          + (f"\nSabab: {html.escape(body.get('reason') or '')}" if act == "reject" and body.get("reason") else ""))
        return web.json_response({"ok": bool(ok), "error": None if ok else "Odamga yozib bo'lmadi (botni bloklagan bo'lishi mumkin)"})

    async def update_lead(request):
        uid = int(request.match_info["uid"])
        lead = api.get_lead(uid)
        if not lead:
            return web.json_response({"ok": False, "error": "Lid topilmadi"}, status=404)
        body = await request.json()
        fields = {}
        if "status" in body:
            if body["status"] not in STATUS_KEYS:
                return web.json_response({"ok": False, "error": "Noto'g'ri status"}, status=400)
            if body["status"] != lead["status"]:
                from datetime import datetime
                fields["status"] = body["status"]
                fields["status_vaqt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if "izoh" in body:
            fields["izoh"] = str(body["izoh"])[:3000]
        if "aloqa_sana" in body:
            v = str(body["aloqa_sana"] or "")[:10]
            fields["aloqa_sana"] = v
        if body.get("korildi") and not lead.get("korildi"):
            from datetime import datetime
            fields["korildi"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if fields:
            api.set_fields(uid, **fields)
        return web.json_response({"ok": True})

    async def network(_):
        import asyncio
        import analytics
        try:
            return web.json_response(await asyncio.to_thread(analytics.compute))
        except Exception as e:
            logging.exception("Tarmoq tahlili xatosi")
            return web.json_response({"error": str(e)}, status=500)

    async def bot_settings_get(_):
        import settings_store as ss
        return web.json_response({"settings": ss.current(), "defaults": ss.DEFAULTS,
                                  "saved": ss.FILE.exists(), "history": ss.history(15)})

    async def bot_settings_save(request):
        import settings_store as ss
        body = await request.json()
        try:
            clean, changed = ss.save(body.get("settings") or {})
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        return web.json_response({"ok": True, "settings": ss.current(), "changed": changed})

    async def recheck_api(_):
        n = 0
        for l in api.all_leads():
            if l["holat"] == api.DONE:
                await api.run_evaluation(l); n += 1
        return web.json_response({"ok": True, "n": n})

    async def bot_settings_reset(_):
        import settings_store as ss
        clean, changed = ss.save(ss.DEFAULTS, who="dashboard (asl holiga qaytarildi)")
        return web.json_response({"ok": True, "settings": ss.current(), "changed": changed})

    async def zones_api(request):
        import asyncio
        import analytics
        try:
            q = request.query
            s, w, n, e = (float(q[k]) for k in ("s", "w", "n", "e"))
        except (KeyError, ValueError):
            return web.json_response({"error": "bbox kerak"}, status=400)
        return web.json_response(await asyncio.to_thread(analytics.zones, s, w, n, e))

    async def evaluate_point(request):
        """Xaritadan belgilangan nuqtani baholash: yaqin filiallar, aholi, shahar/tuman qoidasi bo'yicha xulosa."""
        body = await request.json()
        lat, lon = body.get("lat"), body.get("lon")
        if (lat is None or lon is None) and body.get("url"):
            import asyncio
            found = await asyncio.to_thread(branches.resolve_maps_link, str(body["url"]))
            if found:
                lat, lon = found
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return web.json_response({"ok": False, "error": "Koordinata topilmadi"}, status=400)
        act = branches.active_branches()
        near = sorted(((branches.haversine(lat, lon, b["lat"], b["lng"]), b) for b in act), key=lambda x: x[0])[:5]
        d = branches.density(lat, lon)
        lvl = branches.density_level(d)
        km = near[0][0] if near else 999

        def verdict(limit):
            if km < limit:
                return branches.MAQUL_EMAS, f"{limit:g} km ichida filial bor"
            if lvl == "gavjum":
                return branches.MAQUL, "Yaqinida filial yo'q, aholi gavjum"
            if lvl == "kam":
                return branches.MAQUL_EMAS, "Aholi kam"
            return branches.KORIB, f"Yaqinida filial yo'q, aholi {lvl}"

        leads_near = [{"id": l["user_id"], "name": _unesc(l["name"]),
                       "km": round(branches.haversine(lat, lon, float(l["lat"]), float(l["lon"])), 2)}
                      for l in api.all_leads() if l["lat"]]
        leads_near = sorted([x for x in leads_near if x["km"] <= 5], key=lambda x: x["km"])
        return web.json_response({
            "ok": True, "lat": lat, "lon": lon, "zichlik": d, "daraja": lvl,
            "shahar": verdict(config.SHAHAR_RADIUS_KM), "tuman": verdict(config.TUMAN_RADIUS_KM),
            "radius": {"shahar": config.SHAHAR_RADIUS_KM, "tuman": config.TUMAN_RADIUS_KM},
            "yaqin": [{"nomi": b["nomi"], "hudud": b["hudud"], "km": round(k, 2), "lat": b["lat"], "lng": b["lng"]}
                      for k, b in near],
            "lidlar": leads_near,
        })

    import asyncio
    import branch_store

    def _bresp(fn, *args, status=200):
        try:
            return web.json_response({"ok": True, "branch": fn(*args)}, status=status)
        except ValueError as e:
            return web.json_response({"ok": False, "error": str(e)}, status=400)
        except KeyError:
            return web.json_response({"ok": False, "error": "Filial topilmadi"}, status=404)

    async def branch_create(request):
        body = await request.json()
        resp = await asyncio.to_thread(_bresp, branch_store.create, body, status=201)
        lead_id = body.get("from_lead")
        if resp.status == 201 and lead_id:
            from datetime import datetime
            new = json.loads(resp.body)["branch"]
            api.set_fields(int(lead_id), status="Shartnoma", filial_id=str(new["id"]),
                           status_vaqt=datetime.now().strftime("%Y-%m-%d %H:%M"))
        return resp

    async def branch_update(request):
        return await asyncio.to_thread(_bresp, branch_store.update, request.match_info["bid"], await request.json())

    async def branch_delete(request):
        return await asyncio.to_thread(_bresp, branch_store.delete, request.match_info["bid"])

    async def branch_history(request):
        bid = request.query.get("id")
        return web.json_response(await asyncio.to_thread(branch_store.history, bid, 300))

    async def photo(request):
        uid, key = int(request.match_info["uid"]), request.match_info["key"]
        lead = api.get_lead(uid)
        if not lead or key not in lead["photos"]:
            raise web.HTTPNotFound()
        path = api.photo_path(uid, key)
        if not path.exists():
            await api.download_photo(tg_bot, uid, key, lead["photos"][key])
        if not path.exists():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})

    async def excel(_):
        leads_ = api.all_leads()
        await api.ensure_photos(tg_bot, leads_)
        from datetime import datetime
        name = f"lidlar_{datetime.now():%Y%m%d_%H%M}.xlsx"
        return web.Response(body=api.build_excel(leads_), headers={
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": f'attachment; filename="{name}"'})

    async def offer(request):
        uid = int(request.match_info["uid"])
        lead = api.get_lead(uid)
        if not lead:
            return web.json_response({"ok": False, "error": "Lid topilmadi"}, status=404)
        if lead["bosqich"]:
            return web.json_response({"ok": False, "error": f"Allaqachon: {lead['bosqich']}"}, status=409)
        ok = await api.send_offer(tg_bot, lead)
        if ok:
            await api.send_admins(tg_bot, f"📨 Taklif dashboard orqali yuborildi: {api.lead_title(lead)}")
        return web.json_response({"ok": ok, "error": None if ok else "Yuborib bo'lmadi (botni bloklagan bo'lishi mumkin)"})

    app.router.add_get("/login", login_page)
    app.router.add_post("/login", login)
    app.router.add_get("/", index)
    app.router.add_get("/api/leads", leads)
    app.router.add_get("/api/network", network)
    app.router.add_get("/api/zones", zones_api)
    app.router.add_get("/api/bot_settings", bot_settings_get)
    app.router.add_post("/api/bot_settings", bot_settings_save)
    app.router.add_post("/api/bot_settings/reset", bot_settings_reset)
    app.router.add_post("/api/recheck", recheck_api)
    app.router.add_post("/api/evaluate", evaluate_point)
    app.router.add_post("/api/branches", branch_create)
    app.router.add_put("/api/branches/{bid}", branch_update)
    app.router.add_delete("/api/branches/{bid}", branch_delete)
    app.router.add_get("/api/tarix", branch_history)
    app.router.add_get("/photo/{uid}/{key}", photo)
    app.router.add_get("/export.xlsx", excel)
    app.router.add_post("/api/offer/{uid}", offer)
    app.router.add_post("/api/lead/{uid}", update_lead)
    app.router.add_post("/api/stage/{uid}", stage)
    app.router.add_post("/api/korildi_hammasi", mark_all_seen)
    return app


async def start(tg_bot, api):
    app = create_app(tg_bot, api)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.DASHBOARD_PORT).start()
    print(f"Dashboard: http://localhost:{config.DASHBOARD_PORT}  (parol: config.py -> DASHBOARD_PASSWORD)")
    return runner
