// Engine addresses for swkotor2.exe, Steam/Aspyr 1.0.2.0 (TimeDateStamp 0x5603005D, image base 0x00400000, no ASLR).
//
// Sources: K2SE's published research (github.com/renanaugustomacena-ux/K2SE, DESIGN.md and offsets.h: addresses
// only, none of its code) and KotOR Patch Manager's address database (MIT). Every probe below was also re-read from
// the owner's executable on 2026-11-04 (tools: pefile). Install() refuses to hook if any probe disagrees.
#pragma once
#include <cstdint>

namespace k2ap::engine {

constexpr uint32_t kImageBase = 0x00400000;
constexpr uint32_t kTimeDateStamp = 0x5603005D;

// CSWVirtualMachineCommands vtable slot 2 = ExecuteCommand(int id, int nParams), __thiscall, ret 8.
// The routine dispatcher: every NWScript ACTION goes through it. Its own bound check (877) is at 0x00668FDC.
constexpr uint32_t kSlotExecuteCommand = 0x009940D8;
constexpr uint32_t kExecuteCommand = 0x00668FD0;
constexpr uint32_t kSiteDispatchBound = 0x00668FDC;  // dword 0x36D
constexpr int kVanillaRoutineCount = 877;

// CSWPlayerControlCamRelative vtable slot 10 = Update(float dt), __thiscall, ret 4: once per gameplay frame while the
// player is in control (not in menus, loading screens or the main menu).
constexpr uint32_t kSlotPlayerControlUpdate = 0x009A4840;
constexpr uint32_t kPlayerControlUpdate = 0x00865830;

// CVirtualMachine singleton (a pointer stored here) and its stack accessors, all __thiscall(vm, ...) ret 4,
// returning nonzero on success.
constexpr uint32_t kVirtualMachinePtr = 0x00A1B4A8;
constexpr uint32_t kStackPopInteger = 0x006FD9A0;   // (int* out)
constexpr uint32_t kStackPushInteger = 0x006FD9C0;  // (int value)
constexpr uint32_t kStackPopString = 0x006FDA70;    // (CExoString* out): copy-assigns into a constructed string
constexpr uint32_t kStackPushString = 0x006FDA90;   // (CExoString* in): the engine copies it

// CVirtualMachine::RunScript(CExoString* name, uint32 objectSelf, int flag), __thiscall, ret 0xC.
constexpr uint32_t kRunScript = 0x006FD8D0;

// CExoString { char* text; uint32 capacity; }. The destructor frees with the engine's allocator, so a string the
// engine filled (StackPopString) must be released through it.
constexpr uint32_t kExoStringDtor = 0x00733780;

// CAppManager* at this address; +0x08 is CServerExoApp. GetPlayerCreatureId is __thiscall() ret 0.
constexpr uint32_t kAppManagerPtr = 0x00A1B4A4;
constexpr uint32_t kAppManagerServer = 0x08;
constexpr uint32_t kGetPlayerCreatureId = 0x0051C8F0;

constexpr uint32_t kObjectInvalid = 0x7F000000;

// Error codes the engine's own handlers return.
constexpr int kErrCommandNotFound = -2002;
constexpr int kErrParam = -2001;
constexpr int kErrPush = -2000;

struct ExoString {
    char* text;
    uint32_t capacity;
};

// Our routine IDs (tools/build_scripts.py BRIDGE_ROUTINES).
constexpr int kRoutineVersion = 877;
constexpr int kRoutineRecv = 878;
constexpr int kRoutineSend = 879;
constexpr int kLastRoutine = 879;

// Vanilla routine 564 EndGame: only the ending script (904MAL a_end_game) and an unused demo script call it.
constexpr int kRoutineEndGame = 564;

}  // namespace k2ap::engine
