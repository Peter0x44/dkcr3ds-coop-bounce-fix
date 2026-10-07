# Dump export symbols from the Wii selfile.sel (DOL symbols that RSO modules link against)
import struct
d = open("work/wii_data/DATA/files/RSO/wii_production/selfile.sel", "rb").read()
h = struct.unpack_from(">24I", d, 0)
exp_off, exp_size, exp_names = struct.unpack_from(">III", d, 0x40)
out = []
for i in range(exp_size // 16):
    no, val, sec, hsh = struct.unpack_from(">IIII", d, exp_off + i * 16)
    name = d[exp_names + no:d.index(b"\0", exp_names + no)].decode()
    out.append((val, sec, name))
out.sort()
with open("work/wii_sel_symbols.txt", "w") as f:
    for v, s, n in out: f.write(f"{v:08x} {s} {n}\n")
print(len(out))
