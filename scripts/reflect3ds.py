# Walk a range of 3DS code and print "field name -> store offset (base reg), default" for value-file readers.
import struct, sys, capstone
c = open("work/code.bin", "rb").read()
B = 0x100000
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM); md.detail = True
def cstr(a):
    o = a - B; e = c.index(b"\0", o); return c[o:e].decode(errors="replace")
def arm_imm(w):
    rot = ((w >> 8) & 0xf) * 2; imm = w & 0xff
    return ((imm >> rot) | (imm << (32 - rot))) & 0xffffffff
s, e = int(sys.argv[1], 16), int(sys.argv[2], 16)
name = None; dflt = None
for i in md.disasm(c[s - B:e - B], s):
    w = struct.unpack_from("<I", c, i.address - B)[0]
    if (w & 0x0fff0000) == 0x028f0000 and ((w >> 12) & 0xf) == 1:
        t = (i.address + 8 + arm_imm(w)) & 0xffffffff
        try: name = cstr(t)
        except Exception: name = hex(t)
        continue
    if i.mnemonic == "mov" and i.op_str.startswith("r2, #"): dflt = i.op_str[4:]
    if i.mnemonic == "vldr" and i.op_str.startswith("s0, [pc"):
        a = i.address + 8 + int(i.op_str.split("#")[1].rstrip("]"), 16)
        dflt = "%gf" % struct.unpack_from("<f", c, a - B)[0]
    if name and i.mnemonic in ("str", "strb", "vstr", "strh"):
        print(f"{i.address:x}  {name:45s} -> {i.mnemonic} {i.op_str:22s} default={dflt}")
        name = None; dflt = None
