param(
    [switch]$InstallTools,
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundledCandidate = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (Test-Path -LiteralPath $bundledCandidate) {
    $runtimePython = $bundledCandidate
}
elseif ($null -ne $pythonCommand) {
    $runtimePython = $pythonCommand.Source
}
else {
    throw "Python 3.11 или новее не найден."
}

Push-Location $projectRoot
try {
    if ($InstallTools) {
        & $runtimePython -m pip install -r .\requirements-build.txt
    }
    & $runtimePython -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --name FlowGuardTables `
        --add-data "static;static" `
        --add-data "data\sample_records.csv;data" `
        --hidden-import openpyxl `
        .\app.py
    if ($LASTEXITCODE -ne 0) {
        throw "Сборка FlowGuardTables.exe завершилась с кодом $LASTEXITCODE. Архив не создан."
    }

    $releaseRoot = Join-Path $projectRoot "dist\FlowGuardTables-$Version-windows"
    if (Test-Path -LiteralPath $releaseRoot) {
        $projectFull = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd("\")
        $releaseFull = [System.IO.Path]::GetFullPath($releaseRoot)
        $expectedPrefix = "$projectFull\dist\"
        if (-not $releaseFull.StartsWith($expectedPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Отказ от очистки неожиданного пути: $releaseFull"
        }
        Remove-Item -LiteralPath $releaseFull -Recurse -Force
    }
    New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
    Copy-Item -LiteralPath ".\dist\FlowGuardTables.exe" -Destination $releaseRoot -Force
    Copy-Item -LiteralPath ".\LICENSE" -Destination $releaseRoot -Force
    Copy-Item -LiteralPath ".\COMMERCIAL.md" -Destination $releaseRoot -Force
    Copy-Item -LiteralPath ".\README.md" -Destination $releaseRoot -Force
    Copy-Item -LiteralPath ".\CHANGELOG.md" -Destination $releaseRoot -Force
    Copy-Item -LiteralPath ".\SECURITY.md" -Destination $releaseRoot -Force

    $documentationRoot = Join-Path $releaseRoot "Документация"
    New-Item -ItemType Directory -Path $documentationRoot -Force | Out-Null
    Copy-Item -LiteralPath ".\docs\QUICKSTART_RU.md" -Destination $documentationRoot -Force
    Copy-Item -LiteralPath ".\docs\USER_MANUAL_RU.md" -Destination $documentationRoot -Force
    Copy-Item -LiteralPath ".\docs\TEST_REPORT_0.1.0_RU.md" -Destination $documentationRoot -Force
    Copy-Item -LiteralPath ".\docs\RELEASE_NOTES_0.1.0_RU.md" -Destination $documentationRoot -Force
    Copy-Item -LiteralPath ".\docs\screenshot-main.png" -Destination $documentationRoot -Force
    Copy-Item -LiteralPath ".\docs\screenshot-results.png" -Destination $documentationRoot -Force

    $exeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $releaseRoot "FlowGuardTables.exe")).Hash
    "FlowGuardTables.exe  $exeHash" | Set-Content -LiteralPath (Join-Path $releaseRoot "CHECKSUMS-SHA256.txt") -Encoding utf8

    $archivePath = Join-Path $projectRoot "dist\FlowGuardTables-$Version-windows.zip"
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Compress-Archive -Path (Join-Path $releaseRoot "*") -DestinationPath $archivePath -CompressionLevel Optimal
    Write-Host "Готовая программа: $projectRoot\dist\FlowGuardTables.exe"
    Write-Host "Архив для выдачи: $archivePath"
}
finally {
    Pop-Location
}
