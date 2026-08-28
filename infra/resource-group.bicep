@description('Deployment environment.')
@allowed([
  'dev'
  'staging'
  'production'
])
param environmentName string

@description('Azure region for platform resources.')
param location string

@description('Project name used for resource tags.')
param projectName string = 'e2emlops'

@description('Maximum nodes in the Azure ML CPU cluster.')
@minValue(1)
param maxComputeNodes int = 2

@description('Allowed Azure ML CPU virtual machine size.')
param computeVmSize string = 'Standard_DS3_v2'

@description('GitHub repository in owner/repository format.')
param githubRepository string = ''

@description('GitHub environment used in the workload identity subject.')
param githubEnvironment string = environmentName

@description('Optional exact GitHub OIDC subject for organizations that customize subject claims.')
param githubFederatedSubject string = ''

var resourceToken = uniqueString(subscription().id, location, environmentName)
var commonTags = {
  environment: environmentName
  managedBy: 'bicep'
  project: projectName
  phase: '7'
}

module platform 'modules/ml-platform.bicep' = {
  name: 'azdep${resourceToken}'
  params: {
    computeVmSize: computeVmSize
    environmentName: environmentName
    githubEnvironment: githubEnvironment
    githubFederatedSubject: githubFederatedSubject
    githubRepository: githubRepository
    location: location
    maxComputeNodes: maxComputeNodes
    resourceToken: resourceToken
    tags: commonTags
  }
}

output applicationInsightsName string = platform.outputs.applicationInsightsName
output computeClusterName string = platform.outputs.computeClusterName
output deploymentIdentityClientId string = platform.outputs.deploymentIdentityClientId
output keyVaultName string = platform.outputs.keyVaultName
output logAnalyticsWorkspaceName string = platform.outputs.logAnalyticsWorkspaceName
output machineLearningWorkspaceName string = platform.outputs.machineLearningWorkspaceName
output storageAccountName string = platform.outputs.storageAccountName
