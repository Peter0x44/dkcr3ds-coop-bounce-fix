"""One-shot breakpoint tracer for the Wii version in Dolphin (GDB stub, [General] GDBPort).

Same approach as rsp_trace.py: each breakpoint logs, removes itself and resumes; fired
breakpoints are re-armed every ARM_PERIOD seconds. Times are wall-clock seconds since start.
usage: python rsp_trace_wii.py [--resume-only]
"""
import socket, struct, sys, time

HOST, PORT = "127.0.0.1", 2345
ARM_PERIOD = 0.25

class RSP:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT))
        self.buf = b""

    def _getc(self):
        if not self.buf:
            self.buf = self.s.recv(65536)
            if not self.buf: raise EOFError
        c, self.buf = self.buf[:1], self.buf[1:]
        return c

    def send(self, data):
        if isinstance(data, str): data = data.encode()
        self.s.sendall(b"$" + data + b"#" + b"%02x" % (sum(data) & 0xFF))
        while True:  # wait for ack
            c = self._getc()
            if c == b"+": return
            if c == b"$": self.buf = c + self.buf; return

    def recv(self, timeout=None):
        self.s.settimeout(timeout)
        try:
            while self._getc() != b"$": pass
            data = b""
            while (c := self._getc()) != b"#": data += c
            self._getc(); self._getc(); self.s.sendall(b"+")
            return data
        except socket.timeout:
            return None
        finally:
            self.s.settimeout(None)

    def cmd(self, data):
        self.send(data); return self.recv()

    def reg(self, n):
        return int(self.cmd(f"p{n:x}").decode()[:8], 16)

    def u32(self, a): return int(self.cmd(f"m{a:x},4").decode(), 16)
    def u8(self, a): return int(self.cmd(f"m{a:x},1").decode(), 16)

def creature_state(t, c):
    active = (t.u8(c + 0x55C) >> 6) & 1
    dtype = t.u32(c + 0xDFC)
    return f"active={active} deathType={dtype if dtype != 0xFFFFFFFF else -1}"

def describe(t, pc):
    r3, r4, r5 = t.reg(3), t.reg(4), t.reg(5)
    if pc == 0x80035D20:
        return f"IssueDeath creature={r3:08x} type={r5} lr={t.reg(0x43):08x} [{creature_state(t, r3)}]"
    if pc == 0x8001CDA0:
        return f"CPatterned::Death creature={r3:08x} lr={t.reg(0x43):08x} [{creature_state(t, r3)}]"
    if pc == 0x80054D20:
        c = t.u32(r3 + 4)
        return f"bop KILL fn module={r3:08x} creature={c:08x} [{creature_state(t, c)}]"
    if pc == 0x80054DC0:
        c = t.u32(r3 + 4)
        return f"bop STUN fn module={r3:08x} creature={c:08x} [{creature_state(t, c)}]"
    if pc == 0x80052660:
        c = t.u32(r3 + 4)
        return f"bop module collision creature={c:08x} other={t.u32(r5):08x} moduleState={t.u32(r3 + 0x140)} [{creature_state(t, c)}]"
    if pc == 0x8003C830:
        return f"CONTACT handler creature={r3:08x} lr={t.reg(0x43):08x} [{creature_state(t, r3)}]"
    if pc == 0x80034A98:  # CollidedWith dead branch: r3 = the other object (after GetObjectById)
        kind = (t.u32(r3 + 0x38) >> 6) & 0x3FFFFF
        return (f"DEAD CollidedWith: other={r3:08x} vtable={t.u32(r3):08x} kind={kind:#x} "
                f"(bit8 {'SET -> contact handler' if kind & 8 else 'clear -> ignored'})")
    if pc == 0x80034A10:
        return f"CollidedWith creature={r3:08x} [{creature_state(t, r3)}]"
    return f"stop pc={pc:08x}"

BPS = [0x80035D20, 0x8001CDA0, 0x80054D20, 0x80054DC0, 0x80052660, 0x8003C830, 0x80033AD0, 0x80034A98]
FRAME_TICK = 0x80033AD0   # per-creature corpse-timer tick: runs once per frame per creature (r3 = creature, f1 = dt)

def main_persistent():
    """Breakpoints stay armed: on a hit, log, remove, single-step, re-arm, continue."""
    t = RSP()
    print("initial stop:", t.cmd("?"), flush=True)
    for a in BPS: t.cmd(f"Z0,{a:x},4")
    log = open("trace_wii.log", "a", buffering=1)
    frames = {}          # creature -> frame ticks seen
    watched = set()      # creatures that went through the bop module
    t.send("c")
    while True:
        pkt = t.recv()
        if pkt[:1] not in (b"T", b"S"):
            continue
        pc = t.reg(0x40)
        if pc == FRAME_TICK:
            c = t.reg(3)
            if c in watched:
                frames[c] = frames.get(c, 0) + 1
                line = f"  frame {frames[c]:3d} creature={c:08x} [{creature_state(t, c)}]"
                print(line, flush=True); log.write(line + "\n")
        elif pc in BPS:
            line = describe(t, pc)
            if pc == 0x80052660:
                watched.add(t.u32(t.reg(3) + 4))
            elif pc in (0x8003C830, 0x80035D20, 0x8001CDA0):
                watched.add(t.reg(3))
            print(line, flush=True); log.write(line + "\n")
        if pc in BPS:
            t.cmd(f"z0,{pc:x},4"); t.send("s"); t.recv(); t.cmd(f"Z0,{pc:x},4")
        t.send("c")

def main():
    t = RSP()
    print("initial stop:", t.cmd("?"), flush=True)
    for a in BPS: t.cmd(f"z0,{a:x},4")
    if "--resume-only" in sys.argv:
        t.send("c"); t.s.close(); print("resumed"); return
    armed = set()
    for a in BPS:
        if t.cmd(f"Z0,{a:x},4") == b"OK": armed.add(a)
    print("armed", [hex(a) for a in armed], flush=True)
    log = open("trace_wii.log", "a", buffering=1)
    t0 = time.time(); last = t0
    t.send("c")
    while True:
        pkt = t.recv(timeout=ARM_PERIOD)
        if pkt is None:
            if len(armed) < len(BPS):
                t.s.sendall(b"\x03"); pkt = t.recv()
            else:
                continue
        if pkt[:1] not in (b"T", b"S"):
            continue
        pc = t.reg(0x40)
        if pc in armed:
            line = f"{time.time() - t0:8.3f}  " + describe(t, pc)
            print(line, flush=True); log.write(line + "\n")
            t.cmd(f"z0,{pc:x},4"); armed.discard(pc)
        if time.time() - last > ARM_PERIOD:
            for a in BPS:
                if a not in armed and a != pc and t.cmd(f"Z0,{a:x},4") == b"OK": armed.add(a)
            last = time.time()
        t.send("c")

if __name__ == "__main__":
    main_persistent() if "--persistent" in sys.argv else main()
