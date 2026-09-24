[CmdletBinding()]
param(
  [int]$CandidatePort = 18765,
  [string]$DeviceSerial = '',
  [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'
$StateDir = Join-Path $env:LOCALAPPDATA 'PocketLab'
$StatePath = Join-Path $StateDir 'ui-performance-android-candidate.json'

function Fail([string]$Message) {
  throw "[pocketlab-android-candidate] $Message"
}

function Resolve-Adb {
  $command = Get-Command adb.exe -ErrorAction SilentlyContinue
  if ($command) { return $command.Source }
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'),
    (Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'),
    (Join-Path $env:ANDROID_SDK_ROOT 'platform-tools\adb.exe'),
    (Join-Path $env:ProgramFiles 'Android\Sdk\platform-tools\adb.exe')
  ) | Where-Object { $_ -and (Test-Path $_ -PathType Leaf) }
  if ($candidates.Count -ge 1) { return $candidates[0] }
  Fail 'adb.exe is not available on PATH or in the standard Android SDK locations.'
}

function Read-State {
  if (-not (Test-Path $StatePath -PathType Leaf)) { return $null }
  try { return (Get-Content -Raw $StatePath | ConvertFrom-Json) }
  catch { Fail 'The recorded Android candidate state is not valid JSON.' }
}

$adb = Resolve-Adb
$state = Read-State

if ($Cleanup) {
  if ($state -and $state.device_serial -and $state.candidate_port) {
    & $adb -s ([string]$state.device_serial) reverse --remove "tcp:$([int]$state.candidate_port)" 2>$null | Out-Null
  }
  Remove-Item -Force $StatePath -ErrorAction SilentlyContinue
  Write-Host '[pocketlab-android-candidate] owned ADB reverse cleanup complete.'
  exit 0
}

if ($state) {
  if ([int]$state.candidate_port -ne $CandidatePort) { Fail 'An owned candidate reverse uses a different port.' }
  Fail 'An existing owned candidate reverse is active; clean it up before starting another qualification.'
}

$deviceLines = @(
  (& $adb devices -l) |
    Select-Object -Skip 1 |
    Where-Object { $_ -match '^\S+\s+device(?:\s|$)' }
)
if ($DeviceSerial) {
  $deviceLines = @($deviceLines | Where-Object { ($_ -split '\s+')[0] -eq $DeviceSerial })
}
if ($deviceLines.Count -eq 0) { Fail 'No authorized Android device is available.' }
if ($deviceLines.Count -gt 1) { Fail 'More than one authorized Android device is connected; specify -DeviceSerial.' }

$serial = ($deviceLines[0] -split '\s+')[0]
$reverseLines = @(& $adb -s $serial reverse --list 2>$null)
$existing = $reverseLines | Where-Object { $_ -match "\btcp:$CandidatePort\s+tcp:$CandidatePort\b" }
if ($existing) { Fail 'The candidate reverse port is already mapped by an unowned ADB reverse.' }

New-Item -ItemType Directory -Force $StateDir | Out-Null
& $adb -s $serial reverse "tcp:$CandidatePort" "tcp:$CandidatePort" | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'Could not create the owned ADB reverse mapping.' }

$state = [ordered]@{
  version = 1
  device_serial = $serial
  candidate_port = $CandidatePort
  updated_at = (Get-Date).ToUniversalTime().ToString('o')
}
$state | ConvertTo-Json | Set-Content -Encoding UTF8 $StatePath
Write-Host '[pocketlab-android-candidate] READY'
Write-Host "[pocketlab-android-candidate] candidate loopback port: $CandidatePort"
