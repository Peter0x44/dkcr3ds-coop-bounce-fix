"""Build the DKCR 3D (USA, 00040000000CCE00) co-op enemy-bounce fix.

A bop kills an enemy with death type 1, which keeps the corpse solid and starts a 0.5 s corpse
timer (creature+0x30C). Two checks then throw away every collision with the dead enemy, so the
second player falls through:

  gate 1  Creature::vf9 (collision callback, 0x2ECD78) returns if the creature is dead
  gate 2  the behavior collision dispatcher (0x2EE638) only forwards to the active behavior,
          and a corpse has none

The fix hooks both and adds two routines in the zero padding at the end of .text
(text ends 0x3E887C, its page ends 0x3E9000). Assembly source: asm/cave1.s, asm/cave2.s.

usage: python scripts/build_patches.py [REGION code.bin ...]
  Writes patch/coop_bounce_fix/<REGION>/ for USA, EUR, JPN and KOR. For each REGION given with its
  code.bin (the game's decompressed ExeFS .code, see scripts/extract_3ds_code.py), every original
  word is checked first, so the script refuses a mismatched build.
"""
import os, struct, sys

BASE = 0x100000
OUT = os.path.join(os.path.dirname(__file__), "..", "patch", "coop_bounce_fix")

def b(src, dst, cond=0xE):  # ARM B
    return (cond << 28) | 0x0A000000 | (((dst - (src + 8)) >> 2) & 0xFFFFFF)

def bl(src, dst):  # ARM BL
    return 0xEB000000 | (((dst - (src + 8)) >> 2) & 0xFFFFFF)

# Per-region addresses. USA was found by hand; the others with scripts/find_sites.py
# (signature match against USA). Struct offsets (+0x22D alive, +0x30C corpse timer,
# +0x3C passAll) are identical in all four builds.
REGIONS = {
    #       title ID            hook1     hook2     disp_ret  wrapper   cave
    "USA": ("00040000000CCE00", 0x2ECDDC, 0x2EE644, 0x2EE724, 0x22CCC4, 0x3E8880),
    "EUR": ("00040000000CCF00", 0x2ECE18, 0x2EE680, 0x2EE760, 0x22CCC4, 0x3E88C0),
    "JPN": ("00040000000CC000", 0x2ECEE4, 0x2EE74C, 0x2EE82C, 0x22CD1C, 0x3E89A0),
    "KOR": ("00040000000FFC00", 0x2ECDAC, 0x2EE614, 0x2EE6F4, 0x22CCC4, 0x3E8850),
}

def build(hook1, hook2, disp_ret, wrapper, cave):
    """(address, original word, new word, comment) for one region."""
    c1, c2 = cave, cave + 0x20
    return [
        # gate 1: Creature::vf9 alive check `ldrb r0, [r0, #0x2d]` (r0 = creature + 0x200)
        (hook1, 0xE5D0002D, b(hook1, c1), "hook 1: b cave1"),
        # cave 1: r0 = alive || corpseTimer > 0   (r5 = creature)
        (c1 + 0x00, 0, 0xE5D5022D, "ldrb    r0, [r5, #0x22d]   ; alive"),
        (c1 + 0x04, 0, 0xE3500000, "cmp     r0, #0"),
        (c1 + 0x08, 0, 0x1A000003, "bne     return"),
        (c1 + 0x0C, 0, 0xED950AC3, "vldr    s0, [r5, #0x30c]   ; corpse timer"),
        (c1 + 0x10, 0, 0xEEB50AC0, "vcmpe.f32 s0, #0"),
        (c1 + 0x14, 0, 0xEEF1FA10, "vmrs    APSR_nzcv, fpscr"),
        (c1 + 0x18, 0, 0xC3A00001, "movgt   r0, #1"),
        (c1 + 0x1C, 0, b(c1 + 0x1C, hook1 + 4), "return: b hook1+4"),

        # gate 2: dispatcher `ldrb r0, [r0, #0x3c]` (mPassCollisionEventsToAllBehaviors)
        (hook2, 0xE5D0003C, b(hook2, c2), "hook 2: b cave2"),
        # cave 2: dead + timer running -> contact handler wrapper (creature, other, type, -1)
        #         (r4 = creature, r1 = other actor, r8 = contact type)
        (c2 + 0x00, 0, 0xE5D4022D, "ldrb    r0, [r4, #0x22d]   ; alive"),
        (c2 + 0x04, 0, 0xE3500000, "cmp     r0, #0"),
        (c2 + 0x08, 0, 0x1A000008, "bne     original"),
        (c2 + 0x0C, 0, 0xED940AC3, "vldr    s0, [r4, #0x30c]   ; corpse timer"),
        (c2 + 0x10, 0, 0xEEB50AC0, "vcmpe.f32 s0, #0"),
        (c2 + 0x14, 0, 0xEEF1FA10, "vmrs    APSR_nzcv, fpscr"),
        (c2 + 0x18, 0, 0xDA000004, "ble     original"),
        (c2 + 0x1C, 0, 0xE1A00004, "mov     r0, r4"),
        (c2 + 0x20, 0, 0xE1A02008, "mov     r2, r8"),
        (c2 + 0x24, 0, 0xE3E03000, "mvn     r3, #0"),
        (c2 + 0x28, 0, bl(c2 + 0x28, wrapper), "bl      wrapper            ; contact handler wrapper"),
        (c2 + 0x2C, 0, b(c2 + 0x2C, disp_ret), "b       disp_ret           ; dispatcher return"),
        (c2 + 0x30, 0, 0xE5D4003C, "original: ldrb r0, [r4, #0x3c]  ; displaced instruction"),
        (c2 + 0x34, 0, b(c2 + 0x34, hook2 + 4), "b       hook2+4"),
    ]

def ips(patch):
    out = bytearray(b"PATCH")
    for addr, _, new, _ in patch:  # record: 24-bit offset, 16-bit size, data
        out += struct.pack(">I", addr - BASE)[1:] + struct.pack(">H", 4) + struct.pack("<I", new)
    return bytes(out + b"EOF")

def cheat(patch):
    return "\n".join(["[Co-op enemy bounce fix]"] + [f"{a:08X} {n:08X}" for a, _, n, _ in patch]) + "\n"

# usage: build_patches.py [REGION code.bin ...]  -> verifies original words for those regions
checks = dict(zip(sys.argv[1::2], sys.argv[2::2]))
for region, (tid, *sites) in REGIONS.items():
    patch = build(*sites)
    if region in checks:
        code = open(checks[region], "rb").read()
        for addr, old, _, _ in patch:
            cur = struct.unpack_from("<I", code, addr - BASE)[0]
            assert cur == old, f"{region} {addr:#x}: expected {old:#010x}, found {cur:#010x}"
        print(f"{region}: original bytes verified")
    out = os.path.join(OUT, region)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "code.ips"), "wb").write(ips(patch))
    open(os.path.join(out, "cheat_gateway.txt"), "w", newline="\n").write(cheat(patch))
    print(f"{region} ({tid}): {len(patch)} words -> {out}")
