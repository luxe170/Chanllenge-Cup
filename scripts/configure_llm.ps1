param(
  [Parameter(Mandatory = $true)]
  [string]$ApiKey,

  [string]$Model = "deepseek-v4-flash",
  [string]$BaseUrl = "https://api.deepseek.com",
  [bool]$EnableResumeLlm = $true
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
$resumeEnabled = if ($EnableResumeLlm) { "true" } else { "false" }

$content = @(
  "LLM_API_KEY=$ApiKey",
  "LLM_BASE_URL=$BaseUrl",
  "LLM_MODEL=$Model",
  "LLM_RESUME_ENABLED=$resumeEnabled"
)

Set-Content -LiteralPath $envPath -Value $content -Encoding UTF8
Write-Host "LLM configuration written to .env. The key is stored locally and ignored by git."
