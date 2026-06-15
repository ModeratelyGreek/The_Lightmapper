# Build an installable Blender addon zip for The_Lightmapper fork.
# The runtime module name MUST be "thelightmapper" because the background-bake
# subprocess does `import thelightmapper` (see addon/utility/build.py).
#
# Usage:
#   ./build.ps1                # produces dist/thelightmapper.zip
#   ./build.ps1 -Install       # also installs+enables it into Blender 4.5 (headless test)
#   ./build.ps1 -Blender "C:\path\to\blender.exe"

param(
    [switch]$Install,
    [switch]$Test,
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"
)

$ErrorActionPreference = "Stop"
$root    = $PSScriptRoot
$dist    = Join-Path $root "dist"
$staging = Join-Path $dist "thelightmapper"
$zip     = Join-Path $dist "thelightmapper.zip"

# Clean staging
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
if (Test-Path $zip)     { Remove-Item $zip -Force }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

# Copy runtime files (exclude dev-only: img/, dist/, .git, build script)
Copy-Item (Join-Path $root "__init__.py") $staging
Copy-Item (Join-Path $root "LICENSE")     $staging -ErrorAction SilentlyContinue
Copy-Item (Join-Path $root "addon")       (Join-Path $staging "addon") -Recurse

# Drop python caches
Get-ChildItem $staging -Recurse -Include "__pycache__" -Directory | Remove-Item -Recurse -Force

# Zip with thelightmapper/ as the top-level folder
Compress-Archive -Path $staging -DestinationPath $zip -Force

# OneDrive (Documents is synced) can momentarily make a freshly written file
# disappear from the filesystem view. Wait until the zip is really there, and
# re-zip if it vanishes, so -Install/-Test don't fail with "file not found".
for ($i = 0; $i -lt 20 -and -not (Test-Path $zip); $i++) {
    Start-Sleep -Milliseconds 250
    if (-not (Test-Path $zip)) { Compress-Archive -Path $staging -DestinationPath $zip -Force }
}
if (-not (Test-Path $zip)) { throw "Build produced no zip at $zip (OneDrive sync interference?)" }
Write-Host "Built: $zip"

if ($Install) {
    if (-not (Test-Path $Blender)) { throw "Blender not found at $Blender" }
    $expr = @"
import bpy
bpy.ops.preferences.addon_install(overwrite=True, filepath=r'$zip')
bpy.ops.preferences.addon_enable(module='thelightmapper')
bpy.ops.wm.save_userpref()
print('TLM_ADDON_REGISTER_OK')
"@
    & $Blender --background --factory-startup --python-expr $expr
}

if ($Test) {
    if (-not (Test-Path $Blender)) { throw "Blender not found at $Blender" }
    foreach ($t in @("tests\smoketest.py", "tests\smoketest_atlas.py", "tests\smoketest_enableset.py")) {
        Write-Host "=== $t ==="
        & $Blender --background --python (Join-Path $root $t) 2>&1 |
            Select-String -Pattern "OK:|FAIL:|manifest:|SMOKETEST_RESULT"
    }
}
