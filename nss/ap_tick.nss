// ap_tick: K2APBridge runs this about once a second during gameplay, with the player as OBJECT_SELF.
// It records area visits in the save, applies the client's commands and reports a snapshot (protocol.py).
#include "ap_util"
#include "ap_generated"

void AP_Deliver(string sArgs, object oPC) {
    int nIndex = StringToInt(AP_Head(sArgs));
    string sOp = AP_Rest(sArgs);
    int nCurrent = AP_GetReceived();
    if (nIndex != nCurrent) return;  // already applied (lower) or out of order (higher): the next snapshot tells the client
    string sKind = AP_Head(sOp);
    string sRest = AP_Rest(sOp);
    if (sKind == "G") {
        GiveGoldToCreature(oPC, StringToInt(sRest));
    } else if (sKind == "X") {
        GiveXPToCreature(oPC, StringToInt(sRest));
    } else if (sKind == "C") {
        object oItem = CreateItemOnObject(AP_Head(sRest), oPC, StringToInt(AP_Rest(sRest)));
        if (!GetIsObjectValid(oItem)) return;  // unknown template or no room: keep the index, retry next tick
    } else if (sKind == "M") {
        SetGlobalNumber("AP_MITEMS", GetGlobalNumber("AP_MITEMS") | (1 << StringToInt(sRest)));
    } else if (sKind == "P") {
        SetGlobalNumber("AP_PLANETS", GetGlobalNumber("AP_PLANETS") | (1 << StringToInt(sRest)));
    } else if (sKind != "N") {
        return;  // unknown op: never consume an item silently
    }
    AP_SetReceived(nCurrent + 1);
}

void AP_Bind(string sArgs) {
    if (GetGlobalNumber("AP_ID_A") != 0 || AP_GetReceived() != 0) return;
    SetGlobalNumber("AP_ID_A", StringToInt(AP_Head(sArgs)));
    sArgs = AP_Rest(sArgs);
    SetGlobalNumber("AP_ID_B", StringToInt(AP_Head(sArgs)));
    SetGlobalNumber("AP_ID_C", StringToInt(AP_Rest(sArgs)));
}

// jedi_masters shuffled: the game's master count follows the master items, so the meeting (605DAN/650DAN, at 4)
// waits for them; the masters' own dialogues still add 1 each, which this overwrites.
void AP_ForceMasterCount() {
    int nFlags = GetGlobalNumber("AP_OPTS");
    if ((nFlags & AP_OPT_MASTERS) == 0) return;
    int nRequired = (nFlags >> AP_OPT_REQUIRED_SHIFT) & 7;
    if (nRequired < 1 || nRequired > 4) nRequired = 4;
    int nHave = AP_MasterItems();
    int nCount = nHave;
    if (nHave >= nRequired) nCount = 4;
    else if (nCount > 3) nCount = 3;
    if (GetGlobalNumber("000_Jedi_Found") != nCount) SetGlobalNumber("000_Jedi_Found", nCount);
}

void AP_Command(string sCommand, object oPC) {
    string sKind = AP_Head(sCommand);
    string sArgs = AP_Rest(sCommand);
    if (sKind == "I") AP_Deliver(sArgs, oPC);
    else if (sKind == "B") AP_Bind(sArgs);
    else if (sKind == "O") SetGlobalNumber("AP_OPTS", StringToInt(sArgs));
    else if (sKind == "T") FloatingTextStringOnCreature(sArgs, oPC, FALSE);
    else if (sKind == "K") ApplyEffectToObject(DURATION_TYPE_INSTANT, EffectDeath(), oPC);
}

void main() {
    object oPC = GetFirstPC();
    if (!GetIsObjectValid(oPC) || APB_Version() == 0) return;

    string sModule = GetStringUpperCase(GetModuleName());
    AP_MarkVisit(sModule);
    AP_LatchMasters();
    AP_ForceMasterCount();

    if (!GetIsConversationActive()) {
        int n = 0;
        string sCommand = APB_Recv();
        while (sCommand != "") {
            AP_Command(sCommand, oPC);
            n = n + 1;
            if (n >= AP_COMMANDS_PER_TICK) break;
            sCommand = APB_Recv();
        }
    }

    APB_Send("S " + AP_TABLE_HASH + " " + AP_CONTENT + " " + sModule + " " + IntToString(AP_GetReceived()) + " "
             + IntToString(GetGlobalNumber("AP_ID_A")) + " " + IntToString(GetGlobalNumber("AP_ID_B")) + " "
             + IntToString(GetGlobalNumber("AP_ID_C")) + " " + IntToString(GetGlobalNumber("AP_PLANETS")) + " "
             + AP_VisitBits() + " " + AP_QuestStates() + " " + AP_WatchedGlobals());
}
