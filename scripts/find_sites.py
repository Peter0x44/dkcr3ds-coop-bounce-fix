"""Locate the co-op bounce fix's patch sites in another build of DKCR 3D by signature.

usage: python scripts/find_sites.py <usa code.bin> <other code.bin> <other exheader.bin>

Signatures are instruction windows taken from the USA build around each site. Words that encode
relative offsets (B/BL targets, PC-relative loads/adds) are masked, since they change whenever
code moves. Each window must match exactly once.
"""
import struct, sys

BASE = 0x100000

# USA addresses (see scripts/build_patches.py)
USA = {
    "hook1": 0x2ECDDC,       # Creature::vf9 alive check
    "hook2": 0x2EE644,       # behavior dispatcher: ldrb r0,[r0,#0x3c]
    "disp_ret": 0x2EE724,    # dispatcher epilogue
    "wrapper": 0x22CCC4,     # contact-handler wrapper
    "timer_tick": 0x3C57F4,  # creature update: vldr s0,[r5,#0x30c] (corpse timer)
}
# (window start relative to site, window length in words)
WINDOWS = {
    "hook1": (-0x2C, 24),
    "hook2": (-0x0C, 16),
    "disp_ret": (-0x08, 6),
    "wrapper": (0, 12),
    "timer_tick": (-0x08, 14),
}

def words(buf):
    return struct.unpack(f"<{len(buf) // 4}I", buf[: len(buf) // 4 * 4])

def mask(w):
    if (w >> 25) & 7 == 0b101:              # B / BL: keep cond+opcode, drop offset
        return w & 0xFF000000, 0xFF000000
    if (w & 0x0F7F0000) == 0x051F0000:      # LDR rX, [pc, #imm]
        return w & 0xFFFFF000, 0xFFFFF000
    if (w & 0x0FFF0000) == 0x028F0000:      # ADD rX, pc, #imm
        return w & 0xFFFFF000, 0xFFFFF000
    if (w & 0x0F3F0F00) == 0x0D1F0A00:      # VLDR sX, [pc, #imm]
        return w & 0xFFFFFF00, 0xFFFFFF00
    return w, 0xFFFFFFFF

def find(usa, other, site):
    off, n = WINDOWS[site]
    start = USA[site] + off - BASE
    sig = [mask(w) for w in words(usa[start:start + 4 * n])]
    ow = words(other)
    hits = []
    first_val, first_m = sig[0]
    for i in range(len(ow) - n):
        if ow[i] & first_m != first_val:
            continue
        if all(ow[i + k] & m == v for k, (v, m) in enumerate(sig)):
            hits.append(BASE + 4 * i - off)
    return hits

def main():
    usa = open(sys.argv[1], "rb").read()
    other = open(sys.argv[2], "rb").read()
    exh = open(sys.argv[3], "rb").read()
    text_addr, _, text_size = struct.unpack_from("<III", exh, 0x10)
    text_end = text_addr + text_size
    page_end = (text_end + 0xFFF) & ~0xFFF
    cave = (text_end + 0xF) & ~0xF
    pad = other[text_end - BASE:page_end - BASE]
    print(f"text ends {text_end:#x}, page ends {page_end:#x}, cave at {cave:#x}, "
          f"padding all zero: {not any(pad)} ({page_end - cave} bytes free, need 0x58)")
    print(f"identical to USA: {usa == other}")
    out = {"cave": cave}
    for site in USA:
        hits = find(usa, other, site)
        print(f"{site:10s} USA {USA[site]:#x} -> {[hex(h) for h in hits]}")
        if len(hits) == 1:
            out[site] = hits[0]
    return out

if __name__ == "__main__":
    main()
