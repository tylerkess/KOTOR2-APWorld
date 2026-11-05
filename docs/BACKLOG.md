# Backlog

## Filler rework (owner, 2026-11-04; next session)

Current state: about 180 filler items (8 kinds, fixed amounts: 750 credits, 500 XP, 3 medpacs, 25 components, ...)
plus 4 lightsaber crystals. See client.DELIVERY and data.FILLER / FILLER_WEIGHTS.

Wanted:
1. **XP and credits scale with level.** Use the player's level in ap_tick (GetHitDice on the PC): e.g. XP as a share
   of what the next level needs, credits as a base times level. Delivery ops would carry the scale, not an amount.
2. **Better items more likely later.** Gauge rarity from the game files. Candidates to check:
   - the `Cost` field of each item template (.uti): crystals range 230-3980, for example;
   - `itemcreate.2da` (workbench/lab recipes): may carry level or skill requirements;
   - the game's own random-loot scripts (container treasure) and the `000_RareItemChance` global seen in the 650DAN
     spawn scripts: the generator may already tier items by level;
   - naming tiers in template resrefs (e.g. `_01`.. `_0n`) and `baseitems.2da` categories.
   Then pick filler gear by tier, with the tier window following the player's level (or the share of checks done).
3. **Random skill points.** Check whether KOTOR 2's NWScript has a skill or attribute adjuster (AdjustCreatureSkills /
   AdjustCreatureAttributes are thought to be TSL additions: verify in nwscript before relying on them).
4. **Random Force powers and feats.** GrantSpell (787) and GrantFeat (786) exist. Owner (2026-11-05): the Exile is
   always a Jedi, so every Force power works; powers are usable regardless of alignment (alignment changes their Force
   point cost, a general KOTOR rule); a granted feat works for any class, it just is not selectable at level up for some. Decided
   (owner, 2026-11-05): grants follow the chains, like Archipelago's "progressive" items: a chain's next rank only
   (Force Push before Force Whirlwind, a base feat before its Improved and Master ranks). If the chosen chain's next rank
   is already known (picked at level up) or the chain is complete, pick another random chain that still has a rank to
   give. To do: build the chain list from the game files (spells.2da / feat.2da prerequisite columns). Once every
   chain is complete, a grant does nothing (owner: reaching that would take an absurd level as long as powers are not
   common drops; keep their weight modest).

Also discussed, not chosen yet: per-item weight and amount options in the YAML, more consumable variety (grenades,
shields, repair kits), optional traps.
