# InvoiceFlow Auto-Start Script
# Run this to start InvoiceFlow + ngrok tunnel
# Place in shell:startup for auto-start on login

$APP_DIR = "C:\Users\ADMIN\AppData\Local\Temp\opencode\invoiceflow"
$NGROK = "$env:LOCALAPPDATA\ngrok\ngrok.exe"
$URL_FILE = "$env:USERPROFILE\Desktop\INVOICEFLOW_URL.txt"
$LOG_FILE = "$APP_DIR\invoiceflow.log"

function Log { param($m) $m | Out-File -FilePath $LOG_FILE -Append; Write-Output $m }

Log "=== InvoiceFlow Starting $(Get-Date) ==="

# Kill old processes
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
Stop-Process -Name "ngrok" -Force -ErrorAction SilentlyContinue
Start-Sleep 2

# Start Flask
Start-Process -WindowStyle Hidden -FilePath "python" -ArgumentList "$APP_DIR\app.py"
Log "Flask started"
Start-Sleep 5

# Test Flask is running
try { $r = Invoke-WebRequest -Uri "http://localhost:5000/" -UseBasicParsing -TimeoutSec 3; Log "Flask OK: $($r.StatusCode)" } catch { Log "Flask FAILED!" }

# Start ngrok
Start-Process -WindowStyle Hidden -FilePath $NGROK -ArgumentList "http 5000"
Log "ngrok started"
Start-Sleep 6

# Get URL from ngrok API
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:4040/api/tunnels" -UseBasicParsing -TimeoutSec 5
    $data = $r.Content | ConvertFrom-Json
    $url = $data.tunnels[0].public_url
    Set-Content -Path $URL_FILE -Value "InvoiceFlow is live at: $url"
    Log "URL: $url"
} catch {
    $msg = "Failed to get ngrok URL on first try. Retrying..."
    Log $msg
    Start-Sleep 5
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:4040/api/tunnels" -UseBasicParsing -TimeoutSec 5
        $data = $r.Content | ConvertFrom-Json
        $url = $data.tunnels[0].public_url
        Set-Content -Path $URL_FILE -Value "InvoiceFlow is live at: $url"
        Log "URL: $url"
    } catch {
        Set-Content -Path $URL_FILE -Value "InvoiceFlow: Check http://localhost:4040 for ngrok URL"
        Log "Could not get URL. Check ngrok dashboard at http://localhost:4040"
    }
}

Log "=== InvoiceFlow Ready ==="
