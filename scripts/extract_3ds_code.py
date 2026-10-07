"""usage: python scripts/extract_3ds_code.py <game.cci> [out_dir]
Writes code.bin (decompressed ExeFS .code) and exheader.bin. Needs a decrypted dump."""
import os, struct, sys
CCI = sys.argv[1]
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "work"
os.makedirs(OUT_DIR, exist_ok=True)

def blz_decompress(data):
    # 3DS "backwards LZ" used for ExeFS .code
    enc_len_and_hdr, inc_len = struct.unpack_from("<II", data, len(data) - 8)
    hdr_len = enc_len_and_hdr >> 24
    enc_len = enc_len_and_hdr & 0xFFFFFF
    out = bytearray(data) + bytearray(inc_len)
    src = len(data) - hdr_len
    dst = len(out)
    end = len(data) - enc_len
    while src > end:
        src -= 1; flags = out[src]
        for _ in range(8):
            if src <= end: break
            if flags & 0x80:
                src -= 2
                v = out[src] | (out[src + 1] << 8)
                ln = (v >> 12) + 3
                disp = (v & 0xFFF) + 3
                for _ in range(ln):
                    dst -= 1
                    out[dst] = out[dst + disp]
            else:
                src -= 1; dst -= 1
                out[dst] = out[src]
            flags = (flags << 1) & 0xFF
    return bytes(out)

f = open(CCI, "rb")
ncsd = f.read(0x200)
p0 = struct.unpack_from("<I", ncsd, 0x120)[0] * 0x200
f.seek(p0); ncch = f.read(0x200)
f.seek(p0 + 0x200); exh = f.read(0x400)
open(os.path.join(OUT_DIR, "exheader.bin"), "wb").write(exh)
text_addr, text_pages, text_size = struct.unpack_from("<III", exh, 0x10)
ro_addr, ro_pages, ro_size = struct.unpack_from("<III", exh, 0x20)
data_addr, data_pages, data_size = struct.unpack_from("<III", exh, 0x30)
bss = struct.unpack_from("<I", exh, 0x3C)[0]
compressed = exh[0xD] & 1
print(f"text {text_addr:#x} size {text_size:#x} | ro {ro_addr:#x} size {ro_size:#x} | data {data_addr:#x} size {data_size:#x} bss {bss:#x} | compressed={compressed}")
exefs_off = p0 + struct.unpack_from("<I", ncch, 0x1A0)[0] * 0x200
f.seek(exefs_off); eh = f.read(0x200)
for i in range(10):
    name, off, size = struct.unpack_from("<8sII", eh, i * 16)
    name = name.rstrip(b"\0").decode()
    if not name: continue
    print(name, hex(off), hex(size))
    if name == ".code":
        f.seek(exefs_off + 0x200 + off); code = f.read(size)
        if compressed: code = blz_decompress(code)
        open(os.path.join(OUT_DIR, "code.bin"), "wb").write(code)
        print("code.bin", hex(len(code)))
