# How the DKCR 3D co-op bounce fix was made

A step-by-step record of how we went from "two players can't bounce off the same enemy" to a
tested 24-word code patch for **Donkey Kong Country Returns 3D (USA, 00040000000CCE00)**,
in one session on 2026-10-06/07. It covers everything: the tools, the reverse engineering,
the wrong first guess, the two-player test rig, the live debugging, and the final patch.

**Result:** after P1 bops an enemy, P2 can bounce off it for the next 0.5 s, like on the Wii.
Tested in co-op in two emulator instances. The patch is `patch/coop_bounce_fix/code.ips` (or the
24-line cheat next to it).

---

## 0. The starting point

- **The bug:** in DKCR 3D (and the Switch HD remaster, which was built from the 3DS code), if
  player 1 jumps on an enemy, player 2 falls straight through it. On the Wii, both can bounce
  for about 25 frames. Nintendo fixed it on Switch in update 1.1.0; the 3DS was never patched.
- **What you provided:** your own copies of both games, as 7-Zip archives:
  - Wii: `Donkey Kong Country Returns (USA) (En,Fr,Es) (Rev 1)` → a 3.6 GB `.rvz` disc image
  - 3DS: `Donkey Kong Country Returns 3D (USA) (En,Fr,Es)` → a 4 GB `.cci` cartridge image
- **What you asked:** what's the best approach, how does the 3DS community handle it, and can
  we measure the Wii window and port it to the 3DS.

A web search found no existing 3DS cheat or mod, so we had to build one.

---

## 1. Setting up the tools (all portable, all in `tools/`)

None of the emulators were installed, and you asked for a portable setup:

| Tool | Version | How it was made portable / why |
|---|---|---|
| Dolphin (Wii/GameCube emulator) | 2609 | Official 7z build + an empty `portable.txt` next to `Dolphin.exe`. Used for `DolphinTool.exe`, to extract files from the Wii disc. |
| Azahar (3DS emulator, Citra's successor) | 2126.1.2 | Official zip + a `user/` folder next to `azahar.exe`, which makes it keep its config there. |
| Ghidra (NSA's disassembler/decompiler) | 12.1.4 | Official zip. |
| Eclipse Temurin JDK | 21 | Ghidra needs Java; nothing was installed system-wide. |
| Ghidra GameCube/Wii loader (Cuyler36) | for Ghidra 12.1 | Adds the Wii CPU's ("Gekko/Broadway") extra instructions. Its version string had to be edited from `12.1` to `12.1.4` to load. |

Already on your machine and reused: 7-Zip, portable Python 3.12 (with `capstone` for quick
disassembly), the `llvm-mingw` toolchain (its `clang` became the ARM assembler later), a Windows
build of `gdb`, and the **ViGEmBus** virtual-controller driver (from Nefarius).

---

## 2. Getting the code out of both games

### Wii
1. Extracted the `.rvz` from the 7z archive.
2. `DolphinTool extract -p DATA` dumped the disc's data partition. The game code is
   `sys/main.dol` (5.9 MB of PowerPC code).
3. Bonus find: `files/RSO/wii_production/selfile.sel`. Retro Studios' loadable modules link
   against the main program by name, so this file lists **938 real function names with
   addresses**, e.g. `IssueDeath__16CGenericCreature…`. `scripts/parse_sel.py` turned that into a
   symbol list.
4. `scripts/dol2elf.py` wrapped the DOL in an ELF file for Ghidra's first pass (splitting the
   memory area that overlaps other sections). It was later re-imported with the GameCube/Wii
   loader, which reads the DOL directly.

### 3DS
1. Checked the cartridge header: the **NoCrypto flag was set**, so the dump was already
   decrypted. No console keys were needed (that could have been a dead end).
2. `scripts/extract_3ds_code.py` parsed the cartridge format (NCSD → NCCH → ExeFS) and pulled out
   `.code` → `work/code.bin` (3.4 MB of ARM11 code), plus the "extended header" that says where
   each section loads in memory (code at `0x100000`).
3. `scripts/code2elf.py` wrapped it in an ARM ELF so Ghidra loads it at the right addresses.
4. `scripts/romfs_list.py` listed the game data (level files, streams, video) to see whether
   enemy behaviour was data we could edit instead of code. It wasn't practical, so code it was.
   (The first version of this script had a header-offset bug and ate 29 GB of RAM before I
   killed it.)

---

## 3. Reverse engineering in Ghidra

Ghidra ran **headless** (no GUI) through a small wrapper, `scripts/gh.sh`, plus custom Java
scripts in `scripts/ghidra/`:

| Script | What it does |
|---|---|
| `Decomp.java` | Decompile the function at an address to C-like code |
| `DecompMatching.java` | Decompile every function whose name matches a pattern into one text file |
| `Xrefs.java` | List everything that references an address |
| `Disasm.java` | Print a disassembly listing |
| `FuncOf.java` | Which function contains this address? |
| `ApplySyms.java` | Name functions from a symbol file (used for the Wii `.sel` names) |
| `ApplyVtables.java` | Label C++ vtables and name every virtual function (used for the 3DS) |

Steps:
1. **Both binaries analysed** (the first 3DS + Wii pass ran in parallel, several minutes each).
2. **Wii symbols applied:** 893 functions got their real names from `selfile.sel`.
3. **3DS class names recovered:** the 3DS build still contains C++ type information.
   `scripts/rtti3ds.py` followed each class name to its vtable and found **868 classes**, then
   named about 7,700 virtual functions like `creature::Creature_vf9`. This showed the 3DS port
   (by Monster Games) reuses Retro's engine and class names (`CPlayerModuleGrab`,
   `KONGPlayer`…), so the Wii and 3DS code could be compared side by side.
4. **Everything decompiled to text:** 14,837 3DS functions (19 MB) and 17,311 Wii functions
   (25 MB) went into `work/3ds_all.c` and `work/wii_all.c`, so they could be searched with
   ordinary text tools instead of one Ghidra query at a time.
5. Helpers for the details: `scripts/reflect3ds.py` (reads the game's field-name tables to map
   names like `mDisableCollisionOnDeath` to struct offsets), `scripts/litref.py` (finds code that
   loads a given constant), `scripts/wiidis.py` (quick PowerPC disassembly).

### What the reading found
- The 3DS **creature death function** (`0x250E60`) is a direct port of the Wii's
  `CGenericCreature::IssueDeath`: same death types, same 4-letter messages (`RATL`, `DBNH`), same
  "death type 6/7 = thrown" check.
- The **contact system**: when something touches a creature, the game builds a small
  description (who touched it, from which side, whether the creature is dead), asks the
  creature's **contact rules** what happens, and sends the result to each side. On the 3DS
  these rules are compiled into classes like `normal_creatureRules`. Result flag `0x10000`
  means "bounce the player".
- The rules say **"dead enemy touched from above → bounce the player"**. So the game's own
  logic allows the bounce; something earlier must be stopping it.
- Both versions have a **0.5 s corpse timer** (Wii `+0xD38`, 3DS `+0x30C`) that keeps a corpse
  solid and then turns its collision off.

---

## 4. The first patch (wrong)

The death code adds a "don't collide with characters" bit to the corpse's collision filter, and
the Wii's version doesn't. That looked like the whole bug. I built two variants, published them
in a doc, and asked why there were two (one copied the Wii exactly, one forced the 0.5 s timer).

**It didn't work.** You couldn't see any difference in-game. (The debugger later showed why: a
bop is death type 1, and the original game already clears that bit and starts the 0.5 s timer
for type 1. The bit was never the problem for bops.) That's why the next step was testing on the
running game instead of reading more code.

### How patches are built and delivered
`scripts/build_patches.py` builds everything from a list of (address, original word, new word):
- It **checks every original word** before patching, so it refuses a different game version.
- It writes an **IPS patch** (`code.ips`). Azahar applies it automatically from
  `user/load/mods/00040000000CCE00/exefs/`; Luma3DS on a real 3DS applies it from
  `sd:/luma/titles/00040000000CCE00/`.
- It writes the same change as a **Gateway cheat** (`address value` lines), for Azahar's cheat
  window or Rosalina.
- The Azahar log line `ApplyCodePatch … code.ips patching code.bin` confirms each time it loaded.

---

## 5. The two-player test rig

3DS co-op needs **two consoles**, each with the game, talking over local wireless. To test on one
PC we built a two-console setup:

### 5.1 Two separate emulated 3DSes
- Azahar was copied into `tools/azahar/p1` and `tools/azahar/p2`, each with **its own** `user/`
  folder: separate config, save data, system files and a separate **MAC address**
  (`78:A2:A0:…` vs `48:A5:E7:…`), so the game sees two different consoles.
- Both have the patch in their mods folder and the game folder (`work/`) in their game list.
- "Pause when in background" is off, so the window you're not looking at keeps running.

### 5.2 A private multiplayer room
- Azahar emulates 3DS local wireless through **rooms**. Azahar ships a dedicated room server,
  `azahar-room.exe`, which runs locally as "DKCR-test" on UDP port 24872.
- Both configs were pre-filled with IP `127.0.0.1` and port 24872, plus nicknames.
- Side discovery: running `azahar.exe --help` pops up a **message box** instead of printing,
  because it's a GUI program. It also showed there's no command-line option to auto-join a room.

### 5.3 One keyboard, two controllers
The first try bound the keyboard directly in each Azahar window. Problem: Windows only sends key
presses to the **focused** window, so you could only control one player at a time, and switching
windows is far too slow for a 0.5 s bounce window.

The fix, `scripts/kb2pads.py`:
1. Uses the **ViGEmBus** driver (through the `vgamepad` Python package) to create **two virtual
   Xbox 360 controllers**. To Windows and games they look like real controllers plugged in.
2. Reads the keyboard **globally** (`GetAsyncKeyState`, polled every 2 ms), so it doesn't
   matter which window is focused.
3. Sends the left half of the keyboard to controller 1 and the right half to controller 2.

Then each Azahar instance was bound to "its" controller. To get the exact controller ID
Azahar expects, `pysdl2` listed the controllers the same way Azahar's SDL input sees them: GUID
`0300b9695e0400008e02000000007200`, at port 0 and port 1. Those went straight into each config
file (P1 → port 0, P2 → port 1). All keyboard bindings were **removed** from Azahar, so a stray key
in the focused window can't press HOME or Power.

The key layout changed a few times based on your feedback:
- **Back:** you couldn't leave the "waiting" screen because B wasn't on any key; added R / P.
- **W/I and the circle pad:** they also tilted the virtual circle pad up, which felt wrong, so
  that was removed.
- **W/I as jump:** I misread "can you now make I/W jump" as "not". The final layout puts jump on
  W / I.

Final layout:

| | Jump (A) | Left / Down / Right | Up | Roll (Y) | Back (B) | Start |
|---|---|---|---|---|---|---|
| P1 (left window) | W | A / S / D | E | Q | R | Tab |
| P2 (right window) | I | J / K / L | O | U | P | Enter |

### 5.4 Launching and connecting automatically
- `scripts/launch_coop.ps1` starts the room server and the controller bridge if they aren't
  running, starts both emulators with the game, and **tiles** the windows (P1 left half, P2
  right half) with the Windows `MoveWindow` API.
- `scripts/uia_connect.ps1` joins both windows to the room using **Windows UI Automation**,
  which can read and press buttons in other programs' windows:
  1. Brings the Azahar window to the front and checks it really is in front before doing
     anything (a quick Alt tap lets a background script do that).
  2. Clicks **Multiplayer**, then **Direct Connect to Room**. UI Automation's "invoke" didn't
     open Qt's menu, so it uses a real mouse click at the menu's on-screen position.
  3. Presses **Connect**, then reads each status bar to confirm "Connected".
- **Problem 1:** the room server had quietly died when I force-closed the emulators, so both
  games sat on "Waiting for Diddy/Donkey Kong" with "Not Connected" in the status bar. Restarted it.
- **Problem 2:** P1 was rejected: "Username is already in use". The nickname comes from the
  emulated 3DS's **system username**, and both consoles were called "AZAHAR". I renamed P1's
  console by editing its system config save file (block `0x000A0000`), first to "DK" (rejected:
  names must be 4–20 characters), then to **"DonkeyKong"**.

### 5.5 Two mistakes worth recording
- To check the controls, I first sent simulated **Tab/Enter key presses** and took screenshots.
  The emulator windows were behind your other windows, so the keys went to whatever you had
  focused. I stopped and never injected keys blindly again; later automation always confirms the
  target window is in front first.
- The screenshots showed your other apps (the Claude window, Chrome), not the game, for the same
  reason. Screen-copy only captures what's actually visible.

---

## 6. Live debugging the running game

With the test rig running, we watched the game's code while you played.

### 6.1 Attaching a debugger
- Azahar has a built-in **GDB stub**: `azahar.exe -g 24689` lets a debugger connect over TCP.
- First check: read the patched instructions back from the running game's memory. They were
  correct, so the patch was loading; the problem was my understanding.
- First attempt used **gdb** with "log and continue" breakpoints. It **froze the game** when you
  bopped an enemy: in batch mode gdb doesn't run a breakpoint's "continue" commands, and Azahar's
  stub can't resume from an address that has a breakpoint on it.
- Fix: my own small client for the GDB remote protocol, `scripts/rsp_trace.py`. Each
  breakpoint is **one-shot**: on a hit it logs registers and memory, removes itself, and resumes.
  Every 0.25 s it briefly pauses the game to put fired breakpoints back. That's what made P1
  slow ("unplayable") in one round; later rounds traced fewer points.
- Another lesson: Azahar's stub **leaves the game paused** when a debugger detaches. The
  release has to send "continue" and then drop the connection.

### 6.2 What the traces showed

**Round 1** (single player, first patch):
```
DEATHFN creature=091551c0 type=1 ...
  deathfn -> timer path
TIMER EXPIRED creature=091551c0
```
A bop is **death type 1**, which already takes the corpse-timer path. So the first patch changed
nothing, and the corpse was never losing its collision. The contact into a live enemy came in
through `0x22CCC4`, which led to the creature's collision callback `Creature::vf9`:

```c
if (creature->alive == 0 || other == creature->ignoreActor) return;   // dead → ignore everything
```
**Gate 1.** A dead enemy ignores every collision, even during its 0.5 s corpse window.

**Round 2** (gate 1 patched):
```
VF9 dead creature=091551c0 corpseTimer=0.467 allowed=1
DISPATCH dead creature=091551c0 passAll=0 activeBehavior=00000000
...
TIMER EXPIRED creature=091551c0
VF9 dead creature=091551c0 corpseTimer=-0.033 allowed=0
```
Collisions now got through for exactly the 0.5 s window, but the next function (the behavior
dispatcher, `0x2EE638`) only passes a collision to the creature's **active behavior**, and a
corpse has none. **Gate 2.**

**Round 3** (both gates patched):
```
DEATHFN creature=09158cc0 type=1
CAVE2 corpse contact -> handler creature=09158cc0 other=091c4de0 type=1
RULES on dead: otherType=0 zone=0 -> creature=0x2002 player=0x12004
```
The contact reached the rules. "Zone 0" means from above, and the player result `0x12004`
includes `0x10000`, the bounce. Then you tested in co-op: **both players bounced.**

---

## 7. The final patch

Both fixes need more instructions than the original code has room for, so they live in a
**code cave**: the zero padding at the end of the code segment (`0x3E887C`–`0x3E9000`). It's
inside the executable memory page but unused. Each gate gets a one-instruction jump into its
routine, which does the extra check and jumps back. The routines were written in ARM assembly
(`asm/cave1.s`, `asm/cave2.s`) and assembled with `clang` from `llvm-mingw`. The build script
contains the resulting instructions, annotated, and fills in the jump offsets.

| Part | Where | What it does |
|---|---|---|
| Hook 1 | `0x2ECDDC` | Replaces the alive check in `Creature::vf9` with a jump to routine 1 |
| Routine 1 | `0x3E8880` (8 instructions) | "Alive, **or** corpse timer (`+0x30C`) > 0" → jump back |
| Hook 2 | `0x2EE644` | Jumps from the behavior dispatcher to routine 2 |
| Routine 2 | `0x3E88A0` (14 instructions) | If dead and timer running: call the contact handler (`0x22CCC4`) directly, as a behavior would, and return. Otherwise run the replaced instruction and jump back. |

That's **24 words** in total. The first build also carried the 6 edits from the first attempt.
You asked whether the patch was the bare minimum; it wasn't, so I cut those out and you retested:
it still works.

Why 0.5 s and not "25 frames": the window is the game's own corpse timer, the same 0.5 s value the
Wii uses. It counts **seconds** (it subtracts each frame's real duration), so it's the same length
at 60 fps, 30 fps, or during slowdown. The community's "25 frames" was a measurement at 60 fps.

---

## 8. Files

| Path | What |
|---|---|
| `patch/coop_bounce_fix/code.ips` | **The patch** (IPS, for Azahar/Citra or Luma3DS) |
| `patch/coop_bounce_fix/cheat_gateway.txt` | Same patch as a 24-line cheat |
| `patch/README.md` | Install instructions |
| `scripts/build_patches.py` | Builds the patch; `python scripts/build_patches.py work/code.bin` also verifies the original bytes |
| `asm/cave1.s`, `asm/cave2.s` | Source of the two routines |
| `scripts/kb2pads.py` | Keyboard → two virtual Xbox controllers |
| `scripts/launch_coop.ps1` | Starts room server, bridge, both emulators; tiles windows |
| `scripts/uia_connect.ps1` | Joins both emulators to the room |
| `scripts/rsp_trace.py` | Debugger client for live tracing (`--resume-only` releases a paused game) |
| `scripts/gh.sh`, `scripts/ghidra/*.java` | Headless Ghidra wrapper and analysis scripts |
| `scripts/extract_3ds_code.py`, `dol2elf.py`, `code2elf.py`, `parse_sel.py`, `rtti3ds.py`, … | Extraction and analysis helpers |

Not in the repository (local only, because they're game data, derived from it, or large
downloads): `work/` (the ROMs, extracted code, the whole-program decompiles `3ds_all.c` /
`wii_all.c`), `ghidra_proj/` (Ghidra projects), and `tools/` (portable Dolphin, Azahar p1/p2,
Ghidra, JDK). The analysis helpers expect their inputs in `work/`; extract them with
`scripts/extract_3ds_code.py` and DolphinTool as described in section 2.

## 9. Running the co-op setup again

```bash
powershell -ExecutionPolicy Bypass -File scripts/launch_coop.ps1
```

```bash
powershell -ExecutionPolicy Bypass -File scripts/uia_connect.ps1
```

Then start co-op in the left window as DK and join from the right window as Diddy.

## 10. Still open
- Test on a real 3DS with Luma3DS.
- Try a late-game or K level that needs chained bounces.
- The Switch version's 1.1.0 update fixed the same bug; comparing its window length would be a
  nice cross-check.
