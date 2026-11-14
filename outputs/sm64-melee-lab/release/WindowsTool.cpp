// Original Super Melee 64 setup adapter. GPL-3.0-or-later.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <filesystem>
#include <string>
#include <vector>

static std::wstring quote(const std::wstring& value) {
    std::wstring result=L"\"";unsigned slashes=0;
    for(wchar_t c:value) {
        if(c==L'\\'){slashes++;continue;}
        if(c==L'"')result.append(slashes*2+1,L'\\');
        else result.append(slashes,L'\\');
        result+=c;slashes=0;
    }
    result.append(slashes*2,L'\\');return result+L"\"";
}
int wmain(int argc,wchar_t** argv) {
    wchar_t own[32768];DWORD length=GetModuleFileNameW(nullptr,own,32768);
    if(!length||length>=32768)return 1;
    auto package=std::filesystem::path(own).parent_path().parent_path();
    auto python=package/L"Python"/L"python.exe";
    auto script=package/L"SourceKit"/L"outputs"/L"sm64-melee-lab"/L"release"/L"windows_curl.py";
    std::wstring command=quote(python.wstring())+L" -X utf8 "+quote(script.wstring());
    for(int i=1;i<argc;i++)command+=L" "+quote(argv[i]);
    STARTUPINFOW startup{};startup.cb=sizeof(startup);
    startup.dwFlags=STARTF_USESTDHANDLES;
    startup.hStdInput=GetStdHandle(STD_INPUT_HANDLE);
    startup.hStdOutput=GetStdHandle(STD_OUTPUT_HANDLE);
    startup.hStdError=GetStdHandle(STD_ERROR_HANDLE);
    PROCESS_INFORMATION process{};
    if(!CreateProcessW(python.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW,nullptr,nullptr,&startup,&process))return 1;
    CloseHandle(process.hThread);WaitForSingleObject(process.hProcess,INFINITE);
    DWORD code=1;GetExitCodeProcess(process.hProcess,&code);CloseHandle(process.hProcess);return code;
}
