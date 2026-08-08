param(
    [string]$Python = (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
    [string]$ReleaseName = ("CVJAPP_Producao_{0}" -f (Get-Date -Format "yyyyMMdd_HHmm"))
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Python = (Resolve-Path -LiteralPath $Python).Path
$ReleaseRoot = Join-Path $ProjectRoot "release"
$ReleaseDir = Join-Path $ReleaseRoot $ReleaseName
$ZipPath = Join-Path $ReleaseRoot ($ReleaseName + ".zip")

if ([System.IO.Path]::GetFullPath($ReleaseDir).StartsWith([System.IO.Path]::GetFullPath($ReleaseRoot)) -ne $true) {
    throw "Destino de release invalido."
}
if (Test-Path -LiteralPath $ReleaseDir) {
    throw "A release ja existe: $ReleaseDir"
}
if (Test-Path -LiteralPath $ZipPath) {
    throw "O ZIP ja existe: $ZipPath"
}

Push-Location $ProjectRoot
try {
    & $Python -m PyInstaller --clean --noconfirm .\CVJAPP_Server.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar CVJAPP_Server." }

    & $Python .\limpar_dist.py --apply
    if ($LASTEXITCODE -ne 0) { throw "Falha ao limpar CVJAPP_Server." }

    & $Python -m PyInstaller --clean --noconfirm .\CVJAPP_SyncAgent.spec
    if ($LASTEXITCODE -ne 0) { throw "Falha ao compilar CVJAPP_SyncAgent." }

    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    Copy-Item -LiteralPath .\dist\CVJAPP_Server -Destination (Join-Path $ReleaseDir "CVJAPP_Server") -Recurse
    Copy-Item -LiteralPath .\dist\CVJAPP_SyncAgent.exe -Destination (Join-Path $ReleaseDir "CVJAPP_SyncAgent.exe")
    Copy-Item -LiteralPath .\scripts\install_sync_agent.ps1 -Destination (Join-Path $ReleaseDir "install_sync_agent.ps1")
    Copy-Item -LiteralPath .\.env.example -Destination (Join-Path $ReleaseDir ".env.example")
    Copy-Item -LiteralPath .\docs\INSTALACAO_PRODUCAO.md -Destination (Join-Path $ReleaseDir "LEIA-ME.md")

    $HashLines = Get-ChildItem -LiteralPath $ReleaseDir -Recurse -File |
        Sort-Object FullName |
        ForEach-Object {
            $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
            $Relative = $_.FullName.Substring($ReleaseDir.Length + 1)
            "$($Hash.Hash.ToLowerInvariant())  $Relative"
        }
    $HashLines | Set-Content -LiteralPath (Join-Path $ReleaseDir "CHECKSUMS.sha256") -Encoding UTF8

    Compress-Archive -LiteralPath $ReleaseDir -DestinationPath $ZipPath -CompressionLevel Optimal
    $ZipHash = Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath
    Write-Host "Pacote: $ZipPath"
    Write-Host "SHA256: $($ZipHash.Hash.ToLowerInvariant())"
} finally {
    Pop-Location
}
