[CmdletBinding()]
param()

# The Android SDK adb.exe is a Windows console application.  When this file is
# consumed by Windows PowerShell launched from WSL, invoking the application
# directly with `&` can lose its stdout/stderr handles.  Keep all Windows ADB
# process execution here so the candidate and CDP helpers have identical,
# deterministic behavior.

function Resolve-PocketLabWindowsAdb {
  $override = ([string]$env:POCKETLAB_WINDOWS_ADB).Trim()
  if ($override) {
    if (-not (Test-Path -LiteralPath $override -PathType Leaf)) {
      throw 'adb_unavailable: POCKETLAB_WINDOWS_ADB must name an existing local Windows adb.exe file.'
    }
    return (Resolve-Path -LiteralPath $override).Path
  }

  $candidates = @()
  $commands = @(Get-Command adb.exe -All -ErrorAction SilentlyContinue)
  foreach ($command in $commands) {
    if ($command.CommandType -eq 'Application' -and $command.Source) {
      $candidates += [string]$command.Source
    }
  }

  if ($env:LOCALAPPDATA) {
    $candidates += Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
  }
  if ($env:ANDROID_HOME) {
    $candidates += Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
  }
  if ($env:ANDROID_SDK_ROOT) {
    $candidates += Join-Path $env:ANDROID_SDK_ROOT 'platform-tools\adb.exe'
  }
  if ($env:ProgramFiles) {
    $candidates += Join-Path $env:ProgramFiles 'Android\Sdk\platform-tools\adb.exe'
  }
  if ($env:USERPROFILE) {
    $candidates += Join-Path $env:USERPROFILE 'Downloads\platform-tools-latest-windows\platform-tools\adb.exe'
  }
  $candidates += 'C:\Android\platform-tools\adb.exe'

  $existing = @(
    $candidates |
      Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
      ForEach-Object { (Resolve-Path -LiteralPath $_).Path } |
      Select-Object -Unique
  )
  if ($existing.Count -eq 0) {
    throw 'adb_unavailable: adb.exe is not on PATH or in the standard Android SDK locations.'
  }
  return [string]$existing[0]
}

function Invoke-PocketLabWindowsAdb {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$AdbPath,
    [string[]]$Arguments = @()
  )

  $stdoutPath = [System.IO.Path]::GetTempFileName()
  $stderrPath = [System.IO.Path]::GetTempFileName()
  try {
    try {
      $process = Start-Process -FilePath $AdbPath -ArgumentList $Arguments -WorkingDirectory $env:WINDIR -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    } catch {
      throw "adb_transport_failed: could not start adb.exe ($($_.Exception.Message))."
    }

    $stdout = if (Test-Path -LiteralPath $stdoutPath) {
      [string](Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue)
    } else {
      ''
    }
    $stderr = if (Test-Path -LiteralPath $stderrPath) {
      [string](Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue)
    } else {
      ''
    }
    return [pscustomobject]@{
      ExitCode = [int]$process.ExitCode
      Stdout = $stdout
      Stderr = $stderr
    }
  } finally {
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
  }
}

function Get-PocketLabWindowsAdbVersion {
  param([Parameter(Mandatory = $true)][string]$AdbPath)

  $result = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @('version')
  if ($result.ExitCode -ne 0) {
    throw 'adb_transport_failed: adb.exe version did not complete successfully.'
  }
  $versionMatch = [regex]::Match([string]$result.Stdout, '(?m)^Version\s+([^\r\n]+)')
  if (-not $versionMatch.Success) {
    throw 'adb_transport_failed: adb.exe version returned no usable version.'
  }
  return $versionMatch.Groups[1].Value.Trim()
}

function Write-PocketLabWindowsAdbInfo {
  param([Parameter(Mandatory = $true)][string]$AdbPath)

  $version = Get-PocketLabWindowsAdbVersion -AdbPath $AdbPath
  Write-Host "[pocketlab-adb] adb: $AdbPath"
  Write-Host "[pocketlab-adb] version: $version"
}

function Get-PocketLabAndroidDeviceRecords {
  param([Parameter(Mandatory = $true)][string]$AdbPath)

  $result = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @('devices', '-l')
  if ($result.ExitCode -ne 0) {
    throw 'adb_transport_failed: adb.exe devices -l did not complete successfully.'
  }

  $records = @()
  foreach ($line in ([string]$result.Stdout -split "`r?`n")) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed -eq 'List of devices attached' -or $trimmed.StartsWith('*')) {
      continue
    }
    $parts = @($trimmed -split '\s+')
    if ($parts.Count -lt 2) {
      continue
    }
    $records += [pscustomobject]@{
      Serial = [string]$parts[0]
      Status = [string]$parts[1]
    }
  }
  return $records
}

function Select-PocketLabAndroidDevice {
  param(
    [Parameter(Mandatory = $true)]
    [object[]]$Records,
    [string]$DeviceSerial = ''
  )

  $requested = ([string]$DeviceSerial).Trim()
  if ($requested) {
    $match = @($Records | Where-Object { $_.Serial -eq $requested })
    if ($match.Count -eq 0) {
      throw 'requested_android_device_not_found: the requested Android serial is not present in adb devices -l.'
    }
    if ($match[0].Status -ne 'device') {
      switch ($match[0].Status) {
        'unauthorized' { throw 'android_device_unauthorized: the requested Android device has not authorized USB debugging.' }
        'offline' { throw 'android_device_offline: the requested Android device is offline.' }
        default { throw "adb_transport_failed: the requested Android device reported state '$($match[0].Status)'." }
      }
    }
    return $match[0]
  }

  $authorized = @($Records | Where-Object { $_.Status -eq 'device' })
  if ($authorized.Count -eq 1) {
    return $authorized[0]
  }
  if ($authorized.Count -gt 1) {
    throw 'multiple_android_devices: more than one authorized Android device is connected; specify -DeviceSerial.'
  }
  if ($Records.Count -eq 0) {
    throw 'no_android_device: adb devices -l returned no Android devices.'
  }

  $statuses = @($Records | ForEach-Object { $_.Status } | Select-Object -Unique)
  if ($statuses.Count -eq 1 -and $statuses[0] -eq 'unauthorized') {
    throw 'android_device_unauthorized: the connected Android device has not authorized USB debugging.'
  }
  if ($statuses.Count -eq 1 -and $statuses[0] -eq 'offline') {
    throw 'android_device_offline: the connected Android device is offline.'
  }
  throw 'adb_transport_failed: no authorized Android device is available in the reported ADB states.'
}

function Wake-PocketLabAndroidDevice {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$AdbPath,
    [Parameter(Mandatory = $true)]
    [string]$DeviceSerial
  )

  $result = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @(
    '-s',
    $DeviceSerial,
    'shell',
    'input',
    'keyevent',
    'KEYCODE_WAKEUP'
  )
  if ($result.ExitCode -ne 0) {
    throw 'adb_transport_failed: could not send the bounded Android wake request.'
  }

  # Some Android builds leave the display in ambient/doze after KEYCODE_WAKEUP
  # even though Chrome remains resumed and CDP reports a focused document. That
  # state throttles requestAnimationFrame to zero and would make physical UI
  # evidence look like a browser-target failure. Read the bounded power state
  # before toggling the power key so an already-awake phone is never turned off.
  Start-Sleep -Milliseconds 200
  $power = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @(
    '-s',
    $DeviceSerial,
    'shell',
    'dumpsys',
    'power'
  )
  if ($power.ExitCode -ne 0) {
    throw 'adb_transport_failed: could not inspect Android wakefulness after the wake request.'
  }
  $wakefulnessMatch = [regex]::Match([string]$power.Stdout, '(?m)^\s*mWakefulness=([^\r\n]+)')
  if ($wakefulnessMatch.Success -and $wakefulnessMatch.Groups[1].Value.Trim() -ne 'Awake') {
    $toggle = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @(
      '-s',
      $DeviceSerial,
      'shell',
      'input',
      'keyevent',
      'KEYCODE_POWER'
    )
    if ($toggle.ExitCode -ne 0) {
      throw 'adb_transport_failed: could not exit Android ambient/doze state.'
    }
    Start-Sleep -Milliseconds 200
    $verification = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @(
      '-s',
      $DeviceSerial,
      'shell',
      'dumpsys',
      'power'
    )
    if ($verification.ExitCode -ne 0) {
      throw 'adb_transport_failed: could not verify Android wakefulness.'
    }
    $verifiedWakefulness = [regex]::Match([string]$verification.Stdout, '(?m)^\s*mWakefulness=([^\r\n]+)')
    if ($verifiedWakefulness.Success -and $verifiedWakefulness.Groups[1].Value.Trim() -ne 'Awake') {
      throw 'android_device_not_awake: Android remained in ambient/doze state after the bounded wake request.'
    }
  }
}

function Open-PocketLabAndroidCandidate {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)]
    [string]$AdbPath,
    [Parameter(Mandatory = $true)]
    [string]$DeviceSerial,
    [Parameter(Mandatory = $true)]
    [int]$CandidatePort
  )

  if ($CandidatePort -lt 1024 -or $CandidatePort -gt 65535) {
    throw 'adb_transport_failed: candidate port is outside the user port range.'
  }
  $candidateUrl = "http://127.0.0.1:$CandidatePort"
  $result = Invoke-PocketLabWindowsAdb -AdbPath $AdbPath -Arguments @(
    '-s',
    $DeviceSerial,
    'shell',
    'am',
    'start',
    '-a',
    'android.intent.action.VIEW',
    '-d',
    $candidateUrl,
    'com.android.chrome'
  )
  if ($result.ExitCode -ne 0) {
    throw 'adb_transport_failed: could not open the owned Android candidate URL in Chrome.'
  }
}
