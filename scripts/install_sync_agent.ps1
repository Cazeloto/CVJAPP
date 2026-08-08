param(
    [string]$Python = "C:\CVJAPP\.venv\Scripts\python.exe",
    [string]$AppDir = "C:\CVJAPP"
)

$ErrorActionPreference = "Stop"
$Python = (Resolve-Path -LiteralPath $Python).Path
$AppDir = (Resolve-Path -LiteralPath $AppDir).Path
$AgentScript = Join-Path $AppDir "sync_agent.py"
$EnvPath = Join-Path $AppDir ".env"

if (-not (Test-Path -LiteralPath $AgentScript -PathType Leaf)) {
    throw "Agente nao encontrado: $AgentScript"
}
if (-not (Test-Path -LiteralPath $EnvPath -PathType Leaf)) {
    throw "Configuracao nao encontrada: $EnvPath"
}

& $Python $AgentScript --env $EnvPath --check
if ($LASTEXITCODE -ne 0) {
    throw "A validacao das conexoes do agente falhou."
}

$TaskName = "CVJAPP Neon Local Sync"
$Arguments = "`"$AgentScript`" --env `"$EnvPath`""
$Action = New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $AppDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}
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
Write-Host "Log: $AppDir\outputs\sync-agent.log"
