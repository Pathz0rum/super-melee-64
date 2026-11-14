param([string]$Rom,[string]$Melee,[switch]$PrepareTools)
$ErrorActionPreference = 'Stop'
$native = Join-Path $env:LOCALAPPDATA 'Programs\Super Melee 64\SuperMelee64.exe'
if (!(Test-Path -LiteralPath $native)) {
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show('Download and run the Windows Setup.exe from the latest release. It includes the setup window and prepares everything natively on Windows. This source kit is for developers.', 'Super Melee 64')
    Start-Process 'https://github.com/memelees/super-melee-64/releases'
    exit 0
}
$arguments = @('--setup')
if ($Rom -or $Melee) {
    if (!$Rom -or !$Melee) { throw 'Supply both -Rom and -Melee, or omit both to use the setup window.' }
    # Use the established Windows argument quoting helper for original filenames.
    . (Join-Path $PSScriptRoot 'installer_windows_support.ps1')
    $arguments = @('--install','--rom',$Rom,'--melee',$Melee)
    $quoted = ($arguments | ForEach-Object { ConvertTo-WindowsArgument $_ }) -join ' '
} else { $quoted = '--setup' }
$child = Start-Process -FilePath $native -ArgumentList $quoted -Wait -PassThru
exit $child.ExitCode
