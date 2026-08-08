"""Limpa arquivos dispensaveis do bundle onedir criado pelo PyInstaller.

Por padrao o programa apenas mostra o que faria. Use ``--apply`` para remover.
A limpeza e deliberadamente conservadora e especifica para o CVJAPP_Server.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


APP_NAME = "CVJAPP_Server"

# O app roda no Brasil. UTC e os arquivos de indice sao mantidos para que
# zoneinfo continue funcional para os fusos usados pelo servidor.
TZDATA_KEEP = {
    "zones",
    "zoneinfo/UTC",
    "zoneinfo/UCT",
    "zoneinfo/Universal",
    "zoneinfo/Zulu",
    "zoneinfo/Etc/UTC",
    "zoneinfo/Etc/GMT",
    "zoneinfo/America/Sao_Paulo",
    "zoneinfo/Brazil/East",
    "zoneinfo/iso3166.tab",
    "zoneinfo/zone.tab",
    "zoneinfo/zone1970.tab",
    "zoneinfo/zonenow.tab",
    "zoneinfo/tzdata.zi",
    "zoneinfo/leapseconds",
}


@dataclass(frozen=True)
class Removal:
    path: str
    size: int
    reason: str


def _relative_posix(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def validate_internal_dir(internal: Path) -> Path:
    internal = internal.resolve()
    if internal.name.lower() != "_internal":
        raise ValueError(f'O diretorio deve terminar em "_internal": {internal}')
    if not internal.is_dir():
        raise FileNotFoundError(f"Diretorio nao encontrado: {internal}")

    app_dir = internal.parent
    executable = app_dir / f"{APP_NAME}.exe"
    if app_dir.name != APP_NAME or not executable.is_file():
        raise ValueError(
            "Protecao acionada: a pasta nao parece ser uma distribuicao "
            f"{APP_NAME} valida ({executable} nao encontrado)."
        )
    return internal


def find_removals(internal: Path, aggressive: bool) -> list[Removal]:
    removals: dict[Path, Removal] = {}

    def add(path: Path, reason: str) -> None:
        if path.is_file() and path not in removals:
            removals[path] = Removal(
                path=_relative_posix(path, internal),
                size=path.stat().st_size,
                reason=reason,
            )

    # collect_all('flet') e collect_all('flet_web') copiam os fontes como
    # dados, embora os mesmos modulos ja estejam compilados no PYZ do exe.
    for package_name in ("flet", "flet_web"):
        package_dir = internal / package_name
        if package_dir.is_dir():
            for pattern in ("*.py", "*.pyi", "py.typed"):
                for path in package_dir.rglob(pattern):
                    add(path, f"fonte/metadado duplicado de {package_name}")

    # Arquivos .symbols servem para diagnosticar o WebAssembly e nao sao
    # necessarios para executar a interface web.
    web_dir = internal / "flet_web" / "web"
    if web_dir.is_dir():
        for path in web_dir.rglob("*.symbols"):
            add(path, "simbolos de depuracao WebAssembly")

    # Mantem os indices e os fusos efetivamente relevantes ao servidor.
    tzdata_dir = internal / "tzdata"
    if tzdata_dir.is_dir():
        for path in tzdata_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = _relative_posix(path, tzdata_dir)
            if relative not in TZDATA_KEEP:
                add(path, "fuso horario nao utilizado pelo servidor")

    # A flag e incorporada somente pelos builds que usam FilePicker. Em bundles
    # antigos, Tkinter ainda alimenta os seletores e deve ser preservado.
    if (internal / "no_tkinter.flag").is_file():
        for directory_name in ("_tcl_data", "_tk_data", "tcl8"):
            directory = internal / directory_name
            if directory.is_dir():
                for path in directory.rglob("*"):
                    add(path, "runtime Tcl/Tk nao utilizado")
        for file_name in (
            "_tkinter.pyd",
            "tcl86t.dll",
            "tk86t.dll",
        ):
            add(internal / Path(file_name), "runtime Tcl/Tk nao utilizado")
        pil_dir = internal / "PIL"
        if pil_dir.is_dir():
            for path in pil_dir.glob("_imagingtk*.pyd"):
                add(path, "runtime Tcl/Tk nao utilizado")

    if aggressive:
        # Pyodide permite executar Python dentro do navegador. O CVJAPP usa
        # Python no servidor (FastAPI/Uvicorn), portanto esse runtime nao e
        # usado. Fica opt-in porque futuras telas podem passar a utiliza-lo.
        pyodide_dir = web_dir / "pyodide"
        if pyodide_dir.is_dir():
            for path in pyodide_dir.rglob("*"):
                add(path, "runtime Pyodide nao usado (modo agressivo)")

    return sorted(removals.values(), key=lambda item: item.path.lower())


def remove_files(internal: Path, removals: list[Removal]) -> None:
    for item in removals:
        target = internal / Path(item.path)
        # Defesa adicional contra caminhos manipulados ou saida de _internal.
        if os.path.commonpath((str(internal), str(target.resolve()))) != str(internal):
            raise ValueError(f"Caminho inseguro recusado: {target}")
        target.unlink(missing_ok=True)

    # Exclui somente diretorios que ficaram vazios.
    directories = sorted(
        (path for path in internal.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def write_manifest(
    internal: Path, removals: list[Removal], *, applied: bool, aggressive: bool
) -> Path:
    manifest_name = "limpeza_manifest.json" if applied else "limpeza_simulacao.json"
    manifest = internal.parent / manifest_name
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "internal_dir": str(internal),
        "applied": applied,
        "aggressive": aggressive,
        "removed_file_count": len(removals) if applied else 0,
        "candidate_file_count": len(removals),
        "candidate_bytes": sum(item.size for item in removals),
        "files": [asdict(item) for item in removals],
    }
    manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.2f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpa com seguranca o _internal do CVJAPP_Server."
    )
    parser.add_argument(
        "internal",
        nargs="?",
        type=Path,
        default=Path("dist") / APP_NAME / "_internal",
        help="pasta _internal (padrao: dist/CVJAPP_Server/_internal)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="executa a remocao; sem esta opcao faz apenas uma simulacao",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="remove tambem o runtime Pyodide; exige teste completo da interface",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        internal = validate_internal_dir(args.internal)
        removals = find_removals(internal, args.aggressive)
        total_size = sum(item.size for item in removals)

        mode = "APLICACAO" if args.apply else "SIMULACAO"
        print(f"[{mode}] {internal}")
        print(f"Arquivos candidatos: {len(removals)}")
        print(f"Espaco recuperavel: {format_size(total_size)}")

        by_reason: dict[str, list[Removal]] = {}
        for item in removals:
            by_reason.setdefault(item.reason, []).append(item)
        for reason, items in sorted(by_reason.items()):
            size = sum(item.size for item in items)
            print(f"  - {reason}: {len(items)} arquivo(s), {format_size(size)}")

        if args.apply:
            remove_files(internal, removals)
            print("Limpeza concluida.")
        else:
            print("Nada foi removido. Use --apply para confirmar a limpeza.")

        manifest = write_manifest(
            internal, removals, applied=args.apply, aggressive=args.aggressive
        )
        print(f"Manifesto: {manifest}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
