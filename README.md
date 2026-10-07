# DKC Returns 3D: co-op enemy bounce fix

A 24-word code patch for **Donkey Kong Country Returns 3D** that lets both players bounce off the
same enemy, like in the Wii original. Available for all four retail releases (USA, Europe, Japan,
Korea).

Without it, when player 1 jumps on an enemy, player 2 falls straight through it. The Switch
remaster had the same bug, inherited from the 3DS code, until update 1.1.0; the 3DS was never fixed.

**Status:** the USA patch is tested in co-op in Azahar. The other regions' patches are the same
code at each build's addresses, found and verified automatically, but not yet played. None have
been tested on real hardware.

## Download
Each folder has `code.ips` (IPS patch for Azahar/Citra or Luma3DS) and `cheat_gateway.txt` (the same
patch as a 24-line cheat). Pick the one matching your game's title ID:

| Region | Title ID | Patch |
|---|---|---|
| USA | `00040000000CCE00` | [`patch/coop_bounce_fix/USA/`](patch/coop_bounce_fix/USA/) |
| Europe | `00040000000CCF00` | [`patch/coop_bounce_fix/EUR/`](patch/coop_bounce_fix/EUR/) |
| Japan | `00040000000CC000` | [`patch/coop_bounce_fix/JPN/`](patch/coop_bounce_fix/JPN/) |
| Korea | `00040000000FFC00` | [`patch/coop_bounce_fix/KOR/`](patch/coop_bounce_fix/KOR/) |

Install instructions and a short technical summary: [`patch/README.md`](patch/README.md).

## How it was made
[`PROCESS.md`](PROCESS.md) is the full story: decompiling the Wii and 3DS versions, a first patch
that didn't work, a two-player test setup on one PC (two emulators, a private multiplayer room,
one keyboard split into two virtual controllers), and live debugging of the running game that
found the two checks responsible.

## Repository
| Path | Contents |
|---|---|
| `patch/` | The patch (IPS + cheat) and install notes |
| `asm/` | Assembly source of the two routines the patch adds |
| `scripts/build_patches.py` | Builds the patches for all four regions |
| `scripts/find_sites.py` | Finds the patch sites in another build by signature |
| `scripts/` | Extraction, analysis, test-rig and debugging tools used along the way |
| `scripts/ghidra/` | Headless Ghidra scripts |

No game files are included. To use the analysis scripts you need your own dump of the game.

## License
Public domain ([Unlicense](LICENSE)).
