# List (and optionally extract) files from a decrypted CCI's RomFS.  usage: romfs_list.py <game.cci> [extract_regex]
import struct, sys, re, os
CCI = sys.argv.pop(1)
f = open(CCI, "rb")
ncsd = f.read(0x200)
p0 = struct.unpack_from("<I", ncsd, 0x120)[0] * 0x200
f.seek(p0); ncch = f.read(0x200)
romfs = p0 + struct.unpack_from("<I", ncch, 0x1B0)[0] * 0x200
f.seek(romfs); ivfc = f.read(0x60)
assert ivfc[:4] == b"IVFC"
master_size = struct.unpack_from("<I", ivfc, 0x08)[0]
lv3_bs = 1 << struct.unpack_from("<I", ivfc, 0x4C)[0]
lv3 = romfs + ((0x60 + master_size + lv3_bs - 1) // lv3_bs) * lv3_bs
f.seek(lv3); h = struct.unpack("<10I", f.read(0x28))
dir_meta, file_meta, data_off = lv3 + h[3], lv3 + h[7], lv3 + h[9]
def rd(off, n): f.seek(off); return f.read(n)
out = []
def walk_dir(doff, path):
    d = rd(dir_meta + doff, 0x18)
    parent, sib, child, ffile, nh, nl = struct.unpack("<6I", d)
    name = rd(dir_meta + doff + 0x18, nl).decode("utf-16le")
    p = path + name + "/" if doff else "/"
    fo = ffile
    while fo != 0xFFFFFFFF:
        e = rd(file_meta + fo, 0x20)
        par, fsib, doff2, dsize, nh2, fnl = struct.unpack("<IIQQII", e)
        fname = rd(file_meta + fo + 0x20, fnl).decode("utf-16le")
        out.append((p + fname, data_off + doff2, dsize)); fo = fsib
    c = child
    while c != 0xFFFFFFFF:
        walk_dir(c, p)
        c = struct.unpack_from("<I", rd(dir_meta + c + 4, 4))[0]
walk_dir(0, "")
pat = re.compile(sys.argv[1]) if len(sys.argv) > 1 else None
for p, o, s in out:
    if pat is None: print(f"{s:10d} {p}")
    elif pat.search(p):
        dst = "work/romfs" + p; os.makedirs(os.path.dirname(dst), exist_ok=True)
        f.seek(o); open(dst, "wb").write(f.read(s)); print("extracted", p, s)
