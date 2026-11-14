#!/usr/bin/env python3
"""Build the asset-free Windows setup utilities on a Mac/Linux maintainer machine.

Requires MinGW-w64, CMake, Ninja, Make, 7zz and a POSIX shell. End users do not
run this script. No game image or proprietary game engine is used here.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'release'))
from windows_dependencies import sha
from build_windows_installer import download

PINS={
 'ffi':('libffi-3.4.8.tar.gz','https://github.com/libffi/libffi/releases/download/v3.4.8/libffi-3.4.8.tar.gz','bc9842a18898bfacb0ed1252c4febcc7e78fa139fd27fdc7a3e30d9d9356119b'),
 'xdelta':('xdelta-3.2.2.tar.gz','https://github.com/jmacd/xdelta/archive/refs/tags/v3.2.2.tar.gz','995319ccb7fe721a523fb3142376f5813093685b1cc302d07018ca97d2584af2'),
 '7zip':('7z2605-extra.7z','https://github.com/ip7z/7zip/releases/download/26.05/7z2605-extra.7z','f27a8f103c84785026edcba1f67faf1357225df9d19ddb0b7760d55947141bc7'),
 '7zip-source':('7z2605-src.tar.xz','https://github.com/ip7z/7zip/releases/download/26.05/7z2605-src.tar.xz','0b6080b8c3e7a579161d2d495224c0e51c467576cb4c7048b0ab485ef44cc22e'),
 'vc-runtime':('vc_redist.x64.exe','https://aka.ms/vc14/vc_redist.x64.exe','843068991daaa1f73ad9f6239bce4d0f6a07a51f18c37ea2a867e9beca71295c'),
}
XZ_REVISION='4b73f2ec19a99ef465282fbce633e8deb33691b3' # xz v5.8.3

def run(command,**kw):subprocess.run(list(map(str,command)),check=True,**kw)
def runtime(archive,destination):
    """Stage Microsoft's app-local runtime; never install it system-wide."""
    wanted={name.lower():name for name in ('VCRUNTIME140.dll','VCRUNTIME140_1.dll','MSVCP140.dll','MSVCP140_ATOMIC_WAIT.dll')}
    destination.mkdir(exist_ok=True);data=Path(archive).read_bytes()
    with tempfile.TemporaryDirectory(prefix='supermelee-runtime-') as d:
        root=Path(d)
        for i,match in enumerate(reversed(list(re.finditer(b'MSCF',data)))):
            cab=root/'container.cab';cab.write_bytes(data[match.start():]);inner=root/str(i);inner.mkdir()
            subprocess.run(['cabextract','-q','-d',str(inner),str(cab)],capture_output=True)
            for nested in list(inner.iterdir()):
                if nested.is_file():
                    for suffix in ('x64','amd64'):subprocess.run(['cabextract','-q','-d',str(inner),'-F','*_'+suffix,str(nested)],capture_output=True)
            for path in inner.iterdir():
                for suffix in ('_x64','_amd64'):
                    name=wanted.get(path.name[:-len(suffix)].lower()) if path.name.endswith(suffix) else None
                    if name:shutil.copy2(path,destination/name)
            if all((destination/name).is_file() for name in wanted.values()):return
    raise RuntimeError('Could not extract the pinned Microsoft app-local runtime')
def build(args):
 work=args.work.resolve();work.mkdir(parents=True,exist_ok=True);cache=work/'downloads'
 out=work/'Tools';out.mkdir(exist_ok=True);sources=out/'Sources';sources.mkdir(exist_ok=True)
 archives={key:download(pin,cache) for key,pin in PINS.items()}
 for key in ('ffi','xdelta'):
  with tarfile.open(archives[key]) as archive:archive.extractall(work,filter='data')
 prefix=work/'libffi';ffi=work/'libffi-3.4.8'
 env=dict(os.environ,CFLAGS='-O2 -g0 -ffile-prefix-map='+str(work)+'=/source',CXXFLAGS='-O2 -g0 -ffile-prefix-map='+str(work)+'=/source')
 run(['sh','./configure','--host=x86_64-w64-mingw32','--disable-shared','--enable-static','--disable-docs','--prefix='+str(prefix)],cwd=ffi,env=env)
 run(['make','-j4'],cwd=ffi,env=env);run(['make','install'],cwd=ffi,env=env)
 toolchain=work/'toolchain.cmake'
 toolchain.write_text('''set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)
set(CMAKE_C_COMPILER x86_64-w64-mingw32-gcc)
set(CMAKE_CXX_COMPILER x86_64-w64-mingw32-g++)
set(CMAKE_RC_COMPILER x86_64-w64-mingw32-windres)
''')
 xdelta=work/'xdelta-build'
 run(['cmake','-S',work/'xdelta-3.2.2/xdelta3','-B',xdelta,'-G','Ninja','-DCMAKE_TOOLCHAIN_FILE='+str(toolchain),
      '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS='+env['CFLAGS'],'-DCMAKE_CXX_FLAGS='+env['CXXFLAGS'],
      '-DCMAKE_EXE_LINKER_FLAGS=-static','-DXD3_ARMOR=OFF','-DXD3_LZMA_MODE=on','-DXD3_LZMA_FETCH=ON',
      '-DXD3_LZMA_TAG='+XZ_REVISION,'-DXD3_BUILD_TESTS=OFF'])
 run(['cmake','--build',xdelta,'-j4'])
 extra=work/'7zip';run(['7zz','x','-y','-o'+str(extra),archives['7zip']])
 shutil.copy2(extra/'x64/7za.exe',out/'7zz.exe');shutil.copy2(xdelta/'xdelta3.exe',out/'xdelta3.exe')
 shutil.copytree(prefix/'include',out/'ffi/include',dirs_exist_ok=True);(out/'ffi/lib').mkdir(parents=True,exist_ok=True)
 shutil.copy2(prefix/'lib/libffi.a',out/'ffi/lib/libffi.a')
 run(['x86_64-w64-mingw32-strip','--strip-debug',out/'ffi/lib/libffi.a'])
 run(['x86_64-w64-mingw32-strip',out/'xdelta3.exe'])
 notices=out/'Notices';notices.mkdir(exist_ok=True)
 for source,name in ((extra/'License.txt','7ZIP.txt'),(work/'xdelta-3.2.2/xdelta3/LICENSE','XDELTA.txt'),(ffi/'LICENSE','LIBFFI.txt')):shutil.copy2(source,notices/name)
 # Include corresponding 7-Zip source alongside its unmodified binary; original
 # installer/adapter source is already in SourceKit. Other sources are recorded.
 shutil.copy2(archives['7zip-source'],sources/archives['7zip-source'].name)
 runtime(archives['vc-runtime'],out/'Runtime')
 (notices/'MICROSOFT-RUNTIME.txt').write_text('Microsoft Visual C++ x64 runtime, distributed unmodified from the official redistributable.\nCopyright Microsoft Corporation.\nSource: https://aka.ms/vc14/vc_redist.x64.exe\nDocumentation: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files\nThese files are not covered by the project GPL license.\n',encoding='utf-8')
 provenance=dict(format=1,game_binaries_included=False,source_pins=PINS,xz_revision=XZ_REVISION,
                 xz_source='https://github.com/tukaani-project/xz/tree/'+XZ_REVISION,
                 files={p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'})
 (out/'manifest.json').write_text(json.dumps(provenance,indent=2)+'\n');print(out);return out

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True);build(parser.parse_args())
