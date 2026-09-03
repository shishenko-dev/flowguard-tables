param(
    [int]$Port = 8787
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
    throw "Python 3.11 или новее не найден. Используйте готовый FlowGuardTables.exe."
}

Push-Location $projectRoot
try {
    & $runtimePython .\app.py --port $Port --open-browser
}
finally {
    Pop-Location
}
