"""Autenticacao e administracao dos acessos ao CVJAPP."""

from dataclasses import dataclass
import re
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from psycopg.errors import UniqueViolation

from core.config import Settings, settings
from db.audit import record_audit_event
from db.conn import get_conn
from db.migrations import run_migrations


PASSWORD_HASHER = PasswordHasher(
    time_cost=2,
    memory_cost=19_456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)
DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash("cvjapp-dummy-password")
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,50}$")
_INITIALIZATION_LOCK = Lock()
_INITIALIZED = False
MAX_FAILED_LOGINS = 5
LOGIN_LOCK_MINUTES = 15


class LoginLockedError(PermissionError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        super().__init__("Acesso bloqueado temporariamente.")


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: int
    username: str
    display_name: str
    role: str
    auth_version: int = 1

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: int
    username: str
    display_name: str
    role: str
    active: bool
    last_login: str
    is_locked: bool
    locked_until: str


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "O usuario deve ter de 3 a 50 caracteres: letras sem acento, "
            "numeros, ponto, hifen ou sublinhado."
        )
    return normalized


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("A senha deve ter pelo menos 6 caracteres.")
    if len(password) > 128:
        raise ValueError("A senha deve ter no maximo 128 caracteres.")


def initialize_auth_database(config: Settings = settings) -> None:
    """Cria a tabela e, quando necessario, o primeiro administrador."""

    global _INITIALIZED
    if _INITIALIZED:
        return

    with _INITIALIZATION_LOCK:
        if _INITIALIZED:
            return
        run_migrations(config)
        with get_conn(config) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) AS total FROM public.cvjcura_users")
                if cursor.fetchone()["total"] == 0:
                    if not config.access_username or not config.access_password:
                        raise RuntimeError(
                            "Defina ACCESS_USERNAME e ACCESS_PASSWORD para criar "
                            "o primeiro administrador."
                        )
                    username = validate_username(config.access_username)
                    validate_password(config.access_password)
                    cursor.execute(
                        """
                        INSERT INTO public.cvjcura_users
                            (username, display_name, password_hash, role)
                        VALUES (%s, %s, %s, 'admin')
                        ON CONFLICT DO NOTHING
                        RETURNING user_id
                        """,
                        (
                            username,
                            username,
                            PASSWORD_HASHER.hash(config.access_password),
                        ),
                    )
                    created = cursor.fetchone()
                    if created:
                        record_audit_event(
                            cursor=cursor,
                            actor_id=created["user_id"],
                            action="user.bootstrap",
                            entity_type="user",
                            entity_id=created["user_id"],
                            details={"username": username, "role": "admin"},
                        )
        _INITIALIZED = True


def authenticate_user(username: str, password: str) -> AuthenticatedUser | None:
    """Valida um usuario ativo sem revelar se a conta existe."""

    normalized = normalize_username(username)
    authenticated: AuthenticatedUser | None = None
    locked_seconds = 0
    with get_conn() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, display_name, password_hash, role, active,
                       failed_login_count, locked_until, auth_version,
                       GREATEST(
                           0,
                           EXTRACT(EPOCH FROM (locked_until - CURRENT_TIMESTAMP))::int
                       ) AS lock_seconds
                  FROM public.cvjcura_users
                 WHERE lower(username) = %s
                 FOR UPDATE
                """,
                (normalized,),
            )
            row = cursor.fetchone()
            encoded_hash = row["password_hash"] if row else DUMMY_PASSWORD_HASH
            try:
                password_matches = PASSWORD_HASHER.verify(encoded_hash, password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                password_matches = False

            if row and row["active"] and int(row["lock_seconds"] or 0) > 0:
                locked_seconds = int(row["lock_seconds"])
                record_audit_event(
                    cursor=cursor,
                    actor_id=row["user_id"],
                    action="auth.login",
                    entity_type="session",
                    outcome="denied",
                    details={"locked": True},
                )
            elif not row or not row["active"] or not password_matches:
                newly_locked = False
                if row and row["active"]:
                    cursor.execute(
                        """
                        UPDATE public.cvjcura_users
                           SET failed_login_count = failed_login_count + 1,
                               last_failed_login_at = CURRENT_TIMESTAMP,
                               locked_until = CASE
                                   WHEN failed_login_count + 1 >= %s
                                   THEN CURRENT_TIMESTAMP + (%s * INTERVAL '1 minute')
                                   ELSE NULL
                               END,
                               updated_at = CURRENT_TIMESTAMP
                         WHERE user_id = %s
                        RETURNING locked_until IS NOT NULL AS newly_locked
                        """,
                        (MAX_FAILED_LOGINS, LOGIN_LOCK_MINUTES, row["user_id"]),
                    )
                    newly_locked = bool(cursor.fetchone()["newly_locked"])
                    if newly_locked:
                        locked_seconds = LOGIN_LOCK_MINUTES * 60
                record_audit_event(
                    cursor=cursor,
                    actor_id=row["user_id"] if row else None,
                    actor_label=row["username"] if row else normalized or "desconhecido",
                    action="auth.login",
                    entity_type="session",
                    outcome="denied",
                    details={"locked": newly_locked},
                )
            else:
                replacement_hash = None
                if PASSWORD_HASHER.check_needs_rehash(encoded_hash):
                    replacement_hash = PASSWORD_HASHER.hash(password)
                cursor.execute(
                    """
                    UPDATE public.cvjcura_users
                       SET last_login_at = CURRENT_TIMESTAMP,
                           password_hash = COALESCE(%s, password_hash),
                           failed_login_count = 0,
                           locked_until = NULL,
                           last_failed_login_at = NULL,
                           updated_at = CURRENT_TIMESTAMP
                     WHERE user_id = %s
                    """,
                    (replacement_hash, row["user_id"]),
                )
                record_audit_event(
                    cursor=cursor,
                    actor_id=row["user_id"],
                    action="auth.login",
                    entity_type="session",
                    outcome="success",
                )
                authenticated = AuthenticatedUser(
                    id=row["user_id"],
                    username=row["username"],
                    display_name=row["display_name"],
                    role=row["role"],
                    auth_version=row["auth_version"],
                )

    if locked_seconds:
        raise LoginLockedError(locked_seconds)
    return authenticated


def get_active_user(
    user_id: int,
    expected_auth_version: int | None = None,
) -> AuthenticatedUser | None:
    """Revalida uma sessao usando o estado atual da conta no banco."""

    with get_conn() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, username, display_name, role, auth_version
                  FROM public.cvjcura_users
                 WHERE user_id = %s AND active
                   AND (%s IS NULL OR auth_version = %s)
                """,
                (user_id, expected_auth_version, expected_auth_version),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return AuthenticatedUser(
                id=row["user_id"],
                username=row["username"],
                display_name=row["display_name"],
                role=row["role"],
                auth_version=row["auth_version"],
            )


def list_users(actor_id: int) -> list[UserRecord]:
    with get_conn() as connection:
        with connection.cursor() as cursor:
            _require_admin(cursor, actor_id)
            cursor.execute(
                """
                SELECT user_id, username, display_name, role, active,
                       to_char(last_login_at AT TIME ZONE 'America/Sao_Paulo',
                               'DD/MM/YYYY HH24:MI') AS last_login,
                       locked_until > CURRENT_TIMESTAMP AS is_locked,
                       to_char(locked_until AT TIME ZONE 'America/Sao_Paulo',
                               'DD/MM/YYYY HH24:MI') AS locked_until_label
                  FROM public.cvjcura_users
                 ORDER BY active DESC, display_name, username
                """
            )
            return [
                UserRecord(
                    id=row["user_id"],
                    username=row["username"],
                    display_name=row["display_name"],
                    role=row["role"],
                    active=row["active"],
                    last_login=row["last_login"] or "Nunca acessou",
                    is_locked=bool(row["is_locked"]),
                    locked_until=row["locked_until_label"] or "",
                )
                for row in cursor
            ]


def create_user(
    actor_id: int,
    username: str,
    display_name: str,
    password: str,
    role: str,
) -> None:
    normalized = validate_username(username)
    clean_name = " ".join(display_name.strip().split())
    if len(clean_name) < 2 or len(clean_name) > 120:
        raise ValueError("Informe um nome de exibicao valido.")
    if role not in {"admin", "operador"}:
        raise ValueError("Perfil invalido.")
    validate_password(password)

    try:
        with get_conn() as connection:
            with connection.cursor() as cursor:
                _require_admin(cursor, actor_id)
                cursor.execute(
                    """
                    INSERT INTO public.cvjcura_users
                        (username, display_name, password_hash, role, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING user_id
                    """,
                    (
                        normalized,
                        clean_name,
                        PASSWORD_HASHER.hash(password),
                        role,
                        actor_id,
                    ),
                )
                target_id = cursor.fetchone()["user_id"]
                record_audit_event(
                    cursor=cursor,
                    actor_id=actor_id,
                    action="user.create",
                    entity_type="user",
                    entity_id=target_id,
                    details={"username": normalized, "role": role},
                )
    except UniqueViolation as error:
        raise ValueError("Ja existe um usuario com esse identificador.") from error


def reset_user_password(actor_id: int, target_id: int, password: str) -> None:
    validate_password(password)
    with get_conn() as connection:
        with connection.cursor() as cursor:
            _require_admin(cursor, actor_id)
            cursor.execute(
                """
                UPDATE public.cvjcura_users
                   SET password_hash = %s,
                       failed_login_count = 0,
                       locked_until = NULL,
                       last_failed_login_at = NULL,
                       auth_version = auth_version + 1,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE user_id = %s
                """,
                (PASSWORD_HASHER.hash(password), target_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Usuario nao encontrado.")
            record_audit_event(
                cursor=cursor,
                actor_id=actor_id,
                action="user.password_reset",
                entity_type="user",
                entity_id=target_id,
            )


def unlock_user(actor_id: int, target_id: int) -> None:
    with get_conn() as connection:
        with connection.cursor() as cursor:
            _require_admin(cursor, actor_id)
            cursor.execute(
                """
                UPDATE public.cvjcura_users
                   SET failed_login_count = 0,
                       locked_until = NULL,
                       last_failed_login_at = NULL,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE user_id = %s AND active
                """,
                (target_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("Usuario ativo nao encontrado.")
            record_audit_event(
                cursor=cursor,
                actor_id=actor_id,
                action="user.unlock",
                entity_type="user",
                entity_id=target_id,
            )


def set_user_active(actor_id: int, target_id: int, active: bool) -> None:
    if actor_id == target_id:
        raise ValueError("Voce nao pode desativar o proprio acesso.")

    with get_conn() as connection:
        with connection.cursor() as cursor:
            _require_admin(cursor, actor_id)
            cursor.execute(
                "SELECT role, active FROM public.cvjcura_users WHERE user_id = %s",
                (target_id,),
            )
            target = cursor.fetchone()
            if target is None:
                raise ValueError("Usuario nao encontrado.")
            if not active and target["role"] == "admin" and target["active"]:
                cursor.execute(
                    "SELECT count(*) AS total FROM public.cvjcura_users "
                    "WHERE role = 'admin' AND active"
                )
                if cursor.fetchone()["total"] <= 1:
                    raise ValueError("O sistema precisa manter um administrador ativo.")
            cursor.execute(
                """
                UPDATE public.cvjcura_users
                   SET active = %s,
                       auth_version = auth_version + 1,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE user_id = %s
                """,
                (active, target_id),
            )
            record_audit_event(
                cursor=cursor,
                actor_id=actor_id,
                action="user.activate" if active else "user.deactivate",
                entity_type="user",
                entity_id=target_id,
            )


def require_admin(actor_id: int) -> None:
    """Confirma no banco que o usuario ainda e um administrador ativo."""

    with get_conn() as connection:
        with connection.cursor() as cursor:
            _require_admin(cursor, actor_id)


def _require_admin(cursor, actor_id: int) -> None:
    cursor.execute(
        """
        SELECT 1 FROM public.cvjcura_users
         WHERE user_id = %s AND role = 'admin' AND active
        """,
        (actor_id,),
    )
    if cursor.fetchone() is None:
        raise PermissionError("Acao permitida somente para administradores.")
