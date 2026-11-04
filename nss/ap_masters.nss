// ap_masters: runs first in the masters' meeting scripts (650DAN: k_650enter, k_def_650kavar/vrook/zez), patched in
// by tools/build_scripts.py. With jedi_masters shuffled and unmet_masters absent, every master the Exile never met is
// marked dead just before the scene decides who attends, as if they had been killed. Their own planets are not
// affected: nothing is marked before this point.
#include "ap_util"
#include "ap_generated"

void main() {
    int nFlags = GetGlobalNumber("AP_OPTS");
    if ((nFlags & AP_OPT_MASTERS) == 0 || (nFlags & AP_OPT_ABSENT) == 0) return;
    if (GetGlobalNumber("000_Jedi_Found") < 4) return;
    AP_LatchMasters();
    AP_MarkUnmetMasters();
}
