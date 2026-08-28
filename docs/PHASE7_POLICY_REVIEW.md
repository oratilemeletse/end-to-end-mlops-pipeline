# Phase 7 Azure Policy Review

Review date: 2026-08-21

This review records the inherited Azure Policy constraints used to design the
Phase 7 Bicep templates. Subscription and tenant identifiers are intentionally
excluded from source control.

## Assigned Governance

| Assignment | Effects | Phase 7 impact |
|---|---|---|
| Azure Security Baseline | Audit, AuditIfNotExists | Secure transport, network controls, identity, diagnostics, and data protection are evaluated. |
| MCAPSGov Audit Policies | Audit, AuditIfNotExists | Azure ML requires `allLogs` diagnostics; compute must use current OS images and zero minimum nodes. |
| MCAPSGov Deploy and Modify Policies | Append, DeployIfNotExists, Modify | Public access and local-key settings can be changed automatically; diagnostics and governance resources can be deployed automatically. |
| MCAPSGov Deny Policies | Deny | Blocked VM SKUs and noncompliant Azure SQL authentication prevent deployment. |
| Defender initiatives | DeployIfNotExists | Defender configuration is applied to supported database services. |

## Network and Identity Rules

The modify initiative disables public network access for:

- Storage accounts.
- Key Vaults.
- Azure SQL logical servers.
- Cosmos DB accounts.
- AI Foundry hubs.

It also disables Storage shared-key authentication and anonymous Blob access.
Phase 7 therefore uses Microsoft Entra identities, Azure RBAC, private
endpoints, and private DNS instead of public firewall exceptions or account
keys.

This confirms the previously observed Azure SQL behavior: an Azure SQL server
must use Microsoft Entra-only authentication, and its public network access is
modified to `Disabled`. Any future SQL phase must provision a Microsoft Entra
administrator and private connectivity in the initial template.

## Azure ML Rules

The relevant Azure ML audits require:

- A diagnostic setting with the `allLogs` category group enabled.
- Current operating system images.
- `minNodeCount` set to zero for an `AmlCompute` cluster.

The subscription also denies selected H-, M-, N-, and GPU-oriented VM sizes.
`Standard_DS3_v2` was selected because it is available in South Africa North,
has no subscription restriction, is outside the deny list, and has available
family quota.

## Template Decisions

The Bicep implementation:

- Declares public network access as disabled instead of waiting for policy to
  modify it.
- Uses `systemDatastoresAuthMode: Identity`.
- Disables Storage shared-key and Blob anonymous access.
- Uses separate user-assigned identities for workspace and compute workloads.
- Grants only the Storage and Key Vault data-plane roles required by those
  identities.
- Uses Key Vault RBAC and purge protection.
- Adds private endpoints for Azure ML, Blob, File, and Key Vault.
- Uses a NAT gateway for explicit outbound access from private compute nodes.
- Sends Azure ML logs and metrics to Log Analytics.
- Keeps the training cluster at zero nodes while idle.
- Defers Azure Container Registry until custom Azure ML images justify the
  Premium tier required for Private Link.

Generic guidance that recommends enabling Key Vault public access was not
followed because it directly conflicts with the subscription's enforced
public-network policy.
