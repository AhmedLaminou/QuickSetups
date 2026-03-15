param([string]$Profile)

# Charge les secrets depuis le fichier .env
if (Test-Path ".env.ai") {
    $EnvFile = Get-Content ".env.ai"
    foreach ($line in $EnvFile) {
        if ($line -match "^(?<key>[^=]+)=(?<value>.+)$") {
            [System.Environment]::SetEnvironmentVariable($Matches.key, $Matches.value, "Process")
        }
    }
}

switch ($Profile) {
    "sonnet" {
        $env:CLAUDE_CODE_USE_FOUNDRY = "1"
        $env:ANTHROPIC_FOUNDRY_API_KEY = $env:AZURE_SONNET_KEY
        $env:ANTHROPIC_FOUNDRY_BASE_URL = $env:AZURE_SONNET_URL
        $env:ANTHROPIC_DEFAULT_SONNET_MODEL = "claude-sonnet-4-6"
        Write-Host ">>> MODE SONNET ACTIF (Azure)" -ForegroundColor Green
    }
    "opus" {
        $env:CLAUDE_CODE_USE_FOUNDRY = "1"
        $env:ANTHROPIC_FOUNDRY_API_KEY = $env:AZURE_OPUS_KEY
        $env:ANTHROPIC_FOUNDRY_BASE_URL = $env:AZURE_OPUS_URL
        $env:ANTHROPIC_DEFAULT_OPUS_MODEL = "claude-opus-4-6"
        Write-Host ">>> MODE OPUS ACTIF (Azure)" -ForegroundColor Cyan
    }
}
