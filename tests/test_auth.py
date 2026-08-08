from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.auth import (
    AuthenticatedUser,
    LOGIN_LOCK_MINUTES,
    LoginLockedError,
    PASSWORD_HASHER,
    authenticate_user,
    get_active_user,
    normalize_username,
    require_admin,
    unlock_user,
    validate_password,
    validate_username,
)


class AuthTest(TestCase):
    def test_normalizes_and_validates_username(self):
        self.assertEqual(normalize_username("  Gerson.C  "), "gerson.c")
        self.assertEqual(validate_username("operador-01"), "operador-01")
        with self.assertRaises(ValueError):
            validate_username("usuario com espaco")

    def test_password_policy(self):
        validate_password("123456")
        with self.assertRaises(ValueError):
            validate_password("12345")

    def test_password_is_argon2id_hash(self):
        password_hash = PASSWORD_HASHER.hash("uma senha segura")
        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertTrue(PASSWORD_HASHER.verify(password_hash, "uma senha segura"))

    def test_admin_role(self):
        admin = AuthenticatedUser(1, "admin", "Admin", "admin")
        operator = AuthenticatedUser(2, "operador", "Operador", "operador")
        self.assertTrue(admin.is_admin)
        self.assertFalse(operator.is_admin)

    def test_require_admin_checks_current_database_state(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"authorized": 1}
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager):
            require_admin(7)

        cursor.execute.assert_called_once()
        self.assertEqual(cursor.execute.call_args.args[1], (7,))

    def test_require_admin_rejects_inactive_or_non_admin_user(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager):
            with self.assertRaises(PermissionError):
                require_admin(8)

    def test_successful_login_resets_failures(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            "user_id": 3,
            "username": "operador",
            "display_name": "Operador",
            "password_hash": PASSWORD_HASHER.hash("123456"),
            "role": "operador",
            "active": True,
            "failed_login_count": 2,
            "locked_until": None,
            "lock_seconds": 0,
            "auth_version": 1,
        }
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager), patch(
            "core.auth.record_audit_event"
        ) as audit:
            user = authenticate_user("operador", "123456")

        self.assertEqual(user.id, 3)
        update_sql = cursor.execute.call_args_list[1].args[0]
        self.assertIn("failed_login_count = 0", update_sql)
        audit.assert_called_once()

    def test_fifth_failure_locks_account_in_database(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            {
                "user_id": 3,
                "username": "operador",
                "display_name": "Operador",
                "password_hash": PASSWORD_HASHER.hash("correta"),
                "role": "operador",
                "active": True,
                "failed_login_count": 4,
                "locked_until": None,
                "lock_seconds": 0,
                "auth_version": 1,
            },
            {"newly_locked": True},
        ]
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager), patch(
            "core.auth.record_audit_event"
        ):
            with self.assertRaises(LoginLockedError) as raised:
                authenticate_user("operador", "errada")

        self.assertEqual(
            raised.exception.retry_after_seconds, LOGIN_LOCK_MINUTES * 60
        )

    def test_locked_account_is_denied_even_with_correct_password(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {
            "user_id": 3,
            "username": "operador",
            "display_name": "Operador",
            "password_hash": PASSWORD_HASHER.hash("correta"),
            "role": "operador",
            "active": True,
            "failed_login_count": 5,
            "locked_until": object(),
            "lock_seconds": 125,
            "auth_version": 1,
        }
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager), patch(
            "core.auth.record_audit_event"
        ):
            with self.assertRaises(LoginLockedError) as raised:
                authenticate_user("operador", "correta")

        self.assertEqual(raised.exception.retry_after_seconds, 125)
        self.assertEqual(cursor.execute.call_count, 1)

    def test_session_revalidation_rejects_inactive_user(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager):
            self.assertIsNone(get_active_user(14))

        self.assertEqual(cursor.execute.call_args.args[1], (14, None, None))

    def test_unlock_requires_admin_and_clears_lock(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {"authorized": 1}
        cursor.rowcount = 1
        manager = MagicMock()
        manager.__enter__.return_value = connection

        with patch("core.auth.get_conn", return_value=manager), patch(
            "core.auth.record_audit_event"
        ) as audit:
            unlock_user(1, 14)

        update_sql, params = cursor.execute.call_args_list[1].args
        self.assertIn("failed_login_count = 0", update_sql)
        self.assertEqual(params, (14,))
        audit.assert_called_once_with(
            cursor=cursor,
            actor_id=1,
            action="user.unlock",
            entity_type="user",
            entity_id=14,
        )
