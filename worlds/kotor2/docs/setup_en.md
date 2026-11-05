# KOTOR 2 Archipelago setup

Needs: Star Wars: Knights of the Old Republic II, **Steam (Aspyr) build**, and Archipelago 0.6.8 or newer.
Vanilla, TSLRCM, and TSLRCM with the M4-78 Enhancement Project are supported, from the Steam Workshop or installed by
hand. Set the `content` option to match what you have installed; the client refuses a seed made for another setup.

1. Install the world: double-click `kotor2.apworld`.
2. Install the game files: with KOTOR 2 closed, open **KOTOR 2 Client** from the Archipelago Launcher and type
   `/install`. It detects your setup and puts the bridge (`version.dll`) and the scripts in place, backing up anything
   it replaces. `/uninstall` puts everything back. Nothing needs to be built or compiled.
3. Start a **new game**, then connect from **KOTOR 2 Client**. The first save you play while connected is bound to
   your slot; other saves are left alone.

(Pre-release: `/install` does not exist yet; testers install from source as described in the repository README.)

The bridge logs to `%LOCALAPPDATA%\K2APBridge\bridge.log`. `/bridge` in the client shows its status.

## Troubleshooting

- *"The game does not keep Archipelago's globals"*: another `globalcat.2da` wins over ours. The installer replaces the
  copy in TSLRCM's Workshop folder too, but Steam may put the original back when the mod updates: run the install
  again.
- *"from another version of this world"*: rerun the installer after updating the apworld.
