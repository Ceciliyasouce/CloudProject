@description('Admin username for the VMSS')
param adminUsername string = 'azureuser'

@description('SSH public key for VM login')
param adminPublicKey string

@description('Number of VM instances')
param instanceCount int = 2

@description('VM SKU type')
param vmSku string = 'Standard_B1s'

@description('Flask app port')
param port string = '5000'

@secure()
@description('Storage connection string for Flask app')
param connectionString string

@description('Container name for the Flask app')
param containerName string

var location = resourceGroup().location
var lbName = 'vmss-lb'

// Reference existing VNet and Subnet in CloudProj RG
var subnetId = resourceId('CloudProj', 'Microsoft.Network/virtualNetworks/subnets', 'vmss-vnet', 'vmss-subnet')

// Declare resource IDs to avoid self-reference issues
var frontendIPConfigId = resourceId('Microsoft.Network/loadBalancers/frontendIPConfigurations', lbName, 'frontend')
var backendPoolId = resourceId('Microsoft.Network/loadBalancers/backendAddressPools', lbName, 'backendPool')
var probeId = resourceId('Microsoft.Network/loadBalancers/probes', lbName, 'tcpProbe')

// NSG
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-02-01' = {
  name: 'vmss-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowHTTP'
        properties: {
          priority: 1001
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: port
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowSSH'
        properties: {
          priority: 1002
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// Load Balancer
resource lb 'Microsoft.Network/loadBalancers@2023-02-01' = {
  name: lbName
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    frontendIPConfigurations: [
      {
        name: 'frontend'
        properties: {
          publicIPAddress: {
            id: resourceId('CloudProj', 'Microsoft.Network/publicIPAddresses', 'MyPublicIP')
          }
        }
      }
    ]
    backendAddressPools: [
      {
        name: 'backendPool'
      }
    ]
    probes: [
      {
        name: 'tcpProbe'
        properties: {
          protocol: 'Tcp'
          port: int(port)
        }
      }
    ]
    loadBalancingRules: [
      {
        name: 'httpRule'
        properties: {
          protocol: 'Tcp'
          frontendPort: int(port)
          backendPort: int(port)
          enableFloatingIP: false
          idleTimeoutInMinutes: 5
          loadDistribution: 'Default'
          frontendIPConfiguration: {
            id: frontendIPConfigId
          }
          backendAddressPool: {
            id: backendPoolId
          }
          probe: {
            id: probeId
          }
        }
      }
    ]
  }
}

// VMSS
resource vmss 'Microsoft.Compute/virtualMachineScaleSets@2023-03-01' = {
  name: 'flaskVMSS'
  location: location
  sku: {
    name: vmSku
    capacity: instanceCount
    tier: 'Standard'
  }
  properties: {
    upgradePolicy: {
      mode: 'Manual'
    }
    virtualMachineProfile: {
      storageProfile: {
        imageReference: {
          publisher: 'Canonical'
          offer: 'UbuntuServer'
          sku: '18.04-LTS'
          version: 'latest'
        }
        osDisk: {
          caching: 'ReadWrite'
          createOption: 'FromImage'
          managedDisk: {
            storageAccountType: 'Standard_LRS'
          }
        }
      }
      osProfile: {
        computerNamePrefix: 'flaskvm'
        adminUsername: adminUsername
        linuxConfiguration: {
          disablePasswordAuthentication: true
          ssh: {
            publicKeys: [
              {
                path: '/home/${adminUsername}/.ssh/authorized_keys'
                keyData: adminPublicKey
              }
            ]
          }
        }
        customData: base64(format('#!/bin/bash\nexport CONNECTION_STRING="{0}"\nexport CONTAINER_NAME="{1}"\nexport PORT="{2}"\ncurl -sL https://raw.githubusercontent.com/Ceciliyasouce/CloudProject/main/init-script.sh | bash\n', connectionString, containerName, port))
      }
      networkProfile: {
        networkInterfaceConfigurations: [
          {
            name: 'vmnic'
            properties: {
              primary: true
              ipConfigurations: [
                {
                  name: 'ipconfig'
                  properties: {
                    subnet: {
                      id: subnetId
                    }
                    loadBalancerBackendAddressPools: [
                      {
                        id: backendPoolId
                      }
                    ]
                  }
                }
              ]
            }
          }
        ]
      }
    }
  }
}
