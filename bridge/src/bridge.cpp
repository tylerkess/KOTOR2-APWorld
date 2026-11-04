// K2APBridge: the game side of the KOTOR 2 Archipelago client link.
//
// - Adds NWScript routines 877-879 (APB_Version, APB_Recv, APB_Send) by hooking the routine dispatcher.
// - Runs the ap_tick script about once a second during gameplay (player-control frame hook, game thread).
// - Serves the named pipe \\.\pipe\K2APBridge for the Python client (protocol: bridge/PROTOCOL.md).
// All game logic lives in NWScript (nss/) and Python; this file only moves strings.
#include <windows.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>

#include "engine.h"

namespace k2ap {

constexpr int kProtocol = 1;
constexpr DWORD kTickMs = 1000;
constexpr size_t kMaxQueue = 512;
constexpr size_t kMaxLine = 8192;
constexpr char kVersion[] = "0.0.1";

// ---------------------------------------------------------------------------------------------------------------
// log: %LOCALAPPDATA%\K2APBridge\bridge.log
std::mutex g_logLock;
char g_logPath[MAX_PATH] = {0};

void Log(const char* fmt, ...) {
    std::lock_guard<std::mutex> lock(g_logLock);
    if (!g_logPath[0]) {
        char base[MAX_PATH];
        DWORD n = GetEnvironmentVariableA("LOCALAPPDATA", base, MAX_PATH);
        if (n == 0 || n >= MAX_PATH) return;
        char dir[MAX_PATH];
        snprintf(dir, sizeof(dir), "%s\\K2APBridge", base);
        CreateDirectoryA(dir, nullptr);
        snprintf(g_logPath, sizeof(g_logPath), "%s\\bridge.log", dir);
    }
    FILE* f = fopen(g_logPath, "a");
    if (!f) return;
    SYSTEMTIME t;
    GetLocalTime(&t);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d.%03d ", t.wYear, t.wMonth, t.wDay, t.wHour, t.wMinute, t.wSecond,
            t.wMilliseconds);
    va_list args;
    va_start(args, fmt);
    vfprintf(f, fmt, args);
    va_end(args);
    fputc('\n', f);
    fclose(f);
}

// ---------------------------------------------------------------------------------------------------------------
// queues shared by the game thread and the pipe thread
std::mutex g_lock;
std::deque<std::string> g_toGame;    // commands from the client, taken by APB_Recv
std::deque<std::string> g_toClient;  // events from APB_Send other than snapshots
std::string g_snapshot;              // latest "S ..." line from ap_tick
volatile LONG g_ticks = 0;
volatile LONG g_hooked = 0;
ULONGLONG g_lastTick = 0;

// ---------------------------------------------------------------------------------------------------------------
// memory helpers
bool Readable(const void* p, size_t n) {
    MEMORY_BASIC_INFORMATION mbi;
    if (!p || !VirtualQuery(p, &mbi, sizeof(mbi))) return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return false;
    const auto end = reinterpret_cast<uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return reinterpret_cast<uintptr_t>(p) + n <= end;
}

uint32_t ReadU32(uint32_t va) {
    const void* p = reinterpret_cast<const void*>(va);
    return Readable(p, 4) ? *reinterpret_cast<const volatile uint32_t*>(p) : 0;
}

bool WriteSlot(uint32_t va, uint32_t value) {
    DWORD old = 0;
    void* p = reinterpret_cast<void*>(va);
    if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) return false;
    *reinterpret_cast<volatile uint32_t*>(p) = value;
    DWORD ignored = 0;
    VirtualProtect(p, 4, old, &ignored);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// engine calls. __thiscall functions are called through __fastcall pointers with a dummy EDX: both pass `this` in
// ECX and have the callee clean the stack arguments.
using ExecuteCommandFn = int(__fastcall*)(void* self, void* edx, int id, int nParams);
using UpdateFn = int(__fastcall*)(void* self, void* edx, float dt);
using StackIntFn = int(__fastcall*)(void* vm, void* edx, int value);
using StackPopIntFn = int(__fastcall*)(void* vm, void* edx, int* out);
using StackStringFn = int(__fastcall*)(void* vm, void* edx, engine::ExoString* s);
using RunScriptFn = int(__fastcall*)(void* vm, void* edx, engine::ExoString* name, uint32_t oid, int flag);
using ExoDtorFn = void(__fastcall*)(engine::ExoString* s, void* edx);
using GetPlayerIdFn = uint32_t(__fastcall*)(void* server, void* edx);

ExecuteCommandFn g_origExecute = nullptr;
UpdateFn g_origUpdate = nullptr;

void* VirtualMachine() {
    return reinterpret_cast<void*>(ReadU32(engine::kVirtualMachinePtr));
}

bool PushInt(void* vm, int v) {
    return reinterpret_cast<StackIntFn>(engine::kStackPushInteger)(vm, nullptr, v) != 0;
}

bool PushString(void* vm, const std::string& s) {
    std::string copy = s;  // the engine copies from our buffer; we keep ownership
    engine::ExoString exo{copy.empty() ? nullptr : &copy[0], static_cast<uint32_t>(copy.empty() ? 0 : copy.size() + 1)};
    return reinterpret_cast<StackStringFn>(engine::kStackPushString)(vm, nullptr, &exo) != 0;
}

bool PopString(void* vm, std::string* out) {
    engine::ExoString exo{nullptr, 0};  // a zeroed string is a valid empty one
    const bool ok = reinterpret_cast<StackStringFn>(engine::kStackPopString)(vm, nullptr, &exo) != 0;
    if (ok && exo.text) out->assign(exo.text, strnlen(exo.text, kMaxLine));
    if (exo.text) reinterpret_cast<ExoDtorFn>(engine::kExoStringDtor)(&exo, nullptr);  // engine-allocated
    return ok;
}

uint32_t PlayerObjectId() {
    const uint32_t app = ReadU32(engine::kAppManagerPtr);
    if (!app) return engine::kObjectInvalid;
    const uint32_t server = ReadU32(app + engine::kAppManagerServer);
    if (!server) return engine::kObjectInvalid;
    return reinterpret_cast<GetPlayerIdFn>(engine::kGetPlayerCreatureId)(reinterpret_cast<void*>(server), nullptr);
}

// ---------------------------------------------------------------------------------------------------------------
// routines 877-879
int RunRoutine(int id) {
    void* vm = VirtualMachine();
    if (!vm) return engine::kErrCommandNotFound;
    switch (id) {
        case engine::kRoutineVersion:
            return PushInt(vm, kProtocol) ? 0 : engine::kErrPush;
        case engine::kRoutineRecv: {
            std::string command;
            {
                std::lock_guard<std::mutex> lock(g_lock);
                if (!g_toGame.empty()) {
                    command = g_toGame.front();
                    g_toGame.pop_front();
                }
            }
            return PushString(vm, command) ? 0 : engine::kErrPush;
        }
        case engine::kRoutineSend: {
            std::string event;
            if (!PopString(vm, &event)) return engine::kErrParam;
            std::lock_guard<std::mutex> lock(g_lock);
            if (event.size() > 1 && event[0] == 'S' && event[1] == ' ') {
                g_snapshot = event;
            } else if (!event.empty()) {
                if (g_toClient.size() >= kMaxQueue) g_toClient.pop_front();
                g_toClient.push_back(event);
            }
            return 0;
        }
        default:
            return engine::kErrCommandNotFound;
    }
}

int __fastcall HookExecuteCommand(void* self, void* edx, int id, int nParams) {
    if (id >= engine::kVanillaRoutineCount && id <= engine::kLastRoutine) return RunRoutine(id);
    if (id == engine::kRoutineEndGame) {
        // The ending script sets GBL_GAME_COMPLETE and calls EndGame in one run: no save or tick follows, so the
        // client hears about it from here ("E"; it checks the last snapshot's module).
        std::lock_guard<std::mutex> lock(g_lock);
        g_toClient.push_back("E");
        Log("EndGame called (last snapshot: %.40s)", g_snapshot.c_str());
    }
    return g_origExecute(self, edx, id, nParams);
}

// ---------------------------------------------------------------------------------------------------------------
// the tick
void RunTick() {
    void* vm = VirtualMachine();
    if (!vm) return;
    const uint32_t player = PlayerObjectId();
    if (player == engine::kObjectInvalid || player == 0) return;
    char name[] = "ap_tick";
    engine::ExoString exo{name, sizeof(name)};
    reinterpret_cast<RunScriptFn>(engine::kRunScript)(vm, nullptr, &exo, player, 1);
    const LONG n = InterlockedIncrement(&g_ticks);
    if (n <= 3 || n % 600 == 0) Log("tick %ld (player 0x%08X)", n, player);
}

int __fastcall HookPlayerControlUpdate(void* self, void* edx, float dt) {
    const ULONGLONG now = GetTickCount64();
    if (now - g_lastTick >= kTickMs) {
        g_lastTick = now;
        RunTick();
    }
    return g_origUpdate(self, edx, dt);
}

// ---------------------------------------------------------------------------------------------------------------
// install
bool ImageMatches() {
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(engine::kImageBase);
    if (!Readable(dos, sizeof(*dos)) || dos->e_magic != IMAGE_DOS_SIGNATURE) return false;
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(engine::kImageBase + dos->e_lfanew);
    if (!Readable(nt, sizeof(*nt))) return false;
    if (nt->FileHeader.TimeDateStamp != engine::kTimeDateStamp) {
        Log("REFUSED: TimeDateStamp 0x%08X, expected 0x%08X (not Steam/Aspyr 1.0.2.0)",
            static_cast<unsigned>(nt->FileHeader.TimeDateStamp), engine::kTimeDateStamp);
        return false;
    }
    struct Probe { const char* name; uint32_t va; uint32_t expected; };
    const Probe probes[] = {
        {"ExecuteCommand slot", engine::kSlotExecuteCommand, engine::kExecuteCommand},
        {"dispatch bound", engine::kSiteDispatchBound, 0x36D},
        {"player control Update slot", engine::kSlotPlayerControlUpdate, engine::kPlayerControlUpdate},
    };
    for (const auto& p : probes) {
        const uint32_t got = ReadU32(p.va);
        if (got != p.expected) {
            Log("REFUSED: %s at 0x%08X holds 0x%08X, expected 0x%08X", p.name, p.va, got, p.expected);
            return false;
        }
    }
    return true;
}

bool Install() {
    if (!ImageMatches()) return false;
    g_origExecute = reinterpret_cast<ExecuteCommandFn>(engine::kExecuteCommand);
    g_origUpdate = reinterpret_cast<UpdateFn>(engine::kPlayerControlUpdate);
    if (!WriteSlot(engine::kSlotExecuteCommand, reinterpret_cast<uint32_t>(&HookExecuteCommand))) {
        Log("REFUSED: could not write the ExecuteCommand slot (error %lu)", GetLastError());
        return false;
    }
    if (!WriteSlot(engine::kSlotPlayerControlUpdate, reinterpret_cast<uint32_t>(&HookPlayerControlUpdate))) {
        WriteSlot(engine::kSlotExecuteCommand, engine::kExecuteCommand);
        Log("REFUSED: could not write the player control Update slot (error %lu)", GetLastError());
        return false;
    }
    InterlockedExchange(&g_hooked, 1);
    Log("hooks installed (bridge %s, protocol %d)", kVersion, kProtocol);
    return true;
}

// ---------------------------------------------------------------------------------------------------------------
// pipe: one request per message, one reply per request (bridge/PROTOCOL.md)
std::string Handle(const std::string& req) {
    const size_t space = req.find(' ');
    const std::string verb = req.substr(0, space);
    const std::string arg = space == std::string::npos ? "" : req.substr(space + 1);
    if (verb == "PING") return "OK pong";
    if (verb == "HELLO") return "OK " + std::to_string(kProtocol) + " K2";
    if (verb == "VER") return std::string("OK ") + kVersion;
    std::lock_guard<std::mutex> lock(g_lock);
    if (verb == "STATUS") {
        const ULONGLONG age = g_lastTick ? GetTickCount64() - g_lastTick : 0;
        return "OK " + std::to_string(g_hooked) + " " + std::to_string(g_ticks) + " " + std::to_string(age) + " " +
               std::to_string(g_toGame.size());
    }
    if (verb == "SNAP") return g_snapshot.empty() ? "ERR nosnap" : "OK " + g_snapshot;
    if (verb == "CMD") {
        if (arg.empty()) return "ERR badrequest";
        if (g_toGame.size() >= kMaxQueue) return "ERR full";
        g_toGame.push_back(arg);
        return "OK";
    }
    if (verb == "CLEAR") {
        g_toGame.clear();
        return "OK";
    }
    if (verb == "EVENT") {
        if (g_toClient.empty()) return "OK";
        std::string e = "OK " + g_toClient.front();
        g_toClient.pop_front();
        return e;
    }
    return "ERR badrequest";
}

DWORD WINAPI PipeThread(LPVOID) {
    for (;;) {
        HANDLE pipe = CreateNamedPipeA("\\\\.\\pipe\\K2APBridge", PIPE_ACCESS_DUPLEX,
                                       PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT, 1, kMaxLine, kMaxLine,
                                       0, nullptr);
        if (pipe == INVALID_HANDLE_VALUE) {
            Log("pipe: CreateNamedPipe failed (error %lu)", GetLastError());
            Sleep(5000);
            continue;
        }
        if (ConnectNamedPipe(pipe, nullptr) || GetLastError() == ERROR_PIPE_CONNECTED) {
            Log("pipe: client connected");
            static char buffer[kMaxLine + 1];
            for (;;) {
                DWORD read = 0;
                if (!ReadFile(pipe, buffer, kMaxLine, &read, nullptr)) break;
                buffer[read] = '\0';
                const std::string reply = Handle(std::string(buffer, read));
                DWORD written = 0;
                if (!WriteFile(pipe, reply.data(), static_cast<DWORD>(reply.size()), &written, nullptr)) break;
            }
            Log("pipe: client disconnected");
        }
        DisconnectNamedPipe(pipe);
        CloseHandle(pipe);
    }
}

DWORD WINAPI InitThread(LPVOID) {
    // The vtables are filled by the time the game window exists; wait for the slots rather than guessing a delay.
    for (int i = 0; i < 600; ++i) {
        if (ReadU32(engine::kSlotExecuteCommand) == engine::kExecuteCommand) break;
        Sleep(100);
    }
    if (Install()) CreateThread(nullptr, 0, PipeThread, nullptr, 0, nullptr);
    return 0;
}

}  // namespace k2ap

// ---------------------------------------------------------------------------------------------------------------
// version.dll proxy: forward every export to the system copy.
namespace {
HMODULE g_real = nullptr;

FARPROC Real(const char* name) {
    if (!g_real) {
        char path[MAX_PATH];
        const UINT n = GetSystemDirectoryA(path, MAX_PATH);  // a 32-bit process is redirected to SysWOW64
        if (n == 0 || n > MAX_PATH - 16) return nullptr;
        strcat(path, "\\version.dll");
        g_real = LoadLibraryA(path);
        if (!g_real) return nullptr;
    }
    return GetProcAddress(g_real, name);
}
}  // namespace

#define FORWARD(ret, name, params, args, fail)                       \
    extern "C" ret WINAPI Proxy_##name params {                       \
        using Fn = ret(WINAPI*) params;                               \
        static Fn fn = reinterpret_cast<Fn>(Real(#name));             \
        return fn ? fn args : fail;                                   \
    }

FORWARD(BOOL, GetFileVersionInfoA, (LPCSTR a, DWORD b, DWORD c, LPVOID d), (a, b, c, d), FALSE)
FORWARD(BOOL, GetFileVersionInfoW, (LPCWSTR a, DWORD b, DWORD c, LPVOID d), (a, b, c, d), FALSE)
FORWARD(BOOL, GetFileVersionInfoExA, (DWORD f, LPCSTR a, DWORD b, DWORD c, LPVOID d), (f, a, b, c, d), FALSE)
FORWARD(BOOL, GetFileVersionInfoExW, (DWORD f, LPCWSTR a, DWORD b, DWORD c, LPVOID d), (f, a, b, c, d), FALSE)
FORWARD(DWORD, GetFileVersionInfoSizeA, (LPCSTR a, LPDWORD b), (a, b), 0)
FORWARD(DWORD, GetFileVersionInfoSizeW, (LPCWSTR a, LPDWORD b), (a, b), 0)
FORWARD(DWORD, GetFileVersionInfoSizeExA, (DWORD f, LPCSTR a, LPDWORD b), (f, a, b), 0)
FORWARD(DWORD, GetFileVersionInfoSizeExW, (DWORD f, LPCWSTR a, LPDWORD b), (f, a, b), 0)
FORWARD(BOOL, GetFileVersionInfoByHandle, (DWORD f, HANDLE h, LPVOID* p, LPDWORD n), (f, h, p, n), FALSE)
FORWARD(DWORD, VerFindFileA, (DWORD f, LPCSTR a, LPCSTR b, LPCSTR c, LPSTR d, PUINT e, LPSTR g, PUINT h),
        (f, a, b, c, d, e, g, h), 0)
FORWARD(DWORD, VerFindFileW, (DWORD f, LPCWSTR a, LPCWSTR b, LPCWSTR c, LPWSTR d, PUINT e, LPWSTR g, PUINT h),
        (f, a, b, c, d, e, g, h), 0)
FORWARD(DWORD, VerInstallFileA, (DWORD f, LPCSTR a, LPCSTR b, LPCSTR c, LPCSTR d, LPCSTR e, LPSTR g, PUINT h),
        (f, a, b, c, d, e, g, h), 0)
FORWARD(DWORD, VerInstallFileW,
        (DWORD f, LPCWSTR a, LPCWSTR b, LPCWSTR c, LPCWSTR d, LPCWSTR e, LPWSTR g, PUINT h), (f, a, b, c, d, e, g, h), 0)
FORWARD(DWORD, VerLanguageNameA, (DWORD a, LPSTR b, DWORD c), (a, b, c), 0)
FORWARD(DWORD, VerLanguageNameW, (DWORD a, LPWSTR b, DWORD c), (a, b, c), 0)
FORWARD(BOOL, VerQueryValueA, (LPCVOID a, LPCSTR b, LPVOID* c, PUINT d), (a, b, c, d), FALSE)
FORWARD(BOOL, VerQueryValueW, (LPCVOID a, LPCWSTR b, LPVOID* c, PUINT d), (a, b, c, d), FALSE)

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        char exe[MAX_PATH];
        GetModuleFileNameA(nullptr, exe, MAX_PATH);
        const char* base = strrchr(exe, '\\');
        base = base ? base + 1 : exe;
        if (_stricmp(base, "swkotor2.exe") == 0) {  // stay a plain proxy in any other process
            k2ap::Log("attached to %s", exe);
            CreateThread(nullptr, 0, k2ap::InitThread, nullptr, 0, nullptr);
        }
    }
    return TRUE;
}
