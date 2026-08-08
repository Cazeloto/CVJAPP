import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core.paths import resource_path


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _load_app_env() -> None:
    """Carrega o .env do projeto ou da distribuicao PyInstaller."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / ".env")
    candidates.append(Path(resource_path(".env")))
    candidates.append(Path.cwd() / ".env")

    for env_path in candidates:
        if env_path.is_file():
            load_dotenv(env_path)
            return

    load_dotenv()


_load_app_env()


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuracoes da aplicacao, sem abrir conexoes durante o import."""

    app_name: str = os.getenv("APP_NAME", "CVJAPP")
    app_env: str = os.getenv("APP_ENV", "development")
    access_username: str | None = os.getenv("ACCESS_USERNAME")
    access_password: str | None = os.getenv("ACCESS_PASSWORD")
    print_agent_token: str | None = os.getenv("PRINT_AGENT_TOKEN")
    database_url: str | None = os.getenv("DATABASE_URL")
    pg_host: str | None = os.getenv("PG_HOST")
    pg_port: str = os.getenv("PG_PORT", "5432")
    pg_db: str | None = os.getenv("PG_DB")
    pg_user: str | None = os.getenv("PG_USER")
    pg_password: str | None = os.getenv("PG_PASSWORD")
    session_max_minutes: int = _env_int("SESSION_MAX_MINUTES", 480, 15, 1_440)
    session_recheck_seconds: int = _env_int(
        "SESSION_RECHECK_SECONDS", 30, 10, 300
    )

    def connection_kwargs(self) -> dict[str, str]:
        if self.database_url:
            return {"conninfo": self.database_url}

        required = {
            "PG_HOST": self.pg_host,
            "PG_DB": self.pg_db,
            "PG_USER": self.pg_user,
            "PG_PASSWORD": self.pg_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Configuracao do banco incompleta. Defina: " + ", ".join(missing)
            )

        return {
            "host": self.pg_host or "",
            "port": self.pg_port,
            "dbname": self.pg_db or "",
            "user": self.pg_user or "",
            "password": self.pg_password or "",
            "sslmode": os.getenv("PG_SSLMODE", "prefer"),
        }


settings = Settings()


def get_pdf_dir() -> Path:
    """
    Pasta fixa para salvar PDFs.
    Prioridade:
      1) PDF_DIR no .env
      2) Documentos do usuÃ¡rio: ~/Documents/Consulentes/PDFs
    """
    p = os.getenv("PDF_DIR", "").strip()
    if p:
        return Path(p)

    return Path.home() / "Documents" / "Consulentes" / "PDFs"


def get_pdf_ficha_rodape() -> str:
    """Texto opcional exibido em vermelho no rodape das fichas PDF."""
    return os.getenv("PDF_FICHA_RODAPE", "").strip()
