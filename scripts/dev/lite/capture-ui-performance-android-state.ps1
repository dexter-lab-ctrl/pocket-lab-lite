[CmdletBinding()]
param(
  [string]$DeviceSerial = ''
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'windows-adb.ps1')

function Invoke-SafeAdbText {
  param(
    [Parameter(Mandatory = $true)][string]$AdbPath,
    [Parameter(Mandatory = $true)][string]$Serial,
    [Parameter(Mandatory = $true)][string[]]$Arguments
  )
  $result = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments (@('-s', $Serial, 'shell') + $Arguments)
  if ($result.ExitCode -ne 0) { return '' }
  return ([string]$result.Stdout).Trim()
}

function Match-Int {
  param([string]$Text, [string]$Pattern)
  $match = [regex]::Match([string]$Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if (-not $match.Success) { return $null }
  $value = 0
  if ([int]::TryParse($match.Groups[1].Value, [ref]$value)) { return $value }
  return $null
}

try {
  $adb = Resolve-PocketLabWindowsAdb
  $records = @(Get-PocketLabAndroidDeviceRecords -AdbPath $adb)
  $device = Select-PocketLabAndroidDevice -Records $records -DeviceSerial $DeviceSerial
  $serial = [string]$device.Serial

  $battery = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('dumpsys', 'battery')
  $power = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('dumpsys', 'power')
  $thermal = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('dumpsys', 'thermalservice')
  $focus = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('dumpsys', 'window', 'windows')
  $androidVersion = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('getprop', 'ro.build.version.release')
  $lowPower = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('settings', 'get', 'global', 'low_power')
  $peakRefresh = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('settings', 'get', 'system', 'peak_refresh_rate')
  $minRefresh = Invoke-SafeAdbText -AdbPath $adb -Serial $serial -Arguments @('settings', 'get', 'system', 'min_refresh_rate')

  $foreground = $null
  $focusMatch = [regex]::Match($focus, '(?m)(?:mCurrentFocus|mFocusedApp).*?\s([A-Za-z0-9._]+)/(?:[A-Za-z0-9._$]+)')
  if ($focusMatch.Success) { $foreground = $focusMatch.Groups[1].Value }

  $thermalStatus = Match-Int -Text $thermal -Pattern '(?:Thermal Status|Status)\s*[:=]\s*(\d+)'
  $level = Match-Int -Text $battery -Pattern '(?m)^\s*level:\s*(\d+)'
  $status = Match-Int -Text $battery -Pattern '(?m)^\s*status:\s*(\d+)'
  $plugged = Match-Int -Text $battery -Pattern '(?m)^\s*plugged:\s*(\d+)'
  $screenOn = $null
  if ($power -match 'mWakefulness=Awake|Display Power: state=ON|mScreenBrightnessOverrideFromWindowManager') {
    $screenOn = $true
  } elseif ($power -match 'mWakefulness=Asleep|Display Power: state=OFF') {
    $screenOn = $false
  }

  $parseDouble = {
    param([string]$Value)
    $number = 0.0
    if ([double]::TryParse($Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$number)) {
      return $number
    }
    return $null
  }

  $payload = [ordered]@{
    schema_version = '1.0.0'
    android_version = if ($androidVersion) { $androidVersion } else { $null }
    screen_on = $screenOn
    foreground_package = $foreground
    battery_saver = ($lowPower -eq '1')
    battery_level_percent = $level
    battery_status = $status
    plugged = $plugged
    thermal_status = $thermalStatus
    peak_refresh_rate_hz = (& $parseDouble $peakRefresh)
    min_refresh_rate_hz = (& $parseDouble $minRefresh)
    captured_at = (Get-Date).ToUniversalTime().ToString('o')
    sanitized = $true
  }
  $payload | ConvertTo-Json -Compress
} catch {
  throw "[ui-performance-android-state] $($_.Exception.Message)"
}
