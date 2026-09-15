from __future__ import annotations

import html
import os
import time
from collections import Counter
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from hunter.config import GEO_POSITIVE, INTENT_TERMS, STACK_GROUPS
from storage.supabase import SupabaseStorage

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT = str(os.getenv("TELEGRAM_ALLOWED_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))).strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_WORKFLOW = os.getenv("GITHUB_WORKFLOW", "hunter.yml").strip()
GITHUB_REF = os.getenv("GITHUB_REF", "main").strip()

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

API = f"https://api.telegram.org/bot{TOKEN}"
storage = SupabaseStorage()


def allowed(chat_id) -> bool:
    return bool(ALLOWED_CHAT) and str(chat_id) == ALLOWED_CHAT


def tg(method: str, payload: dict):
    r = requests.post(f"{API}/{method}", json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Telegram {method}: {r.status_code} {r.text[:1000]}")
    return r.json()


def send(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg("sendMessage", payload)


def card(chat_id, r):
    stack = ", ".join((r.get("stack_hits") or [])[:8])
    text = (
        f"🔥 <b>{r.get('score',0)} — {html.escape(str(r.get('source','')))}</b>\n"
        f"<b>{html.escape(str(r.get('title',''))[:220])}</b>\n"
        f"Estado: <b>{html.escape(str(r.get('status','NEW')))}</b>\n"
        f"{html.escape(stack)}\n\n"
        f"{html.escape(str(r.get('reasons',''))[:700])}"
    )
    kb = {"inline_keyboard": [
        [{"text": "🔗 Abrir", "url": r["url"]}],
        [
            {"text": "⭐ Guardar", "callback_data": f"status:{r['id']}:SAVED"},
            {"text": "✅ Apliqué", "callback_data": f"status:{r['id']}:APPLIED"},
            {"text": "🗑 Descartar", "callback_data": f"status:{r['id']}:DISCARDED"},
        ],
        [
            {"text": "📨 Contacté", "callback_data": f"status:{r['id']}:CONTACTED"},
            {"text": "💬 Respondió", "callback_data": f"status:{r['id']}:REPLIED"},
            {"text": "💰 Cliente", "callback_data": f"status:{r['id']}:CLIENT"},
        ],
    ]}
    send(chat_id, text, kb)


def show_rows(chat_id, rows, heading):
    send(chat_id, f"<b>{html.escape(heading)}</b> — {len(rows)} resultado(s)")
    for r in rows[:15]:
        card(chat_id, r)


def trigger_refresh(chat_id):
    if not all([GITHUB_REPO, GITHUB_TOKEN, GITHUB_WORKFLOW]):
        send(chat_id, "⚠️ Falta configurar GITHUB_REPO / GITHUB_TOKEN / GITHUB_WORKFLOW en el bot.")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW}/dispatches"
    r = requests.post(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }, json={"ref": GITHUB_REF}, timeout=30)
    if r.status_code == 204:
        send(chat_id, "🔄 Hunter lanzado en GitHub Actions. Los nuevos leads llegarán por Telegram.")
    else:
        send(chat_id, f"❌ No pude lanzar el workflow: HTTP {r.status_code} {html.escape(r.text[:500])}")


def search_plan_text():
    lines = ["<b>Qué estoy buscando</b>"]
    for g, vals in STACK_GROUPS.items():
        lines.append(f"\n<b>{html.escape(g)}</b>: {html.escape(', '.join(vals))}")
    lines.append("\n<b>Intención</b>: " + html.escape(", ".join(INTENT_TERMS)))
    lines.append("\n<b>Geo/remoto</b>: " + html.escape(", ".join(GEO_POSITIVE)))
    return "\n".join(lines)[:3900]


def handle_command(chat_id, text):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].split("@")[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    if cmd in {"/start", "/help"}:
        send(chat_id, (
            "<b>Freelance Lead Hunter</b>\n\n"
            "/leads — pendientes NEW\n/top — mejores NEW/SAVED\n/today — encontrados en 24h\n"
            "/source LinkedIn — filtrar fuente\n/stack go — filtrar tecnología\n"
            "/saved /applied /contacted /replied — estados\n/stats — embudo\n"
            "/searchplan — ver exactamente qué busca\n/refresh — ejecutar hunter ahora\n"
        ))
    elif cmd == "/leads":
        show_rows(chat_id, storage.list_leads(status="NEW", limit=10), "Leads pendientes")
    elif cmd == "/top":
        rows = [r for r in storage.list_leads(limit=30) if r.get("status") in {"NEW", "SAVED"}][:10]
        show_rows(chat_id, rows, "Top leads")
    elif cmd == "/today":
        show_rows(chat_id, storage.list_leads(limit=15, since_hours=24), "Últimas 24 horas")
    elif cmd == "/source":
        if not arg: send(chat_id, "Uso: <code>/source LinkedIn</code>"); return
        show_rows(chat_id, storage.list_leads(source=arg, limit=15), f"Fuente: {arg}")
    elif cmd == "/stack":
        if not arg: send(chat_id, "Uso: <code>/stack go</code> o <code>/stack kubernetes</code>"); return
        show_rows(chat_id, storage.list_by_text(arg, limit=15), f"Stack: {arg}")
    elif cmd in {"/saved", "/applied", "/contacted", "/replied"}:
        status = cmd[1:].upper()
        show_rows(chat_id, storage.list_leads(status=status, limit=15), status)
    elif cmd == "/stats":
        rows = storage.get_recent(limit=1000)
        c = Counter(r.get("status", "NEW") for r in rows)
        sources = Counter(r.get("source", "?") for r in rows)
        send(chat_id, (
            f"📊 <b>Stats</b>\nTotal: {len(rows)}\n"
            f"NEW: {c['NEW']} | SAVED: {c['SAVED']} | APPLIED: {c['APPLIED']}\n"
            f"CONTACTED: {c['CONTACTED']} | REPLIED: {c['REPLIED']} | CLIENT: {c['CLIENT']}\n\n"
            + "Fuentes: " + html.escape(", ".join(f"{k}:{v}" for k,v in sources.most_common(8)))
        ))
    elif cmd == "/searchplan":
        send(chat_id, search_plan_text())
    elif cmd == "/refresh":
        trigger_refresh(chat_id)
    else:
        send(chat_id, "No reconozco ese comando. Usa /help.")


def handle_callback(q):
    chat_id = q.get("message", {}).get("chat", {}).get("id")
    if not allowed(chat_id):
        return
    data = q.get("data", "")
    if data.startswith("status:"):
        _, lead_id, status = data.split(":", 2)
        row = storage.update_status(int(lead_id), status)
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": f"Estado: {status}"})
        if row:
            send(chat_id, f"✅ <b>{html.escape(row.get('title','')[:100])}</b> → {status}")


def main():
    print("Telegram bot running with long polling...")
    offset = None
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message", "callback_query"]}
            if offset is not None: params["offset"] = offset
            r = requests.get(f"{API}/getUpdates", params=params, timeout=60)
            r.raise_for_status()
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                if "callback_query" in update:
                    handle_callback(update["callback_query"]); continue
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                if not allowed(chat_id):
                    continue
                text = msg.get("text", "")
                if text.startswith("/"):
                    handle_command(chat_id, text)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Bot loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
