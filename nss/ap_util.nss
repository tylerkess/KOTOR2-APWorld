// Archipelago helpers shared by ap_tick and ap_gm_lock.
// APB_Version / APB_Recv / APB_Send are routines 877-879 added by K2APBridge (docs/DESIGN.md).

int AP_GetReceived() {
    return GetGlobalNumber("AP_RECV_LO") + 100 * GetGlobalNumber("AP_RECV_HI");
}

void AP_SetReceived(int nIndex) {
    SetGlobalNumber("AP_RECV_LO", nIndex % 100);
    SetGlobalNumber("AP_RECV_HI", nIndex / 100);
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
