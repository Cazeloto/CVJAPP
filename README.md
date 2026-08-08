# CVJAPP

Versao operacional local do sistema da Casa da Vovo Joaquina, conectada ao
PostgreSQL Neon e mantida em paralelo ao CVJCURA.

## Caracteristicas

- execucao local em `http://127.0.0.1:8550`;
- banco de dados compartilhado no Neon;
- autenticacao com perfis `admin` e `operador`;
- bloqueio temporario depois de cinco erros de senha;
- sessoes revalidadas e revogaveis;
- gestao de usuarios exclusiva para administradores;
- auditoria propria do CVJAPP;
- exportacao e carga integral exclusivas para administradores;
- impressao local original preservada;
- backup diario criptografado e testado automaticamente;
- sincronizacao transacional do Neon para o PostgreSQL 10 local, com fila
  persistente e retomada automatica.

Nao existe dependencia de dominio publico, Render ou agente de impressao
remoto nesta versao.

## Execucao

1. Configure o `.env` a partir de `.env.example`.
2. Instale as dependencias de `requirements.txt`.
3. Execute `python server.py` ou `run_server.bat`.

Os usuarios sao compartilhados com o CVJCURA porque as duas aplicacoes usam o
mesmo banco Neon. A auditoria do CVJAPP fica separada na tabela
`cvjapp_audit_events`.

O Neon e a fonte principal dos dados operacionais. O agente local replica as
alteracoes para o PostgreSQL 10 sem expor esse banco na internet. Consulte
[`docs/SINCRONIZACAO_NEON_LOCAL.md`](docs/SINCRONIZACAO_NEON_LOCAL.md).

Consulte tambem:

- [`docs/SEGURANCA.md`](docs/SEGURANCA.md)
- [`docs/BACKUP_E_RESTAURACAO.md`](docs/BACKUP_E_RESTAURACAO.md)
