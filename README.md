# DKC Returns 3D: co-op enemy bounce fix

A 24-word code patch for **Donkey Kong Country Returns 3D (USA, title ID 00040000000CCE00)**
that lets both players bounce off the same enemy, like in the Wii original.

Without it, when player 1 jumps on an enemy, player 2 falls straight through it. The Switch
remaster had the same bug, inherited from the 3DS code, until update 1.1.0; the 3DS was never fixed.

**Status:** tested in co-op in Azahar. Not yet tested on real hardware.

## Download
- [`patch/coop_bounce_fix/code.ips`](patch/coop_bounce_fix/code.ips): IPS patch for Azahar/Citra or Luma3DS
- [`patch/coop_bounce_fix/cheat_gateway.txt`](patch/coop_bounce_fix/cheat_gateway.txt): the same patch as a 24-line cheat

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
| `scripts/build_patches.py` | Builds the patch |
| `scripts/` | Extraction, analysis, test-rig and debugging tools used along the way |
| `scripts/ghidra/` | Headless Ghidra scripts |

No game files are included. To use the analysis scripts you need your own dump of the game.
