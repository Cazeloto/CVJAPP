param(
    [string]$AgentExe = (Join-Path $PSScriptRoot "..\CVJAPP_SyncAgent.exe"),
    [string]$EnvPath = (Join-Path $PSScriptRoot "..\CVJAPP_Server\.env"),
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "CVJAPP Sync Agent"),
    [switch]$RunInitialSync
)

$ErrorActionPreference = "Stop"
$AgentExe = (Resolve-Path -LiteralPath $AgentExe).Path
$EnvPath = (Resolve-Path -LiteralPath $EnvPath).Path
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$TaskName = "CVJAPP Neon Local Sync"

if (-not (Test-Path -LiteralPath $AgentExe -PathType Leaf)) {
    throw "Agente nao encontrado: $AgentExe"
}
if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
    throw "Configuracao nao encontrada: $EnvPath"
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
$InstalledAgent = Join-Path $InstallDir "CVJAPP_SyncAgent.exe"

$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}
$AgentProcesses = Get-CimInstance Win32_Process -Filter "Name='CVJAPP_SyncAgent.exe'" |
    Where-Object { $_.ExecutablePath -eq $InstalledAgent }
foreach ($AgentProcess in $AgentProcesses) {
    Stop-Process -Id $AgentProcess.ProcessId -Force
}

Copy-Item -LiteralPath $AgentExe -Destination $InstalledAgent -Force

& $InstalledAgent --env $EnvPath --check
if ($LASTEXITCODE -ne 0) {
    throw "A validacao das conexoes do agente falhou."
}

if ($RunInitialSync) {
    & $InstalledAgent --env $EnvPath --initial --once
    if ($LASTEXITCODE -ne 0) {
        throw "A carga inicial falhou."
    }
} else {
    & $InstalledAgent --env $EnvPath --once
    if ($LASTEXITCODE -ne 0) {
        throw "O banco local ainda nao foi inicializado. Execute novamente com -RunInitialSync depois de gerar o backup."
    }
}

$Arguments = "--env `"$EnvPath`""
$Action = New-ScheduledTaskAction `
    -Execute $InstalledAgent `
    -Argument $Arguments `
    -WorkingDirectory $InstallDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Replica alteracoes do Neon para o PostgreSQL 10 local." `
    -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Agente de sincronizacao instalado e iniciado."
Write-Host "Tarefa: $TaskName"
Write-Host "Executavel: $InstalledAgent"
Write-Host "Configuracao: $EnvPath"
Write-Host "Log: $([System.IO.Path]::GetDirectoryName($EnvPath))\outputs\sync-agent.log"
