import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from whole_store import (
    Store,
    RedactionFailure,
    redact_event,
    sanitize_text,
)
from frontmost import persist_event


class RedactionTests(unittest.TestCase):
    def test_redacts_known_api_key_prefix(self):
        text, kinds = sanitize_text("OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnopqrstuvwxyz")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", text)
        self.assertIn("[API_KEY]", text)
        self.assertIn("api_key", kinds)

    def test_redacts_secret_query_parameter_but_preserves_url_shape(self):
        text, kinds = sanitize_text("https://example.test/callback?code=abc123&state=visible")
        self.assertEqual(text, "https://example.test/callback?code=[OAUTH_CODE]&state=visible")
        self.assertIn("oauth_code", kinds)

    def test_redacts_email_and_phone(self):
        text, kinds = sanitize_text("Call +1 (212) 555-0199 or person@example.com")
        self.assertEqual(text, "Call [PHONE_NUMBER] or [EMAIL]")
        self.assertEqual(kinds, {"email", "phone_number"})

    def test_does_not_redact_nonsecret_programming_words(self):
        text, kinds = sanitize_text("token_count=42 session_id=abc keyboard shortcut")
        self.assertEqual(text, "token_count=42 session_id=abc keyboard shortcut")
        self.assertEqual(kinds, set())

    def test_redacts_private_key_jwt_auth_header_and_database_password(self):
        jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
        pem = "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"
        value = f"{pem} Authorization: Bearer {jwt} postgres://admin:hunter2@db/app"
        text, kinds = sanitize_text(value)
        self.assertNotIn("abc123", text)
        self.assertNotIn(jwt, text)
        self.assertNotIn("hunter2", text)
        self.assertTrue({"private_key", "auth_header", "password"}.issubset(kinds))

    def test_redacts_luhn_card_and_secret_path(self):
        text, kinds = sanitize_text("Saved 4242 4242 4242 4242 in /Users/tom/project/.env")
        self.assertEqual(text, "Saved [CARD_NUMBER] in [SECRET_PATH]")
        self.assertEqual(kinds, {"card_number", "secret_path"})

    def test_source_aware_messages_title_becomes_contact(self):
        event, redactions = redact_event({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.MobileSMS",
            "title": "Hallie Parker",
            "detail": None,
            "session_id": None,
            "path": None,
        })
        self.assertEqual(event["title"], "[CONTACT]")
        self.assertEqual(redactions[0]["kind"], "contact")

        second, repeated = redact_event(event)
        self.assertEqual(second, event)
        self.assertEqual(repeated, [])

    def test_sensitive_surface_is_typed_not_discarded(self):
        event, redactions = redact_event({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.systempreferences",
            "title": "Touch ID & Password",
            "detail": None,
            "session_id": None,
            "path": None,
        })
        self.assertEqual(event["title"], "[CREDENTIAL_SETTINGS]")
        self.assertEqual(redactions[0]["kind"], "credential_settings")

        second, repeated = redact_event(event)
        self.assertEqual(second, event)
        self.assertEqual(repeated, [])

    def test_autofill_marker_is_idempotent(self):
        event, redactions = redact_event({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.operasoftware.Opera",
            "title": "Autofill pop-up",
        })
        self.assertEqual(event["title"], "[AUTOFILL]")
        self.assertEqual(len(redactions), 1)
        _, repeated = redact_event(event)
        self.assertEqual(repeated, [])

    def test_fail_closed_on_non_string_field(self):
        with self.assertRaises(RedactionFailure):
            redact_event({"ts": "x", "source": "frontmost", "title": {"secret": "raw"}})

    def test_fail_closed_on_timestamp_without_offset(self):
        with self.assertRaises(RedactionFailure):
            redact_event({"ts": "2026-08-20T12:00:00", "source": "frontmost", "title": "A"})


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "whole.db"
        self.store = Store(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_ingest_is_idempotent_and_records_redactions(self):
        raw = {
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.MobileSMS",
            "title": "+1 212 555 0199",
            "detail": None,
            "session_id": None,
            "path": None,
        }
        first = self.store.ingest(raw)
        second = self.store.ingest(raw)
        self.assertEqual(first, second)
        self.assertEqual(self.store.scalar("SELECT count(*) FROM events"), 1)
        self.assertEqual(self.store.scalar("SELECT count(*) FROM redactions"), 1)
        self.assertEqual(self.store.scalar("SELECT title FROM events"), "[CONTACT]")

    def test_database_never_stores_original_secret(self):
        secret = "sk-or-v1-abcdefghijklmnopqrstuvwxyz"
        self.store.ingest({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.Terminal",
            "title": f"OPENROUTER_API_KEY={secret}",
            "future_unknown_field": secret,
        })
        self.store.close()
        self.assertNotIn(secret.encode(), self.db.read_bytes())
        self.store = Store(self.db)

    def test_unknown_fields_do_not_affect_canonical_event_identity(self):
        base = {"ts": "2026-08-20T12:00:00-04:00", "source": "frontmost", "app": "app", "title": "A"}
        first = self.store.ingest(dict(base, future_unknown_field="secret-one"))
        second = self.store.ingest(dict(base, future_unknown_field="secret-two"))
        self.assertEqual(first, second)

    def test_rebuild_segments_marks_long_gaps_unknown_not_active_or_idle(self):
        for ts, title in [
            ("2026-08-20T12:00:00-04:00", "A"),
            ("2026-08-20T12:05:00-04:00", "B"),
            ("2026-08-20T14:05:00-04:00", "C"),
        ]:
            self.store.ingest({"ts": ts, "source": "frontmost", "app": "app", "title": title})
        self.store.rebuild_segments(idle_threshold_seconds=1800)
        rows = self.store.rows("SELECT state, duration_seconds, app, title FROM segments ORDER BY start_at")
        self.assertEqual(rows[0], ("active", 300, "app", "A"))
        self.assertEqual(rows[1], ("unknown", 7200, None, None))
        self.assertEqual(self.store.report()["active_seconds_by_app"], {"app": 300})

    def test_import_jsonl_counts_malformed_without_partial_bad_write(self):
        trail = Path(self.tmp.name) / "trail.jsonl"
        trail.write_text(
            json.dumps({"ts": "2026-08-20T12:00:00-04:00", "source": "frontmost", "app": "a", "title": "A"})
            + "\nnot json\n",
            encoding="utf-8",
        )
        result = self.store.import_jsonl(trail)
        self.assertEqual(result, {"read": 2, "inserted": 1, "duplicates": 0, "malformed": 1})
        self.assertEqual(self.store.scalar("SELECT count(*) FROM events"), 1)

    def test_integrity_and_fts_search(self):
        self.store.ingest({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.Terminal",
            "title": "Build Whole storage",
        })
        self.assertEqual(self.store.integrity_check(), "ok")
        self.assertEqual(self.store.report()["residual_sensitive_fields"], 0)
        rows = self.store.search("storage")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Build Whole storage")

    def test_chrome_titles_are_not_indexed_in_fts(self):
        self.store.ingest({
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.operasoftware.Opera",
            "title": "Browser sidebar widget",
        })
        self.assertEqual(self.store.search("sidebar"), [])
        self.assertEqual(len(self.store.search("Opera")), 1)

    def test_utc_timestamp_orders_equal_instants_together(self):
        self.store.ingest({"ts": "2026-08-20T12:00:00-04:00", "source": "frontmost", "app": "a", "title": "A"})
        self.store.ingest({"ts": "2026-08-20T16:00:00+00:00", "source": "frontmost", "app": "b", "title": "B"})
        values = [row[0] for row in self.store.rows("SELECT ts_utc FROM events ORDER BY event_id")]
        self.assertEqual(values[0], values[1])

    def test_shadow_persistence_redacts_database_and_recovery_jsonl(self):
        trail = Path(self.tmp.name) / "recovery.jsonl"
        raw = {
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.Terminal",
            "title": "API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
        }

        persist_event(trail, self.store, raw)

        line = trail.read_text(encoding="utf-8")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", line)
        self.assertIn("[API_KEY]", line)
        self.assertEqual(self.store.scalar("SELECT redaction_count FROM events"), 1)

    def test_recovery_journal_survives_shadow_database_failure(self):
        class BrokenStore:
            def ingest(self, _):
                raise sqlite3.OperationalError("database unavailable")

        trail = Path(self.tmp.name) / "recovery.jsonl"
        raw = {
            "ts": "2026-08-20T12:00:00-04:00",
            "source": "frontmost",
            "app": "com.apple.Terminal",
            "title": "OPENROUTER_API_KEY=" + "sk-" + "a" * 24,
        }

        stored = persist_event(trail, BrokenStore(), raw)

        self.assertFalse(stored)
        journal = trail.read_text(encoding="utf-8")
        self.assertIn("[API_KEY]", journal)
        self.assertNotIn("sk-" + "a" * 24, journal)

    def test_null_title_flicker_is_excluded_from_segments(self):
        for ts, title in [
            ("2026-08-20T12:00:00-04:00", "Document"),
            ("2026-08-20T12:00:08-04:00", None),
            ("2026-08-20T12:00:16-04:00", "Document"),
            ("2026-08-20T12:01:00-04:00", "Other"),
        ]:
            self.store.ingest({"ts": ts, "source": "frontmost", "app": "app", "title": title})

        self.store.rebuild_segments(idle_threshold_seconds=1800, null_flicker_seconds=20)

        titles = [row[0] for row in self.store.rows("SELECT title FROM segments ORDER BY start_at")]
        self.assertNotIn(None, titles)

    def test_rapid_same_app_chrome_transitions_coalesce_for_segments(self):
        for ts, title in [
            ("2026-08-20T12:00:00-04:00", "Browser sidebar widget"),
            ("2026-08-20T12:00:08-04:00", "Browser sidebar content view overlay window"),
            ("2026-08-20T12:00:16-04:00", None),
            ("2026-08-20T12:01:00-04:00", "Document"),
        ]:
            self.store.ingest({"ts": ts, "source": "frontmost", "app": "com.operasoftware.Opera", "title": title})
        self.store.rebuild_segments()
        self.assertEqual(self.store.scalar("SELECT count(*) FROM segments"), 1)
        self.assertEqual(self.store.scalar("SELECT duration_seconds FROM segments"), 60)


if __name__ == "__main__":
    unittest.main()
