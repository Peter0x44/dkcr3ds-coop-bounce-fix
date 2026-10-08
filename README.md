# DKC Returns 3D: co-op fixes

Two small code patches for **Donkey Kong Country Returns 3D**, for all four retail releases
(USA, Europe, Japan, Korea):

- **Co-op enemy bounce fix** (24 words): both players can bounce off the same enemy, like in the
  Wii original. Without it, when player 1 jumps on an enemy, player 2 falls straight through it.
  The Switch remaster had the same bug, inherited from the 3DS code, until update 1.1.0; the 3DS
  was never fixed.
- **Region-free local multiplayer** (3 words): consoles with different regions of the game can
  find each other in local co-op. Without it, a session from another region simply never shows up.

**Status:**
- **Bounce fix:** tested in co-op in Azahar with the USA version.
- **Region-free patch:** tested in Azahar with a USA copy and a patched European copy playing together.
- **Other regions:** the remaining versions use the same code at each build's addresses, found and
  verified automatically, but not yet played.
- **Real hardware:** nothing tested yet.

## Download
Each folder has `code.ips` (IPS patch for Azahar/Citra or Luma3DS) and `cheat_gateway.txt` (the same
patch as a cheat). Luma loads only one `code.ips` per game, so use **both** if you want both fixes.

| Region | Title ID | Bounce fix | Region-free | Both |
|---|---|---|---|---|
| USA | `00040000000CCE00` | [USA](patch/coop_bounce_fix/USA/) | [USA](patch/region_free_multiplayer/USA/) | [USA](patch/both/USA/) |
| Europe | `00040000000CCF00` | [EUR](patch/coop_bounce_fix/EUR/) | [EUR](patch/region_free_multiplayer/EUR/) | [EUR](patch/both/EUR/) |
| Japan | `00040000000CC000` | [JPN](patch/coop_bounce_fix/JPN/) | [JPN](patch/region_free_multiplayer/JPN/) | [JPN](patch/both/JPN/) |
| Korea | `00040000000FFC00` | [KOR](patch/coop_bounce_fix/KOR/) | [KOR](patch/region_free_multiplayer/KOR/) | [KOR](patch/both/KOR/) |

The region-free patch makes every copy use the USA version's network ID, so unpatched USA copies
can already join; only non-USA copies need it.

Install instructions and a short technical summary: [`patch/README.md`](patch/README.md).

## How it was made
[`PROCESS.md`](PROCESS.md) is the full story: decompiling the Wii and 3DS versions, a first patch
that didn't work, a two-player test setup on one PC (two emulators, a private multiplayer room,
one keyboard split into two virtual controllers), and live debugging of the running game that
found the two checks responsible.

## Repository
| Path | Contents |
|---|---|
| `patch/` | The patches (IPS + cheat) and install notes |
| `asm/` | Assembly source of the two routines the patch adds |
| `scripts/build_patches.py` | Builds both patches (and the combined one) for all four regions |
| `scripts/find_sites.py` | Finds the patch sites in another build by signature |
| `scripts/` | Extraction, analysis, test-rig and debugging tools used along the way |
| `scripts/ghidra/` | Headless Ghidra scripts |

No game files are included. To use the analysis scripts you need your own dump of the game.

## License
Public domain ([Unlicense](LICENSE)).
