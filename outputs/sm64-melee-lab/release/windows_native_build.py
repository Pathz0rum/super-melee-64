"""Native Windows build orchestration, independent of shells or Linux installs."""
from contextlib import contextmanager
from pathlib import Path
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys


@contextmanager
def build_drive(directory, preferred='R:'):
    """Map only an unused per-user DOS drive, and remove only our exact mapping."""
    if os.name != 'nt':
        raise RuntimeError('The native Windows installer must run on Windows.')
    from ctypes import wintypes
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if str(directory).isascii() and not any(char.isspace() for char in str(directory)):
        yield directory
        return
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetShortPathNameW.restype = wintypes.DWORD
    short = ctypes.create_unicode_buffer(32768)
    length = kernel.GetShortPathNameW(str(directory), short, len(short))
    if length and length < len(short) and short.value.isascii() and not any(c.isspace() for c in short.value):
        alias = Path(short.value)
        if alias.exists() and os.path.samefile(alias, directory):
            yield alias
            return
    kernel.DefineDosDeviceW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR]
    kernel.DefineDosDeviceW.restype = wintypes.BOOL
    kernel.QueryDosDeviceW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.QueryDosDeviceW.restype = wintypes.DWORD
    drive = None
    for candidate in dict.fromkeys([preferred, *[chr(i) + ':' for i in range(ord('R'), ord('Z'))]]):
        buffer = ctypes.create_unicode_buffer(32768)
        if kernel.QueryDosDeviceW(candidate, buffer, len(buffer)):
            continue
        if ctypes.get_last_error() != 2:
            raise ctypes.WinError(ctypes.get_last_error())
        target = '\\??\\' + str(directory)
        if not kernel.DefineDosDeviceW(1 | 8, candidate, target):  # raw target; no broadcast
            raise ctypes.WinError(ctypes.get_last_error())
        drive = candidate
        break
    if not drive:
        raise RuntimeError('Setup needs one unused drive letter between R: and Y:. Close another temporary build, then retry.')
    try:
        alias = Path(drive + '/')
        if not alias.exists() or not os.path.samefile(alias, directory):
            raise RuntimeError('Windows could not create the private temporary build drive.')
        yield alias
    finally:
        # DDD_EXACT_MATCH_ON_REMOVE prevents deleting a mapping changed by others.
        kernel.DefineDosDeviceW(1 | 2 | 4 | 8, drive, target)


def build_fighter_engine(upstream, run):
    upstream = Path(upstream)
    source = upstream / 'build/native-proof/melee-pc'
    work = source.parent
    run([sys.executable, '-c', '''from native_mac import stage
from native_bridge import prepare_bridge
from native_roster import generate
from native_bindings import generate as bindings
from native_reference import generate as reference
from native_compatibility import WORK
stage();prepare_bridge(destination=WORK/'mac-runtime');reference();generate();bindings()
'''], cwd=upstream / 'tools/melee3d')
    library = Path(os.environ['SMB_WINDOWS_FFI'])
    if not (library / 'lib/libffi.a').is_file():
        raise RuntimeError('The native Windows installer is missing its libffi build dependency. Reinstall the complete installer.')
    build = source / 'build/windows-proof'
    build.mkdir(parents=True, exist_ok=True)
    compiler = Path(shutil.which('x86_64-w64-mingw32-gcc'))
    cxx = Path(shutil.which('x86_64-w64-mingw32-g++'))
    rc = Path(shutil.which('x86_64-w64-mingw32-windres'))
    run(['cmake', '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_C_COMPILER=' + compiler.as_posix(), '-DCMAKE_CXX_COMPILER=' + cxx.as_posix(),
         '-DCMAKE_RC_COMPILER=' + rc.as_posix(), '-DAURORA_DAWN_PROVIDER=package',
         '-DCMAKE_OBJECT_PATH_MAX=180',
         '-DAURORA_NOD_PROVIDER=package', '-DAURORA_SDL3_PROVIDER=package',
         '-DM3D_FFI_ROOT=' + library.as_posix(), '-DCMAKE_TLS_VERIFY=ON',
         '-DCMAKE_TLS_CAINFO=' + os.environ.get('SSL_CERT_FILE', '').replace('\\', '/')])
    run(['ninja', '-C', build, '-j4', 'melee'])
    runtime=Path(os.environ['SMB_SETUP_PACKAGE'])/'Tools/Runtime'
    for name in ('VCRUNTIME140.dll','VCRUNTIME140_1.dll','MSVCP140.dll','MSVCP140_ATOMIC_WAIT.dll'):
        shutil.copy2(runtime/name,build/name)
    threads = Path(subprocess.check_output([str(compiler), '-print-file-name=libwinpthread-1.dll'], text=True).strip())
    if threads.is_file():
        shutil.copy2(threads, build / threads.name)
    digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    (work / 'native-windows-build.json').write_text(json.dumps(dict(platform='Windows-x64',
        executable_sha256=digest(build / 'melee.exe'),
        patch_sha256=digest(upstream / 'native/mac/capacity.patch'),
        source='Pinned source compiled by private native Windows tools'), indent=2) + '\n')


def native_subprocess_environment(environment):
    """Keep UTF-8 and hide compiler console windows; cancellation remains explicit."""
    result = dict(environment, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    return result
