// Native per-user setup and launcher. Game images are processed locally only.
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shellapi.h>
#include <shlobj.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <algorithm>
#ifndef SMB_VERSION
#define SMB_VERSION "development"
#endif
namespace fs=std::filesystem;
static HWND window,romEdit,discEdit,installButton,playButton,cancelButton,statusText,progressBar;
static HANDLE worker=nullptr,job=nullptr,instanceMutex=nullptr;
static fs::path package,data;
static bool cancelling=false,headless=false;
static ULONGLONG cancelStarted=0;
static bool processGroup(){
    if(job){TerminateJobObject(job,130);CloseHandle(job);}
    job=CreateJobObjectW(nullptr,nullptr);JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    return job&&SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits,sizeof(limits));
}
static void waitForGameSession(){
    // The CRT's execv co-op handoff can create a replacement process. Keep the
    // whole session alive, including recorder finalization, after its launcher exits.
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info{};
    while(QueryInformationJobObject(job,JobObjectBasicAccountingInformation,&info,sizeof(info),nullptr)&&info.ActiveProcesses)Sleep(100);
}
static std::wstring quote(const std::wstring& value){
    std::wstring result=L"\"";size_t slashes=0;
    for(wchar_t c:value){if(c==L'\\'){slashes++;continue;}result.append(c==L'\"'?slashes*2+1:slashes,L'\\');slashes=0;result+=c;}
    result.append(slashes*2,L'\\');return result+L"\"";
}
static std::wstring wide(const std::string& text){
    int n=MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),nullptr,0);
    std::wstring result(n,L'\0');MultiByteToWideChar(CP_UTF8,0,text.data(),int(text.size()),result.data(),n);return result;
}
static std::wstring read(const fs::path& path){std::ifstream file(path,std::ios::binary);return wide(std::string(std::istreambuf_iterator<char>(file),{}));}
static void message(const std::wstring& text){MessageBoxW(window,text.c_str(),L"Super Melee 64",MB_OK|MB_ICONERROR);}
static std::wstring text(HWND control){int n=GetWindowTextLengthW(control);std::wstring value(n+1,L'\0');GetWindowTextW(control,value.data(),n+1);value.resize(n);return value;}
static fs::path known(REFKNOWNFOLDERID id){PWSTR p=nullptr;fs::path result;if(SUCCEEDED(SHGetKnownFolderPath(id,0,nullptr,&p))){result=p;CoTaskMemFree(p);}return result;}
static bool ready(){return fs::exists(data/L"ready.json")&&fs::exists(data/L"Workspace/Super Melee 64.exe")&&read(data/L"installed-version.txt")==wide(SMB_VERSION);}
static bool launch(const fs::path& exe,const std::wstring& arguments,bool capture,HANDLE* process){
    SECURITY_ATTRIBUTES inherit{sizeof(inherit),nullptr,TRUE};
    HANDLE out=INVALID_HANDLE_VALUE,input=INVALID_HANDLE_VALUE;
    STARTUPINFOW info{};info.cb=sizeof(info);
    if(capture){
        out=CreateFileW((data/L"setup-gui.log").c_str(),GENERIC_WRITE,FILE_SHARE_READ,&inherit,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,nullptr);
        input=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&inherit,OPEN_EXISTING,0,nullptr);
        if(out==INVALID_HANDLE_VALUE||input==INVALID_HANDLE_VALUE){if(out!=INVALID_HANDLE_VALUE)CloseHandle(out);if(input!=INVALID_HANDLE_VALUE)CloseHandle(input);return false;}
        info.dwFlags=STARTF_USESTDHANDLES;info.hStdOutput=out;info.hStdError=out;info.hStdInput=input;
    }
    std::wstring cmd=quote(exe.wstring())+L" "+arguments;PROCESS_INFORMATION child{};
    // Assign the suspended worker before it can start any compiler children.
    BOOL ok=CreateProcessW(exe.c_str(),cmd.data(),nullptr,nullptr,capture,CREATE_NO_WINDOW|CREATE_SUSPENDED,nullptr,package.c_str(),&info,&child);
    if(capture){CloseHandle(out);CloseHandle(input);}
    if(!ok)return false;
    if(job&&!AssignProcessToJobObject(job,child.hProcess)){TerminateProcess(child.hProcess,1);CloseHandle(child.hProcess);CloseHandle(child.hThread);return false;}
    ResumeThread(child.hThread);CloseHandle(child.hThread);*process=child.hProcess;return true;
}
static void openPath(const fs::path& path){ShellExecuteW(window,L"open",path.c_str(),nullptr,nullptr,SW_SHOWNORMAL);}
static void play(){
    if(!ready()){message(L"Complete setup before playing. Your existing saves are kept when you update.");return;}
    HANDLE process=nullptr;
    if(!launch(data/L"Workspace/Super Melee 64.exe",L"",false,&process)){message(L"Windows could not start the prepared game. Choose Repair / Resume and check the setup log.");return;}
    // Launcher waits for gameplay; the setup/update mutex remains held.
    ShowWindow(window,SW_HIDE);WaitForSingleObject(process,INFINITE);waitForGameSession();CloseHandle(process);DestroyWindow(window);
}
static void browse(HWND control,bool rom){
    wchar_t filename[32768]={};OPENFILENAMEW dialog{};dialog.lStructSize=sizeof(dialog);dialog.hwndOwner=window;
    dialog.lpstrTitle=rom?L"Choose your Super Mario 64 (USA) ROM":L"Choose your Super Smash Bros. Melee (USA, Rev 2) disc";
    dialog.lpstrFilter=rom?L"Nintendo 64 ROM (*.z64;*.n64;*.v64)\0*.z64;*.n64;*.v64\0All files\0*.*\0":L"Melee disc (*.iso;*.gcm)\0*.iso;*.gcm\0All files\0*.*\0";
    dialog.lpstrFile=filename;dialog.nMaxFile=32768;dialog.Flags=OFN_FILEMUSTEXIST|OFN_PATHMUSTEXIST|OFN_NOCHANGEDIR;
    if(GetOpenFileNameW(&dialog))SetWindowTextW(control,filename);
}
static std::wstring backend(const fs::path& rom,const fs::path& disc){
    return L"-X utf8 "+quote((package/L"SourceKit/outputs/sm64-melee-lab/release/windows_setup.py").wstring())+
        L" --package "+quote(package.wstring())+L" --data "+quote(data.wstring())+L" --rom "+quote(rom.wstring())+L" --melee "+quote(disc.wstring());
}
static void build(){
    if(worker)return;
    fs::path rom=text(romEdit),disc=text(discEdit);
    if(!fs::is_regular_file(rom)||!fs::is_regular_file(disc)){message(L"Choose both original game files. Files stay on this computer; setup will verify their versions before downloading tools.");return;}
    fs::remove(data/L"setup.cancel");fs::remove(data/L"setup-error.txt");fs::remove(data/L"setup-ui.status");
    if(!launch(package/L"Python/python.exe",backend(rom,disc),true,&worker)){message(L"Windows could not start setup. Reinstall the complete Windows installer, then try again. Error "+std::to_wstring(GetLastError()));return;}
    cancelling=false;EnableWindow(romEdit,FALSE);EnableWindow(discEdit,FALSE);EnableWindow(installButton,FALSE);EnableWindow(playButton,FALSE);EnableWindow(cancelButton,TRUE);
    SetWindowTextW(statusText,L"Checking your game files…");SetTimer(window,1,300,nullptr);
}
static void cancel(){if(!worker||cancelling)return;cancelling=true;cancelStarted=GetTickCount64();std::ofstream(data/L"setup.cancel")<<"cancel\n";SetWindowTextW(statusText,L"Stopping safely. Verified downloads and completed work will be kept…");EnableWindow(cancelButton,FALSE);}
static void update(){
    if(!worker)return;
    if(cancelling&&GetTickCount64()-cancelStarted>30000)TerminateJobObject(job,130);
    auto status=read(data/L"setup-ui.status");size_t end=status.find(L'\n');
    if(end!=std::wstring::npos&&!cancelling){int percent=_wtoi(status.substr(0,end).c_str());SendMessageW(progressBar,PBM_SETPOS,std::clamp(percent,0,100),0);SetWindowTextW(statusText,status.substr(end+1).c_str());}
    if(WaitForSingleObject(worker,0)!=WAIT_OBJECT_0)return;
    DWORD code=1;GetExitCodeProcess(worker,&code);CloseHandle(worker);worker=nullptr;KillTimer(window,1);
    // End any compiler grandchildren before a retry starts using their outputs.
    if(!processGroup()){message(L"Windows could not reset the setup process group. Close setup and reopen it before retrying.");DestroyWindow(window);return;}
    EnableWindow(romEdit,TRUE);EnableWindow(discEdit,TRUE);EnableWindow(installButton,TRUE);EnableWindow(playButton,ready());EnableWindow(cancelButton,FALSE);
    SetWindowTextW(installButton,L"Repair / Resume");
    if(code==0){SendMessageW(progressBar,PBM_SETPOS,100,0);SetWindowTextW(statusText,L"Ready to play. Your saves are kept separately from the application.");}
    else if(code==130||cancelling)SetWindowTextW(statusText,L"Setup stopped. Choose Install / Resume to continue where you left off.");
    else{SetWindowTextW(statusText,L"Setup needs attention. Open the setup log for details, then Repair / Resume.");auto detail=read(data/L"setup-error.txt");if(detail.empty())detail=L"Setup stopped unexpectedly (exit "+std::to_wstring(code)+L"). Open the setup log for the last completed step. Your files and verified downloads are kept.";message(detail);}
}
static HWND control(const wchar_t* cls,const wchar_t* label,int id,int x,int y,int w,int h,DWORD flags=0){
    HWND value=CreateWindowExW(cls==std::wstring(L"EDIT")?WS_EX_CLIENTEDGE:0,cls,label,WS_CHILD|WS_VISIBLE|flags,x,y,w,h,window,(HMENU)(INT_PTR)id,GetModuleHandleW(nullptr),nullptr);
    SendMessageW(value,WM_SETFONT,(WPARAM)GetStockObject(DEFAULT_GUI_FONT),TRUE);return value;
}
static LRESULT CALLBACK proc(HWND hwnd,UINT msg,WPARAM wp,LPARAM lp){
    switch(msg){
    case WM_COMMAND:switch(LOWORD(wp)){case 10:browse(romEdit,true);break;case 11:browse(discEdit,false);break;case 12:build();break;case 13:play();break;case 14:cancel();break;case 15:openPath(fs::exists(data/L"setup-gui.log")?data/L"setup-gui.log":data);break;}return 0;
    case WM_DROPFILES:{HDROP drop=(HDROP)wp;for(UINT i=0;i<DragQueryFileW(drop,0xffffffff,nullptr,0);++i){wchar_t p[32768];DragQueryFileW(drop,i,p,32768);std::wstring ext=fs::path(p).extension().wstring();std::transform(ext.begin(),ext.end(),ext.begin(),towlower);if(!worker)SetWindowTextW(ext==L".z64"||ext==L".n64"||ext==L".v64"?romEdit:discEdit,p);}DragFinish(drop);return 0;}
    case WM_TIMER:update();return 0;
    case WM_CLOSE:if(worker){cancel();return 0;}DestroyWindow(hwnd);return 0;
    case WM_DESTROY:PostQuitMessage(0);return 0;
    }return DefWindowProcW(hwnd,msg,wp,lp);
}
static int application(HINSTANCE instance){
    SetProcessDPIAware();std::vector<wchar_t> exe(32768);DWORD n=GetModuleFileNameW(nullptr,exe.data(),DWORD(exe.size()));if(!n||n>=exe.size())return 1;package=fs::path(std::wstring(exe.data(),n)).parent_path();
    int count=0;LPWSTR* arguments=CommandLineToArgvW(GetCommandLineW(),&count);std::vector<std::wstring> args(arguments+1,arguments+count);LocalFree(arguments);
    if(args.size()==1&&args[0]==L"--self-test")return quote(L"a b")==L"\"a b\""&&quote(L"x\\")==L"\"x\\\\\""?0:1;
    bool setup=false,install=false,uiTest=false;fs::path rom,disc;std::wstring extra;
    for(size_t i=0;i<args.size();++i){if(args[i]==L"--setup")setup=true;else if(args[i]==L"--ui-self-test"){setup=true;uiTest=true;}else if(args[i]==L"--install")install=true;else if(args[i]==L"--check-only")extra+=L" --check-only";else if(i+1<args.size()&&args[i]==L"--data")data=args[++i];else if(i+1<args.size()&&args[i]==L"--rom")rom=args[++i];else if(i+1<args.size()&&args[i]==L"--melee")disc=args[++i];else if(i+1<args.size()&&args[i]==L"--minimum-free-gib")extra+=L" --minimum-free-gib "+quote(args[++i]);else{message(L"Unknown setup option.");return 2;}}
    instanceMutex=CreateMutexW(nullptr,FALSE,L"Local\\SuperMelee64.Running");if(!instanceMutex||GetLastError()==ERROR_ALREADY_EXISTS){message(L"Super Melee 64 or its setup is already running. Close it before starting another instance or updating.");return 2;}
    if(data.empty())data=known(FOLDERID_LocalAppData)/L"Memelees/SuperMelee64";
    std::error_code ec;fs::create_directories(data,ec);if(ec){message(L"Cannot write your local setup folder. Check available disk space and permissions.");return 1;}
    if(!processGroup()){message(L"Windows could not create the setup process group.");return 1;}
    SetEnvironmentVariableW(L"PYTHONHOME",(package/L"Python").c_str());SetEnvironmentVariableW(L"PYTHONPATH",L"");SetEnvironmentVariableW(L"PYTHONNOUSERSITE",L"1");SetEnvironmentVariableW(L"PYTHONUTF8",L"1");
    if(install){HANDLE process=nullptr;if(rom.empty()||disc.empty()||!launch(package/L"Python/python.exe",backend(rom,disc)+extra,true,&process))return 2;WaitForSingleObject(process,INFINITE);DWORD code=1;GetExitCodeProcess(process,&code);CloseHandle(process);CloseHandle(job);return int(code);}
    if(!setup&&ready()){HANDLE process=nullptr;if(!launch(data/L"Workspace/Super Melee 64.exe",L"",false,&process))return 1;WaitForSingleObject(process,INFINITE);waitForGameSession();DWORD code=1;GetExitCodeProcess(process,&code);CloseHandle(process);CloseHandle(job);return int(code);}
    INITCOMMONCONTROLSEX common{sizeof(common),ICC_PROGRESS_CLASS};InitCommonControlsEx(&common);
    WNDCLASSW cls{};cls.lpfnWndProc=proc;cls.hInstance=instance;cls.lpszClassName=L"SuperMelee64Setup";cls.hCursor=LoadCursorW(nullptr,IDC_ARROW);cls.hbrBackground=(HBRUSH)(COLOR_WINDOW+1);cls.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(1));RegisterClassW(&cls);
    window=CreateWindowExW(WS_EX_ACCEPTFILES,cls.lpszClassName,L"Super Melee 64 — Setup",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,CW_USEDEFAULT,CW_USEDEFAULT,730,455,nullptr,nullptr,instance,nullptr);
    if(!window){if(!uiTest)message(L"Windows could not create the setup window (error "+std::to_wstring(GetLastError())+L"). Reopen setup, or keep this error code for the project maintainer.");return 4;}
    control(L"STATIC",L"Super Melee 64",0,24,20,660,30);
    control(L"STATIC",L"Drag in your game files, or choose them below. Preparation happens on this PC.\nThe first setup downloads tools and builds the game; updates keep your saves.",0,24,58,660,44);
    control(L"STATIC",L"Super Mario 64 — USA ROM",0,24,116,620,20);romEdit=control(L"EDIT",L"",0,24,140,555,26,ES_AUTOHSCROLL|WS_TABSTOP);control(L"BUTTON",L"Choose…",10,588,140,100,26,WS_TABSTOP);
    control(L"STATIC",L"Super Smash Bros. Melee — USA, Rev 2 disc",0,24,180,620,20);discEdit=control(L"EDIT",L"",0,24,204,555,26,ES_AUTOHSCROLL|WS_TABSTOP);control(L"BUTTON",L"Choose…",11,588,204,100,26,WS_TABSTOP);
    auto owned=data/L"Workspace/work";auto savedRom=owned/L"sm64ex-source/baserom.us.z64",savedDisc=owned/L"game-inputs/Melee.iso";
    if(fs::exists(savedRom))SetWindowTextW(romEdit,savedRom.c_str());if(fs::exists(savedDisc))SetWindowTextW(discEdit,savedDisc.c_str());
    statusText=control(L"STATIC",L"Choose both files to begin. At least 12 GiB free space is required; 20 GiB is recommended.",0,24,250,660,44);
    progressBar=control(PROGRESS_CLASSW,L"",0,24,300,664,20);SendMessageW(progressBar,PBM_SETRANGE32,0,100);
    installButton=control(L"BUTTON",L"Install / Resume",12,24,340,150,32,WS_TABSTOP|BS_DEFPUSHBUTTON);playButton=control(L"BUTTON",L"Play",13,186,340,100,32,WS_TABSTOP);EnableWindow(playButton,ready());
    control(L"BUTTON",L"Open Setup Log",15,348,340,150,32,WS_TABSTOP);cancelButton=control(L"BUTTON",L"Cancel Setup",14,510,340,178,32,WS_TABSTOP);EnableWindow(cancelButton,FALSE);
    if(uiTest){bool valid=IsWindow(romEdit)&&IsWindow(discEdit)&&IsWindow(installButton)&&IsWindow(playButton)&&IsWindow(progressBar)&&IsWindow(cancelButton)&&!IsWindowEnabled(cancelButton);DestroyWindow(window);CloseHandle(job);CloseHandle(instanceMutex);return valid?0:5;}
    ShowWindow(window,SW_SHOWNORMAL);MSG msg;while(GetMessageW(&msg,nullptr,0,0)>0){if(!IsDialogMessageW(window,&msg)){TranslateMessage(&msg);DispatchMessageW(&msg);}}
    CloseHandle(job);CloseHandle(instanceMutex);return 0;
}
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE,PWSTR,int){
    try{return application(instance);}
    catch(const std::exception& error){message(L"Setup could not access a local file or folder. Check its permissions and available disk space, then reopen setup.\n\n"+wide(error.what()));return 1;}
}
