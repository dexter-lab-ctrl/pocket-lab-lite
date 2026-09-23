[CmdletBinding()]
param(
  [int]$AdbPort = 9222,
  [int]$BridgePort = 19222,
  [string]$DeviceSerial = '',
  [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'
$FirewallRuleName = 'Pocket Lab Android CDP from WSL'
$StateDir = Join-Path $env:LOCALAPPDATA 'PocketLab'
$StatePath = Join-Path $StateDir 'ui-performance-cdp.json'

function Fail([string]$Message) {
  throw "[pocketlab-cdp] $Message"
}

function Assert-Administrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail 'Run this helper from an elevated PowerShell window (Run as administrator).'
  }
}

function Remove-RecordedPortProxy {
  if (-not (Test-Path $StatePath)) { return }
  try {
    $state = Get-Content -Raw $StatePath | ConvertFrom-Json
    if ($state.wsl_gateway -and $state.bridge_port) {
      & netsh interface portproxy delete v4tov4 "listenaddress=$($state.wsl_gateway)" "listenport=$($state.bridge_port)" | Out-Null
    }
  } catch {
    Write-Warning "[pocketlab-cdp] Could not remove the previously recorded portproxy: $($_.Exception.Message)"
  }
}

Assert-Administrator

if ($Cleanup) {
  Remove-RecordedPortProxy
  Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -Confirm:$false
  if (Get-Command adb -ErrorAction SilentlyContinue) {
    try {
      if ($DeviceSerial) {
        & adb -s $DeviceSerial forward --remove "tcp:$AdbPort" | Out-Null
      } else {
        & adb forward --remove "tcp:$AdbPort" | Out-Null
      }
    } catch {
      Write-Warning '[pocketlab-cdp] ADB forward cleanup was skipped.'
    }
  }
  Remove-Item -Force $StatePath -ErrorAction SilentlyContinue
  Write-Host '[pocketlab-cdp] Pocket Lab CDP bridge cleanup complete.'
  exit 0
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
  Fail 'adb is not available on PATH. Install Android SDK Platform-Tools first.'
}

$deviceLines = @(
  (& adb devices -l) |
    Select-Object -Skip 1 |
    Where-Object { $_ -match '^\S+\s+device(?:\s|$)' }
)

if ($DeviceSerial) {
  $deviceLines = @($deviceLines | Where-Object { ($_ -split '\s+')[0] -eq $DeviceSerial })
}

if ($deviceLines.Count -eq 0) {
  Fail 'No authorized Android device is available. Connect the Server Phone and approve USB debugging.'
}
if ($deviceLines.Count -gt 1) {
  Fail 'More than one authorized Android device is connected. Re-run with -DeviceSerial <serial>.'
}

$serial = ($deviceLines[0] -split '\s+')[0]
$chromePid = (& adb -s $serial shell pidof com.android.chrome 2>$null).Trim()
if (-not $chromePid) {
  Fail 'Google Chrome is not running on the Android device. Open a normal (non-Incognito) Chrome tab and retry.'
}

$unixSockets = & adb -s $serial shell cat /proc/net/unix
$chromeSocket = ''
foreach ($line in $unixSockets) {
  if ($line -match '@(chrome_devtools_remote(?:_[0-9]+)?)\s*$') {
    $chromeSocket = $Matches[1]
    break
  }
}
if (-not $chromeSocket) {
  Fail 'Android Chrome is running, but no chrome_devtools_remote socket is exposed. Keep a normal Chrome tab open and retry.'
}

$wantedForward = "$serial tcp:$AdbPort localabstract:$chromeSocket"
$currentForwards = @(& adb forward --list)
if (-not ($currentForwards -contains $wantedForward)) {
  & adb -s $serial forward --remove "tcp:$AdbPort" 2>$null | Out-Null
  & adb -s $serial forward "tcp:$AdbPort" "localabstract:$chromeSocket" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Fail "Could not create ADB forward tcp:$AdbPort -> localabstract:$chromeSocket."
  }
}

try {
  $windowsCdp = Invoke-RestMethod -Uri "http://127.0.0.1:$AdbPort/json/version" -TimeoutSec 5
} catch {
  Fail "ADB forwarding exists, but Android Chrome CDP did not answer on Windows 127.0.0.1:$AdbPort. $($_.Exception.Message)"
}
if ($windowsCdp.'Android-Package' -ne 'com.android.chrome') {
  Fail 'The forwarded endpoint is not Google Chrome on Android.'
}

$wslGateway = (& wsl.exe -e sh -lc "ip route | sed -n 's/^default via \([^ ]*\).*/\1/p' | head -n1").Trim()
$wslAddressCidr = (& wsl.exe -e sh -lc "ip -o -4 addr show dev eth0 | sed -n 's/.* inet \([^ ]*\).*/\1/p' | head -n1").Trim()
$wslIp = ($wslAddressCidr -split '/')[0]

if ($wslGateway -notmatch '^\d{1,3}(?:\.\d{1,3}){3}$') {
  Fail 'Could not determine the Windows host address used by WSL2.'
}
if ($wslIp -notmatch '^\d{1,3}(?:\.\d{1,3}){3}$') {
  Fail 'Could not determine the current WSL2 IPv4 address.'
}

New-Item -ItemType Directory -Force $StateDir | Out-Null
Remove-RecordedPortProxy

& netsh interface portproxy add v4tov4 "listenaddress=$wslGateway" "listenport=$BridgePort" "connectaddress=127.0.0.1" "connectport=$AdbPort" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Fail 'Windows portproxy configuration failed.'
}

Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue |
  Remove-NetFirewallRule -Confirm:$false
New-NetFirewallRule -DisplayName $FirewallRuleName -Direction Inbound -Action Allow -Protocol TCP -LocalAddress $wslGateway -LocalPort $BridgePort -RemoteAddress $wslIp -Profile Any | Out-Null

$state = [ordered]@{
  version = 1
  device_serial = $serial
  chrome_socket = $chromeSocket
  adb_port = $AdbPort
  bridge_port = $BridgePort
  wsl_gateway = $wslGateway
  wsl_ip = $wslIp
  updated_at = (Get-Date).ToUniversalTime().ToString('o')
}
$state | ConvertTo-Json | Set-Content -Encoding UTF8 $StatePath

$wslProbe = (& wsl.exe -e sh -lc "curl -fsS --connect-timeout 3 --max-time 5 http://$wslGateway`:$BridgePort/json/version").Trim()
if (-not $wslProbe) {
  Fail "The Windows bridge was created, but WSL could not read http://$wslGateway`:$BridgePort/json/version."
}
try {
  $wslCdp = $wslProbe | ConvertFrom-Json
} catch {
  Fail 'WSL reached the bridge, but the CDP version response was not valid JSON.'
}
if ($wslCdp.'Android-Package' -ne 'com.android.chrome') {
  Fail 'WSL reached the bridge, but the endpoint is not Google Chrome on Android.'
}

Write-Host '[pocketlab-cdp] READY'
Write-Host "[pocketlab-cdp] Android device: $serial"
Write-Host "[pocketlab-cdp] Chrome socket: $chromeSocket"
Write-Host "[pocketlab-cdp] Windows ADB endpoint: 127.0.0.1:$AdbPort"
Write-Host "[pocketlab-cdp] WSL bridge endpoint: $wslGateway`:$BridgePort"
Write-Host '[pocketlab-cdp] Next: run scripts/dev/lite/run-ui-performance-android-cdp.sh from WSL with LITE_BASE_URL set.'
