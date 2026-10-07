# Wrap the 3DS ExeFS .code (text/ro/data, flat) + bss into an ARM ELF for Ghidra.
import struct
exh = open("work/exheader.bin", "rb").read()
code = open("work/code.bin", "rb").read()
segs = []
for off, flags in ((0x10, 5), (0x20, 4), (0x30, 6)):
    addr, pages, size = struct.unpack_from("<III", exh, off)
    segs.append((addr, size, flags))
bss = struct.unpack_from("<I", exh, 0x3C)[0]
base = segs[0][0]
phnum = len(segs) + 1
cur = 52 + 32 * phnum
ph = bytearray(); body = bytearray()
for addr, size, flags in segs:
    data = code[addr - base:addr - base + size]
    ph += struct.pack("<8I", 1, cur, addr, addr, len(data), len(data), flags, 4)
    body += data; cur += len(data)
d_addr, d_size, _ = segs[2]
bss_addr = (d_addr + d_size + 3) & ~3
ph += struct.pack("<8I", 1, cur, bss_addr, bss_addr, 0, bss, 6, 4)
eh = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8) + struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, base, 52, 0, 0x5000000, 52, 32, phnum, 40, 0, 0)
open("work/code_3ds.elf", "wb").write(eh + ph + body)
print("ok", [hex(s[0]) for s in segs], hex(bss_addr), hex(bss))
