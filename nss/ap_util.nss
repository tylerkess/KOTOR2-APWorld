// Archipelago helpers shared by ap_tick and ap_gm_lock.
// APB_Version / APB_Recv / APB_Send are routines 877-879 added by K2APBridge (docs/DESIGN.md).

int AP_GetReceived() {
    return GetGlobalNumber("AP_RECV_LO") + 100 * GetGlobalNumber("AP_RECV_HI");
}

void AP_SetReceived(int nIndex) {
    SetGlobalNumber("AP_RECV_LO", nIndex % 100);
    SetGlobalNumber("AP_RECV_HI", nIndex / 100);
}

// The level the player's XP has earned, level-ups taken or not: level L+1 starts at 500 x L x (L+1) XP (the d20
// curve in exptable.2da; tools/build_scripts.py checks it). Read fresh for each delivery, so a queued XP item scales
// with the levels the ones before it earned.
int AP_Level(object oPC) {
    int nXP = GetXP(oPC);
    int n = 1;
    while (n < 50 && nXP >= 500 * n * (n + 1)) {
        n = n + 1;
    }
    return n;
}

int AP_HasPlanetBit(int nBit) {
    return (GetGlobalNumber("AP_PLANETS") & (1 << nBit)) != 0;
}

// First space-separated token of s.
string AP_Head(string s) {
    int i = FindSubString(s, " ");
    if (i < 0) return s;
    return GetSubString(s, 0, i);
}

// Everything after the first space of s ("" when there is none).
string AP_Rest(string s) {
    int i = FindSubString(s, " ");
    if (i < 0) return "";
    return GetSubString(s, i + 1, GetStringLength(s) - i - 1);
}
