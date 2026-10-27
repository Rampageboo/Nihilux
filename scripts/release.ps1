# Publish a new Nihilux version: set the version everywhere, commit, tag, push.
# GitHub Actions (.github/workflows/release.yml) then builds, signs and publishes the
# installer; installed apps offer the update within six hours or on "Check for updates".
#
#   scripts\release.ps1 -Version 0.2.0
#
# Release notes: docs/releases/v<version>.md (shown in the app's update notice and Settings).
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (git status --porcelain) { throw "Commit or stash your changes first." }
if ((git rev-parse --abbrev-ref HEAD) -ne "main") { throw "Release from main." }
if (git tag --list "v$Version") { throw "v$Version already exists." }

$notes = Join-Path $repo "docs\releases\v$Version.md"
if (-not (Test-Path $notes)) { throw "Write the release notes first: docs\releases\v$Version.md" }

$utf8 = New-Object Text.UTF8Encoding $false

function Set-Version([string]$path, [string]$pattern, [int]$count = 1) {
    $full = Join-Path $repo $path
    $text = [IO.File]::ReadAllText($full)
    $regex = New-Object Text.RegularExpressions.Regex $pattern, ([Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $regex.IsMatch($text)) { throw "no version found in $path" }
    $updated = $regex.Replace($text, "`${1}$Version`${2}", $count)
    [IO.File]::WriteAllText($full, $updated, $utf8)
}

$jsonVersion = '("version"\s*:\s*")[^"]+(")'
Set-Version "desktop\src-tauri\tauri.conf.json" $jsonVersion
Set-Version "desktop\package.json" $jsonVersion
# Only the shell's own two version fields (root and packages[""]): re-resolving the lock
# here could produce a tree that the release build's npm ci rejects.
Set-Version "desktop\package-lock.json" $jsonVersion 2
Set-Version "desktop\src-tauri\Cargo.toml" '^(version = ")[^"]+(")'
Set-Version "desktop\src-tauri\Cargo.lock" '(name = "nihilux"\r?\nversion = ")[^"]+(")'
Set-Version "storyboard_tool\__init__.py" '^(__version__ = ")[^"]+(")'

$files = @(
    "desktop/src-tauri/tauri.conf.json", "desktop/package.json", "desktop/package-lock.json",
    "desktop/src-tauri/Cargo.toml", "desktop/src-tauri/Cargo.lock", "storyboard_tool/__init__.py", $notes
)
git add @files
git commit -m "Release v$Version"
if ($LASTEXITCODE) { throw "commit failed" }
git tag "v$Version"
git push origin main "v$Version"
if ($LASTEXITCODE) { throw "push failed" }
Write-Host "Pushed v$Version. Build progress: https://github.com/Rampageboo/Nihilux/actions" -ForegroundColor Green
