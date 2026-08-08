"""Hook do bundle web: nao inclui o runtime desktop de aproximadamente 88 MB."""

# O hook distribuido pelo flet_cli sempre copia flet_desktop quando o pacote
# esta instalado. Este aplicativo usa ft.run(..., export_asgi_app=True) e serve
# a interface por flet_web/FastAPI, portanto nao precisa de arquivos desktop.
datas = []
binaries = []
hiddenimports = []
