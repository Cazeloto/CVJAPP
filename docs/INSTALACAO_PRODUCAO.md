# Instalacao do CVJAPP em producao

O pacote nao contem senhas. Antes da instalacao, edite uma copia de
`.env.example` e salve como `CVJAPP_Server\.env`.

## 1. Configurar

- `PG_*`: conexao com o Neon;
- `DB_*`: conexao com o PostgreSQL 10 local;
- `ACCESS_*`: somente para a criacao inicial de usuario, quando aplicavel;
- `PDF_DIR`: pasta de documentos e impressoes.

## 2. Validar a aplicacao

Execute `CVJAPP_Server\CVJAPP_Server.exe` e abra
`http://127.0.0.1:8550`. Copie sempre a pasta `CVJAPP_Server` inteira; o
executavel depende de `_internal`.

## 3. Fazer backup local

Antes da primeira sincronizacao, gere um backup completo e validado do banco
PostgreSQL local.

## 4. Instalar o sincronizador

Na primeira instalacao, depois do backup:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_sync_agent.ps1 -RunInitialSync
```

Em atualizacoes futuras:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_sync_agent.ps1
```

A tarefa `CVJAPP Neon Local Sync` inicia no login do usuario Windows que fez a
instalacao. O log fica em `CVJAPP_Server\outputs\sync-agent.log`.

## 5. Verificar

```powershell
Get-ScheduledTask -TaskName "CVJAPP Neon Local Sync"
```

O estado esperado e `Running`.
