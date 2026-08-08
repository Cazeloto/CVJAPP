import sys
import os
import tempfile
from pathlib import Path

def resource_path(relative_path: str) -> str:
    """
    Retorna caminho correto tanto em desenvolvimento
    quanto no executável PyInstaller.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def sql_upload_dir() -> Path:
    """Pasta temporaria usada pelo FilePicker quando o app roda no navegador."""
    directory = Path(tempfile.gettempdir()) / "cvjapp_sql_uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory
