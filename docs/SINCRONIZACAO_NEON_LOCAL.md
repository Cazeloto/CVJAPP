# Sincronizacao Neon -> PostgreSQL local

O Neon e a fonte principal. Toda alteracao feita pelo CVJAPP ou pelo CVJCURA
gera um evento transacional em `cvjcura_sync_outbox`. O agente executado no
computador local aplica esses eventos no PostgreSQL 10 em ordem e grava o
ultimo evento confirmado em `cvjcura_sync_state`.

## Garantias

- nenhuma porta do PostgreSQL local precisa ser exposta na internet;
- se o computador estiver desligado, os eventos permanecem no Neon;
- cada lote e aplicado em uma transacao local;
- o checkpoint so avanca depois que todo o lote foi confirmado;
- a carga inicial faz `upsert` e nao apaga o historico que existe apenas no
  banco local;
- Neon vence em caso de conflito nos registros replicados.

## Configuracao

O `.env` do CVJAPP deve conter `PG_*` para o Neon e `DB_*` para o PostgreSQL
local. As opcoes `SYNC_POLL_SECONDS` e `SYNC_BATCH_SIZE` sao opcionais.

## Primeira execucao

Antes de ativar o processo continuo:

```powershell
.\.venv\Scripts\python.exe sync_agent.py --check
.\.venv\Scripts\python.exe sync_agent.py --initial --once
.\.venv\Scripts\python.exe sync_agent.py --once
```

Depois, instale a tarefa do Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_sync_agent.ps1
```

O log fica em `outputs\sync-agent.log`. A tarefa agendada se chama
`CVJAPP Neon Local Sync`.
