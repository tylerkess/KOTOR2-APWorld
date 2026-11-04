// ap_gm_lock: called from the patched a_galaxymap just before ShowGalaxyMap (tools/build_scripts.py).
// The vanilla script has already decided which planets are open; this only closes the ones whose Archipelago
// coordinates have not arrived. A save never bound to a slot (AP_ID_A 0) is left alone. It never calls a bridge
// routine, so the galaxy map keeps working when version.dll is missing.
#include "ap_util"
#include "ap_generated"

void main() {
    if (GetGlobalNumber("AP_ID_A") == 0) return;
    AP_LockPlanets();
    // m4_78_access coordinates_only: the item alone opens M4-78, while the hub is open (not before Telos is done, not
    // in the endgame). 000_M478_Found is left alone so T3-M4's datapad scene on Korriban plays as usual.
    if ((GetGlobalNumber("AP_OPTS") & AP_OPT_M478) != 0 && AP_HasPlanetBit(AP_M478_BIT)
        && GetGlobalNumber("262TEL_Escape_Telos") == 1 && GetGlobalNumber("900MAL_Open") == 0) {
        SetPlanetAvailable(AP_M478_ROW, TRUE);
        SetPlanetSelectable(AP_M478_ROW, TRUE);
    }
}
