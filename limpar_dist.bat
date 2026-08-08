@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0limpar_dist.py" --apply %*
) else (
    python "%~dp0limpar_dist.py" --apply %*
)
if errorlevel 1 (
    echo.
    echo A limpeza falhou. Nenhuma outra etapa sera executada.
    exit /b 1
)

echo.
echo Diretorio dist limpo com sucesso.
exit /b 0
