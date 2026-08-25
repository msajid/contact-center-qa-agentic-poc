#Requires -Version 7.3
<#
.SYNOPSIS
    Deploy the Contact Center QA POC to Azure Container Apps (build from source),
    give it a managed identity, and grant that identity access to the Foundry resource.

.DESCRIPTION
    Idempotent enough to re-run. Requires an authenticated Azure CLI (az login) with
    rights to create resources and role assignments in the target subscription.

.EXAMPLE
    ./deploy/azure-containerapp.ps1 `
        -FoundryAccount '<foundry-account-name>' `
        -FoundryResourceGroup '<foundry-resource-group>' `
        -FoundryEndpoint 'https://<resource>.services.ai.azure.com/api/projects/<project>'
#>
[CmdletBinding()]
param(
    [string]$ResourceGroup = 'rg-ccqa-demo',
    [string]$Location = 'eastus',
    [string]$AppName = 'ccqa-app',
    [string]$EnvironmentName = 'ccqa-env',
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$FoundryAccount,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$FoundryResourceGroup,
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$FoundryEndpoint,
    [string]$FoundryModel = 'gpt-4o'
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host '==> Ensuring Container Apps CLI + providers' -ForegroundColor Cyan
az extension add --name containerapp --upgrade --only-show-errors | Out-Null
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

Write-Host "==> Resource group $ResourceGroup ($Location)" -ForegroundColor Cyan
az group create --name $ResourceGroup --location $Location --output none

Write-Host '==> Building image from source and deploying the container app' -ForegroundColor Cyan
$buildContext = Join-Path ([System.IO.Path]::GetTempPath()) "ccqa-build-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $buildContext | Out-Null
try {
    foreach ($item in @('Dockerfile', 'requirements.txt', 'backend', 'frontend')) {
        Copy-Item -Path (Join-Path $repoRoot $item) -Destination $buildContext -Recurse
    }

    az containerapp up `
        --name $AppName `
        --resource-group $ResourceGroup `
        --location $Location `
        --environment $EnvironmentName `
        --source $buildContext `
        --ingress external `
        --target-port 8000 `
        --env-vars "FOUNDRY_PROJECT_ENDPOINT=$FoundryEndpoint" "FOUNDRY_MODEL=$FoundryModel" 'AZURE_CREDENTIAL=default' 'ENABLE_WEB_SEARCH=true' 'LOG_LEVEL=INFO' 'ENABLE_AGENT_TRACES=false'
}
finally {
    Remove-Item -Path $buildContext -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host '==> Assigning a system-managed identity' -ForegroundColor Cyan
$principalId = az containerapp identity assign `
    --name $AppName --resource-group $ResourceGroup --system-assigned `
    --query principalId --output tsv

Write-Host '==> Granting the identity access to the Foundry resource' -ForegroundColor Cyan
$foundryId = az cognitiveservices account show `
    --name $FoundryAccount --resource-group $FoundryResourceGroup --query id --output tsv
foreach ($role in @('Azure AI Developer', 'Cognitive Services OpenAI User')) {
    az role assignment create `
        --assignee-object-id $principalId --assignee-principal-type ServicePrincipal `
        --role $role --scope $foundryId --output none
}

Write-Host '==> Restarting the active revision to pick up the identity' -ForegroundColor Cyan
$revision = az containerapp revision list --name $AppName --resource-group $ResourceGroup --query '[0].name' --output tsv
az containerapp revision restart --name $AppName --resource-group $ResourceGroup --revision $revision --output none

$fqdn = az containerapp show --name $AppName --resource-group $ResourceGroup `
    --query 'properties.configuration.ingress.fqdn' --output tsv
Write-Host "==> Deployed: https://$fqdn" -ForegroundColor Green
