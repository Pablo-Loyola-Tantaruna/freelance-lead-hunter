import unittest
from datetime import datetime, timezone

from hunter.qualification import category, evaluate, has_term, is_recent, posted_at, suggested_message


class QualificationTests(unittest.TestCase):
    def test_short_keywords_do_not_match_substrings(self):
        self.assertFalse(has_term("Google Kubernetes", "go"))
        self.assertTrue(has_term("Go engineer", "go"))
        self.assertFalse(has_term("PostgreSQL", "sql"))

    def test_direct_buyer_outscores_generic_technologies(self):
        result = evaluate("LinkedIn", "Need help fixing Spring Boot API",
                          "urgent, budget $300, remote LATAM", "https://linkedin.com/posts/abc", ["spring boot"])
        self.assertEqual(result[1], "CLIENTE_DIRECTO")
        self.assertGreaterEqual(result[0], 6)
        self.assertTrue(result[3])

    def test_generic_job_board_not_notified(self):
        result = evaluate("RemoteOK", "Senior Java developer",
                          "remote worldwide $3000 per month", "https://remoteok.com/a", ["java"])
        self.assertFalse(result[3])

    def test_query_text_not_used_as_buyer_intent(self):
        result = evaluate("Web", "Building backend tips", "Spring Boot", "https://example.com/a", ["spring boot"])
        self.assertFalse(result[3])

    def test_marketplace_only_when_concrete_listing(self):
        self.assertEqual(category("Upwork", "Fix Java bug", "", "https://www.upwork.com/freelance-jobs/apply/x"), "PROYECTO_FREELANCE")
        self.assertEqual(category("Upwork", "Java Jobs", "", "https://www.upwork.com/freelance-jobs/"), "SIN_INTENCION_CONFIRMADA")

    def test_restricted_location_is_rejected(self):
        result = evaluate("LinkedIn", "Need help with Java", "US citizens only", "https://linkedin.com/posts/x", ["java"])
        self.assertEqual(result[0], 0)
        self.assertFalse(result[3])

    def test_generic_is_rejected(self):
        result = evaluate("Web", "Find freelance jobs", "need help java", "https://example.com", ["java"], generic=True)
        self.assertEqual(result[0], 0)

    def test_iso_and_relative_dates(self):
        now = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(is_recent("2 hours ago", 48, now))
        self.assertFalse(is_recent("3 days ago", 48, now))
        self.assertFalse(is_recent("2026-10-27T00:00:00Z", 48, now))
        self.assertTrue(is_recent("unknown date", 48, now))
        self.assertEqual(posted_at("ayer", now).day, 31)

    def test_spanish_message(self):
        msg = suggested_message("Busco desarrollador Java", ["java"])
        self.assertIn("¿Podrías", msg)
        self.assertIn("precio cerrado", msg)


if __name__ == "__main__":
    unittest.main()
