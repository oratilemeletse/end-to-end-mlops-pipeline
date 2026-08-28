@description('Deployment environment.')
param environmentName string

@description('Azure region for all platform resources.')
param location string

@description('Deterministic token shared by globally unique resource names.')
param resourceToken string

@description('Maximum nodes in the Azure ML CPU cluster.')
param maxComputeNodes int

@description('Azure ML CPU virtual machine size.')
param computeVmSize string

@description('GitHub repository in owner/repository format.')
param githubRepository string

@description('GitHub environment used by workload identity federation.')
param githubEnvironment string

@description('Optional exact GitHub OIDC subject override.')
param githubFederatedSubject string

@description('Resource tags.')
param tags object

var applicationInsightsName = 'azai${resourceToken}'
var computeClusterName = 'azcpu${resourceToken}'
var computeIdentityName = 'azid${resourceToken}cpu'
var deploymentIdentityName = 'azid${resourceToken}ci'
var keyVaultName = 'azkv${resourceToken}'
var logAnalyticsWorkspaceName = 'azlog${resourceToken}'
var machineLearningWorkspaceName = 'azml${resourceToken}'
var natGatewayName = 'aznat${resourceToken}'
var natPublicIpName = 'azpip${resourceToken}'
var networkSecurityGroupName = 'aznsg${resourceToken}'
var privateEndpointSubnetName = 'azsn${resourceToken}pe'
var storageAccountName = 'azst${resourceToken}'
var trainingSubnetName = 'azsn${resourceToken}cpu'
var virtualNetworkName = 'azvn${resourceToken}'
var workspaceIdentityName = 'azid${resourceToken}ws'
var githubOidcSubject = empty(githubFederatedSubject)
  ? 'repo:${githubRepository}:environment:${githubEnvironment}'
  : githubFederatedSubject

var privateDnsZoneNames = [
  'privatelink.api.azureml.ms'
  'privatelink.notebooks.azure.net'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.file.${environment().suffixes.storage}'
  'privatelink.vaultcore.azure.net'
]

var contributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b24988ac-6180-42a0-ab88-20f7382dd24c'
)
var keyVaultSecretsOfficerRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
)
var rbacAdministratorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'f58310d9-a9f6-439a-9e8d-f62e7b41a168'
)
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var storageFileDataPrivilegedContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '69566ab7-960f-475b-8e7c-b3118f30c6bd'
)

resource networkSecurityGroup 'Microsoft.Network/networkSecurityGroups@2024-07-01' = {
  name: networkSecurityGroupName
  location: location
  tags: tags
}

resource natPublicIp 'Microsoft.Network/publicIPAddresses@2024-07-01' = {
  name: natPublicIpName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAddressVersion: 'IPv4'
    publicIPAllocationMethod: 'Static'
  }
}

resource natGateway 'Microsoft.Network/natGateways@2024-07-01' = {
  name: natGatewayName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: natPublicIp.id
      }
    ]
  }
}

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: virtualNetworkName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.20.0.0/16'
      ]
    }
    subnets: [
      {
        name: trainingSubnetName
        properties: {
          addressPrefix: '10.20.0.0/24'
          defaultOutboundAccess: false
          natGateway: {
            id: natGateway.id
          }
          networkSecurityGroup: {
            id: networkSecurityGroup.id
          }
        }
      }
      {
        name: privateEndpointSubnetName
        properties: {
          addressPrefix: '10.20.1.0/24'
          networkSecurityGroup: {
            id: networkSecurityGroup.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

resource trainingSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' existing = {
  parent: virtualNetwork
  name: trainingSubnetName
}

resource privateEndpointSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' existing = {
  parent: virtualNetwork
  name: privateEndpointSubnetName
}

resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [
  for privateDnsZoneName in privateDnsZoneNames: {
    name: privateDnsZoneName
    location: 'global'
    tags: tags
  }
]

resource privateDnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [
  for (privateDnsZoneName, index) in privateDnsZoneNames: {
    parent: privateDnsZones[index]
    name: 'azlnk${resourceToken}${index}'
    location: 'global'
    tags: tags
    properties: {
      registrationEnabled: false
      virtualNetwork: {
        id: virtualNetwork.id
      }
    }
  }
]

resource workspaceIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: workspaceIdentityName
  location: location
  tags: tags
}

resource computeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: computeIdentityName
  location: location
  tags: tags
}

resource deploymentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: deploymentIdentityName
  location: location
  tags: tags
}

resource githubFederatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2024-11-30' = if (githubRepository != '') {
  parent: deploymentIdentity
  name: 'github${environmentName}'
  properties: {
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: 'https://token.actions.githubusercontent.com'
    subject: githubOidcSubject
  }
}

resource deploymentContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (githubRepository != '') {
  name: guid(resourceGroup().id, deploymentIdentity.id, contributorRoleDefinitionId)
  properties: {
    principalId: deploymentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinitionId
  }
}

resource deploymentRbacAdministratorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (githubRepository != '') {
  name: guid(resourceGroup().id, deploymentIdentity.id, rbacAdministratorRoleDefinitionId)
  properties: {
    principalId: deploymentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: rbacAdministratorRoleDefinitionId
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    isHnsEnabled: false
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Disabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    containerDeleteRetentionPolicy: {
      days: 7
      enabled: true
    }
    deleteRetentionPolicy: {
      days: 7
      enabled: true
    }
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    accessPolicies: []
    enablePurgeProtection: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: 'Disabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
    softDeleteRetentionInDays: 90
    tenantId: tenant().tenantId
  }
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    features: {
      disableLocalAuth: true
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
    workspaceCapping: {
      dailyQuotaGb: 1
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    DisableLocalAuth: true
    IngestionMode: 'LogAnalytics'
    RetentionInDays: 30
    WorkspaceResourceId: logAnalyticsWorkspace.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

resource workspaceStorageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workspaceIdentity.id, storageBlobDataContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: workspaceIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource workspaceStorageFileRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, workspaceIdentity.id, storageFileDataPrivilegedContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: workspaceIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageFileDataPrivilegedContributorRoleDefinitionId
  }
}

resource computeStorageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, computeIdentity.id, storageBlobDataContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: computeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
  }
}

resource computeStorageFileRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, computeIdentity.id, storageFileDataPrivilegedContributorRoleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: computeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageFileDataPrivilegedContributorRoleDefinitionId
  }
}

resource workspaceKeyVaultSecretsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, workspaceIdentity.id, keyVaultSecretsOfficerRoleDefinitionId)
  scope: keyVault
  properties: {
    principalId: workspaceIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsOfficerRoleDefinitionId
  }
}

resource machineLearningWorkspace 'Microsoft.MachineLearningServices/workspaces@2025-06-01' = {
  name: machineLearningWorkspaceName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workspaceIdentity.id}': {}
    }
  }
  properties: {
    applicationInsights: applicationInsights.id
    description: 'Policy-compliant Azure ML workspace for ${environmentName}.'
    friendlyName: '${environmentName} MLOps workspace'
    hbiWorkspace: false
    keyVault: keyVault.id
    managedNetwork: {
      isolationMode: 'Disabled'
    }
    primaryUserAssignedIdentity: workspaceIdentity.id
    publicNetworkAccess: 'Disabled'
    storageAccount: storageAccount.id
    systemDatastoresAuthMode: 'Identity'
    v1LegacyMode: false
  }
  dependsOn: [
    workspaceKeyVaultSecretsRole
    workspaceStorageBlobRole
    workspaceStorageFileRole
  ]
}

resource computeCluster 'Microsoft.MachineLearningServices/workspaces/computes@2025-06-01' = {
  parent: machineLearningWorkspace
  name: computeClusterName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${computeIdentity.id}': {}
    }
  }
  properties: {
    computeType: 'AmlCompute'
    description: 'Autoscaling CPU cluster for reproducible training jobs.'
    disableLocalAuth: true
    properties: {
      enableNodePublicIp: false
      osType: 'Linux'
      remoteLoginPortPublicAccess: 'Disabled'
      scaleSettings: {
        maxNodeCount: maxComputeNodes
        minNodeCount: 0
        nodeIdleTimeBeforeScaleDown: 'PT5M'
      }
      subnet: {
        id: trainingSubnet.id
      }
      vmPriority: 'Dedicated'
      vmSize: computeVmSize
    }
  }
  dependsOn: [
    computeStorageBlobRole
    computeStorageFileRole
    machineLearningPrivateEndpoint
  ]
}

resource workspaceDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'azdiag${resourceToken}'
  scope: machineLearningWorkspace
  properties: {
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
    workspaceId: logAnalyticsWorkspace.id
  }
}

module storageBlobPrivateEndpoint 'private-endpoint.bicep' = {
  name: 'azdep${resourceToken}stb'
  params: {
    groupId: 'blob'
    location: location
    name: 'azpe${resourceToken}stb'
    privateDnsZoneIds: [
      privateDnsZones[2].id
    ]
    privateLinkServiceId: storageAccount.id
    subnetId: privateEndpointSubnet.id
    tags: tags
  }
}

module storageFilePrivateEndpoint 'private-endpoint.bicep' = {
  name: 'azdep${resourceToken}stf'
  params: {
    groupId: 'file'
    location: location
    name: 'azpe${resourceToken}stf'
    privateDnsZoneIds: [
      privateDnsZones[3].id
    ]
    privateLinkServiceId: storageAccount.id
    subnetId: privateEndpointSubnet.id
    tags: tags
  }
}

module keyVaultPrivateEndpoint 'private-endpoint.bicep' = {
  name: 'azdep${resourceToken}kv'
  params: {
    groupId: 'vault'
    location: location
    name: 'azpe${resourceToken}kv'
    privateDnsZoneIds: [
      privateDnsZones[4].id
    ]
    privateLinkServiceId: keyVault.id
    subnetId: privateEndpointSubnet.id
    tags: tags
  }
}

module machineLearningPrivateEndpoint 'private-endpoint.bicep' = {
  name: 'azdep${resourceToken}ml'
  params: {
    groupId: 'amlworkspace'
    location: location
    name: 'azpe${resourceToken}ml'
    privateDnsZoneIds: [
      privateDnsZones[0].id
      privateDnsZones[1].id
    ]
    privateLinkServiceId: machineLearningWorkspace.id
    subnetId: privateEndpointSubnet.id
    tags: tags
  }
}

output applicationInsightsName string = applicationInsights.name
output computeClusterName string = computeCluster.name
output deploymentIdentityClientId string = deploymentIdentity.properties.clientId
output keyVaultName string = keyVault.name
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name
output machineLearningWorkspaceName string = machineLearningWorkspace.name
output storageAccountName string = storageAccount.name
