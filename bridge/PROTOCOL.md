# K2APBridge pipe protocol (version 1)

Named pipe `\\.\pipe\K2APBridge`, message mode, one client at a time. One ASCII request per message, one reply:
`OK`, `OK <value>` or `ERR <reason>`.

| Request | Reply | |
|---|---|---|
| `PING` | `OK pong` | |
| `HELLO <n>` | `OK 1 K2` | bridge protocol |
| `VER` | `OK <bridge version>` | |
| `STATUS` | `OK <hooked 0/1> <ticks> <ms since last tick> <queued commands>` | |
| `SNAP` | `OK S ...` / `ERR nosnap` | the last snapshot ap_tick sent (worlds/kotor2/protocol.py) |
| `CMD <text>` | `OK` / `ERR full` | queue a command for ap_tick (APB_Recv) |
| `CLEAR` | `OK` | drop queued commands (the client resends from the snapshot's received index) |
| `EVENT` | `OK <event>` / `OK` | next event: `E` = the game called EndGame (the ending) |

Game side (NWScript, compiled by tools/build_scripts.py): routine 877 `int APB_Version()`, 878 `string APB_Recv()`,
879 `void APB_Send(string)`. A `S ...` string from APB_Send replaces the stored snapshot; anything else is queued as an
event. The bridge runs `ap_tick` (OBJECT_SELF = the player) once a second from the player-control frame hook.
