# DKC Returns 3D — co-op fixes

Three folders, each with a `code.ips` and a `cheat_gateway.txt` per region:

- **`both/` (recommended):** both fixes in one patch. Use this unless you have a reason not to.
- `coop_bounce_fix/`: only the bounce fix (both players can bounce off the same enemy).
- `region_free_multiplayer/`: only the region fix (different regions can play local co-op together).

The separate folders are there to examine each fix on its own. Luma loads only one `code.ips` per
game, so to get both fixes use `both/`, not two separate patches.

## Co-op enemy bounce fix

**Status:** USA tested in co-op in Azahar; both players can now bounce off the same enemy. Europe,
Japan and Korea use the same code at their own addresses (verified by build script), not play-tested.

**Bug:** when player 1 bops an enemy, player 2 falls straight through it. The game already
keeps a bopped enemy's corpse solid for 0.5 s (death type 1 starts a corpse timer), but two
checks throw away any collision with a dead enemy before the bounce rules see it:

1. `Creature::vf9` (collision callback, `0x2ECD78`) returns immediately if the creature is dead.
2. The behavior collision dispatcher (`0x2EE638`) only forwards collisions to the creature's
   active behavior, and a corpse has none.

The contact rules themselves still say "dead enemy touched from above → bounce the player".

**Fix:** two small code caves in unused padding at the end of `.text` (USA `0x3E8880`):
- Cave 1 (hooked from `0x2ECDDC`): treat the creature as alive while its corpse timer (`+0x30C`) is running.
- Cave 2 (hooked from `0x2EE644`): if the creature is dead and the timer is running, send the
  contact straight to the contact handler (`0x22CCC4`), as a behavior would.

The window is the game's own corpse timer: a bop kills with death type 1, which already keeps the
corpse solid and starts a 0.5 s timer (it counts seconds, not frames). The patch only stops the two
checks from ignoring collisions during that window. After it, the corpse stops being solid, as before.

The patch is 24 words: two 1-instruction hooks and two routines (8 and 14 instructions).

## Region-free local multiplayer

**Bug:** 3DS local play only shows sessions with the same *local communication ID*. The game builds
it from its region's unique ID (USA `0xCCE`, Europe `0xCCF`, Japan `0xCC0`, Korea `0xFFC`), so
copies from different regions never see each other's sessions, with no error.

**Fix:** the ID is built by one small helper, called only when scanning for sessions and when
creating one. Its code is identical in all four versions. Three instructions make it always build
the USA ID (flag bits unchanged):

| Offset in helper | Original | Patched |
|---|---|---|
| `+0x04` | `bic r0, r0, #0xf00000` | `mov r0, #0xcc0` |
| `+0x18` | `cmp r1, #0` | `orr r2, r2, #0xe00` |
| `+0x1C` | `orrne r2, r2, #1` | `orr r2, r2, r1` |

Helper address: USA `0x1201D4`, Europe `0x1201F4`, Japan `0x1201FC`, Korea `0x120218`. Unpatched
USA copies already use this ID, so they can join patched copies of any region.

**Status:** tested in Azahar with a USA copy playing together with a patched European copy, and with
a patched Japanese copy. The Korean patch is the same three instructions at Korea's helper address,
not play-tested.

## Pick your region
Use the folder matching your game's title ID (`TID` below). Bounce-fix addresses elsewhere in this
file are the USA build's; the other builds have the same code at slightly shifted addresses:

| Region | TID | Folder | bounce hook 1 | bounce hook 2 | bounce routines |
|---|---|---|---|---|---|
| USA | `00040000000CCE00` | `coop_bounce_fix/USA/` | `0x2ECDDC` | `0x2EE644` | `0x3E8880` |
| Europe | `00040000000CCF00` | `coop_bounce_fix/EUR/` | `0x2ECE18` | `0x2EE680` | `0x3E88C0` |
| Japan | `00040000000CC000` | `coop_bounce_fix/JPN/` | `0x2ECEE4` | `0x2EE74C` | `0x3E89A0` |
| Korea | `00040000000FFC00` | `coop_bounce_fix/KOR/` | `0x2ECDAC` | `0x2EE614` | `0x3E8850` |

## Install
Replace `<TID>` with your region's title ID, and use the files from `both/<REGION>/` (or one of the
separate folders if you only want one fix).
- **Azahar / Citra:** `<user>/load/mods/<TID>/exefs/code.ips`
  (or right-click the game → *Open Mods Location*).
- **Real 3DS (Luma3DS):** `sd:/luma/titles/<TID>/code.ips`, then enable
  *"Enable game patching"* in the Luma config menu (hold SELECT on boot).
- **Cheat instead of IPS:** `cheat_gateway.txt` (Azahar cheat window, or `sd:/cheats/<TID>.txt`
  for Rosalina). Enable it before entering a level.

Rebuild with `python scripts/build_patches.py`. Pass `REGION code.bin` pairs (code from
`scripts/extract_3ds_code.py`) to also check every original word, e.g.
`python scripts/build_patches.py USA work/code.bin EUR work/EUR/code.bin`. The non-USA addresses
were found with `scripts/find_sites.py`, which matches instruction sequences from the USA build.
