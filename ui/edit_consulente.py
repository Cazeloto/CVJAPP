# ui/edit_consulente.py
import flet as ft
import requests
import threading
import unicodedata
from datetime import datetime
from typing import Optional, Callable, Dict, Any


class EditorConsulente:
    def __init__(
        self,
        page: ft.Page,
        dados_atuais: dict,
        on_save_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_cancel_callback: Optional[
            Callable[[], None]
        ] = None,  # Adicionado callback de cancelamento
    ):
        self.page = page
        self.dados_atuais = dados_atuais
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = (
            on_cancel_callback  # Armazenar callback de cancelamento
        )
        self.dialogo = None

        print(f"DEBUG: Dados recebidos no editor: {type(dados_atuais)}")

        self._construir_interface()

    def _normalizar_nome_consulente(self, valor: str) -> str:
        valor = " ".join((valor or "").strip().split())
        valor = unicodedata.normalize("NFD", valor)
        valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
        return valor.upper()

    def _normalizar_nome_digitando(self, valor: str) -> str:
        valor = unicodedata.normalize("NFD", valor or "")
        valor = "".join(ch for ch in valor if unicodedata.category(ch) != "Mn")
        return valor.upper()

    def _normalizar_nome_change(self, e):
        novo_nome = self._normalizar_nome_digitando(e.control.value or "")
        if novo_nome != (e.control.value or ""):
            e.control.value = novo_nome
            e.control.update()

    def _buscar_cep(self, e):
        """Busca endereço via CEP usando ViaCEP"""
        cep = self.cep_tf.value.strip().replace("-", "").replace(".", "")

        if len(cep) != 8 or not cep.isdigit():
            self.cep_tf.error_text = "CEP inválido"
            self.page.update()
            return

        self.cep_tf.error_text = None
        self.cep_tf.disabled = True
        self.endereco_tf.disabled = True
        self.bairro_tf.disabled = True
        self.cidade_tf.disabled = True
        self.page.update()

        def buscar():
            try:
                url = f"https://viacep.com.br/ws/{cep}/json/"
                response = requests.get(url, timeout=10)
                data = response.json()

                if "erro" not in data:
                    # Atualizar a interface diretamente
                    self.endereco_tf.value = data.get("logradouro", "")
                    self.bairro_tf.value = data.get("bairro", "")
                    self.cidade_tf.value = (
                        f"{data.get('localidade', '')}-{data.get('uf', '')}"
                    )
                else:
                    self.cep_tf.error_text = "CEP não encontrado"
            except Exception as ex:
                self.cep_tf.error_text = f"Erro na busca: {str(ex)}"
            finally:
                # Reabilitar campos
                self.cep_tf.disabled = False
                self.endereco_tf.disabled = False
                self.bairro_tf.disabled = False
                self.cidade_tf.disabled = False

                # Atualizar a página
                self.page.update()

        threading.Thread(target=buscar, daemon=True).start()

    def _construir_interface(self):
        """Constrói a interface do editor"""

        # Helper para extrair dados
        def get_valor(campo, default=""):
            if isinstance(self.dados_atuais, dict):
                return self.dados_atuais.get(campo, default)
            else:
                # Mapeamento de campos para índices
                mapeamento = {
                    "con_nome": 1,
                    "con_sexo": 2,
                    "con_nascim": 3,
                    "con_preferencial": 4,
                    "con_status": 5,
                    "con_passe": 6,
                    "con_npasse": 7,
                    "con_datainicial": 8,
                    "con_fonecel": 9,
                    "con_email": 10,
                    "con_endereco": 11,
                    "con_numero": 12,
                    "con_complemento": 13,
                    "con_bairro": 14,
                    "con_cidade": 15,
                    "con_cep": 16,
                    "con_diagnostico": 17,
                    "con_diagnant": 18,
                    "con_ebo": 19,
                    "con_cromoterapia": 20,
                    "con_massagem": 21,
                    "con_cirurgia": 22,
                    "con_desenv": 23,
                    "con_pontos": 24,
                }
                idx = mapeamento.get(campo)
                if idx is not None and len(self.dados_atuais) > idx:
                    valor = self.dados_atuais[idx]
                    return valor if valor is not None else default
                return default

        # === DADOS PESSOAIS ===
        self.nome_tf = ft.TextField(
            label="Nome Completo",
            value=self._normalizar_nome_consulente(get_valor("con_nome", "")),
            width=600,
            on_change=self._normalizar_nome_change,
        )

        self.sexo_dd = ft.Dropdown(
            label="Sexo",
            value=get_valor("con_sexo", "M"),
            options=[
                ft.dropdown.Option("M", "Masculino"),
                ft.dropdown.Option("F", "Feminino"),
                ft.dropdown.Option("O", "Outro"),
            ],
            width=200,
        )

        # Formatar data de nascimento
        nasc_raw = get_valor("con_nascim")
        if nasc_raw:
            if isinstance(nasc_raw, str):
                nasc_formatado = nasc_raw
            else:
                try:
                    nasc_formatado = nasc_raw.strftime("%d/%m/%Y")
                except:
                    nasc_formatado = ""
        else:
            nasc_formatado = ""

        self.nascimento_tf = ft.TextField(
            label="Data de Nascimento (DD/MM/AAAA)",
            value=nasc_formatado,
            width=250,
            hint_text="Ex: 15/05/1980",
        )

        self.preferencial_dd = ft.Dropdown(
            label="Preferencial",
            value=get_valor("con_preferencial", ""),
            options=[
                ft.dropdown.Option("", "Não"),
                ft.dropdown.Option("X", "Sim (X)"),
                ft.dropdown.Option("P", "Prioritário (P)"),
                ft.dropdown.Option("S", "Especial (S)"),
            ],
            width=200,
        )

        # === CONTATOS ===
        self.celular_tf = ft.TextField(
            label="Celular",
            value=get_valor("con_fonecel", ""),
            width=300,
        )

        self.email_tf = ft.TextField(
            label="Email",
            value=get_valor("con_email", ""),
            width=400,
        )

        # === ENDEREÇO ===
        self.cep_tf = ft.TextField(
            label="CEP",
            value=get_valor("con_cep", ""),
            width=200,
            hint_text="Digite o CEP",
            keyboard_type=ft.KeyboardType.NUMBER,
            suffix=ft.IconButton(
                icon=ft.Icons.SEARCH,
                on_click=self._buscar_cep,
                tooltip="Buscar endereço pelo CEP",
            ),
            on_submit=self._buscar_cep,
        )

        self.endereco_tf = ft.TextField(
            label="Endereço",
            value=get_valor("con_endereco", ""),
            width=500,
        )

        self.numero_tf = ft.TextField(
            label="Número",
            value=get_valor("con_numero", ""),
            width=150,
        )

        self.complemento_tf = ft.TextField(
            label="Complemento",
            value=get_valor("con_complemento", ""),
            width=300,
        )

        self.bairro_tf = ft.TextField(
            label="Bairro",
            value=get_valor("con_bairro", ""),
            width=400,
        )

        self.cidade_tf = ft.TextField(
            label="Cidade",
            value=get_valor("con_cidade", ""),
            width=400,
            hint_text="Ex: Brasília-DF",
        )

        # === DIAGNÓSTICOS ===
        self.diagnostico_tf = ft.TextField(
            label="Diagnóstico Atual",
            value=get_valor("con_diagnostico", ""),
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=600,
        )

        self.diagnostico_ant_tf = ft.TextField(
            label="Diagnóstico Anterior",
            value=get_valor("con_diagnant", ""),
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=600,
        )

        # === OBSERVAÇÕES ===
        self.ebo_tf = ft.TextField(
            label="Ebó",
            value=get_valor("con_ebo", ""),
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=600,
        )

        # Converter valores numéricos para string para os campos de texto
        pontos_val = get_valor("con_pontos", "")
        desenv_val = get_valor("con_desenv", "")

        self.pontos_tf = ft.TextField(
            label="Pontos",
            value=str(pontos_val) if pontos_val not in [None, ""] else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=600,
        )

        self.desenv_tf = ft.TextField(
            label="Desenvolvimento",
            value=str(desenv_val) if desenv_val not in [None, ""] else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
            width=600,
        )

        # === TRATAMENTOS (CAMPOS NUMÉRICOS) ===
        passe_val = get_valor("con_passe", 0)
        cromo_val = get_valor("con_cromoterapia", 0)
        massa_val = get_valor("con_massagem", 0)
        cirur_val = get_valor("con_cirurgia", 0)

        self.passe_tf = ft.TextField(
            label="Passe (sessões autorizadas)",
            value=str(passe_val),
            width=250,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.cromoterapia_tf = ft.TextField(
            label="Cromoterapia (sessões autorizadas)",
            value=str(cromo_val),
            width=250,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.massagem_tf = ft.TextField(
            label="Massagem (sessões autorizadas)",
            value=str(massa_val),
            width=250,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.cirurgia_tf = ft.TextField(
            label="Cirurgia (sessões autorizadas)",
            value=str(cirur_val),
            width=250,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # === LAYOUT PRINCIPAL ===
        self.conteudo = ft.Container(
            padding=20,
            width=800,
            content=ft.Column(
                [
                    # Dados Pessoais
                    ft.Text("Dados Pessoais", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row([ft.Column([self.nome_tf], expand=True)]),
                    ft.Row(
                        [
                            ft.Column([self.sexo_dd]),
                            ft.Column([self.nascimento_tf]),
                            ft.Column([self.preferencial_dd]),
                        ],
                        spacing=20,
                    ),
                    # Contatos
                    ft.Container(height=20),
                    ft.Text("Contatos", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column([self.celular_tf]),
                            ft.Column([self.email_tf], expand=True),
                        ],
                        spacing=20,
                    ),
                    # Endereço
                    ft.Container(height=20),
                    ft.Text("Endereço", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column([self.cep_tf]),
                            ft.Column([self.endereco_tf], expand=True),
                            ft.Column([self.numero_tf]),
                        ],
                        spacing=20,
                    ),
                    ft.Row(
                        [
                            ft.Column([self.complemento_tf]),
                            ft.Column([self.bairro_tf]),
                            ft.Column([self.cidade_tf], expand=True),
                        ],
                        spacing=20,
                    ),
                    # Diagnósticos
                    ft.Container(height=20),
                    ft.Text("Diagnósticos", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row([ft.Column([self.diagnostico_tf], expand=True)]),
                    ft.Row([ft.Column([self.diagnostico_ant_tf], expand=True)]),
                    # Observações
                    ft.Container(height=20),
                    ft.Text("Observações", size=16, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Row([ft.Column([self.ebo_tf], expand=True)]),
                    ft.Row([ft.Column([self.pontos_tf], expand=True)]),
                    ft.Row([ft.Column([self.desenv_tf], expand=True)]),
                    # Tratamentos
                    ft.Container(height=20),
                    ft.Text(
                        "Tratamentos Autorizados", size=16, weight=ft.FontWeight.BOLD
                    ),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column([self.passe_tf]),
                            ft.Column([self.cromoterapia_tf]),
                            ft.Column([self.massagem_tf]),
                            ft.Column([self.cirurgia_tf]),
                        ],
                        spacing=20,
                    ),
                    ft.Container(height=20),
                ],
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def abrir(self):
        """Abre o diálogo de edição"""
        print("DEBUG: Abrindo diálogo de edição...")

        # Criar o diálogo
        self.dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar Consulente"),
            content=self.conteudo,
            actions=[
                ft.TextButton("Cancelar", on_click=self._cancelar),
                ft.ElevatedButton("Salvar", on_click=self._salvar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Adicionar à página e abrir
        self.page.overlay.append(self.dialogo)
        self.dialogo.open = True
        self.page.update()

        return self.dialogo  # Retorna o diálogo para referência

    def _cancelar(self, e=None):
        """Fecha o diálogo quando o usuário cancela"""
        print("DEBUG: Cancelando edição...")

        # Fechar o diálogo
        if self.dialogo:
            self.dialogo.open = False
            # Não remover do overlay aqui - deixar o Flet gerenciar
            self.page.update()

        # Chamar callback de cancelamento se existir
        if self.on_cancel_callback:
            self.on_cancel_callback()

    def _salvar(self, e=None):
        """Processa o salvamento dos dados"""
        print("DEBUG: Processando salvamento...")

        try:
            if not self.nome_tf.value or not self.nome_tf.value.strip():
                self.page.snack_bar = ft.SnackBar(ft.Text("Nome é obrigatório!"))
                self.page.snack_bar.open = True
                self.page.update()
                return

            # Preparar dados para atualização
            nome_norm = self._normalizar_nome_consulente(self.nome_tf.value)
            dados_atualizados = {
                "con_nome": nome_norm,
                "con_sexo": self.sexo_dd.value,
                "con_nascim": self.nascimento_tf.value.strip(),
                "con_preferencial": self.preferencial_dd.value,
                "con_fonecel": self.celular_tf.value.strip(),
                "con_email": self.email_tf.value.strip(),
                "con_cep": self.cep_tf.value.strip(),
                "con_endereco": self.endereco_tf.value.strip(),
                "con_numero": self.numero_tf.value.strip(),
                "con_complemento": self.complemento_tf.value.strip(),
                "con_bairro": self.bairro_tf.value.strip(),
                "con_cidade": self.cidade_tf.value.strip(),
                "con_diagnostico": self.diagnostico_tf.value.strip(),
                "con_diagnant": self.diagnostico_ant_tf.value.strip(),
                "con_ebo": self.ebo_tf.value.strip(),
                "con_pontos": (
                    str(self.pontos_tf.value).strip()
                    if self.pontos_tf.value is not None
                    else ""
                ),
                "con_desenv": (
                    str(self.desenv_tf.value).strip()
                    if self.desenv_tf.value is not None
                    else ""
                ),
                "con_passe": (
                    int(self.passe_tf.value)
                    if self.passe_tf.value and self.passe_tf.value.strip()
                    else 0
                ),
                "con_cromoterapia": (
                    int(self.cromoterapia_tf.value)
                    if self.cromoterapia_tf.value and self.cromoterapia_tf.value.strip()
                    else 0
                ),
                "con_massagem": (
                    int(self.massagem_tf.value)
                    if self.massagem_tf.value and self.massagem_tf.value.strip()
                    else 0
                ),
                "con_cirurgia": (
                    int(self.cirurgia_tf.value)
                    if self.cirurgia_tf.value and self.cirurgia_tf.value.strip()
                    else 0
                ),
            }

            print(f"DEBUG: Dados a serem salvos: {dados_atualizados}")

            # Fechar o diálogo primeiro
            if self.dialogo:
                self.dialogo.open = False
                self.page.update()

            # Chamar callback de salvamento
            if self.on_save_callback:
                print("DEBUG: Chamando callback de salvamento...")
                self.on_save_callback(dados_atualizados)

        except ValueError as ve:
            print(f"DEBUG: Erro de valor: {ve}")
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"Erro nos campos numéricos: {ve}")
            )
            self.page.snack_bar.open = True
            self.page.update()
        except Exception as ex:
            print(f"DEBUG: Erro geral: {ex}")
            # Fechar o diálogo mesmo com erro
            if self.dialogo:
                self.dialogo.open = False
                self.page.update()

            self.page.snack_bar = ft.SnackBar(ft.Text(f"Erro ao salvar: {ex}"))
            self.page.snack_bar.open = True
            self.page.update()
