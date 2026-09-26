param([Parameter(Mandatory=$true)][string]$BundlePath)

$lines = Get-Content -LiteralPath $BundlePath
$payload = ($lines | Where-Object { $_ -like 'payload=*' }) -replace '^payload=', ''
$compressed = [Convert]::FromBase64String($payload)
$input = [IO.MemoryStream]::new($compressed)
$zlib = [IO.Compression.ZLibStream]::new($input, [IO.Compression.CompressionMode]::Decompress)
$output = [IO.MemoryStream]::new()
$zlib.CopyTo($output)
[Text.Encoding]::UTF8.GetString($output.ToArray())

