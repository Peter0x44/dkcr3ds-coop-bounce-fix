"""Minimal GDB remote-protocol tracer for Azahar's gdb stub.

Azahar's stub can't resume from a breakpointed PC, so every breakpoint here is one-shot:
on a hit we log registers/memory, remove it, and continue. Breakpoints in RE-ARM are put
back the next time the target is stopped (we interrupt every ARM_PERIOD seconds to do that).

usage: python rsp_trace.py [--resume-only]
"""
import socket, struct, sys, time

HOST, PORT = "127.0.0.1", 24689
ARM_PERIOD = 0.25

class RSP:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT))
        self.s.settimeout(None)
        self.buf = b""

    def _raw_send(self, data):
        pkt = b"$" + data + b"#" + b"%02x" % (sum(data) & 0xFF)
        while True:
            self.s.sendall(pkt)
            c = self._getc()
            if c == b"+": return
            if c != b"-": self.buf = c + self.buf; return

    def _getc(self):
        if not self.buf:
            self.buf = self.s.recv(65536)
            if not self.buf: raise EOFError
        c, self.buf = self.buf[:1], self.buf[1:]
        return c

    def recv(self, timeout=None):
        self.s.settimeout(timeout)
        try:
            while True:
                c = self._getc()
                if c == b"$": break
            data = b""
            while True:
                c = self._getc()
                if c == b"#": break
                data += c
            self._getc(); self._getc()
            self.s.sendall(b"+")
            return data
        except socket.timeout:
            return None
        finally:
            self.s.settimeout(None)

    def cmd(self, data):
        self._raw_send(data.encode() if isinstance(data, str) else data)
        return self.recv()

    def regs(self):
        r = bytes.fromhex(self.cmd("g").decode())
        return list(struct.unpack_from("<16I", r, 0))

    def mem(self, addr, n):
        return bytes.fromhex(self.cmd(f"m{addr:x},{n:x}").decode())

    def u32(self, a): return struct.unpack("<I", self.mem(a, 4))[0]
    def u8(self, a): return self.mem(a, 1)[0]

def describe(t, pc, r):
    if pc == 0x250E60:
        return f"DEATHFN creature={r[0]:08x} type={r[1]} lr={r[14]:08x} alive={t.u8(r[0]+0x22d)}"
    if pc == 0x251014:
        return f"  deathfn branch type={r[1]} disableOnDeath={t.u8(r[7]+0x3d)}"
    if pc == 0x25103C:
        return "  deathfn -> timer path"
    if pc == 0x3C5064:
        return f"INLINE death creature={r[5]:08x} lr={r[14]:08x}"
    if pc == 0x3C5100:
        return f"  inline branch type={r[1]} disableOnDeath={t.u8(r[6]+0x3d)}"
    if pc == 0x3C5128:
        return "  inline -> timer path"
    if pc == 0x3C581C:
        return f"TIMER EXPIRED creature={r[0]:08x}"
    if pc == 0x254958:
        c = r[0]
        actor = t.u32(c + 4)
        return (f"CONTACT creature={c:08x} vt={t.u32(c):08x} alive={t.u8(c+0x22d)} other={r[1]:08x} "
                f"info0={t.u8(r[2])} lr={r[14]:08x} excl={t.u32(actor+0xf0):08x}:{t.u32(actor+0xf4):08x}")
    if pc == 0x3E889C:  # code cave exit: r0 = allow collision
        c = r[5]
        if t.u8(c + 0x22d): return None
        timer = struct.unpack("<f", t.mem(c + 0x30c, 4))[0]
        return f"VF9 dead creature={c:08x} other={r[4]:08x} corpseTimer={timer:.3f} allowed={r[0]}"
    if pc == 0x2EE638:
        c = r[0]
        if t.u8(c + 0x22d): return None
        return f"DISPATCH dead creature={c:08x} other={r[1]:08x} passAll={t.u8(c+0x3c)} activeBehavior={t.u32(c+0x280):08x}"
    if pc == 0x3E88C8:
        return f"CAVE2 corpse contact -> handler creature={r[4]:08x} other={r[1]:08x} type={r[8]}"
    if pc == 0x254AF0:
        sp = r[13]
        d = t.mem(sp + 0xE0, 0x14)
        res_c, res_p = t.u32(sp + 0xD8), t.u32(sp + 0xDC)
        if not d[0x12]: return None
        return f"RULES on dead: otherType={d[0]} zone={d[9]} -> creature={res_c:#x} player={res_p:#x}"
    if pc == 0x2326A0:  # CollidedWith (0x232468) dead-enemy exit: r7 = creature, r8 = other actor
        c, o = r[7], r[8]
        timer = struct.unpack("<f", t.mem(c + 0x30c, 4))[0]
        is_player = o != 0 and t.u32(o + 0x108) != 0
        return (f"DEAD CollidedWith creature={c:08x} other={o:08x} player={is_player} "
                f"corpseTimer={timer:.3f}  -> original game ignores this")
    return f"stop pc={pc:08x}"

BPS = [0x250E60, 0x2326A0, 0x3E88C8]

def main():
    t = RSP()
    stop = t.cmd("?")
    print("initial stop:", stop, flush=True)
    # clear anything gdb left behind
    for a in BPS: t.cmd(f"z0,{a:x},4")
    if "--resume-only" in sys.argv:
        # Azahar stays paused after a detach ("D"), so continue and drop the connection instead
        t._raw_send(b"c"); t.s.close(); print("resumed"); return
    armed = set()
    def arm():
        for a in BPS:
            if a not in armed and t.cmd(f"Z0,{a:x},4") == b"OK": armed.add(a)
    arm()
    log = open("trace.log", "a", buffering=1)
    t._raw_send(b"c")
    last = time.time()
    while True:
        pkt = t.recv(timeout=ARM_PERIOD)
        if pkt is None:
            # periodic interrupt to re-arm one-shot breakpoints
            if len(armed) < len(BPS):
                t.s.sendall(b"\x03"); pkt = t.recv()
            else:
                continue
        if pkt and pkt[:1] in (b"T", b"S"):
            r = t.regs(); pc = r[15]
            if pc in armed:
                line = describe(t, pc, r)
                if line:
                    print(line, flush=True); log.write(f"{time.strftime('%H:%M:%S')} {line}\n")
                t.cmd(f"z0,{pc:x},4"); armed.discard(pc)
            arm_now = time.time() - last > ARM_PERIOD
            if arm_now:
                # never re-arm the breakpoint at the current pc (stub can't step over it)
                for a in BPS:
                    if a not in armed and a != pc and t.cmd(f"Z0,{a:x},4") == b"OK": armed.add(a)
                last = time.time()
            t._raw_send(b"c")
        elif pkt and pkt[:1] in (b"W", b"X"):
            print("target exited", pkt); return

if __name__ == "__main__":
    main()
