# Native Windows installation

Download the Windows **Setup.exe**, install it for your account, and open
**Super Melee 64** from the Start menu. Its setup window accepts your own US
SM64 ROM and Melee USA Rev 2 ISO/GCM. Choose **Install / Resume** and let the
local preparation finish, then choose **Play**.

No Ubuntu, WSL, administrator access or separately installed Python is required.
The setup window runs native Windows executables. Initial preparation compiles
the game from pinned source; it can take a while. Allow at least 12 GiB free,
preferably 20 GiB. Game images and extracted files stay on your computer.

## Updates, repair and removal

Run a newer Setup.exe to update the application. Close the game and any other
setup window first. The installer refuses to replace files during an active
session. Open **Set up or repair Super Melee 64** from the Start menu to resume
an interrupted build or prepare the updated source. Previously imported game
files are offered automatically.

Verified downloads and incremental compiler outputs are retained on cancellation.
Updates preserve user data, and source edits are checked before any managed file
is replaced. A changed local source file produces a preservation error rather
than silently overwriting your changes.

Windows Settings can uninstall the application. User data is deliberately kept:

| Location | Contents |
| --- | --- |
| `%LOCALAPPDATA%\Programs\Super Melee 64` | Installed setup, launcher and reviewed source kit |
| `%LOCALAPPDATA%\Memelees\SuperMelee64` | Imports, local builds, verified tools and setup logs |
| `%APPDATA%\Super Melee 64` | Saves and gameplay preferences |
| Your Windows Videos folder, `Super Melee 64` | Recordings |

To remove user data too, close the game and setup, back up any saves you want,
and delete the corresponding folders manually. Reinstalling the application
does not require deleting them.

The setup window's **Open Setup Log** button opens `setup-gui.log`. The detailed
build output is in `Workspace\setup.log` beside it. `setup-error.txt` records
the failed step, installer version, error code and recovery instructions.

## How the installer works

`WindowsInstaller.cpp` is the native Win32 setup/launcher. Inno Setup installs
it per user, adds shortcuts and registers an uninstaller. The frontend starts
a bundled Windows Python worker without opening a console. A Windows Job Object
owns setup children, preventing abandoned compilers after cancellation or an
unexpected shutdown. Gameplay uses the same guard and waits for the complete
session, including the single-player to co-op process handoff.

`windows_setup.py` validates the reviewed source manifest and game identities
before downloading build dependencies. It stages source in a separate workspace,
then calls the existing `Setup.py` pipeline. Portable GCC/Make, MinGit/BusyBox,
CMake and Ninja are downloaded with pinned byte counts and SHA-256 hashes.
They are private to this workspace and do not change the system PATH. HTTPS
certificate validation stays enabled. Python, Pillow, certificate roots,
7-Zip, xdelta and libffi are bundled setup dependencies; required Microsoft
runtime DLLs are installed app-locally rather than system-wide.

Build aliases handle account paths containing spaces or non-ASCII characters.
The helper uses an existing short path where available, otherwise creates a
temporary mapping on an unused drive letter and removes only its own mapping.
The generated launchers and game executables use UTF-8 Windows manifests.

Prepared assets have a local hash manifest. Retries verify that cache and avoid
patching entire disc images again. Checked temporary patched images are removed
after extraction; the original supplied games are retained.

No compiled game engine, ROM, disc image or extracted character/audio data is
included in the downloadable installer. See [Licensing](../LICENSING.md).

## Building the installer

Maintainers first create an audited public source export using
`export_public_source.py`. On a Mac/Linux machine with MinGW-w64, CMake, Ninja,
Make, 7zz and cabextract:

```sh
python3 outputs/sm64-melee-lab/native/build_windows_tools.py --work /path/to/tool-build
python3 outputs/sm64-melee-lab/native/build_windows_installer.py \
  --source-kit /path/to/audited-public-export \
  --tools /path/to/tool-build/Tools \
  --cache /path/to/download-cache \
  --output /path/to/installer-output \
  --iscc /path/to/InnoSetup/ISCC.exe \
  --wine /path/to/CrossOver/bin/wine \
  --bottle SuperMelee64-Native-Validation
```

`--wine` is a maintainer build/test option on macOS. Windows users run the
resulting Setup.exe directly. Inno Setup 6.7.4 is the reference packaging tool.
Runtime versions and upstream archives are pinned in the two builder scripts.
The tooling build includes source provenance, third-party notices and 7-Zip's
corresponding source archive. The packaging manifest records every payload hash.
Do not distribute a payload marked `development_only`.

Native CI tests require no game files. They cover source-update preservation,
archive boundaries, download verification rules, Windows path aliases and
compiling/executing the setup frontend. CrossOver exercises Windows executables
on a Mac; graphics, controllers and multiplayer still require Windows hardware
testing before the Windows beta label can be removed.
