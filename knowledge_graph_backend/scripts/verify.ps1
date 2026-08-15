$ErrorActionPreference = 'Stop'
$BackendRoot = Split-Path -Parent $PSScriptRoot
$TempRoot = Join-Path (Split-Path -Parent $BackendRoot) 'knowledge_graph_backend_temp'
$env:PYTHONPYCACHEPREFIX = Join-Path $TempRoot 'pycache'
$env:COVERAGE_FILE = Join-Path $TempRoot '.coverage'

Push-Location $BackendRoot
try {
    python -m compileall -q app tests
    pytest --basetemp (Join-Path $TempRoot 'pytest') -o "cache_dir=$(Join-Path $TempRoot 'pytest_cache')" --cov=app --cov-report=term-missing
}
finally {
    Pop-Location
}
