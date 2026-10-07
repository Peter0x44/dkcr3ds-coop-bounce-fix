# find ARM 'ldr rX, [pc, #imm]' instructions that load from the given literal-pool addresses
import struct, sys
c = open("work/code.bin", "rb").read(); B = 0x100000
tg = {int(a, 16) for a in sys.argv[1:]}
for off in range(0, 0x2e9000, 4):
    w = struct.unpack_from("<I", c, off)[0]
    if (w & 0x0f7f0000) == 0x051f0000:  # LDR Rt,[PC,#+/-imm12]
        imm = w & 0xfff; a = B + off + 8 + (imm if w & (1 << 23) else -imm)
        if a in tg: print(f"{B+off:x} loads {a:x} -> r{(w>>12)&15}")
    if (w & 0x0f3f0f00) == 0x0d1f0a00:  # VLDR s,[PC,#imm]
        imm = (w & 0xff) * 4; a = B + off + 8 + (imm if w & (1 << 23) else -imm)
        if a in tg: print(f"{B+off:x} vldr {a:x}")
