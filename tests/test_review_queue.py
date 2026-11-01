"""Checks that the review queue preserves useful, recent V5/V6 leads."""
import unittest
from unittest.mock import MagicMock

from storage.supabase import SupabaseStorage
from hunter.lead_hunter import search_locale


class ReviewQueueTests(unittest.TestCase):
    def test_filters_out_remote_jobs_and_old_scoring(self):
        storage = object.__new__(SupabaseStorage)
        items = [
            {"id": 1, "score": 6, "reasons": "tipo: PROYECTO_FREELANCE (+3); stack relevante +2"},
            {"id": 2, "score": 8, "reasons": "tipo: EMPLEO_REMOTO (+1); stack relevante +2"},
            {"id": 3, "score": 7, "reasons": "stack +6: java"},
            {"id": 4, "score": 5, "reasons": "tipo: CLIENTE_DIRECTO (+4); stack relevante +1"},
        ]
        storage._request = MagicMock(return_value=items)
        result = storage.list_qualified_for_review(min_score=5, since_hours=72, limit=5)
        self.assertEqual([row["id"] for row in result], [1, 4])
        args = storage._request.call_args
        self.assertEqual(args.args[:2], ("GET", "leads"))
        params = dict(args.kwargs["params"])
        self.assertEqual(params["score"], "gte.5")
        self.assertEqual(params["status"], "in.(NEW,SAVED)")
        self.assertEqual(params["reasons"], "like.*tipo:*")

    def test_review_queue_caps_output(self):
        storage = object.__new__(SupabaseStorage)
        storage._request = MagicMock(return_value=[
            {"id": i, "score": 5, "reasons": "tipo: PROYECTO_FREELANCE (+3)"}
            for i in range(30)
        ])
        result = storage.list_qualified_for_review(limit=5)
        self.assertEqual(len(result), 5)

    def test_spanish_queries_use_peru_search_locale(self):
        self.assertEqual(search_locale('busco desarrollador Java freelance'), ("pe", "es"))
        self.assertEqual(search_locale('site:linkedin.com/posts "necesito" Java'), ("pe", "es"))

    def test_english_queries_use_default_search_locale(self):
        gl, hl = search_locale("freelance Spring Boot developer")
        self.assertEqual((gl, hl), ("us", "en"))

    def test_pending_notifications_accept_five_point_buyer(self):
        storage = object.__new__(SupabaseStorage)
        storage._request = MagicMock(return_value=[
            {"id": 1, "score": 5, "reasons": "tipo: PROYECTO_FREELANCE (+3)"},
            {"id": 2, "score": 6, "reasons": "tipo: EMPLEO_REMOTO (+1)"},
        ])
        result = storage.get_pending_notifications(min_score=5, since_hours=48, limit=5)
        self.assertEqual([r["id"] for r in result], [1])


if __name__ == "__main__":
    unittest.main()
