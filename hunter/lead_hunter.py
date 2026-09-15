from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv

from hunter.config import (
    CORE_QUERIES, DIRECT_NEED_TERMS, GENERIC_PAGE_PATTERNS, GEO_POSITIVE,
    INTENT_TERMS, MARKETPLACE_SOURCES, NEGATIVE_TERMS, QUERY_GROUPS, STACK,
)
from storage.supabase import SupabaseStorage

load_dotenv()

MIN_SCORE = int(os.getenv("MIN_SCORE", "4"))
NOTIFY_SCORE = int(os.getenv("NOTIFY_SCORE", "6"))
DEBUG = os.getenv("DEBUG", "1").lower() not in {"0", "false", "no"}
MAX_AGE_HOURS = int(os.getenv("MAX_AGE_HOURS", "48"))

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "").strip()
SERPER_GL = os.getenv("SERPER_GL", "us").strip() or "us"
SERPER_HL = os.getenv("SERPER_HL", "en").strip() or "en"
SERPER_TBS = os.getenv("SERPER_TBS", "qdr:d").strip()
SERPER_NUM = max(1, min(100, int(os.getenv("SERPER_NUM", "10"))))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_PUSH_MAX = max(1, min(20, int(os.getenv("TELEGRAM_PUSH_MAX", "8"))))

OUT_DIR = Path(os.getenv("OUT_DIR", "."))
CSV_PATH = OUT_DIR / "leads.csv"
HTML_PATH = OUT_DIR / "leads.html"
LINKS_PATH = OUT_DIR / "links.txt"


@dataclass
class Lead:
    source: str
    title: str
    url: str
    snippet: str
    published_text: str = ""
    query: str = ""
    score: int = 0
    reasons: str = ""
    stack_hits: list[str] | None = None
    intent_hits: list[str] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def normalize_url(url: str) -> str:
    try:
        s = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "trk"}]
        return urlunsplit((s.scheme.lower(), s.netloc.lower(), s.path.rstrip("/"), urlencode(query), ""))
    except Exception:
        return url


def looks_generic(lead: Lead) -> bool:
    title = normalize(lead.title)
    if any(x in title for x in GENERIC_PAGE_PATTERNS):
        return True
    u = lead.url.lower()
    if lead.source == "Upwork" and "/freelance-jobs/apply" not in u and "/jobs/" not in u:
        return True
    return False


def score_lead(lead: Lead) -> Lead:
    text = normalize(f"{lead.title} {lead.snippet}")
    query = normalize(lead.query)
    score = 0
    reasons: list[str] = []

    stack_hits = sorted({kw for kw in STACK if kw in text})
    lead.stack_hits = stack_hits
    if stack_hits:
        # Reward breadth, cap so one verbose post doesn't dominate.
        stack_score = min(6, 1 + len(stack_hits) // 2)
        score += stack_score
        reasons.append(f"stack +{stack_score}: {', '.join(stack_hits[:8])}")

    intent_hits = sorted({kw for kw in INTENT_TERMS if kw in text})
    lead.intent_hits = intent_hits
    if intent_hits:
        intent_score = min(4, 1 + len(intent_hits) // 2)
        score += intent_score
        reasons.append(f"intent +{intent_score}: {', '.join(intent_hits[:6])}")

    if any(term in text for term in DIRECT_NEED_TERMS):
        score += 2
        reasons.append("direct need +2")

    if query:
        if any(x in query for x in ["looking for", "need help", "looking for someone", "need someone"]):
            score += 2
            reasons.append("search intent +2")
        elif any(x in query for x in ["contract", "contractor", "consultant", "freelance"]):
            score += 1
            reasons.append("search intent +1")

    if lead.source in MARKETPLACE_SOURCES:
        score += 2
        reasons.append("freelance marketplace +2")

    geo_hits = sorted({x for x in GEO_POSITIVE if x in text})
    if geo_hits:
        score += min(2, len(geo_hits))
        reasons.append(f"geo/remote +{min(2, len(geo_hits))}: {', '.join(geo_hits[:4])}")

    if any(x in text for x in ["usd", "$", "dollar", "hourly rate", "/hr", "per hour"]):
        score += 1
        reasons.append("USD/rate +1")

    neg_hits = [kw for kw in NEGATIVE_TERMS if kw in text]
    if neg_hits:
        score -= 5
        reasons.append(f"constraints -5: {', '.join(neg_hits[:3])}")

    if looks_generic(lead):
        score -= 7
        reasons.append("generic/search page -7")

    lead.score = max(0, score)
    lead.reasons = "; ".join(reasons)
    return lead


def source_for_url(url: str) -> str:
    u = url.lower()
    if "linkedin.com" in u: return "LinkedIn"
    if "upwork.com" in u: return "Upwork"
    if "freelancer.com" in u: return "Freelancer"
    if "workana.com" in u: return "Workana"
    if "contra.com" in u: return "Contra"
    return "Web"


def serper_search(query: str) -> Iterable[Lead]:
    payload = {"q": query, "num": SERPER_NUM, "gl": SERPER_GL, "hl": SERPER_HL}
    if SERPER_TBS:
        payload["tbs"] = SERPER_TBS
    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Serper HTTP {r.status_code}: {r.text[:1000]}")
    out = []
    for item in r.json().get("organic", []):
        url = item.get("link") or ""
        if not url:
            continue
        out.append(Lead(
            source=source_for_url(url), title=item.get("title", ""), url=normalize_url(url),
            snippet=item.get("snippet", ""), published_text=item.get("date", ""), query=query,
        ))
    return out


def remotive_jobs() -> Iterable[Lead]:
    try:
        r = requests.get("https://remotive.com/api/remote-jobs", params={"search": "backend"}, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Remotive error: {e}")
        return []
    out = []
    for j in r.json().get("jobs", [])[:100]:
        out.append(Lead(
            source="Remotive", title=j.get("title", ""), url=normalize_url(j.get("url", "")),
            snippet=" ".join(filter(None, [j.get("company_name", ""), j.get("candidate_required_location", ""), j.get("job_type", ""), j.get("description", "")[:700]])),
            published_text=j.get("publication_date", ""),
        ))
    return out


def arbeitnow_jobs() -> Iterable[Lead]:
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Arbeitnow error: {e}")
        return []
    out = []
    for j in r.json().get("data", [])[:100]:
        out.append(Lead(
            source="Arbeitnow", title=j.get("title", ""), url=normalize_url(j.get("url", "")),
            snippet=" ".join(filter(None, [j.get("company_name", ""), j.get("location", ""), "remote" if j.get("remote") else "", " ".join(j.get("tags", []) or [])])),
            published_text=str(j.get("created_at", "")),
        ))
    return out


def remoteok_jobs() -> Iterable[Lead]:
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status(); data = r.json()
    except Exception as e:
        print(f"RemoteOK error: {e}")
        return []
    out = []
    for j in data[1:101] if isinstance(data, list) else []:
        if not isinstance(j, dict):
            continue
        out.append(Lead(
            source="RemoteOK", title=j.get("position", ""), url=normalize_url(j.get("url", "")),
            snippet=" ".join(filter(None, [j.get("company", ""), j.get("location", ""), " ".join(j.get("tags", []) or []), j.get("description", "")[:500]])),
            published_text=j.get("date", ""),
        ))
    return out


def current_query_group() -> tuple[str, list[str]]:
    names = list(QUERY_GROUPS)
    slot = (datetime.now(timezone.utc).hour // 3) % len(names)
    name = names[slot]
    return name, CORE_QUERIES + QUERY_GROUPS[name]


def as_row(lead: Lead) -> dict:
    return {
        "source": lead.source,
        "title": lead.title[:500],
        "url": lead.url,
        "url_hash": hashlib.sha256(lead.url.encode("utf-8")).hexdigest(),
        "snippet": lead.snippet[:4000],
        "published_text": lead.published_text[:200],
        "score": lead.score,
        "reasons": lead.reasons[:2000],
        "stack_hits": lead.stack_hits or [],
        "intent_hits": lead.intent_hits or [],
        "query": lead.query[:1000],
        "status": "NEW",
        "notified": False,
        "found_at": now_iso(),
        "updated_at": now_iso(),
    }


def telegram_send_lead(row: dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    text = (
        f"🔥 <b>{html.escape(str(row['score']))}/10+ — {html.escape(row['source'])}</b>\n"
        f"<b>{html.escape(row['title'][:180])}</b>\n\n"
        f"{html.escape(', '.join((row.get('stack_hits') or [])[:8]))}\n"
        f"{html.escape((row.get('reasons') or '')[:700])}"
    )
    keyboard = {"inline_keyboard": [
        [{"text": "🔗 Abrir", "url": row["url"]}],
        [
            {"text": "⭐ Guardar", "callback_data": f"status:{row['id']}:SAVED"},
            {"text": "✅ Apliqué", "callback_data": f"status:{row['id']}:APPLIED"},
            {"text": "❌ Descartar", "callback_data": f"status:{row['id']}:DISCARDED"},
        ]
    ]}
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": keyboard},
        timeout=30,
    )
    r.raise_for_status()


def write_exports(storage: SupabaseStorage):
    rows = storage.get_recent(limit=500)
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        cols = ["id", "source", "title", "url", "score", "status", "found_at", "published_text", "stack_hits", "reasons"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(r.get(k), ensure_ascii=False) if isinstance(r.get(k), (list, dict)) else r.get(k, "") for k in cols})
    with LINKS_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(f"[{r.get('score')}] {r.get('source')} | {r.get('title')}\n{r.get('url')}\n\n")
    cards = []
    for r in rows:
        cards.append(f"<article><b>[{r.get('score')}] {html.escape(r.get('source',''))}</b> — {html.escape(r.get('status',''))}<h3>{html.escape(r.get('title',''))}</h3><p>{html.escape((r.get('reasons') or '')[:700])}</p><a href=\"{html.escape(r.get('url',''), quote=True)}\">Abrir ↗</a></article>")
    HTML_PATH.write_text("<meta charset='utf-8'><style>body{font-family:Arial;max-width:1000px;margin:auto;padding:20px}article{border:1px solid #ddd;padding:14px;margin:10px;border-radius:10px}a{color:#2563eb}</style><h1>Freelance Lead Hunter V4</h1>" + "".join(cards), encoding="utf-8")


def main():
    storage = SupabaseStorage()
    group_name, queries = current_query_group()
    print(f"Query rotation group: {group_name}")
    print(f"Serper queries this run: {len(queries)}")

    candidates: list[Lead] = []
    for fn in (remotive_jobs, arbeitnow_jobs, remoteok_jobs):
        for lead in fn():
            if lead.url:
                candidates.append(score_lead(lead))

    if SERPER_API_KEY:
        for q in queries:
            try:
                results = list(serper_search(q))
                print(f"Serper: {len(results):2d} | {q}")
                candidates.extend(score_lead(x) for x in results)
            except Exception as e:
                print(f"Serper error: {q!r}: {e}")
    else:
        print("SERPER_API_KEY missing: only public job APIs will be searched.")

    best: dict[str, Lead] = {}
    for lead in candidates:
        if lead.score < MIN_SCORE or not lead.url:
            continue
        old = best.get(lead.url)
        if old is None or lead.score > old.score:
            best[lead.url] = lead

    new_rows = []
    for lead in sorted(best.values(), key=lambda x: x.score, reverse=True):
        inserted = storage.insert_if_new(as_row(lead))
        if inserted:
            new_rows.append(inserted)

    write_exports(storage)
    notifiable = [r for r in new_rows if int(r.get("score") or 0) >= NOTIFY_SCORE][:TELEGRAM_PUSH_MAX]
    for row in notifiable:
        try:
            telegram_send_lead(row)
            storage.mark_notified(int(row["id"]))
        except Exception as e:
            print(f"Telegram notification error for lead {row.get('id')}: {e}")

    print(f"Candidates: {len(candidates)} | above threshold unique: {len(best)} | new: {len(new_rows)} | pushed: {len(notifiable)}")
    if DEBUG:
        for lead in sorted(best.values(), key=lambda x: x.score, reverse=True)[:15]:
            print(f"[{lead.score}] {lead.source}: {lead.title[:100]} | {lead.reasons}")


if __name__ == "__main__":
    main()
