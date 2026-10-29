[CmdletBinding()]
param(
    [ValidateSet('dev', 'staging', 'production')]
    [string] $EnvironmentName = 'dev',

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')]
    [string] $GitHubRepository,

    [string] $GitHubFederatedSubject = '',

    [string] $OutputDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path $PSScriptRoot -Parent
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $repositoryRoot "outputs\deployment\$EnvironmentName"
}
$null = New-Item -ItemType Directory -Path $OutputDirectory -Force
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$null = Get-Command az -ErrorAction Stop

function Invoke-AzureCli {
    param([string[]] $Arguments)

    & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI failed with exit code ${LASTEXITCODE}: az $($Arguments -join ' ')"
    }
}

$subscriptionTemplate = Join-Path $OutputDirectory 'subscription.template.json'
$groupTemplate = Join-Path $OutputDirectory 'resource-group.template.json'
$subscriptionParameters = Join-Path $OutputDirectory 'subscription.parameters.json'
$groupParameters = Join-Path $OutputDirectory 'resource-group.parameters.json'

Invoke-AzureCli -Arguments @(
    'bicep', 'build', '--file', (Join-Path $repositoryRoot 'infra\main.bicep'),
    '--outfile', $subscriptionTemplate, '--only-show-errors'
)
Invoke-AzureCli -Arguments @(
    'bicep', 'build', '--file', (Join-Path $repositoryRoot 'infra\resource-group.bicep'),
    '--outfile', $groupTemplate, '--only-show-errors'
)

$parameterJson = Invoke-AzureCli -Arguments @(
    'bicep', 'build-params', '--file',
    (Join-Path $repositoryRoot "infra\environments\$EnvironmentName.bicepparam"),
    '--stdout', '--only-show-errors'
)
$compiled = ($parameterJson -join "`n") | ConvertFrom-Json -AsHashtable
$parameters = $compiled.parametersJson | ConvertFrom-Json -AsHashtable
if ($parameters.parameters.environmentName.value -ne $EnvironmentName) {
    throw 'The compiled parameter environment does not match the requested environment.'
}
$parameters.parameters.githubRepository = @{ value = $GitHubRepository }
$parameters.parameters.githubEnvironment = @{ value = $EnvironmentName }
$parameters.parameters.githubFederatedSubject = @{ value = $GitHubFederatedSubject }

foreach ($path in @($subscriptionParameters, $groupParameters)) {
    $parameters | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $path -Encoding utf8
}

Write-Host "Prepared $EnvironmentName deployment artifacts in $OutputDirectory"
Write-Host 'No Azure resources were provisioned. Review and validate before deployment.'
