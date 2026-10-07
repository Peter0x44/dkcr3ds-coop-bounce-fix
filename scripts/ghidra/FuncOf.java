// Print containing function for each address arg
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
public class FuncOf extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            Function f = getFunctionContaining(toAddr(a));
            Instruction i = getInstructionAt(toAddr(a));
            println(a + " -> " + (f == null ? "?" : f.getName() + "@" + f.getEntryPoint()) + "   " + (i == null ? "" : i.toString()));
        }
    }
}
