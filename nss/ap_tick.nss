// ap_tick: K2APBridge runs this about once a second during gameplay, with the player as OBJECT_SELF.
// It records area visits in the save, applies the client's commands and reports a snapshot (protocol.py).
#include "ap_util"
#include "ap_generated"

// Gear: "<prefix> <size> <skip> <rare %> <jackpot %>" (protocol.GEAR_GROUPS). The tier follows the game's own loot
// (k_plc_it_*): earned level -5..+2, clamped to 1..30. A rare roll lands 0..+12 above the level instead; a jackpot
// anywhere from level +3 to 30. Families shorter than 30 cover the same range in bigger steps.
void AP_GiveGear(string s, object oPC) {
    string sPrefix = AP_Head(s);
    s = AP_Rest(s);
    int nSize = StringToInt(AP_Head(s));
    s = AP_Rest(s);
    int nSkip = StringToInt(AP_Head(s));
    s = AP_Rest(s);
    int nRare = StringToInt(AP_Head(s));
    int nJackpot = StringToInt(AP_Rest(s));
    int nLevel = AP_Level(oPC);
    int nTier = nLevel + Random(8) - 5;
    int nRoll = Random(100);
    if (nRoll < nJackpot) {
        int nLow = nLevel + 3;
        if (nLow > 30) nLow = 30;
        nTier = nLow + Random(31 - nLow);
    } else if (nRoll < nJackpot + nRare) {
        nTier = nTier + 5 + Random(6);
    }
    if (nTier < 1) nTier = 1;
    if (nTier > 30) nTier = 30;
    int n = (nTier * nSize + 29) / 30;
    if (n < 1) n = 1;
    if (n > nSize) n = nSize;
    if (n == nSkip) {
        if (n < nSize) n = n + 1;
        else n = n - 1;
    }
    string sNumber = IntToString(n);
    if (n < 10) sNumber = "0" + sNumber;
    CreateItemOnObject(sPrefix + sNumber, oPC, 1);
}

void AP_Deliver(string sArgs, object oPC) {
    int nIndex = StringToInt(AP_Head(sArgs));
    string sOp = AP_Rest(sArgs);
    int nCurrent = AP_GetReceived();
    if (nIndex != nCurrent) return;  // already applied (lower) or out of order (higher): the next snapshot tells the client
    string sKind = AP_Head(sOp);
    string sRest = AP_Rest(sOp);
    if (sKind == "G") {
        GiveGoldToCreature(oPC, StringToInt(sRest));
    } else if (sKind == "GS") {  // credits per level
        GiveGoldToCreature(oPC, StringToInt(sRest) * AP_Level(oPC));
    } else if (sKind == "X") {
        GiveXPToCreature(oPC, StringToInt(sRest));
    } else if (sKind == "XS") {  // percent of the earned level's span: 1000 x level XP (AP_Level)
        GiveXPToCreature(oPC, StringToInt(sRest) * 10 * AP_Level(oPC));
    } else if (sKind == "C") {
        // Not retried on an invalid result: an item that merges into a stack the player already has comes back
        // invalid although it was given (seen in game 2026-11-05: Chemicals delivered every 5 s).
        CreateItemOnObject(AP_Head(sRest), oPC, StringToInt(AP_Rest(sRest)));
    } else if (sKind == "R2") {
        AP_GiveGear(sRest, oPC);
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
