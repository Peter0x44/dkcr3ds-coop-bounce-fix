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
- **Real hardware:** tested on two 3DS consoles, a patched USA copy and a patched European copy
  playing co-op together. Works.
- **Emulator:** bounce fix tested in co-op in Azahar. (Azahar doesn't filter local sessions by
  region, so it can't test the region fix; that was tested on real hardware.)
- **Korea:** the same patches at that version's addresses, checked automatically but not play-tested.

## Download

**Recommended: the combined patch ("Both")**, which includes both fixes. Pick your version by
title ID and download `code.ips` (or `cheat_gateway.txt` for the cheat version):

| Region | Title ID | **Both (recommended)** | Bounce fix only | Region-free only |
|---|---|---|---|---|
| USA | `00040000000CCE00` | **[patch/both/USA](patch/both/USA/)** | [USA](patch/coop_bounce_fix/USA/) | [USA](patch/region_free_multiplayer/USA/) |
| Europe | `00040000000CCF00` | **[patch/both/EUR](patch/both/EUR/)** | [EUR](patch/coop_bounce_fix/EUR/) | [EUR](patch/region_free_multiplayer/EUR/) |
| Japan | `00040000000CC000` | **[patch/both/JPN](patch/both/JPN/)** | [JPN](patch/coop_bounce_fix/JPN/) | [JPN](patch/region_free_multiplayer/JPN/) |
| Korea | `00040000000FFC00` | **[patch/both/KOR](patch/both/KOR/)** | [KOR](patch/coop_bounce_fix/KOR/) | [KOR](patch/region_free_multiplayer/KOR/) |

**Which one?**
- **Both** is what almost everyone wants. There's no downside to having both fixes.
- The **separate patches** are kept for anyone who wants to examine or apply one fix on its own.
  Luma loads only one `code.ips` per game, so you can't install two of these together; use
  **Both** for that.
- **Playing together:** everyone uses **Both**, whatever their region.
- **Private network ID:** **Both** uses its own local-multiplayer ID that no retail copy uses, so
  patched copies only ever find other patched copies. A patched and an unpatched copy can't
  accidentally join each other and desync.

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
