# Compatibility entry point for older source kits. The installed helper is native.
& (Join-Path $PSScriptRoot 'SetupWindows.ps1')
exit $LASTEXITCODE
