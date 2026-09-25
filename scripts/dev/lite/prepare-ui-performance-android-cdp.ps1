[CmdletBinding()]
param(
  [int]$AdbPort = 9222,
  [int]$BridgePort = 19222,
  [string]$DeviceSerial = '',
  [string]$AdbPath = '',
  [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'
$FirewallRuleName = 'Pocket Lab Android CDP from WSL'
$StateDir = Join-Path $env:LOCALAPPDATA 'PocketLab'
$StatePath = Join-Path $StateDir 'ui-performance-cdp.json'
. (Join-Path $PSScriptRoot 'windows-adb.ps1')

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

try {
  if ($AdbPath) {
    $env:POCKETLAB_WINDOWS_ADB = $AdbPath
  }
  $adb = Resolve-PocketLabWindowsAdb
  Write-PocketLabWindowsAdbInfo -AdbPath $adb
} catch {
  Fail $_.Exception.Message
}

if ($Cleanup) {
  Remove-RecordedPortProxy
  Get-NetFirewallRule -DisplayName $FirewallRuleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule -Confirm:$false
  try {
    if ($DeviceSerial) {
      $cleanupResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $DeviceSerial, 'forward', '--remove', "tcp:$AdbPort")
    } else {
      $cleanupResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('forward', '--remove', "tcp:$AdbPort")
    }
  } catch {
    Write-Warning '[pocketlab-cdp] ADB forward cleanup was skipped.'
  }
  Remove-Item -Force $StatePath -ErrorAction SilentlyContinue
  Write-Host '[pocketlab-cdp] Pocket Lab CDP bridge cleanup complete.'
  exit 0
}

$records = @()
try {
  $records = @(Get-PocketLabAndroidDeviceRecords -AdbPath $adb)
  $device = Select-PocketLabAndroidDevice -Records $records -DeviceSerial $DeviceSerial
} catch {
  Fail $_.Exception.Message
}

$serial = [string]$device.Serial
try {
  Wake-PocketLabAndroidDevice -AdbPath $adb -DeviceSerial $serial
} catch {
  Fail $_.Exception.Message
}
$pidResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $serial, 'shell', 'pidof', 'com.android.chrome')
if ($pidResult.ExitCode -ne 0) {
  Fail 'adb_transport_failed: could not inspect the Android Chrome process.'
}
$chromePid = ([string]$pidResult.Stdout).Trim()
if (-not $chromePid) {
  Fail 'Google Chrome is not running on the Android device. Open a normal (non-Incognito) Chrome tab and retry.'
}

$socketResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $serial, 'shell', 'cat', '/proc/net/unix')
if ($socketResult.ExitCode -ne 0) {
  Fail 'adb_transport_failed: could not inspect Android Chrome DevTools sockets.'
}
$unixSockets = @([string]$socketResult.Stdout -split "`r?`n")
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
$forwardListResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('forward', '--list')
if ($forwardListResult.ExitCode -ne 0) {
  Fail 'adb_transport_failed: could not inspect existing ADB forward mappings.'
}
$currentForwards = @([string]$forwardListResult.Stdout -split "`r?`n" | Where-Object { $_.Trim() })
if (-not ($currentForwards -contains $wantedForward)) {
  $removeForwardResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $serial, 'forward', '--remove', "tcp:$AdbPort")
  $createForwardResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $serial, 'forward', "tcp:$AdbPort", "localabstract:$chromeSocket")
  if ($createForwardResult.ExitCode -ne 0) {
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
Write-Host "[pocketlab-cdp] Chrome socket: $chromeSocket"
Write-Host "[pocketlab-cdp] Windows ADB endpoint: 127.0.0.1:$AdbPort"
Write-Host "[pocketlab-cdp] WSL bridge endpoint: $wslGateway`:$BridgePort"
Write-Host '[pocketlab-cdp] Next: run scripts/dev/lite/run-ui-performance-android-cdp.sh from WSL with LITE_BASE_URL set.'
