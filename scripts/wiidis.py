import struct, sys, capstone
d = open("work/main.dol", "rb").read()
o = struct.unpack_from(">18I", d, 0); a = struct.unpack_from(">18I", d, 0x48); s = struct.unpack_from(">18I", d, 0x90)
def read(addr, n):
    for i in range(18):
        if s[i] and a[i] <= addr < a[i] + s[i]: return d[o[i] + addr - a[i]: o[i] + addr - a[i] + n]
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
addr = int(sys.argv[1], 16); n = int(sys.argv[2])
code = read(addr, n * 4)
for i in range(n):
    w = code[i*4:i*4+4]
    ins = list(md.disasm(w, addr + i*4))
    print(f"{addr+i*4:08x}  {w.hex()}  " + (f"{ins[0].mnemonic} {ins[0].op_str}" if ins else ".word"))
