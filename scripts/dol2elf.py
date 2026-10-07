# Minimal DOL -> ELF32 (PPC big-endian) converter so Ghidra can load the Wii executable.
import struct, sys
src, dst = sys.argv[1], sys.argv[2]
d = open(src, "rb").read()
offs = struct.unpack_from(">18I", d, 0)
addrs = struct.unpack_from(">18I", d, 0x48)
sizes = struct.unpack_from(">18I", d, 0x90)
bss_addr, bss_size, entry = struct.unpack_from(">III", d, 0xD8)
segs = [(i < 7, addrs[i], d[offs[i]:offs[i] + sizes[i]]) for i in range(18) if sizes[i]]
# BSS overlaps .sdata/.sdata2 in Retro DOLs; split it around loaded segments
bss_ranges = [(bss_addr, bss_addr + bss_size)]
for _, addr, data in segs:
    nxt = []
    for a, b in bss_ranges:
        e = addr + len(data)
        if e <= a or addr >= b: nxt.append((a, b)); continue
        if a < addr: nxt.append((a, addr))
        if e < b: nxt.append((e, b))
    bss_ranges = nxt
phnum = len(segs) + len(bss_ranges)
hdr_size = 52 + 32 * phnum
body = bytearray(); phdrs = bytearray(); cur = hdr_size
for is_text, addr, data in segs:
    phdrs += struct.pack(">8I", 1, cur, addr, addr, len(data), len(data), 5 if is_text else 6, 32)
    body += data; cur += len(data)
for a, b in bss_ranges:
    phdrs += struct.pack(">8I", 1, cur, a, a, 0, b - a, 6, 32)
ehdr = b"\x7fELF" + bytes([1, 2, 1, 0]) + bytes(8) + struct.pack(">HHIIIIIHHHHHH", 2, 20, 1, entry, 52, 0, 0, 52, 32, phnum, 40, 0, 0)
open(dst, "wb").write(ehdr + phdrs + body)
for is_text, addr, data in segs: print("text" if is_text else "data", hex(addr), hex(len(data)))
print("bss", [(hex(a), hex(b)) for a, b in bss_ranges], "entry", hex(entry))
