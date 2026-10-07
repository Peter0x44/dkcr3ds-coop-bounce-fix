# Recover class names -> typeinfo -> vtables from the 3DS code via Itanium/ARM RTTI.
import struct, re, collections
code = open("work/code.bin", "rb").read()
BASE = 0x100000
TEXT_END = 0x3e9000
words = collections.defaultdict(list)
for off in range(0, len(code) - 3, 4):
    words[struct.unpack_from("<I", code, off)[0]].append(BASE + off)
def u32(a): return struct.unpack_from("<I", code, a - BASE)[0]

classes = {}
for m in re.finditer(rb"(?<=\0)(N?[0-9]+[A-Za-z_][\x21-\x7e]*?E?)\0", code):
    name_addr = BASE + m.start(1)
    name = m.group(1).decode()
    for ref in words.get(name_addr, []):
        ti = ref - 4
        # typeinfo: [vptr of type_info class][name ptr]...
        if not (0x3e9000 <= ti < 0x460000): continue
        for vref in words.get(ti, []):
            if u32(vref - 4) != 0 and u32(vref - 4) < 0xffff0000: continue  # offset-to-top must be 0 or negative
            vt = vref + 4
            funcs = []
            a = vt
            while a - BASE < len(code) - 4:
                f = u32(a)
                if not (BASE <= (f & ~1) < TEXT_END): break
                funcs.append(f); a += 4
            if funcs:
                classes.setdefault(name, []).append((ti, vt, funcs))

def pretty(n):
    # demangle the anonymous-namespace nesting enough to be readable
    m = re.match(r"N\d+_GLOBAL__N__\d+_(\w+?)_cpp_[0-9a-f]+\d+(\w+)E$", n)
    if m:
        s = n[n.index("_cpp_") + 5 + 8:]
        s = re.sub(r"^\d+", "", s)[:-1]
        return f"{m.group(1)}::{s}"
    return re.sub(r"^\d+", "", n)

with open("work/rtti3ds.txt", "w") as f, open("work/syms3ds_vt.txt", "w") as g:
    for n, lst in sorted(classes.items()):
        for ti, vt, funcs in lst:
            f.write(f"{pretty(n)}  typeinfo={ti:#x} vtable={vt:#x} nfuncs={len(funcs)}\n")
            g.write(f"{vt:08x} vt_{pretty(n).replace('::','__')}_{vt:x}\n")
print(len(classes))
