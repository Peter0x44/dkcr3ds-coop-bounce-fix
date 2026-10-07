"""Build the DKCR 3D (USA, 00040000000CCE00) co-op enemy-bounce fix.

A bop kills an enemy with death type 1, which keeps the corpse solid and starts a 0.5 s corpse
timer (creature+0x30C). Two checks then throw away every collision with the dead enemy, so the
second player falls through:

  gate 1  Creature::vf9 (collision callback, 0x2ECD78) returns if the creature is dead
  gate 2  the behavior collision dispatcher (0x2EE638) only forwards to the active behavior,
          and a corpse has none

The fix hooks both and adds two routines in the zero padding at the end of .text
(text ends 0x3E887C, its page ends 0x3E9000). Assembly source: asm/cave1.s, asm/cave2.s.

usage: python scripts/build_patches.py [path/to/code.bin]
  With code.bin (the game's decompressed ExeFS .code, see scripts/extract_3ds_code.py), every
  original word is checked first, so the script refuses a different game version.
"""
import os, struct, sys

BASE = 0x100000
TID = "00040000000CCE00"
OUT = os.path.join(os.path.dirname(__file__), "..", "patch", "coop_bounce_fix")

def b(src, dst, cond=0xE):  # ARM B
    return (cond << 28) | 0x0A000000 | (((dst - (src + 8)) >> 2) & 0xFFFFFF)

def bl(src, dst):  # ARM BL
    return 0xEB000000 | (((dst - (src + 8)) >> 2) & 0xFFFFFF)

CAVE1 = 0x3E8880
CAVE2 = 0x3E88A0

# (address, original word, new word, comment)
PATCH = [
    # gate 1: Creature::vf9 alive check `ldrb r0, [r0, #0x2d]` (r0 = creature + 0x200)
    (0x2ECDDC, 0xE5D0002D, b(0x2ECDDC, CAVE1), "hook 1: b cave1"),
    # cave 1: r0 = alive || corpseTimer > 0   (r5 = creature)
    (CAVE1 + 0x00, 0, 0xE5D5022D, "ldrb    r0, [r5, #0x22d]   ; alive"),
    (CAVE1 + 0x04, 0, 0xE3500000, "cmp     r0, #0"),
    (CAVE1 + 0x08, 0, 0x1A000003, "bne     return"),
    (CAVE1 + 0x0C, 0, 0xED950AC3, "vldr    s0, [r5, #0x30c]   ; corpse timer"),
    (CAVE1 + 0x10, 0, 0xEEB50AC0, "vcmpe.f32 s0, #0"),
    (CAVE1 + 0x14, 0, 0xEEF1FA10, "vmrs    APSR_nzcv, fpscr"),
    (CAVE1 + 0x18, 0, 0xC3A00001, "movgt   r0, #1"),
    (CAVE1 + 0x1C, 0, b(CAVE1 + 0x1C, 0x2ECDE0), "return: b 0x2ECDE0"),

    # gate 2: dispatcher `ldrb r0, [r0, #0x3c]` (mPassCollisionEventsToAllBehaviors)
    (0x2EE644, 0xE5D0003C, b(0x2EE644, CAVE2), "hook 2: b cave2"),
    # cave 2: dead + timer running -> contact handler wrapper (creature, other, type, -1)
    #         (r4 = creature, r1 = other actor, r8 = contact type)
    (CAVE2 + 0x00, 0, 0xE5D4022D, "ldrb    r0, [r4, #0x22d]   ; alive"),
    (CAVE2 + 0x04, 0, 0xE3500000, "cmp     r0, #0"),
    (CAVE2 + 0x08, 0, 0x1A000008, "bne     original"),
    (CAVE2 + 0x0C, 0, 0xED940AC3, "vldr    s0, [r4, #0x30c]   ; corpse timer"),
    (CAVE2 + 0x10, 0, 0xEEB50AC0, "vcmpe.f32 s0, #0"),
    (CAVE2 + 0x14, 0, 0xEEF1FA10, "vmrs    APSR_nzcv, fpscr"),
    (CAVE2 + 0x18, 0, 0xDA000004, "ble     original"),
    (CAVE2 + 0x1C, 0, 0xE1A00004, "mov     r0, r4"),
    (CAVE2 + 0x20, 0, 0xE1A02008, "mov     r2, r8"),
    (CAVE2 + 0x24, 0, 0xE3E03000, "mvn     r3, #0"),
    (CAVE2 + 0x28, 0, bl(CAVE2 + 0x28, 0x22CCC4), "bl      0x22CCC4           ; contact handler wrapper"),
    (CAVE2 + 0x2C, 0, b(CAVE2 + 0x2C, 0x2EE724), "b       0x2EE724           ; dispatcher return"),
    (CAVE2 + 0x30, 0, 0xE5D4003C, "original: ldrb r0, [r4, #0x3c]  ; displaced instruction"),
    (CAVE2 + 0x34, 0, b(CAVE2 + 0x34, 0x2EE648), "b       0x2EE648"),
]

def ips(patch):
    out = bytearray(b"PATCH")
    for addr, _, new, _ in patch:  # record: 24-bit offset, 16-bit size, data
        out += struct.pack(">I", addr - BASE)[1:] + struct.pack(">H", 4) + struct.pack("<I", new)
    return bytes(out + b"EOF")

def cheat(patch):
    return "\n".join(["[Co-op enemy bounce fix]"] + [f"{a:08X} {n:08X}" for a, _, n, _ in patch]) + "\n"

if len(sys.argv) > 1:
    code = open(sys.argv[1], "rb").read()
    for addr, old, _, _ in PATCH:
        cur = struct.unpack_from("<I", code, addr - BASE)[0]
        assert cur == old, f"{addr:#x}: expected {old:#010x}, found {cur:#010x} (wrong game/version?)"
    print("original bytes verified")

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "code.ips"), "wb").write(ips(PATCH))
open(os.path.join(OUT, "cheat_gateway.txt"), "w", newline="\n").write(cheat(PATCH))
print(f"{len(PATCH)} words")
for addr, old, new, c in PATCH:
    print(f"  {addr:08X}: {old:08X} -> {new:08X}  {c}")
