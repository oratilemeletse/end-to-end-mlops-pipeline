@description('Private endpoint resource name.')
param name string

@description('Azure region for the private endpoint.')
param location string

@description('Resource ID exposed through Private Link.')
param privateLinkServiceId string

@description('Private Link group ID.')
param groupId string

@description('Subnet resource ID for the private endpoint.')
param subnetId string

@description('Private DNS zone resource IDs associated with this endpoint.')
param privateDnsZoneIds array

@description('Resource tags.')
param tags object

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    privateLinkServiceConnections: [
      {
        name: name
        properties: {
          groupIds: [
            groupId
          ]
          privateLinkServiceId: privateLinkServiceId
        }
      }
    ]
    subnet: {
      id: subnetId
    }
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-07-01' = {
  parent: privateEndpoint
  name: 'azdzg'
  properties: {
    privateDnsZoneConfigs: [
      for (privateDnsZoneId, index) in privateDnsZoneIds: {
        name: 'azcfg${index}'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output id string = privateEndpoint.id

