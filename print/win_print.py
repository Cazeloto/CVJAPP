try:
    import win32api
    _HAS_WIN32 = True
except ImportError:
    win32api = None
    _HAS_WIN32 = False


def abrir_pdf_windows(caminho_pdf: str):
    if not _HAS_WIN32:
        raise RuntimeError("win32api não disponível (modo web ou ambiente sem pywin32).")
    win32api.ShellExecute(0, "open", caminho_pdf, None, ".", 1)


def imprimir_pdf_windows(caminho_pdf: str):
    if not _HAS_WIN32:
        raise RuntimeError("win32api não disponível (modo web ou ambiente sem pywin32).")
    win32api.ShellExecute(0, "print", caminho_pdf, None, ".", 0)
