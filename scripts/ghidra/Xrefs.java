// List references to each address arg, with containing function.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import ghidra.program.model.symbol.*;

public class Xrefs extends GhidraScript {
    public void run() throws Exception {
        for (String a : getScriptArgs()) {
            Address addr = toAddr(a);
            println("== refs to " + addr);
            for (Reference r : getReferencesTo(addr)) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  " + r.getFromAddress() + " " + r.getReferenceType() + " in " + (f == null ? "?" : f.getName() + "@" + f.getEntryPoint()));
            }
        }
    }
}
