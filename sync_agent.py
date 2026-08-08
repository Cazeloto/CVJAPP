"""Agente local que mantem o PostgreSQL 10 alinhado ao Neon."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from db.sync import NeonToLocalSynchronizer, SyncConfig


def default_env_path() -> Path:
    return Path(__file__).resolve().parent / ".env"


def configure_logging(log_path: Path, verbose: bool = False) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if verbose:
        handlers.append(logging.StreamHandler())
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        handlers=handlers,
        force=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sincroniza dados operacionais do Neon para o PostgreSQL local."
    )
    parser.add_argument("--env", type=Path, default=default_env_path())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--initial", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.env.resolve().parent / "outputs" / "sync-agent.log", args.verbose)
    config = SyncConfig.load(args.env)
    synchronizer = NeonToLocalSynchronizer(config)
    if args.check:
        result = synchronizer.check()
        print(
            f"Configuracao OK: {result['source_version']} -> "
            f"{result['target_version']} ({result['tables']} tabelas)"
        )
        return 0
    if args.initial:
        total = synchronizer.initial_sync()
        print(f"Carga inicial concluida: {total} registros processados.")
        if args.once:
            return 0
    if args.once:
        total = synchronizer.sync_once()
        print(f"Sincronizacao concluida: {total} evento(s).")
        return 0

    logger = logging.getLogger("cvjapp.sync_agent")
    logger.info("Agente de sincronizacao iniciado")
    while True:
        try:
            processed = synchronizer.sync_once()
            if processed >= config.batch_size:
                continue
        except Exception:
            logger.exception("Falha na sincronizacao; nova tentativa sera realizada")
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
