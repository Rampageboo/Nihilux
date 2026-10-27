# Assemble what the Nihilux installer carries into packaging/stage (git-ignored):
#   stage/app/     backend code (storyboard_tool, with the built React app and the Blender
#                  add-on), packaged.json marker, bin/ (LGPL ffmpeg + ffprobe),
#                  integrations/photoshop/*.ccx, licences
#   stage/python/  self-contained CPython (python-build-standalone, pinned + hashed) with the
#                  runtime dependencies from requirements.lock.txt already installed
# desktop/src-tauri/tauri.release.conf.json maps both folders into the installer's resources.
#
#   packaging\stage.ps1                     # builds the frontend first
#   packaging\stage.ps1 -SkipFrontendBuild  # CI: the frontend was just built and tested

param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$stage = Join-Path $PSScriptRoot "stage"
$app = Join-Path $stage "app"
$python = Join-Path $stage "python\python.exe"
$downloads = Join-Path $PSScriptRoot "downloads"

# Same CPython minor version as the tested dev venv (3.14); the lock's wheels are cp314.
$pythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.14.8%2B20261013-x86_64-pc-windows-msvc-install_only.tar.gz"
$pythonSha256 = "3adacae2a39dfcbebe8d95a6e87a0dee167a057ab8f822eacf38e5fa4c97f76e"

# LGPL ffmpeg (shared build: ffmpeg/ffprobe share the DLLs). BtbN prunes old autobuilds, so
# the same file is also looked for on the Nihilux "build-deps" release (upload it there once).
$ffmpegName = "ffmpeg-n8.1.3-24-g92611900bb-win64-lgpl-shared-8.1"
$ffmpegUrls = @(
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-26-14-25/$ffmpegName.zip",
    "https://github.com/Rampageboo/Nihilux/releases/download/build-deps/$ffmpegName.zip"
)
$ffmpegSha256 = "96afe9bee66012f4cbc336a473f0b595060d73bdc5efe4331d55101500d0a93e"

# Development-only packages from requirements.lock.txt: the pywebview launcher and pytest.
$devOnly = @("pywebview", "pythonnet", "clr_loader", "bottle", "proxy_tools", "pytest", "iniconfig", "pluggy", "Pygments")

function Invoke-Native([string]$what, [scriptblock]$command) {
    # Windows PowerShell 5.1 turns a native tool's stderr (npm, pip warnings) into a terminating
    # error under "Stop" when output is redirected; judge native tools by exit code only.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $command 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $previous }
    if ($LASTEXITCODE) { throw "$what failed (exit $LASTEXITCODE)" }
}

function Get-Pinned($urls, $sha256, $fileName) {
    New-Item -ItemType Directory -Force $downloads | Out-Null
    $target = Join-Path $downloads $fileName
    if ((Test-Path $target) -and (Get-FileHash $target -Algorithm SHA256).Hash.ToLower() -eq $sha256) { return $target }
    foreach ($url in $urls) {
        try {
            Write-Host "Downloading $url"
            Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing
            $actual = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()
            if ($actual -eq $sha256) { return $target }
            Write-Warning "hash mismatch for $url ($actual)"
        } catch {
            Write-Warning "download failed: $url ($($_.Exception.Message))"
        }
    }
    throw "Could not get $fileName with SHA-256 $sha256"
}

function Copy-Tree($from, $to, [string[]]$excludeDirs = @(), [string[]]$excludeFiles = @()) {
    # robocopy: fast, keeps structure; exit codes below 8 mean success.
    $xd = @("__pycache__", ".pytest_cache", "node_modules") + $excludeDirs
    $xf = @("*.pyc", "*.pyo") + $excludeFiles
    robocopy $from $to /E /NFL /NDL /NJH /NJS /NP /XD $xd /XF $xf | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "copy failed: $from" }
}

$version = (Get-Content (Join-Path $repo "desktop\src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json).version

if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $app | Out-Null

# 1. Frontend: the backend serves storyboard_tool/web/dist.
if (-not $SkipFrontendBuild) {
    Push-Location (Join-Path $repo "frontend")
    try {
        Invoke-Native "npm ci" { npm ci --no-audit --no-fund }
        Invoke-Native "frontend build" { npm run build }
    } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $repo "storyboard_tool\web\dist\index.html"))) { throw "frontend not built" }

# 2. App code (the Blender add-on lives in storyboard_tool/blender_addon).
Copy-Tree (Join-Path $repo "storyboard_tool") (Join-Path $app "storyboard_tool")
foreach ($file in @("requirements.lock.txt", "LICENSE", "THIRD_PARTY_NOTICES.md")) {
    Copy-Item (Join-Path $repo $file) $app
}
@{ version = $version; built = (Get-Date).ToUniversalTime().ToString("o") } | ConvertTo-Json |
    Out-File (Join-Path $app "packaged.json") -Encoding ascii

# 3. Bundled CPython with the runtime dependencies.
$pythonArchive = Get-Pinned @($pythonUrl) $pythonSha256 "python-$pythonSha256.tar.gz"
# Windows' own bsdtar: a GNU tar on PATH (Git) reads "C:\..." as a remote host.
Invoke-Native "extracting Python" { & (Join-Path $env:SystemRoot "System32\tar.exe") -xzf $pythonArchive -C $stage }
if (-not (Test-Path $python)) { throw "unexpected Python archive layout" }

$lock = Get-Content (Join-Path $repo "requirements.lock.txt") | Where-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return $false }
    $name = ($line -split "==")[0].Trim()
    -not ($devOnly | Where-Object { $_ -ieq $name })
}
$runtimeLock = Join-Path $stage "requirements.runtime.txt"
$lock | Out-File $runtimeLock -Encoding ascii
$env:PYTHONNOUSERSITE = "1"
Invoke-Native "pip install" { & $python -m pip install --disable-pip-version-check --no-warn-script-location --no-deps --only-binary=:all: -r $runtimeLock }
Move-Item $runtimeLock (Join-Path $app "requirements.runtime.txt") -Force
# Debug symbols (~90 MB) are of no use on a user's machine.
Get-ChildItem (Join-Path $stage "python") -Recurse -Filter *.pdb | Remove-Item -Force
Invoke-Native "runtime import check" { & $python -c "import fastapi, uvicorn, PIL, cv2, psd_tools, reportlab, keyring, comfy_sdk, tkinter; print('runtime imports ok')" }

# 4. ffmpeg + ffprobe (LGPL) next to their DLLs in app/bin; runtime_paths looks there first.
$ffmpegZip = Get-Pinned $ffmpegUrls $ffmpegSha256 "$ffmpegName.zip"
$ffmpegTmp = Join-Path $stage "ffmpeg-extract"
Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegTmp -Force
$ffmpegRoot = Join-Path $ffmpegTmp $ffmpegName
$bin = Join-Path $app "bin"
New-Item -ItemType Directory -Force $bin | Out-Null
Copy-Item (Join-Path $ffmpegRoot "bin\ffmpeg.exe"), (Join-Path $ffmpegRoot "bin\ffprobe.exe") $bin
Copy-Item (Join-Path $ffmpegRoot "bin\*.dll") $bin
Copy-Item (Join-Path $ffmpegRoot "LICENSE.txt") (Join-Path $bin "FFMPEG-LICENSE.txt")
Remove-Item -Recurse -Force $ffmpegTmp
Invoke-Native "bundled ffmpeg check" { & (Join-Path $bin "ffmpeg.exe") -hide_banner -version } | Select-Object -First 1

# 5. Photoshop plugin: a .ccx is a zip of the plugin folder, rebuilt from the repo version.
$pluginOut = Join-Path $app "integrations\photoshop"
New-Item -ItemType Directory -Force $pluginOut | Out-Null
$manifest = Get-Content (Join-Path $repo "photoshop_uxp_plugin\manifest.json") -Raw | ConvertFrom-Json
$ccx = Join-Path $pluginOut "$($manifest.id)_PS.ccx"
Invoke-Native "Photoshop plugin package" { & $python -I (Join-Path $PSScriptRoot "build_ccx.py") (Join-Path $repo "photoshop_uxp_plugin") $ccx }

# 6. Byte-compile the app code so the first start does not.
Invoke-Native "compileall" { & $python -m compileall -q (Join-Path $app "storyboard_tool") }

$size = [math]::Round(((Get-ChildItem $stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host "Staged Nihilux $version in $stage ($size MB)"
