$EndpointId = 'CB-17'
$CollectionId = 'FKCOL-2841'
$InstructionSet = 'COLLECT-FK-3'

function New-CallbackRequest {
    param([Parameter(Mandatory=$true)][string]$Integrity)
    @{
        endpoint_id = $EndpointId
        collection_id = $CollectionId
        integrity = $Integrity
    } | ConvertTo-Json -Compress
}

