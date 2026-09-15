from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


class SupabaseStorage:
    def __init__(self):
        self.base = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not self.base or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for V4 shared state.")
        self.rest = f"{self.base}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, params=None, json=None, prefer: str | None = None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        r = requests.request(method, f"{self.rest}/{path}", headers=headers, params=params, json=json, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Supabase {method} {path}: HTTP {r.status_code} {r.text[:1000]}")
        if not r.text:
            return None
        return r.json()

    def insert_if_new(self, lead: dict[str, Any]) -> dict[str, Any] | None:
        # ignore-duplicates + return=representation lets us detect whether this URL was newly inserted.
        rows = self._request(
            "POST",
            "leads",
            params={"on_conflict": "url"},
            json=lead,
            prefer="resolution=ignore-duplicates,return=representation",
        ) or []
        return rows[0] if rows else None

    def list_leads(self, *, status: str | None = None, source: str | None = None,
                   limit: int = 10, min_score: int | None = None,
                   since_hours: int | None = None) -> list[dict[str, Any]]:
        params: list[tuple[str, str]] = [
            ("select", "*"),
            ("order", "score.desc,found_at.desc"),
            ("limit", str(max(1, min(limit, 200)))),
        ]
        if status:
            params.append(("status", f"eq.{status}"))
        if source:
            params.append(("source", f"ilike.{source}"))
        if min_score is not None:
            params.append(("score", f"gte.{min_score}"))
        if since_hours is not None:
            ts = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
            params.append(("found_at", f"gte.{ts}"))
        return self._request("GET", "leads", params=params) or []

    def get_recent(self, limit: int = 500) -> list[dict[str, Any]]:
        return self.list_leads(limit=limit)

    def update_status(self, lead_id: int, status: str) -> dict[str, Any] | None:
        rows = self._request(
            "PATCH", "leads",
            params={"id": f"eq.{lead_id}"},
            json={"status": status, "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=representation",
        ) or []
        return rows[0] if rows else None

    def mark_notified(self, lead_id: int):
        self._request(
            "PATCH", "leads", params={"id": f"eq.{lead_id}"},
            json={"notified": True, "updated_at": datetime.now(timezone.utc).isoformat()},
            prefer="return=minimal",
        )

    def list_by_text(self, term: str, *, limit: int = 10, status: str | None = None) -> list[dict[str, Any]]:
        # Fetch a bounded recent set and filter client-side to avoid fragile PostgREST OR escaping.
        rows = self.list_leads(status=status, limit=200)
        q = term.lower().strip()
        return [r for r in rows if q in " ".join([
            str(r.get("title", "")), str(r.get("snippet", "")),
            " ".join(r.get("stack_hits") or []), str(r.get("reasons", "")),
        ]).lower()][:limit]
