from __future__ import annotations

import html
import os
import time
from collections import Counter
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from hunter.config import GEO_POSITIVE, INTENT_TERMS, STACK_GROUPS
from bot.applications import (
    advertised_email, check_signature, email_subject, make_draft, make_preview,
    parse_preview, platform_only, send_approved_email, signature, smtp_configured,
    valid_email,
)
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
        [{"text": "🤖 Preparar candidatura", "callback_data": f"pitch:{r['id']}"}],
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



def get_lead_or_notify(chat_id, lead_id: int):
    lead = storage.get_lead(lead_id)
    if not lead:
        send(chat_id, f"⚠️ No encontré la oportunidad #{lead_id}.")
    return lead


def show_pitch(chat_id, lead_id: int):
    lead = get_lead_or_notify(chat_id, lead_id)
    if not lead:
        return
    draft = make_draft(lead)
    label = "IA" if draft.used_ai else "Plantilla (configura OPENAI_API_KEY para IA)"
    body = (
        f"🤖 <b>Propuesta para #{lead_id}</b> — {html.escape(label)}\n"
        f"<b>{html.escape(str(lead.get('title') or '')[:140])}</b>\n\n"
        f"{html.escape(draft.body)}\n\n"
        "⚠️ Revisa el anuncio y personaliza antes de enviarla. No se ha postulado automáticamente."
    )
    keyboard = {"inline_keyboard": [
        [{"text": "🔗 Abrir oferta y postular", "url": lead["url"]}],
    ]}
    address = advertised_email(lead) if not platform_only(lead) else None
    if address:
        keyboard["inline_keyboard"].append([
            {"text": "✉️ Preparar correo a dirección anunciada",
             "callback_data": f"prepareemail:{lead_id}"}
        ])
    if not platform_only(lead):
        body += (f"\n\nPara un email distinto expresamente indicado en el anuncio:"
                 f" <code>/email {lead_id} destino@empresa.com</code>")
    send(chat_id, body, keyboard)


def start_email_review(chat_id, lead_id: int, recipient: str):
    lead = get_lead_or_notify(chat_id, lead_id)
    if not lead:
        return
    if platform_only(lead):
        send(chat_id, "⚠️ Ese marketplace exige postular por su propia plataforma. Usa /pitch y Abrir.")
        return
    if lead.get("status") not in {"NEW", "SAVED"}:
        send(chat_id, "⚠️ Este lead ya tiene un estado de postulación/contacto. No enviaré dos veces.")
        return
    if not valid_email(recipient):
        send(chat_id, "⚠️ Dirección de correo inválida.")
        return
    draft = make_draft(lead)
    preview = make_preview(lead_id, recipient, email_subject(lead), draft.body)
    digest = signature(preview, TOKEN)
    keyboard = {"inline_keyboard": [
        [{"text": "✅ CONFIRMAR Y ENVIAR EMAIL", "callback_data": f"sendemail:{lead_id}:{digest}"}],
        [{"text": "❌ Cancelar", "callback_data": f"cancelmail:{lead_id}"}],
        [{"text": "🔗 Revisar oferta original", "url": lead["url"]}],
    ]}
    if not smtp_configured():
        send(chat_id, "ℹ️ El envío por correo aún no está habilitado en el servidor. "
                      "Puedes revisar/copiar la propuesta; configura EMAIL_SEND_ENABLED y SMTP para activar el envío.")
    send(chat_id, html.escape(preview), keyboard)


def confirm_email(q, chat_id):
    """Authenticated one-message preview + explicit user click, never a bulk/scheduled action."""
    if q.get("message", {}).get("chat", {}).get("type") != "private":
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Solo disponible en chat privado"})
        return
    parts = q.get("data", "").split(":")
    if len(parts) != 3:
        return
    try:
        lead_id = int(parts[1])
        raw = q.get("message", {}).get("text") or ""
        if not check_signature(raw, parts[2], TOKEN):
            raise ValueError("El borrador fue modificado o no es válido")
        preview_id, recipient, subject, body = parse_preview(raw)
        if preview_id != lead_id:
            raise ValueError("No coincide el ID del lead")
        age = time.time() - int(q.get("message", {}).get("date", 0))
        if age < -60 or age > 24 * 3600:
            raise ValueError("Confirmación vencida: vuelve a preparar el correo")
    except (ValueError, TypeError, OverflowError) as exc:
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Revisión inválida o vencida"})
        send(chat_id, f"⚠️ {html.escape(str(exc))}")
        return
    tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Procesando envío aprobado"})
    lead = get_lead_or_notify(chat_id, lead_id)
    if not lead or platform_only(lead):
        send(chat_id, "⚠️ Este lead no admite correo directo.")
        return
    old_status = lead.get("status")
    if old_status not in {"NEW", "SAVED"}:
        send(chat_id, "⚠️ Este lead ya fue postulado/contactado, no se repetirá el envío.")
        return
    if not smtp_configured():
        send(chat_id, "⚠️ Falta activar y configurar SMTP en el servidor; no se envió correo.")
        return
    claimed = storage.claim_for_contact(lead_id)
    if not claimed:
        send(chat_id, "⚠️ Otro envío ya reclamó este lead. No se duplicó el correo.")
        return
    try:
        send_approved_email(recipient, subject, body)
    except Exception as exc:
        # SMTP timeouts can have ambiguous delivery outcomes; check Sent before retrying.
        try:
            storage.release_failed_contact(lead_id, old_status)
        except Exception as release_err:
            print(f"Could not release claim for {lead_id}: {type(release_err).__name__}")
        print(f"Approved email send failed: {type(exc).__name__}")
        send(chat_id, "❌ No pude confirmar el envío. Verifica configuración y carpeta Enviados "
                      "antes de reintentar; algunas fallas de red dejan resultado incierto.")
        return
    storage.update_status(lead_id, "CONTACTED")
    message = q.get("message", {})
    try:
        tg("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message["message_id"],
            "reply_markup": {"inline_keyboard": []},
        })
    except Exception:
        pass
    send(chat_id, f"✅ Email enviado al destinatario aprobado: <b>{html.escape(recipient)}</b>. "
                  f"Lead #{lead_id} marcado como CONTACTED.")


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
            "/searchplan — búsquedas\n/refresh — ejecutar hunter\n"
            "/queue — mejores proyectos (72h)\n/backlog — historial reciente (7 días)\n/pitch ID — propuesta IA\n"
            "/email ID correo@empresa.com — revisar y aprobar correo\n"
        ))
    elif cmd == "/queue":
        rows = storage.list_qualified_for_review(limit=5, min_score=5, since_hours=72)
        show_rows(chat_id, rows, "5 oportunidades priorizadas (72h)")
    elif cmd == "/backlog":
        rows = storage.list_qualified_for_review(limit=15, min_score=4, since_hours=168)
        show_rows(chat_id, rows, "Backlog de oportunidades (7 días)")
    elif cmd == "/pitch":
        if not arg.isdigit():
            send(chat_id, "Uso: <code>/pitch 123</code>")
            return
        show_pitch(chat_id, int(arg))
    elif cmd == "/email":
        parts_email = arg.split(maxsplit=1)
        if len(parts_email) != 2 or not parts_email[0].isdigit():
            send(chat_id, "Uso: <code>/email 123 apply@empresa.com</code>")
            return
        start_email_review(chat_id, int(parts_email[0]), parts_email[1].strip())
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
    if data.startswith("pitch:"):
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Preparando propuesta"})
        try:
            show_pitch(chat_id, int(data.split(":", 1)[1]))
        except (ValueError, TypeError):
            send(chat_id, "⚠️ Identificador de lead inválido.")
        return
    if data.startswith("prepareemail:"):
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Preparando correo"})
        try:
            lead_id = int(data.split(":", 1)[1])
        except (ValueError, TypeError):
            return
        lead = get_lead_or_notify(chat_id, lead_id)
        address = advertised_email(lead) if lead and not platform_only(lead) else None
        if address:
            start_email_review(chat_id, lead_id, address)
        else:
            send(chat_id, "⚠️ El anuncio no contiene una dirección explícita de postulación por email.")
        return
    if data.startswith("sendemail:"):
        confirm_email(q, chat_id)
        return
    if data.startswith("cancelmail:"):
        tg("answerCallbackQuery", {"callback_query_id": q["id"], "text": "Envío cancelado"})
        send(chat_id, "❌ Correo cancelado. No se envió ninguna candidatura.")
        return
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
