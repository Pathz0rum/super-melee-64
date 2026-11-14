#!/usr/bin/env python3
"""Package the native Windows setup, without distributing either game's code or assets.

Maintainer inputs: an audited public source export, pinned OSS tools built with
build_windows_tools.py, and MinGW-w64. Inno Setup compiles the final per-user EXE.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'release'))
from windows_dependencies import sha,unzip
from package_release import VERSION

RUNTIME={
 'python':('python-3.14.10-embed-amd64.zip','https://www.python.org/ftp/python/3.14.10/python-3.14.10-embed-amd64.zip','90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'),
 'pillow':('pillow-12.0.0-cp314-cp314-win_amd64.whl','https://files.pythonhosted.org/packages/2b/24/b350c31543fb0107ab2599464d7e28e6f856027aadda995022e695313d94/pillow-12.0.0-cp314-cp314-win_amd64.whl','8dc232e39d409036af549c86f24aed8273a40ffa459981146829a324e0848b4b'),
 'certifi':('certifi-2026.10.23-py3-none-any.whl','https://files.pythonhosted.org/packages/32/d1/a3652fe2c19134d0d15922177821d863cbd7e842d53a21bbe7e8e3a1b5ac/certifi-2026.10.23-py3-none-any.whl','e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1'),
}
def download(pin,cache):
 name,url,expected=pin;target=cache/name;cache.mkdir(parents=True,exist_ok=True)
 if not target.exists():
  partial=target.with_suffix('.partial')
  with urllib.request.urlopen(url,timeout=90) as incoming,partial.open('wb') as out:shutil.copyfileobj(incoming,out)
  if sha(partial)!=expected:raise ValueError('Runtime checksum mismatch: '+name)
  partial.replace(target)
 if sha(target)!=expected:raise ValueError('Runtime checksum mismatch: '+name)
 return target

def inno(stage,output,files):
 # User data intentionally lives outside {app}; no UninstallDelete on it.
 # Wildcard enumeration skips hidden files under Wine, including .gitignore
 # and .github. List every audited payload member so installation preserves
 # the exact source manifest on both Windows and the packaging host.
 entries=[]
 for name in sorted(files):
  parent=Path(name).parent.as_posix()
  destination='{app}'+('\\'+parent.replace('/','\\') if parent!='.' else '')
  entries.append(f'Source: "{stage}/{name}"; DestDir: "{destination}"; Flags: ignoreversion')
 payload='\n'.join(entries)
 return f'''[Setup]
AppId={{{{D24CDA46-81D9-41AD-941F-63944996EEAB}}
AppName=Super Melee 64
AppVersion={VERSION}
AppPublisher=Memelees
AppPublisherURL=https://github.com/memelees/super-melee-64
AppSupportURL=https://github.com/memelees/super-melee-64/issues
DefaultDirName={{localappdata}}\\Programs\\Super Melee 64
DefaultGroupName=Super Melee 64
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.18362
DisableProgramGroupPage=yes
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
OutputDir={output}
OutputBaseFilename=SuperMelee64-{VERSION}-Windows-x64-Setup
SetupIconFile={stage}/SuperMelee64.ico
UninstallDisplayIcon={{app}}\\SuperMelee64.exe
AppMutex=Local\\SuperMelee64.Running
CloseApplications=no
RestartApplications=no
LicenseFile={stage}/SourceKit/LICENSE
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
[Files]
{payload}
[Icons]
Name: "{{group}}\\Super Melee 64"; Filename: "{{app}}\\SuperMelee64.exe"
Name: "{{group}}\\Set up or repair Super Melee 64"; Filename: "{{app}}\\SuperMelee64.exe"; Parameters: "--setup"
Name: "{{autodesktop}}\\Super Melee 64"; Filename: "{{app}}\\SuperMelee64.exe"; Tasks: desktopicon
[Run]
Filename: "{{app}}\\SuperMelee64.exe"; Description: "Open Super Melee 64"; Flags: nowait postinstall skipifsilent
'''

def build(args):
 source=args.source_kit.resolve();destination=args.output.resolve();destination.mkdir(parents=True,exist_ok=True)
 from windows_setup import source_files
 source_files(source) # exact reviewed source, no Git history or implicit recursion
 from verify_repository import audit
 if not audit(source,history=False)['passed']:raise RuntimeError('The source export failed its source-only/privacy audit')
 stage=destination/'payload'
 if stage.exists():shutil.rmtree(stage)
 stage.mkdir();shutil.copytree(source,stage/'SourceKit')
 python=stage/'Python';python.mkdir()
 unzip(download(RUNTIME['python'],args.cache),python)
 site=python/'Lib/site-packages';site.mkdir(parents=True)
 for name in ('pillow','certifi'):unzip(download(RUNTIME[name],args.cache),site)
 # The embedded distribution's isolated ._pth omits script directories. The
 # launcher fixes PYTHONHOME and disables user-site imports instead, allowing
 # verified setup/build scripts to import their own adjacent source modules.
 (python/'python314._pth').unlink()
 shutil.copytree(args.tools,stage/'Tools')
 supplied=json.loads((stage/'Tools/manifest.json').read_text(encoding='utf-8'))
 if supplied.get('development_only') or supplied.get('game_binaries_included') is not False:
  raise RuntimeError('Use reviewed OSS tools from build_windows_tools.py, not a development payload.')
 actual={p.relative_to(stage/'Tools').as_posix() for p in (stage/'Tools').rglob('*') if p.is_file() and p.name!='manifest.json'}
 if actual!=set(supplied['files']):raise RuntimeError('Unexpected or missing setup-tool file')
 for name,expected in supplied['files'].items():
  if sha(stage/'Tools'/name)!=expected:raise RuntimeError('Changed setup-tool input: '+name)
 # Tool provenance and complete dependency imports are checked before packing.
 from windows_setup import verify_tools
 # curl adapter is first-party, built below rather than supplied externally.
 branding=source/'outputs/sm64-melee-lab/branding/Super Melee 64 Rendered.png'
 from PIL import Image,ImageOps
 mark=ImageOps.contain(Image.open(branding).convert('RGBA'),(256,256),Image.Resampling.LANCZOS)
 icon=Image.new('RGBA',(256,256));icon.alpha_composite(mark,((256-mark.width)//2,(256-mark.height)//2));icon.save(stage/'SuperMelee64.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
 manifest=destination/'windows.manifest'
 manifest.write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"><assemblyIdentity version="1.0.0.0" processorArchitecture="amd64" name="Memelees.SuperMelee64" type="win32"/><trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo><application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings><activeCodePage xmlns="http://schemas.microsoft.com/SMI/2019/WindowsSettings">UTF-8</activeCodePage><longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">true</longPathAware></windowsSettings></application></assembly>''')
 resource=destination/'windows.rc';resource.write_text('1 ICON "'+(stage/'SuperMelee64.ico').as_posix()+'"\n1 24 "'+manifest.as_posix()+'"\n')
 obj=destination/'windows.res.o'
 subprocess.run([args.compiler.replace('g++','windres'),str(resource),'-o',str(obj)],check=True)
 release=source/'outputs/sm64-melee-lab/release'
 common=[args.compiler,'-std=c++17','-O2','-s','-static','-municode','-ffile-prefix-map='+str(source)+'=/source']
 subprocess.run([*common,'-mwindows','-DSMB_VERSION="'+VERSION+'"',release/'WindowsInstaller.cpp',obj,'-o',stage/'SuperMelee64.exe','-lshell32','-lole32','-luuid','-lcomctl32','-lcomdlg32'],check=True)
 subprocess.run([*common,release/'WindowsTool.cpp',obj,'-o',stage/'Tools/curl.exe','-lshell32'],check=True)
 files={p.relative_to(stage/'Tools').as_posix():sha(p) for p in sorted((stage/'Tools').rglob('*')) if p.is_file() and p.name!='manifest.json'}
 provenance=json.loads((stage/'Tools/manifest.json').read_text())
 provenance['files']=files;(stage/'Tools/manifest.json').write_text(json.dumps(provenance,indent=2)+'\n')
 verify_tools(stage)
 forbidden={'.iso','.gcm','.z64','.n64','.v64','.rvz','.dat','.usd','.dol','.smm','.mp4'}
 if any(p.suffix.lower() in forbidden for p in stage.rglob('*')):raise RuntimeError('Game asset found in installer payload')
 audit=dict(version=VERSION,game_assets_included=False,game_binaries_included=False,private_source_history_included=False,
   runtime_pins=RUNTIME,tools=provenance,files={p.relative_to(stage).as_posix():sha(p) for p in sorted(stage.rglob('*')) if p.is_file()})
 (destination/'native-installer-manifest.json').write_text(json.dumps(audit,indent=2)+'\n')
 recipe=destination/'setup.iss'
 inno_path=lambda path: ('Z:'+str(path).replace('/','\\')) if args.wine else str(path)
 recipe.write_text(inno(inno_path(stage),inno_path(destination),audit['files']),encoding='utf-8-sig')
 if args.iscc:
  command=[str(args.iscc),str(recipe)]
  if args.wine:command=[str(args.wine),'--bottle',args.bottle,'--no-gui',*['Z:'+str(p).replace('/','\\') for p in (args.iscc,recipe)]]
  subprocess.run(command,check=True)
 print(stage);return stage

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source-kit',type=Path,required=True);parser.add_argument('--tools',type=Path,required=True)
 parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--compiler',default='x86_64-w64-mingw32-g++');parser.add_argument('--iscc',type=Path)
 parser.add_argument('--wine',type=Path);parser.add_argument('--bottle',default='SuperMelee64-Native-Validation')
 build(parser.parse_args())
if __name__=='__main__':main()
