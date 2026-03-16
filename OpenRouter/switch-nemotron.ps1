# Script pour basculer Claude Code sur OpenRouter (NVIDIA Nemotron)
# Usage: . .\switch-nemotron.ps1

if (Test-Path ".env.ai") {
    $EnvFile = Get-Content ".env.ai"
    foreach ($line in $EnvFile) {
        if ($line -match "^(?<key>[^=]+)=(?<value>.+)$") {
            [System.Environment]::SetEnvironmentVariable($Matches.key, $Matches.value, "Process")
        }
    }
} else {
    Write-Host "Erreur : Fichier .env.ai introuvable." -ForegroundColor Red
    return
}

# Configuration du proxy OpenRouter
$env:CLAUDE_CODE_USE_FOUNDRY = $null
$env:ANTHROPIC_FOUNDRY_API_KEY = $null
$env:ANTHROPIC_FOUNDRY_BASE_URL = $null

# "Peau d'Anthropic" sur OpenRouter
$env:ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
$env:ANTHROPIC_AUTH_TOKEN = $env:NEMOTRON_KEY
$env:ANTHROPIC_API_KEY = "" # On vide la clé standard pour éviter les conflits

# On force Claude Code à utiliser le modèle Nemotron
$env:ANTHROPIC_MODEL = $env:NEMOTRON_MODEL
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $env:NEMOTRON_MODEL

Write-Host ">>> MODE NVIDIA NEMOTRON ACTIF (OpenRouter - FREE)" -ForegroundColor Yellow
Write-Host "Note: Tapez 'claude /logout' si vous avez un message de conflit d'authentification." -ForegroundColor Gray
Write-Host "Vous pouvez maintenant lancer 'claude'." -ForegroundColor Gray
