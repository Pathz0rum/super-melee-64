#!/usr/bin/env python3
"""Build the independent 16-player host with the shared native fighter bridge."""
from pathlib import Path
from build_paths import project_root
import os,sys,shutil,subprocess,hashlib,tarfile,urllib.request
HERE=Path(__file__).resolve().parent;ROOT=project_root(__file__)

def windows_lua(cc):
    cache=ROOT/'work/release-deps';archive=cache/'lua-5.3.5.tar.gz'
    if not archive.exists():
        temporary=archive.with_suffix('.part')
        subprocess.run(['curl','--fail','--location','--retry','2','https://www.lua.org/ftp/lua-5.3.5.tar.gz','-o',str(temporary)],check=True)
        temporary.rename(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!='0c2eed3f960446e1a3e4b9a1ca2f3ff893b6ce41942cf54d5dd59ab4b3b058ac':raise ValueError('Lua source checksum mismatch')
    with tarfile.open(archive) as package:package.extractall(cache,filter='data')
    source=cache/'lua-5.3.5/src';build=cache/'lua-5.3.5/windows-build';build.mkdir(exist_ok=True)
    files=[str(p) for p in source.glob('*.c') if p.name not in ('lua.c','luac.c')]
    subprocess.run([cc,'-O2','-c',*files],cwd=build,check=True)
    library=build/'liblua53.a';subprocess.run([cc.replace('gcc','ar'),'rcs',str(library),*[str(p) for p in build.glob('*.o')]],check=True)
    return library

def build():
    from build_host import make_program,mac_sound_tools
    make=make_program()
    sound_tools=mac_sound_tools() if os.environ.get('SMB_BUILD_TARGET')!='windows' else []
    from prepare_coop_host import prepare
    prepare()
    command=[make,'-C',str(ROOT/'work/sm64coopdx-melee'),'-j8','VERSION=us','USE_APP=0','DISCORD_SDK=0','COOPNET=1','UPDATER=0','CP=cp']
    command+=sound_tools
    if os.environ.get('SMB_BUILD_TARGET')=='windows':
        from build_host import prepare_windows,windows_resource
        sdl,glew=prepare_windows();runtime=Path(os.environ.get('SMB_RUNTIME_DIR',ROOT/'work/melee-embedded'));zlib=runtime/'abi/build-deps/zlib-build'
        if not (zlib/'libzlib.dll.a').is_file():raise FileNotFoundError('Build the frozen Windows Melee runtime before the co-op host')
        shutil.copy2(zlib/'libzlib.dll.a',glew/'lib/libz.a')
        cc=os.environ.get('SMB_WINDOWS_CC','x86_64-w64-mingw32-gcc');lua=windows_lua(cc)
        wrapper=ROOT/'work/release-deps/coop-sdl2-config'
        wrapper.write_text('#!/bin/sh\ncase "$1" in\n--cflags) echo "-I'+(sdl/'include').as_posix()+' -I'+(sdl/'include/SDL2').as_posix()+' -Dmain=SDL_main";;\n--prefix) echo "'+(sdl).as_posix()+'";;\n*) echo "-L'+(sdl/'lib').as_posix()+' -lmingw32 -lSDL2main -l:libSDL2.dll.a -lm -ldinput8 -ldxguid -luser32 -lgdi32 -lwinmm -limm32 -lole32 -loleaut32 -lshell32 -lsetupapi -lversion -luuid -lcomdlg32";;\nesac\n',encoding='utf-8',newline='\n');wrapper.chmod(0o755)
        command+=['HOST_OS=Windows','OSX_BUILD=0','WINDOWS_BUILD=1','TARGET_ARCH=x86-64','TARGET_BITS=64','NO_BZERO_BCOPY=1','BUILD_DIR_BASE=build-melee-windows',
            'CROSS=x86_64-w64-mingw32-','CC='+cc,'CXX='+cc.replace('gcc','g++'),'LD='+cc.replace('gcc','g++'),'CPP='+cc.replace('gcc','cpp')+' -P',
            'OBJCOPY='+cc.replace('gcc','objcopy'),'OBJDUMP='+cc.replace('gcc','objdump'),'AS='+cc.replace('gcc','as'),
            'SDLCONFIG='+((os.environ['SHELL']+' ') if os.name=='nt' else '')+(wrapper).as_posix(),'SMB_EXTRA_CFLAGS=-I'+(glew/'include').as_posix()+' -DGLEW_STATIC -I'+(zlib).as_posix(),'ICON=0','SMB_LUA_LIB='+(lua).as_posix(),'SMB_EXTRA_LDFLAGS=-L'+(glew/'lib').as_posix()+' '+windows_resource().as_posix()]
    command+=['SMB_TOOLS_CC='+('clang' if sys.platform=='darwin' else 'cc'),'SMB_TOOLS_CXX='+('clang++' if sys.platform=='darwin' else 'c++')]

    
    if os.name=='nt':command+=['SHELL='+os.environ['SHELL']]
    subprocess.run(command,check=True)
    if os.environ.get('SMB_BUILD_TARGET')=='windows':
        source=ROOT/'work/sm64coopdx-melee/build-melee-windows/us_pc/sm64coopdx.exe';destination=ROOT/'work/SuperMelee64-Windows'
        destination.mkdir(exist_ok=True);shutil.copy2(source,destination/'SuperMelee64Coop.exe');shutil.copy2(runtime/'melee_embedded.dll',destination/'melee_embedded.dll');shutil.copy2(zlib/'libzlib1.dll',destination/'libzlib1.dll')
if __name__=='__main__':build()
