function Test-PortOpen([int]$port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', $port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-NarrAI([int]$port) {
    try {
        $request = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$port/openapi.json")
        $request.Proxy = $null
        $request.Timeout = 2000
        $request.ReadWriteTimeout = 2000
        $response = $request.GetResponse()
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            $body = $reader.ReadToEnd()
            $reader.Close()
        } finally {
            $response.Close()
        }
        return $body -match 'NarrAI API'
    } catch {
        return $false
    }
}

if (-not (Test-PortOpen 8000)) {
    Write-Output 'free:8000'
    exit 0
}

if (Test-NarrAI 8000) {
    Write-Output 'reuse:8000'
    exit 0
}

foreach ($port in 8001..8020) {
    if (-not (Test-PortOpen $port)) {
        Write-Output "other:$port"
        exit 0
    }
    if (Test-NarrAI $port) {
        Write-Output "reuse:$port"
        exit 0
    }
}

Write-Output 'fail'
exit 1
