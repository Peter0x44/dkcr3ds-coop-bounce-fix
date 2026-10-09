"""Build the DKCR 3D co-op enemy-bounce fix and the region-free local multiplayer patch.

Co-op enemy-bounce fix

A bop kills an enemy with death type 1, which keeps the corpse solid and starts a 0.5 s corpse
timer (creature+0x30C). Two checks then throw away every collision with the dead enemy, so the
second player falls through:

  gate 1  Creature::vf9 (collision callback, 0x2ECD78) returns if the creature is dead
  gate 2  the behavior collision dispatcher (0x2EE638) only forwards to the active behavior,
          and a corpse has none

The fix hooks both and adds two routines in the zero padding at the end of .text
(text ends 0x3E887C, its page ends 0x3E9000). Assembly source: asm/cave1.s, asm/cave2.s.

Region-free local multiplayer
Local play only finds sessions with the same local communication ID, which the game builds from
its region's unique ID (USA 0xCCE, EUR 0xCCF, JPN 0xCC0, KOR 0xFFC) in one small helper, called
only when scanning for and creating sessions. The patch makes that helper always build USA's ID,
so every patched copy (and any unpatched USA copy) can see the others.

usage: python scripts/build_patches.py [REGION code.bin ...]
  Writes patch/<patch>/<REGION>/ for USA, EUR, JPN and KOR, for three patches: coop_bounce_fix,
  region_free_multiplayer, and both (Luma loads only one code.ips per game). For each REGION given with its
  code.bin (the game's decompressed ExeFS .code, see scripts/extract_3ds_code.py), every original
  word is checked first, so the script refuses a mismatched build.
"""
import os, struct, sys

BASE = 0x100000
OUT = os.path.join(os.path.dirname(__file__), "..", "patch")

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

# nn::uds MakeLocalCommunicationId-style helper (identical code in all four builds):
#   ldr r2,[pc,#0x20] / bic r0,r0,#0xF00000 / ldrb r3,[r2,#0x14] / mov r2,#0x10 / tst r3,#1 /
#   moveq r2,#0x90 / cmp r1,#0 / orrne r2,r2,#1 / orr r0,r2,r0,lsl #8 / bx lr
COMM_ID_HELPER = {"USA": 0x1201D4, "EUR": 0x1201F4, "JPN": 0x1201FC, "KOR": 0x120218}

def build_region_free(helper):
    """Always return USA's local communication ID (unique ID 0xCCE), keeping the flag bits."""
    return [
        (helper + 0x04, 0xE3C0060F, 0xE3A00D33, "mov r0, #0xcc0      ; was bic r0,r0,#0xf00000 (ignore caller's ID)"),
        (helper + 0x18, 0xE3510000, 0xE3822C0E, "orr r2, r2, #0xe00  ; was cmp r1,#0 (0xcc0|0xe = 0xcce after <<8)"),
        (helper + 0x1C, 0x13822001, 0xE1822001, "orr r2, r2, r1      ; was orrne r2,r2,#1 (r1 is 0 or 1)"),
    ]

# Private ID for the combined patch: unique ID 0xDC001, used by no retail version, so copies with
# the bounce fix only ever find each other (a patched and an unpatched copy desync and disconnect).
# The last digit is the patch's network version: bump it if a future change alters game logic.
PRIVATE_UNIQUE_ID = 0xDC001

def build_private_id(helper):
    """Always return the private local communication ID (unique ID 0xDC001), keeping the flag bits."""
    return [
        (helper + 0x04, 0xE3C0060F, 0xE3A00937, "mov r0, #0xdc000    ; was bic r0,r0,#0xf00000 (ignore caller's ID)"),
        (helper + 0x18, 0xE3510000, 0xE3822C01, "orr r2, r2, #0x100  ; was cmp r1,#0 (0xdc000|0x1 = 0xdc001 after <<8)"),
        (helper + 0x1C, 0x13822001, 0xE1822001, "orr r2, r2, r1      ; was orrne r2,r2,#1 (r1 is 0 or 1)"),
    ]

def ips(patch):
    out = bytearray(b"PATCH")
    for addr, _, new, _ in patch:  # record: 24-bit offset, 16-bit size, data
        out += struct.pack(">I", addr - BASE)[1:] + struct.pack(">H", 4) + struct.pack("<I", new)
    return bytes(out + b"EOF")

TITLES = {"coop_bounce_fix": "Co-op enemy bounce fix",
          "region_free_multiplayer": "Region-free local multiplayer",
          "both": "Co-op enemy bounce fix + region-free local multiplayer"}

def cheat(patch, name):
    return "\n".join([f"[{TITLES[name]}]"] + [f"{a:08X} {n:08X}" for a, _, n, _ in patch]) + "\n"

# usage: build_patches.py [REGION code.bin ...]  -> verifies original words for those regions
checks = dict(zip(sys.argv[1::2], sys.argv[2::2]))
for region, (tid, *sites) in REGIONS.items():
    patches = {
        "coop_bounce_fix": build(*sites),
        "region_free_multiplayer": build_region_free(COMM_ID_HELPER[region]),
    }
    patches["both"] = patches["coop_bounce_fix"] + build_private_id(COMM_ID_HELPER[region])
    if region in checks:
        code = open(checks[region], "rb").read()
        for addr, old, _, _ in patches["both"]:
            cur = struct.unpack_from("<I", code, addr - BASE)[0]
            assert cur == old, f"{region} {addr:#x}: expected {old:#010x}, found {cur:#010x}"
        print(f"{region}: original bytes verified")
    for name, patch in patches.items():
        out = os.path.join(OUT, name, region)
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, "code.ips"), "wb").write(ips(patch))
        open(os.path.join(out, "cheat_gateway.txt"), "w", newline="\n").write(cheat(patch, name))
        print(f"{region} ({tid}) {name}: {len(patch)} words")
