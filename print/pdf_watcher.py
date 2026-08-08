import os
import time
import shutil
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class WatchConfig:
    watch_dir: str
    printed_dir: str
    error_dir: str
    poll_seconds: float = 1.0
    stable_checks: int = 3          # quantas leituras iguais para considerar "terminou de gravar"
    stable_interval: float = 0.5    # intervalo entre leituras do tamanho


class PdfAutoPrinter:
    """
    Monitora uma pasta e imprime PDFs novos.
    Depois move para printed_dir. Em erro, move para error_dir.
    """

    def __init__(
        self,
        cfg: WatchConfig,
        print_func: Callable[[str], None],
        log_func: Optional[Callable[[str], None]] = None,
    ):
        self.cfg = cfg
        self.print_func = print_func
        self.log = log_func or (lambda msg: None)

        self._stop = False
        self._seen = set()  # caminhos já processados

    def stop(self):
        self._stop = True

    def _ensure_dirs(self):
        os.makedirs(self.cfg.watch_dir, exist_ok=True)
        os.makedirs(self.cfg.printed_dir, exist_ok=True)
        os.makedirs(self.cfg.error_dir, exist_ok=True)

    def _is_pdf(self, name: str) -> bool:
        return name.lower().endswith(".pdf")

    def _is_stable(self, path: str) -> bool:
        """
        Evita imprimir enquanto o arquivo ainda está sendo gravado.
        Considera estável se o tamanho repetir stable_checks vezes.
        """
        last = -1
        same = 0
        for _ in range(self.cfg.stable_checks * 2):
            try:
                sz = os.path.getsize(path)
            except OSError:
                return False
            if sz == last and sz > 0:
                same += 1
                if same >= self.cfg.stable_checks:
                    return True
            else:
                same = 0
                last = sz
            time.sleep(self.cfg.stable_interval)
        return False

    def _safe_move(self, src: str, dst_dir: str) -> str:
        base = os.path.basename(src)
        dst = os.path.join(dst_dir, base)

        # evita sobrescrever
        if os.path.exists(dst):
            root, ext = os.path.splitext(base)
            dst = os.path.join(dst_dir, f"{root}_{int(time.time())}{ext}")

        shutil.move(src, dst)
        return dst

    def run(self):
        self._ensure_dirs()
        self.log(f"[auto-print] monitorando: {self.cfg.watch_dir}")

        while not self._stop:
            try:
                for name in os.listdir(self.cfg.watch_dir):
                    if not self._is_pdf(name):
                        continue

                    path = os.path.join(self.cfg.watch_dir, name)

                    # ignora se já processou este caminho
                    if path in self._seen:
                        continue

                    # ignora arquivos temporários
                    if name.startswith("~") or name.endswith(".tmp"):
                        continue

                    # espera ficar estável antes de imprimir
                    if not self._is_stable(path):
                        continue

                    self._seen.add(path)

                    try:
                        self.log(f"[auto-print] imprimindo: {name}")
                        self.print_func(path)
                        moved = self._safe_move(path, self.cfg.printed_dir)
                        self.log(f"[auto-print] impresso -> {moved}")
                    except Exception as ex:
                        self.log(f"[auto-print] erro imprimindo {name}: {ex}")
                        try:
                            moved = self._safe_move(path, self.cfg.error_dir)
                            self.log(f"[auto-print] movido para erro -> {moved}")
                        except Exception:
                            pass

            except Exception as ex:
                self.log(f"[auto-print] erro no watcher: {ex}")

            time.sleep(self.cfg.poll_seconds)
