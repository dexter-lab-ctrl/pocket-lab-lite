[CmdletBinding()]
param(
  [int]$CandidatePort = 18765,
  [string]$DeviceSerial = '',
  [string]$AdbPath = '',
  [switch]$OpenCandidate,
  [switch]$Wake,
  [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'
$StateDir = Join-Path $env:LOCALAPPDATA 'PocketLab'
$StatePath = Join-Path $StateDir 'ui-performance-android-candidate.json'
. (Join-Path $PSScriptRoot 'windows-adb.ps1')

function Fail([string]$Message) {
  throw "[pocketlab-android-candidate] $Message"
}

function Read-State {
  if (-not (Test-Path $StatePath -PathType Leaf)) { return $null }
  try { return (Get-Content -Raw $StatePath | ConvertFrom-Json) }
  catch { Fail 'The recorded Android candidate state is not valid JSON.' }
}

try {
  if ($AdbPath) {
    $env:POCKETLAB_WINDOWS_ADB = $AdbPath
  }
  $adb = Resolve-PocketLabWindowsAdb
  Write-PocketLabWindowsAdbInfo -AdbPath $adb
} catch {
  Fail $_.Exception.Message
}
$state = Read-State

if ($Cleanup) {
  if ($state -and $state.device_serial -and $state.candidate_port) {
    $cleanupResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @(
      '-s',
      [string]$state.device_serial,
      'reverse',
      '--remove',
      "tcp:$([int]$state.candidate_port)"
    )
  }
  Remove-Item -Force $StatePath -ErrorAction SilentlyContinue
  Write-Host '[pocketlab-android-candidate] owned ADB reverse cleanup complete.'
  exit 0
}

if ($Wake) {
  if (-not $state -or -not $state.device_serial) {
    Fail 'No owned Android candidate state is available for a bounded wake request.'
  }
  Wake-PocketLabAndroidDevice -AdbPath $adb -DeviceSerial ([string]$state.device_serial)
  if ($OpenCandidate) {
    Open-PocketLabAndroidCandidate -AdbPath $adb -DeviceSerial ([string]$state.device_serial) -CandidatePort ([int]$state.candidate_port)
  }
  Write-Host '[pocketlab-android-candidate] bounded wake request complete.'
  exit 0
}

if ($state) {
  if ([int]$state.candidate_port -ne $CandidatePort) { Fail 'An owned candidate reverse uses a different port.' }
  Fail 'An existing owned candidate reverse is active; clean it up before starting another qualification.'
}

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
$reverseResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @('-s', $serial, 'reverse', '--list')
if ($reverseResult.ExitCode -ne 0) {
  Fail 'adb_transport_failed: could not inspect existing ADB reverse mappings.'
}
$reverseLines = @([string]$reverseResult.Stdout -split "`r?`n")
$existing = $reverseLines | Where-Object { $_ -match "\btcp:$CandidatePort\s+tcp:$CandidatePort\b" }
if ($existing) { Fail 'The candidate reverse port is already mapped by an unowned ADB reverse.' }

New-Item -ItemType Directory -Force $StateDir | Out-Null
$createResult = Invoke-PocketLabWindowsAdb -AdbPath $adb -Arguments @(
  '-s',
  $serial,
  'reverse',
  "tcp:$CandidatePort",
  "tcp:$CandidatePort"
)
if ($createResult.ExitCode -ne 0) { Fail 'adb_transport_failed: could not create the owned ADB reverse mapping.' }

$state = [ordered]@{
  version = 1
  device_serial = $serial
  candidate_port = $CandidatePort
  updated_at = (Get-Date).ToUniversalTime().ToString('o')
}
$state | ConvertTo-Json | Set-Content -Encoding UTF8 $StatePath
if ($OpenCandidate) {
  try {
    Open-PocketLabAndroidCandidate -AdbPath $adb -DeviceSerial $serial -CandidatePort $CandidatePort
  } catch {
    Fail $_.Exception.Message
  }
}
Write-Host '[pocketlab-android-candidate] READY'
Write-Host "[pocketlab-android-candidate] candidate loopback port: $CandidatePort"
