from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from db.audit import list_audit_events, record_audit_event


class AuditTest(TestCase):
    def test_records_safe_event_in_supplied_transaction(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {"event_id": 81}

        event_id = record_audit_event(
            cursor=cursor,
            actor_id=7,
            action="user.password_reset",
            entity_type="user",
            entity_id=12,
        )

        self.assertEqual(event_id, 81)
        params = cursor.execute.call_args.args[1]
        self.assertEqual(params[0], 7)
        self.assertEqual(params[3:7], ("user.password_reset", "user", "12", "success"))

    def test_rejects_sensitive_detail_names(self):
        cursor = MagicMock()
        with self.assertRaises(ValueError):
            record_audit_event(
                cursor=cursor,
                action="auth.login",
                entity_type="session",
                details={"password": "nao deve entrar"},
            )
        cursor.execute.assert_not_called()

    def test_listing_rechecks_current_admin_role(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("db.audit.get_conn", return_value=manager):
            with self.assertRaises(PermissionError):
                list_audit_events(4)

        self.assertEqual(cursor.execute.call_args.args[1], (4,))

    def test_lists_recent_events_for_admin(self):
        now = datetime.now(timezone.utc)
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"authorized": 1}
        cursor.__iter__.return_value = iter(
            [
                {
                    "event_id": 9,
                    "occurred_at": now,
                    "actor_label": "gerson",
                    "action": "auth.login",
                    "entity_type": "session",
                    "entity_id": None,
                    "outcome": "success",
                    "details": {},
                }
            ]
        )
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("db.audit.get_conn", return_value=manager):
            events = list_audit_events(1, 25)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].action, "auth.login")
        self.assertEqual(cursor.execute.call_args.args[1], (25,))
