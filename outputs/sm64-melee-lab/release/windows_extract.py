"""Verified build-tool archive extraction, including Windows/Wine root entries."""
from pathlib import Path
import argparse
import posixpath
import re
import shutil
import tarfile
import zipfile
from windows_dependencies import unzip,safe_member

def extract(archive,destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    if zipfile.is_zipfile(archive):return unzip(archive,destination)
    with tarfile.open(archive) as source:
        members=source.getmembers()
        if sum(m.size for m in members)>4*1024**3:raise ValueError('Oversized build archive')
        for member in members:
            if member.name.rstrip('/') in ('.',''):continue
            safe_member(member.name)
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):raise ValueError('Special build archive member')
        entries={posixpath.normpath(m.name):m for m in members}
        def regular(member,seen=()):
            name=posixpath.normpath(member.name)
            if name in seen:raise ValueError('Cyclic build archive link')
            if member.isfile():return member
            target=posixpath.normpath(posixpath.join(posixpath.dirname(name) if member.issym() else '',member.linkname))
            safe_member(target)
            if target not in entries:raise ValueError('Dangling build archive link')
            return regular(entries[target],(*seen,name))
        links=[m for m in members if m.issym() or m.islnk()]
        # Validate every link before writing. Materialize internal file links as
        # copies, so Windows needs neither Developer Mode nor symlink privileges.
        resolved=[(m,regular(m)) for m in links]
        source.extractall(destination,members=[m for m in members if (m.isfile() or m.isdir()) and m.name.rstrip('/') not in ('.','')],filter='data')
        for member,target in resolved:
            path=destination/member.name;path.parent.mkdir(parents=True,exist_ok=True)
            with source.extractfile(target) as incoming,path.open('wb') as outgoing:shutil.copyfileobj(incoming,outgoing)

def configure(cmake,python,script):
    template=Path(cmake).parent.parent/'share/cmake-3.31/Modules/ExternalProject/extractfile.cmake.in'
    original=template.read_text(encoding='utf-8')
    before='execute_process(COMMAND ${CMAKE_COMMAND} -E tar @args@ ${filename} @options@'
    # An update may move the private build alias. Replace only our exact known
    # command form; never edit an arbitrary changed CMake template.
    original=re.sub(r'^execute_process\(COMMAND "[^"\r\n]+/python.exe" "[^"\r\n]+/windows_extract.py" "\$\{filename\}" "\$\{ut_dir\}"$',lambda _:before,original,flags=re.M)
    after='execute_process(COMMAND "'+Path(python).as_posix()+'" "'+Path(script).as_posix()+'" "${filename}" "${ut_dir}"'
    if before not in original and after not in original:raise RuntimeError('The pinned CMake extraction template changed; preserve it and reinstall setup tools.')
    template.write_text(original.replace(before,after),encoding='utf-8',newline='\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archive',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();extract(args.archive,args.destination)
