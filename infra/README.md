---
title: Phase 7 Azure Infrastructure
description: Prepare, validate, and deploy the private Azure ML platform with Bicep.
---

This directory contains subscription-scoped Bicep for the Azure Machine
Learning development, staging, and production environments.

No subscription IDs, tenant IDs, credentials, tokens, or connection strings
are stored in these files. Resource names are deterministic per subscription,
region, and environment.

## Architecture

The templates provision:

- An Azure Machine Learning workspace with public network access disabled.
- A private Storage account with shared-key access disabled.
- A private, RBAC-enabled Key Vault with purge protection.
- A Log Analytics workspace and workspace-based Application Insights.
- An autoscaling CPU training cluster with zero minimum nodes.
- Separate user-assigned identities for the workspace, compute, and CI.
- Least-privilege Storage and Key Vault data-plane role assignments.
- A virtual network, network security group, private endpoints, and private
  DNS zones for Azure ML, Blob, File, and Key Vault.
- A NAT gateway that gives private compute nodes explicit outbound access
  without assigning public IP addresses to individual nodes.
- Azure ML diagnostic logs and metrics sent to Log Analytics.
- An optional GitHub Actions federated credential when `githubRepository` is
  supplied during the first deployment.

Azure Container Registry is intentionally deferred. A private registry
requires the Premium tier for Private Link and would add idle cost before the
project needs custom images in Azure ML.

## Policy-Aware Choices

The selected subscription inherits governance policies that:

- Modify Storage and Key Vault public network access to `Disabled`.
- Modify Storage shared-key access to `false`.
- Audit Azure ML workspaces without `allLogs` diagnostics.
- Audit Azure ML compute that does not use current images or has minimum nodes
  above zero.
- Deny several expensive H-, M-, N-, and GPU-oriented VM SKUs.
- Deny Azure SQL servers that do not use Microsoft Entra-only authentication.
- Modify Azure SQL public network access to `Disabled`.

The templates declare these settings directly instead of relying on policy to
repair resources after deployment. See
[`docs/PHASE7_POLICY_REVIEW.md`](../docs/PHASE7_POLICY_REVIEW.md).

## Local Validation

### Generate a deployment bundle

Use PowerShell 7 and the installed Azure CLI with Bicep to generate the
approved development artifacts. This command compiles locally and does not
sign in, contact ARM, provision resources, or submit training:

```powershell
pwsh -File scripts\prepare_deployment.ps1 `
  -EnvironmentName dev `
  -GitHubRepository 'oratilemeletse/end-to-end-mlops-pipeline'
```

The ignored `outputs/deployment/dev/` directory contains:

| Artifact | Purpose |
|---|---|
| `subscription.template.json` | Bootstrap the resource group and platform |
| `subscription.parameters.json` | Development configuration and GitHub OIDC inputs |
| `resource-group.template.json` | Update an existing environment at resource-group scope |
| `resource-group.parameters.json` | The same approved inputs for scoped updates |

The parameter files contain no subscription identifiers or credentials. Both
scopes use the checked environment configuration, including VM size and node
limit, rather than duplicating these settings in a second deployment recipe.
Use `-GitHubFederatedSubject` when your organization customizes the OIDC subject.
The command overwrites only its four named bundle files on subsequent runs.
A failed compilation raises an error; do not deploy a bundle from a failed run.

Validate and preview the bootstrap bundle after confirming your account and
setting `AZURE_SUBSCRIPTION_ID` to the intended subscription:

```powershell
if ([string]::IsNullOrWhiteSpace($env:AZURE_SUBSCRIPTION_ID)) {
  throw 'Set AZURE_SUBSCRIPTION_ID to the reviewed deployment target.'
}
az deployment sub validate `
  --subscription $env:AZURE_SUBSCRIPTION_ID `
  --location southafricanorth `
  --template-file outputs\deployment\dev\subscription.template.json `
  --parameters '@outputs\deployment\dev\subscription.parameters.json'
az deployment sub what-if `
  --subscription $env:AZURE_SUBSCRIPTION_ID `
  --location southafricanorth `
  --template-file outputs\deployment\dev\subscription.template.json `
  --parameters '@outputs\deployment\dev\subscription.parameters.json'
```

For an already provisioned environment, use `az deployment group validate`
and `az deployment group what-if` with the resource-group bundle and an explicit
`--resource-group` instead. Do not bootstrap a second environment merely
because a historical session recorded different deterministic resource names.
Resolve the actual target from current deployment outputs.

Private Azure ML, Blob, File, and Key Vault data-plane operations require a
network-connected operator or runner with private DNS resolution. GitHub-hosted
runners can run ARM validation and infrastructure updates but cannot upload
data or submit jobs to the private workspace without network connectivity.

### Validate source templates

Confirm the intended account before every Azure command:

```powershell
az account show --query "{name:name, tenantId:tenantId, subscriptionId:id}"
```

Build the templates without contacting Azure:

```powershell
az bicep build --file infra\main.bicep --stdout 1>$null
Get-ChildItem infra\environments\*.bicepparam |
  ForEach-Object {
    az bicep build-params --file $_.FullName --stdout 1>$null
  }
```

Validate the development environment without creating resources:

```powershell
az deployment sub validate `
  --name phase7-dev `
  --location southafricanorth `
  --parameters infra\environments\dev.bicepparam
```

Review the exact development changes without creating resources:

```powershell
az deployment sub what-if `
  --name phase7-dev `
  --location southafricanorth `
  --parameters infra\environments\dev.bicepparam `
  --result-format ResourceIdOnly
```

## First Deployment and GitHub OIDC

The first deployment must be run interactively by an authorized owner because
it bootstraps the GitHub workload identity and its resource-group-scoped role
assignments. Replace `OWNER/REPOSITORY` with the actual GitHub repository:

```powershell
az deployment sub create `
  --name phase7-dev `
  --location southafricanorth `
  --parameters infra\environments\dev.bicepparam `
  --parameters githubRepository='OWNER/REPOSITORY'
```

If the GitHub organization customizes OIDC subject claims, pass the exact
subject reported by `azure/login`:

```powershell
az deployment sub create `
  --name phase7-dev `
  --location southafricanorth `
  --parameters infra\environments\dev.bicepparam `
  --parameters githubRepository='OWNER/REPOSITORY' `
  --parameters githubFederatedSubject='<exact-subject-claim>'
```

Read the generated values:

```powershell
az deployment sub show `
  --name phase7-dev `
  --query "properties.outputs.{
    clientId:deploymentIdentityClientId.value,
    resourceGroup:resourceGroupName.value
  }"
```

Create GitHub environments named `dev`, `staging`, and `production`. Add these
non-secret environment variables:

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | `deploymentIdentityClientId` output |
| `AZURE_TENANT_ID` | `az account show --query tenantId --output tsv` |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id --output tsv` |

Protect staging and production with required reviewers. The infrastructure
workflow uses `infra/resource-group.bicep` after the interactive bootstrap so
the federated identity needs permissions only on its environment resource
group. It always builds and validates first, runs `what-if` before deployment,
and deploys only through an explicit manual `workflow_dispatch` selection.

## Cost Controls

- The training cluster has `minNodeCount: 0` and scales down after five idle
  minutes. Compute charges occur only while nodes run.
- Log Analytics is capped at 1 GB/day with 30-day retention.
- Storage uses locally redundant Standard storage.
- No Premium Container Registry is provisioned.
- Private endpoints have hourly charges even when no training runs are active.
- The NAT gateway and its public IP have hourly charges while deployed.
- Log Analytics, Application Insights, Storage, and Key Vault can incur
  consumption charges while the environment exists.

Deploy only when the Azure phases are being used actively.

## Cleanup

Resolve the resource group from deployment outputs, review it, and then delete
only that environment:

```powershell
$resourceGroup = az deployment sub show `
  --name phase7-dev `
  --query properties.outputs.resourceGroupName.value `
  --output tsv

Write-Host "Deleting Phase 7 resource group: $resourceGroup"
az group delete --name $resourceGroup --yes --no-wait
```

Key Vault purge protection is intentionally enabled. Deleting the resource
group soft-deletes the vault; Azure retains it for the configured retention
period and it cannot be force-purged while purge protection applies.
