// Decompile all functions whose name matches regex arg0; write to file arg1
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
import java.util.*;

public class DecompMatching extends GhidraScript {
    public void run() throws Exception {
        String re = getScriptArgs()[0];
        PrintWriter pw = new PrintWriter(new FileWriter(getScriptArgs()[1]));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Set<Long> done = new HashSet<>();
        int n = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (!f.getName().matches(re)) continue;
            if (!done.add(f.getEntryPoint().getOffset())) continue;
            DecompileResults r = di.decompileFunction(f, 60, monitor);
            pw.println("===== " + f.getName() + " @ " + f.getEntryPoint());
            pw.println(r.getDecompiledFunction() != null ? r.getDecompiledFunction().getC() : r.getErrorMessage());
            n++;
        }
        pw.close();
        println("decompiled " + n);
    }
}
