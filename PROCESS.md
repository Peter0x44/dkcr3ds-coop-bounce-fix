# How the DKCR 3D co-op bounce fix was made

A step-by-step record of how we went from "two players can't bounce off the same enemy" to a
tested 24-word code patch for **Donkey Kong Country Returns 3D (USA, 00040000000CCE00)**,
in one session on 2026-10-06/07. It covers everything: the tools, the reverse engineering,
the wrong first guess, the two-player test rig, the live debugging, and the final patch.

**Result:** after P1 bops an enemy, P2 can bounce off it for the next 0.5 s, like on the Wii.
Tested in co-op in two emulator instances. The patch is `patch/coop_bounce_fix/USA/code.ips` (or the
24-line cheat next to it), with versions for Europe, Japan and Korea alongside (section 10).

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

### 3.1 Strategy

The plan was to **diff behaviour, not bytes**. The Wii and 3DS builds are compiled for different
CPUs (PowerPC vs ARM), so their machine code can't be compared directly. But the 3DS port is
based on Retro's code, so the same *logic* should appear in both. The idea was to find the
code that runs when an enemy is bopped in each version, line the two up, and look for the
difference. Most of the work went into finding landmarks: functions I could recognise in both
binaries.

### 3.2 First probes: strings and a magic number

**Strings.** The quickest way into an unknown binary is its text. The 3DS code has about 8,800
strings, and searching them for `bop`, `bounce`, `death` and `collision` found a lot:
- class names like `BopJumpBehavior` and `StunnedByBopBehavior`
- enemy rule names like `tank_boppable` and `spider_drop_dead_on_bop`
- data field names like `mDisableCollisionOnDeath`, `mIgnoreAllDuringDeath` and
  `mContactRuleDelay`

The `m…` field names exist because the game reads enemy settings from data files *by name*.
That's very useful for reverse engineering, because each name sits next to the code that reads
it.

The Wii build has fewer useful strings, mostly state-machine names (`IsDead`, `Dead_AI`,
`IsHittingCreatureOnAttackBounce`), because Retro's data uses hashed IDs instead of names.

**The 25-frame number.** The community said the Wii window is about 25 frames, which is
25/60 = 0.41667 s. If that were a hard-coded constant, the float `0x3ED55555` would appear
somewhere. It appeared **exactly once** in the Wii build, in the small-constants area.

On PowerPC, those constants aren't addressed directly. The code reads them as an offset from
register `r2`, which is set once at startup. So I read the startup code to get `r2 = 0x80627C20`,
computed the offset (`-0x4684`), and searched every instruction for a load from `r2-0x4684`.
There was one, at `0x8038578C`, in the **controller input code**: a key-repeat delay.

**Dead end.** That told me the window wasn't a single named constant, so I needed to understand
the logic instead.

### 3.3 The Wii build had real function names

While extracting the Wii disc I noticed a folder of `.rso` files, which are Wii dynamic modules.
They link against the main program **by name**, and the list of names they use is in
`selfile.sel`, with each function's address. Parsing it gave 938 real C++ names, including the
exact one I wanted: `CGenericCreature::IssueDeath`, the Wii's "an enemy has died" function.

The first decompile of it was broken (`halt_baddata`). The Wii's CPU has extra "paired-single"
float instructions that standard PowerPC doesn't, and Ghidra stopped at the first one. Installing
the GameCube/Wii loader extension added those instructions, and re-importing fixed the
decompiles.

### 3.4 The 3DS build had its class names

The 3DS build has no symbol file, but C++ programs that use `dynamic_cast` keep **RTTI** (run-time
type information). For each class with virtual functions there's a chain:

1. a name string, e.g. `N36_GLOBAL__N__12_creature_cpp_11fbdbcb8CreatureE`
2. a **typeinfo** record that points to that string
3. a **vtable** (the class's list of virtual functions) that points to the typeinfo

`scripts/rtti3ds.py` walks that chain backwards: for each name string, it finds the words that
point to it, then the words that point to *those*. That recovered 868 classes and their vtables.
Ghidra then named every virtual function, e.g. `creature::Creature_vf9` (Creature's 10th virtual).

The names also leak **source file names**, because classes in an unnamed C++ namespace get the
file name mangled in: `creature.cpp`, `b_damaged.cpp`, `b_stunned_bop.cpp`, `rules.cpp`. The
`rules.cpp` file had **84 classes**, one per enemy kind (`normal_creatureRules`,
`boppapotamusRules`, `electro_bro_unboppableRules`…). Code shaped like that is usually
generated from data, which turned out to be right.

### 3.5 Decoding the contact rules

Each rules class has one real method. It takes a small description of a contact and returns two
32-bit results: what happens to the creature, and what happens to the other actor (the player).

The simplest class, `kill_rule`, always returns `(0x100, 0x10000)`. A guess from the name:
`0x100` means "kill the creature" and `0x10000` means "the player bounces". Both guesses held up
later.

`normal_creatureRules` is a decision tree on bytes of the description. Two 4-letter codes show up
in it, `'KILL'` and `'HBPB'`, compared against a field of the description. That gave a way in.

### 3.6 Finding the contact handler

Ghidra had **no cross-references** to the rules method. It's only called through a vtable, so no
instruction names its address. Instead, I searched for the `'KILL'` / `'HBPB'` constants **outside**
the rules classes.

ARM code stores constants in **literal pools**, small data blocks next to the code that loads
them with `ldr rX, [pc, #offset]`. `scripts/litref.py` finds every such load of a given address.
It found five users, and one of them was the **contact handler** (`0x254958`). Decompiled, it does
this:

1. **Debounce:** ignore the other actor if it already touched this creature recently. Each entry
   lasts `mContactRuleDelay`, 0.1 s by default.
2. **Describe the contact** (`0x37E5E0`): who the other actor is, which **zone** it touched, and
   whether this creature is dead. The dead flag is byte `0x12` of the description, set when
   creature byte `+0x22D` is 0, so `+0x22D` is the creature's "alive" flag.
3. **Ask the rules,** then send the player's result to the player and the creature's result to
   the creature's behaviors.

**The zone.** At first I misread it. I assumed zone 0 was a side touch, which made the rules look
like they'd *hurt* a player who touched a corpse. Reading the zone function's geometry (`0x37E0D8`)
showed zone 0 means "the other actor's bottom is above this creature's top", i.e. **from above**.
With that corrected, the dead-creature branch of the rules says:

> dead + touched from above → creature `0x2002`, player `0x12004` (which includes `0x10000`, the bounce)

**Key realisation.** The rules already allow bouncing off a dead enemy. So the bug isn't in the
rules; something stops the contact from ever reaching them.

### 3.7 A false lead: `mIgnoreAllDuringDeath`

That field name looked like the answer. Its default is `true`, and the name says "ignore
everything while dying".

Field-name strings are tricky to trace on ARM. The code reaches them with a **PC-relative add**
(`add r1, pc, #imm`), not a stored pointer, so a plain pointer search finds nothing and Ghidra
missed the references too. A small scanner for those `add` instructions found the reader. Then
`scripts/reflect3ds.py` listed every field that function reads, with the offset each is stored at.

The neighbouring fields were `mSuicideOnPlayerTouch`, `mTargetingTime` and `mAttackRangeSquared`.
That's the settings block of the **Seeker** (a homing enemy), not generic creatures. A good-looking
name on the wrong struct. The lesson: always check what struct a field belongs to.

(Ghidra also sometimes split ARM functions in the wrong place, so a "function" started mid-way
through a real one. Reading raw disassembly with capstone around a suspicious address helped
there.)

### 3.8 Lining up the Wii and 3DS death code

To find the Wii's equivalent of the contact description, I searched the Wii decompile for callers
of the named function `CGenericCreatureRules::CalculateContactZone`. That led to `0x8004FA20`,
which also sets a "dead" byte: alive flag cleared, or a death type set. Same idea as the 3DS.

The Wii evaluates its rules from **data** at runtime (`0x800D3FC0`). It then converts the result
bits with two lookup functions (`0x8004DC50`, `0x8004DD40`) into the **same** output flags the
3DS uses: `0x100`, `0x10000`, `0x2000`… That confirmed the 3DS's 84 rules classes are a compiled
form of Retro's rules data. **The rules aren't the difference.**

Next, does the Wii delay death after a bop, leaving the enemy alive for 25 frames? The Wii damage
function (`0x80042FF0`) calls `IssueDeath` **immediately** when health reaches 0, the same as the
3DS's `CDamagedBehavior`. So that's not the difference either.

Then the death functions themselves. I matched the 3DS one (`0x250E60`) to Wii `IssueDeath` by
details that are unlikely by chance:
- the death type stored in the creature (3DS `+0x192`, Wii `+0xDFC`)
- the same `0x200` flag and the same "type 6 or 7 = thrown" test
- the same 4-letter messages sent (`'RATL'`, `'DBNH'`)

### 3.9 The collision filter and the corpse timer

In the 3DS death function, when an enemy goes from alive to dead, it does
`actor[+0xF0] |= 0x100000`. To work out what that word is:
- A collision query elsewhere builds its filter by combining `+0xE0`, `+0xE8` and `+0xF0`, so
  these are the actor's **material list** (`+0xE0`) and **include/exclude filters** (`+0xE8`,
  `+0xF0`).
- The player's own death code removes bit `0x100000` from the player's material list, so that bit
  is the **"character" material**, which players and enemies share.

So the corpse adds "characters" to the things it ignores. I didn't see that line in the Wii's
`IssueDeath`, and it looked like the bug. (It was a misreading: the Wii does the same thing one
call deeper, in `CPatterned::Death`. Section 11 covers how that came out.)

There was a wrinkle. Right after that line, death types 1 and 3 *clear the bit again* and write
0.5 to `+0x30C`. At first I took `+0x30C` for the hit-flash blink timer, because the player update
counts it down and toggles visibility. Then the creature's own update (`0x3C57F4`) turned out to
count it down and, at zero, set the exclusion bit. So for creatures it's a **corpse timer**:
"stay solid for 0.5 s, then stop colliding".

The Wii has the same mechanism. Its timer is at `+0xD38`, counted down in `0x80033AD0`, and at
zero `0x80033B10` excludes the same `0x100000` bit. The Wii arms it at `0x80035C5C`, for types 1
and 3 only, with the constant 0.5 (read via `r2-0x7C80`). The branch structure is identical to the
3DS.

---

## 4. The first patch (wrong)

From that comparison I concluded the exclusion was a 3DS-only addition and the cause of the bug,
and built a patch to remove it. There were two variants: one copied the Wii exactly, and one also forced every death type
onto the 0.5 s timer. You asked why there were two.

**It didn't work.** You couldn't see any difference in-game.

**What I'd missed.** I never checked *which death type a bop uses*. The debugger later showed a
bop is type 1, the case where the original game already clears the bit and starts the timer. So
on the bop path, the corpse was never losing its collision. And, as it turned out later, the Wii
adds the same exclusion too (section 11), so the line wasn't a porting difference at all.

**The lesson.** Reading code shows every road; it doesn't show which road the game actually
takes. That's what moved the work from reading code to watching the running game.

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

### How the hooks were designed

**Where to put new code.** The code segment's last instruction is at `0x3E8878`, but the memory
page it lives in runs to `0x3E9000`, and the loader maps whole pages as executable. That leaves
about 1.9 KB of zeroes that are loaded, executable, and never used. I checked the bytes were all
zero in `code.bin` before using them.

**Hook 1 (gate 1).** The original instruction at `0x2ECDDC` is `ldrb r0, [r0, #0x2d]`. Here `r0` is
`creature + 0x200`, so this loads the alive byte at `+0x22D`, and the next instruction tests it.
The hook replaces just that load with a jump. The routine has to leave `r0` non-zero for "carry
on" and zero for "ignore", then jump back to the very next instruction (`0x2ECDE0`), so the rest
of the function runs unchanged. At that point `r5` still holds the creature pointer, so the
routine uses `r5` to read both the alive byte and the timer.

**Comparing the float timer.** The timer is a float, so the routine uses the VFP (floating-point)
unit: `vldr` loads it, `vcmpe.f32 s0, #0` compares it with zero, and `vmrs` copies the result into
the normal condition flags so `movgt` can act on it. Using `s0` is safe: it's a scratch register
under the ARM calling convention, and the function had just made a call that could have
overwritten it anyway, so nothing could still be relying on it.

**Hook 2 (gate 2).** At the start of the dispatcher (`0x2EE644`), the registers hold exactly what's
needed: `r4` = creature, `r1` = the other actor, `r8` = the contact type. The instruction it
replaces (`ldrb r0, [r0, #0x3c]`) is re-run at the end of the routine's "normal" path, so live
creatures behave exactly as before. For a dead creature inside its window, the routine calls the
same contact-handler wrapper (`0x22CCC4`) that each behavior's collision method calls, with the
same arguments (`type`, `-1`). It then jumps to the dispatcher's existing return code (`0x2EE724`),
which restores the stack and registers properly.

**Why routine 2 also checks the timer.** Gate 1 already guarantees that only in-window corpses
reach the dispatcher *from the collision callback*. But the dispatcher has a second caller I hadn't
traced (`0x232468`, used for grabbed and thrown objects). Checking the timer again keeps that path
exactly as it was.

**Branch encoding.** ARM's `b` and `bl` store a 24-bit word offset relative to the instruction's
address + 8. The build script computes each one from the real addresses, so moving a routine
wouldn't require recalculating anything by hand.

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
| `patch/coop_bounce_fix/<REGION>/code.ips` | **The patch** (IPS, for Azahar/Citra or Luma3DS), per region |
| `patch/coop_bounce_fix/<REGION>/cheat_gateway.txt` | Same patch as a 24-line cheat |
| `patch/region_free_multiplayer/<REGION>/`, `patch/both/<REGION>/` | Region-free local multiplayer patch (section 12), and both patches combined |
| `scripts/find_sites.py` | Finds the patch sites in another build by signature |
| `patch/README.md` | Install instructions |
| `scripts/build_patches.py` | Builds the patch; `python scripts/build_patches.py work/code.bin` also verifies the original bytes |
| `asm/cave1.s`, `asm/cave2.s` | Source of the two routines |
| `scripts/kb2pads.py` | Keyboard → two virtual Xbox controllers |
| `scripts/launch_coop.ps1` | Starts room server, bridge, both emulators; tiles windows |
| `scripts/uia_connect.ps1` | Joins both emulators to the room |
| `scripts/rsp_trace.py` | Debugger client for live tracing (`--resume-only` releases a paused game) |
| `scripts/rsp_trace_wii.py` | Same for the Wii version in Dolphin (`GDBPort` + `DebugModeEnabled`; `--persistent` keeps breakpoints armed) |
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

## 10. Other regions: Europe, Japan, Korea

After the USA patch worked, you added the European, Japanese and Korean releases. All three dumps
were already decrypted. Each has its own title ID and a slightly different code size, so the USA
patch can't simply be reused:

| Region | Title ID | Code size | vs USA |
|---|---|---|---|
| USA | `00040000000CCE00` | `0x2E887C` | reference |
| Europe | `00040000000CCF00` | `0x2E88BC` | +0x40 |
| Japan | `00040000000CC000` | `0x2E899C` | +0x120 |
| Korea | `00040000000FFC00` | `0x2E884C` | -0x30 |

Instead of repeating the reverse engineering, `scripts/find_sites.py` finds each patch site by
**signature**. It takes a window of 6–24 instructions around each USA site and searches the other
build for the same sequence. Words that encode a relative distance (`b`/`bl` targets, PC-relative
loads and adds) are masked out, because those change whenever code shifts.

A match is trusted only if:
- **each signature matches exactly once** in the build,
- the **distances between related sites** are the same as in USA (hook 1 → hook 2 = `0x1868`;
  hook 2 → dispatcher return = `0xE0`),
- the matched windows contain the **same struct offsets** the routines rely on (`+0x22D`, `+0x30C`,
  `+0x3C`), so the creature layout is unchanged.

All three regions passed. Japan's code is shifted the most (an extra `0x108` before the hooks), and
its contact-handler wrapper moved too (`0x22CD1C` instead of `0x22CCC4`). Each build also has zero
padding after its code for the routines.

`scripts/build_patches.py` now holds a table of the five addresses per region and builds all four
patches from the same routines. With each region's `code.bin`, it checks every original word
first. A final check applied each patch to its region's code and disassembled it: every hook jumps
into its routine and back to the next instruction, and in each build the routine's call reaches
the same contact handler.

The USA patch is byte-identical to the one tested in co-op. The other three haven't been played
yet; testing them is the same two-window setup with a different `.cci` (and the patch in that
title ID's mods folder).

## 11. What the port actually broke

**In one sentence:** on the Wii, a dead enemy still passes player collisions to the bounce rules;
the 3DS port lost the line of code that does that.

### What happens on the Wii

Traced live in Dolphin, replaying a co-op save state where DK bops an enemy and Diddy lands on it
right after:

1. **DK lands on the enemy.** The enemy dies immediately (death type 1) and is marked "not
   active". Its corpse stays solid for 0.5 s (the corpse timer).
2. **Diddy lands on the corpse.** That's a physics collision, handled by the enemy's
   `CollidedWith` function (`0x80034A10`), which has two branches:
   - **enemy alive:** pass the collision to the enemy's modules (its AI and behaviour logic);
   - **enemy dead:** if the other object is a `CPatterned`, pass it **straight to the contact
     handler** (`0x8003C830`).

   Players count as `CPatterned` in DKCR (the player class derives from it), so Diddy's landing goes
   to the contact handler.
3. **The contact handler asks the rules,** which say "dead enemy, touched from above → bounce the
   player". Diddy bounces.

The trace shows exactly this: the bop kills the enemy, then a player object collides with the dead
enemy, and the contact handler is called from inside that dead-enemy branch.

### What's different on the 3DS

The 3DS has the same pieces: the immediate type-1 death, the 0.5 s corpse timer, the contact handler
and the same rules. But its version of `CollidedWith` (`0x232468`) ends like this:

```c
if (creature->alive)
    DispatchToBehaviors(...);
// dead: nothing
```

The dead-enemy branch is gone. Nothing else on the 3DS passes a corpse's collisions to the rules
either, so player 2's landing is simply ignored and they fall through.

| | Wii | 3DS (original) |
|---|---|---|
| Bop kills the enemy | Immediately, type 1 | Immediately, type 1 |
| Corpse stays solid | 0.5 s | 0.5 s |
| Dead enemy + player collision | Sent to the contact handler | **Ignored** |
| Rules for "dead + from above" | Bounce | Bounce (never reached) |

### Wii modules vs 3DS behaviours

Both versions are C++, but they organise enemy logic differently. Retro's Wii engine drives much of
it from **data loaded from the game files**; Monster Games' 3DS port turns much of that into
**compiled C++ classes**. The bug sits right at the seam between the two designs.

**On the Wii, an enemy is a stack of modules.** Each enemy (`CGenericCreature`) carries a list of
*modules* (`CGameCharacterModule`), each handling one aspect: movement, damage, a finite-state
machine (`CFiniteStateMachineModule`) whose states (`Dead_AI`, `DeathDelete`…) come from an asset
file, and so on. When the enemy collides with something, the module dispatcher (`0x8003B540`) calls
each module's collision method in turn, up to the current one. A dead enemy skips the modules and
goes straight to the contact handler instead.

**On the 3DS, an enemy has behaviours.** Each enemy (`creature::Creature`) has a list of
*behaviours*, each a C++ class in its own source file: `b_damaged.cpp`, `b_stunned_bop.cpp`,
`b_bopjump.cpp`, `b_grabbed.cpp` and so on. One behaviour is *active* at a time. The dispatcher
(`0x2EE638`) passes a collision to the behaviours only while there is an active one, and a corpse
has none.

**Contact rules, data vs code.** Both versions decide what a contact does (kill, damage, bounce)
with the same rules, but store them differently:
- **Wii:** the rules are data, walked by a small interpreter (`0x800D3FC0`). Its output bits are
  translated into the engine's flags (`0x8004DC50`, `0x8004DD40`).
- **3DS:** the same rules are compiled into 84 C++ classes in `rules.cpp`, one per enemy kind
  (`normal_creatureRules`, `kill_rule`, `boppapotamusRules`…). Each is a small decision function
  that returns the same flags directly, e.g. `0x10000` = bounce the player.

This is probably for speed: interpreting data at runtime costs time, and the 3DS CPU is far weaker
than the Wii's.

**Enemy settings.** The 3DS reads enemy settings by *name* (`mDeathType`, `mContactRuleDelay`…);
the Wii uses hashed IDs. The names made the 3DS much easier to read.

| | Wii (Retro) | 3DS (Monster Games port) |
|---|---|---|
| Enemy logic units | Modules, incl. data-driven state machines | Behaviour classes (`b_*.cpp`) |
| Collision dispatch | All modules up to the current one | Only while a behaviour is active |
| Dead enemy + player | Contact handler, directly | Dropped (the bug) |
| Contact rules | Data, interpreted at runtime | Compiled into 84 C++ classes |
| Enemy settings | Hashed IDs | Field names |
| Player contact arrives via | `CollidedWith` (physics) | `Touch` |

### Why it was probably lost

The 3DS port replaced Retro's *modules* with its own *behaviours* and rewrote the code that hands
collisions to them. The "alive" branch hands collisions to modules/behaviours, so it was carried
over. The "dead" branch doesn't involve them at all, which makes it easy to drop in a rewrite. (This
is an inference from the code, not something the binary can prove.)

It's invisible in single player: after a bop you bounce away and never touch the corpse again. Only a
second player landing within half a second needs that branch.

### How the patch relates

The patch does what the missing branch did: it sends a dead enemy's collision with a player to the
contact handler while the 0.5 s corpse timer is running.

It can't simply re-add the Wii's branch to the 3DS `CollidedWith`, because on the 3DS a player's
landing never arrives there. A trace of the 3DS during a co-op double bounce showed the corpse's
`CollidedWith` running only for collisions with the level itself (floor, walls), never with a
player. Player-vs-enemy contact on the 3DS comes through the `Touch` path instead. So the port also
moved player contact from the physics path (Wii) to the touch path (3DS).

That's why the patch hooks the two places a player's landing actually reaches on the 3DS: the
`Touch` check (`Creature::vf9`, which skipped dead enemies) and the behaviour dispatcher (which needs
an active behaviour). From there it uses the same contact handler, the same rules and the same 0.5 s
window as the Wii.

## 12. Region-free local multiplayer

**The problem you hit:** you and a friend with a European copy couldn't see each other in local
co-op. There was no error; the other session just never appeared. With two European copies it
worked.

**How 3DS local play finds sessions:** the system's local wireless service ("UDS") only shows
sessions advertised with the same **local communication ID** as the one the game searches for.
Games usually build that ID from their title's unique ID, and each region of DKCR 3D has a
different one:

| Region | Title ID | Unique ID |
|---|---|---|
| USA | `00040000000CCE00` | `0xCCE` |
| Europe | `00040000000CCF00` | `0xCCF` |
| Japan | `00040000000CC000` | `0xCC0` |
| Korea | `00040000000FFC00` | `0xFFC` |

**Finding it:** searching the USA code for the constant `0xCCE` found it in two literal pools. The
code loading them is the game's two UDS calls, both named in its error-logging strings:

```c
// searching for sessions (nn::uds::CTR::Scan)
id = MakeCommId(0xCCE, 0);         // FUN_001201d4
Scan(buffer, 0x2000, 1, id);

// hosting a session (nn::uds::CTR::CreateNetwork)
id = MakeCommId(0xCCE, 0);
CreateNetwork(1, maxPlayers, id, ...);
```

The helper (`0x1201D4` in USA) returns `(uniqueId << 8) | flags`. The European build has `0xCCF` at
the same spots, and Japan builds `0xCC0` directly in a `mov` instruction. Korea computes `0xFFC` from
another constant (`0x10B4 - 0xB8`).

**Checking for other region locks:** before patching, the rest of the network code was checked
for anything else region-specific:
- the beacon data each session advertises starts with the same magic, `'rwnu'`, in every
  version, and that's what the scan-result handler checks;
- the extra value the host and join calls pass comes from the network object's runtime state, not
  from a region constant.

The communication ID was the only difference.

**The patch:** the helper is called only from those two places, and its code is identical in all
four versions. So instead of patching each region's ID constant (which can't be done in one
instruction for Japan, since `0xCCE` doesn't fit an ARM immediate), the helper itself is changed
to always build USA's ID:

```
mov r0, #0xcc0          ; was: bic r0, r0, #0xf00000    (ignore the caller's ID)
...
orr r2, r2, #0xe00      ; was: cmp r1, #0               (0xcc0 | 0xe = 0xcce, after the << 8)
orr r2, r2, r1          ; was: orrne r2, r2, #1          (same flag; r1 is 0 or 1)
```

For every combination of the flag bits, the result equals what an unpatched USA copy produces.
So patched copies of any region and **unpatched USA copies** all use the same ID. (They can find
each other; whether they can then play together depends on running the same game logic, see
"Real-hardware results" below.)

**Tested:** on real hardware (see "Real-hardware results" below): patched USA and European copies
find each other and play together.

Azahar can't test this patch. Its scan handler (`RecvBeaconBroadcastData` in `nwm_uds.cpp`) reads
the requested communication ID but only logs it, and returns every session it has received. So in
Azahar any two copies see each other, patched or not; mixed-region sessions there say nothing about
the fix. Japan and Korea use the same three instructions at their own helper addresses and weren't
tested on hardware.

The build script produces it as `patch/region_free_multiplayer/` and, combined with the bounce fix,
as `patch/both/`. Luma loads only one `code.ips` per game, hence the combined version.

### Real-hardware results

Later tested on two real 3DS consoles:

- **Patched USA + patched European copy:** co-op works.
- **Mismatched patch, as an experiment:** a USA copy patched to use Europe's network ID (plus the
  bounce fix) joined an **unpatched** European copy. The session was found, but the game
  immediately reported the connection as lost.

So the session-finding part works across regions, but the consoles must also run identical game
logic. Co-op keeps them in lockstep, and the bounce fix changes what happens when a corpse is
touched, so a patched and an unpatched copy diverge and the game detects it. **Every player needs
the same patch.**

### A private network ID for the combined patch

After that result, the combined patch (`both/`) was switched to a **private** communication ID that
no retail version uses, unique ID `0xDC001`. Patched copies then only find other patched copies, and
an unpatched copy can never be joined by accident. The last digit is a network version, to bump if
a future patch changes game logic again.

It's the same three instructions in the ID helper with different values (`mov r0, #0xdc000` and
`orr r2, r2, #0x100`), checked to give `0xDC001` for every flag combination.
`region_free_multiplayer/` keeps the USA ID, since it doesn't change game logic.

Testing it in Azahar showed a patched and an unpatched copy finding each other. That led to the
discovery that Azahar ignores the ID completely (see the "Tested" note above), so the emulator can't
show the effect. On real hardware, the ID decides which sessions are visible, as the original
region lock shows.

## 13. Still open
- Play-test the Europe, Japan and Korea bounce patches, and the region fix with Japanese and Korean
  copies on real hardware.
- Try a late-game or K level that needs chained bounces.
- The Switch version's 1.1.0 update fixed the same bug; comparing its window length would be a
  nice cross-check.
