"""Buyer-focused lead qualification. Pure functions; no API credentials required."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

BUYER_SIGNALS = (
    "need help", "need someone", "looking for someone", "looking to hire",
    "seeking a developer", "seeking a contractor", "hire a developer",
    "necesito", "busco desarrollador", "buscamos desarrollador", "busco programador",
    "contratar desarrollador", "contratar programador", "preciso de um desenvolvedor",
)
PROJECT_SIGNALS = (
    "freelance", "freelancer", "contractor", "contract", "project-based",
    "fixed price", "fixed-price", "one-time project", "short-term", "hourly",
    "por proyecto", "por horas", "presupuesto", "proyecto puntual",
)
AGENCY_SIGNALS = (
    "software agency", "development agency", "digital agency", "software studio",
    "agencia de software", "agencia de desarrollo", "staff augmentation",
)
BUDGET_SIGNALS = ("budget", "presupuesto", "fixed price", "fixed-price", "usd", "hourly rate")
REMOTE_SIGNALS = ("peru", "perú", "latam", "latin america", "worldwide", "anywhere", "global", "remote worldwide")
URGENCY_SIGNALS = ("urgent", "asap", "immediately", "urgente", "esta semana", "this week")
RESTRICTED_SIGNALS = (
    "us citizens only", "u.s. citizens only", "must be located in the us",
    "must be based in the us", "us residents only", "security clearance required",
    "onsite only", "on-site only", "no remote", "full-time onsite", "full time onsite",
    "only us applicants", "solo residentes de estados unidos",
)
GENERIC_TITLES = (
    "find freelance jobs", "hire freelancers", "freelance jobs online",
    "best freelance", "top backend jobs available", "top spring boot jobs available",
    "freelance jobs: work remote", "find jobs", "browse jobs",
)
MARKETPLACES = ("Upwork", "Freelancer", "Workana", "Contra")


def has_term(text: str, phrase: str) -> bool:
    """Whole-token match (Go must not match Google, SQL not PostgreSQL)."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.IGNORECASE))


def hits(text: str, phrases) -> list[str]:
    return [phrase for phrase in phrases if has_term(text, phrase)]


def is_restricted(text: str) -> bool:
    return bool(hits(text, RESTRICTED_SIGNALS))


def category(source: str, title: str, snippet: str, url: str = "") -> str:
    text = f"{title} {snippet}"
    path = url.lower()
    if hits(text, BUYER_SIGNALS):
        return "CLIENTE_DIRECTO"
    if source in MARKETPLACES and any(x in path for x in ("/jobs/", "/job/", "/projects/", "/freelance-jobs/apply")):
        return "PROYECTO_FREELANCE"
    if hits(text, AGENCY_SIGNALS):
        return "AGENCIA"
    if hits(text, PROJECT_SIGNALS):
        return "PROYECTO_POR_VALIDAR"
    if source in ("Remotive", "RemoteOK", "Arbeitnow"):
        return "EMPLEO_REMOTO"
    return "SIN_INTENCION_CONFIRMADA"


def evaluate(source: str, title: str, snippet: str, url: str, stack: list[str], generic: bool = False):
    """Return (score 0..10, lead_type, reasons, worth_notifying)."""
    text = f"{title} {snippet}"
    kind = category(source, title, snippet, url)
    if generic or any(has_term(title, x) for x in GENERIC_TITLES):
        return 0, kind, ["página genérica, no publicación verificable"], False
    if is_restricted(text):
        return 0, kind, ["restricción explícita de ubicación/elegibilidad"], False

    base = {"CLIENTE_DIRECTO": 4, "PROYECTO_FREELANCE": 3,
            "AGENCIA": 2, "PROYECTO_POR_VALIDAR": 2,
            "EMPLEO_REMOTO": 1, "SIN_INTENCION_CONFIRMADA": 0}[kind]
    reasons = [f"tipo: {kind} (+{base})"]
    score = base
    if stack:
        points = min(2, len(stack))
        score += points
        reasons.append(f"stack relevante +{points}: {', '.join(stack[:5])}")
    budget = bool(hits(text, BUDGET_SIGNALS)) or bool(re.search(r"(?:US\$|\$|€)\s*\d", text))
    if budget:
        score += 2
        reasons.append("mención de presupuesto/tarifa +2 (sin verificar monto)")
    if hits(text, REMOTE_SIGNALS):
        score += 1
        reasons.append("señal geográfica favorable +1 (elegibilidad por confirmar)")
    if hits(text, URGENCY_SIGNALS):
        score += 1
        reasons.append("urgencia +1")
    score = min(10, score)
    notify = kind in {"CLIENTE_DIRECTO", "PROYECTO_FREELANCE", "AGENCIA", "PROYECTO_POR_VALIDAR"} and bool(stack)
    return score, kind, reasons, notify


def posted_at(value: str, now: datetime | None = None) -> datetime | None:
    """Parse source date conservatively. Unknown dates remain unknown."""
    if not value or not value.strip():
        return None
    now = now or datetime.now(timezone.utc)
    text = value.strip().lower()
    if text in {"today", "hoy", "just now", "ahora"}:
        return now
    if text in {"yesterday", "ayer"}:
        return now - timedelta(days=1)
    unit_pattern = (r"(\d+)\s*(minutes?|mins?|hours?|hrs?|days?|weeks?|months?|"
                    r"minutos?|horas?|d[ií]as?|semanas?|meses?)\s*(?:ago|hace)?")
    m = re.fullmatch(unit_pattern, text)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith(("min",)):
            return now - timedelta(minutes=n)
        if unit.startswith(("hour", "hr", "hora")):
            return now - timedelta(hours=n)
        if unit.startswith(("day", "dí", "di")):
            return now - timedelta(days=n)
        if unit.startswith(("week", "semana")):
            return now - timedelta(weeks=n)
        return now - timedelta(days=n * 30)
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def is_recent(value: str, max_age_hours: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    when = posted_at(value, now)
    if when is None:
        return True  # Unknown, not confirmed recent; display source date for manual verification.
    delta = now - when
    return timedelta(hours=-1) <= delta <= timedelta(hours=max_age_hours)


def suggested_message(title: str, stack: list[str], text: str = "") -> str:
    """Honest template, not a claim of verified requirements or availability."""
    focus = ", ".join(stack[:3]) or "backend y automatización"
    is_spanish = bool(hits(f"{title} {text}", ("necesito", "busco", "buscamos", "proyecto", "desarrollador", "presupuesto")))
    if is_spanish:
        return (f"Hola, vi tu publicación sobre {title[:80]}. Tengo experiencia en {focus}. "
                "¿Podrías compartir alcance, fecha límite y presupuesto? "
                "Puedo proponerte un primer entregable pequeño con precio cerrado.")
    return (f"Hi, I saw your post about {title[:80]}. I have experience with {focus}. "
            "Could you share the scope, deadline, and budget? "
            "I can propose a small fixed-price first milestone.")
