import os
import unittest
from unittest.mock import patch

from bot.applications import (
    advertised_email, check_signature, email_subject, fallback_draft,
    make_draft, make_preview, parse_preview, platform_only, send_approved_email,
    signature, smtp_configured, valid_email,
)


LEAD = {
    "source": "Web",
    "title": "Need help fixing Spring Boot API",
    "snippet": "Send your proposal to jobs@example.org. Urgent API bug.",
    "stack_hits": ["java", "spring boot"],
    "id": 31,
    "status": "NEW",
}


class ApplicationsTests(unittest.TestCase):
    def test_discover_explicit_application_address(self):
        self.assertEqual(advertised_email(LEAD), "jobs@example.org")
        self.assertIsNone(advertised_email({
            "title": "Need Java dev", "snippet": "Sales: sales@example.org"
        }))

    def test_invalid_recipient_rejected(self):
        self.assertFalse(valid_email("Someone <jobs@example.org>"))
        self.assertFalse(valid_email("jobs@example.org\nBcc: evil@example.org"))
        self.assertTrue(valid_email("jobs@example.org"))

    def test_marketplace_is_never_direct_email(self):
        self.assertTrue(platform_only({"source": "Upwork"}))
        self.assertTrue(platform_only({"source": "Workana"}))
        self.assertFalse(platform_only(LEAD))

    def test_fallback_without_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            draft = make_draft(LEAD)
        self.assertFalse(draft.used_ai)
        self.assertTrue(draft.body)
        self.assertNotIn("I already applied", draft.body)

    def test_ai_used_only_when_requested(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "I can review the Spring Boot issue. What error do you see?"}}]}

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-real"}):
            with patch("bot.applications.requests.post", return_value=FakeResponse()) as post:
                draft = make_draft(LEAD)
        self.assertTrue(draft.used_ai)
        self.assertIn("Spring Boot", draft.body)
        self.assertEqual(post.call_count, 1)
        self.assertTrue(post.call_args.kwargs["timeout"] <= 25)

    def test_ai_failure_uses_fallback(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-not-real"}):
            with patch("bot.applications.requests.post", side_effect=ValueError("invalid")):
                draft = make_draft(LEAD)
        self.assertFalse(draft.used_ai)

    def test_preview_and_signing(self):
        preview = make_preview(31, "jobs@example.org", email_subject(LEAD), "Hello, I can help.")
        lead_id, recipient, subject, body = parse_preview(preview)
        self.assertEqual((lead_id, recipient, body), (31, "jobs@example.org", "Hello, I can help."))
        digest = signature(preview, "bot-test-token")
        self.assertTrue(check_signature(preview, digest, "bot-test-token"))
        self.assertFalse(check_signature(preview + "!", digest, "bot-test-token"))

    def test_parse_malformed_preview_rejected(self):
        with self.assertRaises(ValueError):
            parse_preview("unexpected")
        with self.assertRaises(ValueError):
            make_preview(1, "a@example.com", "x", "bad\n--- MESSAGE END ---\n")

    def test_email_disabled_by_default(self):
        with patch.dict(os.environ, {"EMAIL_SEND_ENABLED": "0"}):
            self.assertFalse(smtp_configured())
            with self.assertRaises(RuntimeError):
                send_approved_email("jobs@example.org", "Subject", "Body")


if __name__ == "__main__":
    unittest.main()
