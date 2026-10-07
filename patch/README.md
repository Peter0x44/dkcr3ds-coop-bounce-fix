# DKC Returns 3D (USA, 00040000000CCE00) — co-op enemy bounce fix

**Status:** tested in co-op in Azahar. Both players can now bounce off the same enemy.

**Bug:** when player 1 bops an enemy, player 2 falls straight through it. The game already
keeps a bopped enemy's corpse solid for 0.5 s (death type 1 starts a corpse timer), but two
checks throw away any collision with a dead enemy before the bounce rules see it:

1. `Creature::vf9` (collision callback, `0x2ECD78`) returns immediately if the creature is dead.
2. The behavior collision dispatcher (`0x2EE638`) only forwards collisions to the creature's
   active behavior, and a corpse has none.

The contact rules themselves still say "dead enemy touched from above → bounce the player".

**Fix:** two small code caves in unused padding at the end of `.text` (`0x3E8880`):
- Cave 1 (hooked from `0x2ECDDC`): treat the creature as alive while its corpse timer (`+0x30C`) is running.
- Cave 2 (hooked from `0x2EE644`): if the creature is dead and the timer is running, send the
  contact straight to the contact handler (`0x22CCC4`), as a behavior would.

The window is the game's own corpse timer: a bop kills with death type 1, which already keeps the
corpse solid and starts a 0.5 s timer (it counts seconds, not frames). The patch only stops the two
checks from ignoring collisions during that window. After it, the corpse stops being solid, as before.

The patch is 24 words: two 1-instruction hooks and two routines (8 and 14 instructions).

## Install
- **Azahar / Citra:** `<user>/load/mods/00040000000CCE00/exefs/code.ips`
  (or right-click the game → *Open Mods Location*).
- **Real 3DS (Luma3DS):** `sd:/luma/titles/00040000000CCE00/code.ips`, then enable
  *"Enable game patching"* in the Luma config menu (hold SELECT on boot).
- **Cheat instead of IPS:** `cheat_gateway.txt` (Azahar cheat window, or `sd:/cheats/00040000000CCE00.txt`
  for Rosalina). Enable it before entering a level.

Rebuild with `python scripts/build_patches.py`. Pass your own `code.bin` (from
`scripts/extract_3ds_code.py`) to also check every original word, so it refuses the wrong game or version.
