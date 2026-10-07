// Decompile functions containing the given addresses. Args: addr [addr...]; output to stdout.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;

public class Decomp extends GhidraScript {
    public void run() throws Exception {
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (String a : getScriptArgs()) {
            Address addr = toAddr(a);
            Function f = getFunctionContaining(addr);
            if (f == null) {
                disassemble(addr);
                f = createFunction(addr, null);
            }
            if (f == null) { println("NOFUNC " + a); continue; }
            DecompileResults r = di.decompileFunction(f, 120, monitor);
            println("===== " + f.getName() + " @ " + f.getEntryPoint());
            println(r.getDecompiledFunction() != null ? r.getDecompiledFunction().getC() : r.getErrorMessage());
        }
    }
}
