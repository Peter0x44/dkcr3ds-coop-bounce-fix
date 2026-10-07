// Disassembly listing: args addr count
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;

public class Disasm extends GhidraScript {
    public void run() throws Exception {
        String[] a = getScriptArgs();
        Address addr = toAddr(a[0]);
        int n = Integer.parseInt(a[1]);
        Instruction ins = getInstructionAt(addr);
        if (ins == null) { disassemble(addr); ins = getInstructionAt(addr); }
        for (int i = 0; i < n && ins != null; i++) {
            Function f = getFunctionAt(ins.getAddress());
            if (f != null) println("---- " + f.getName());
            StringBuilder hex = new StringBuilder();
            for (byte b : ins.getBytes()) hex.append(String.format("%02x", b));
            println(ins.getAddress() + "  " + hex + "  " + ins);
            ins = ins.getNext();
        }
    }
}
